#  -*- coding: utf-8 -*-
# *****************************************************************************
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

"""drivers for trinamic PD-1161 motors"""

import time
import struct

from secop.core import BoolType, Command, EnumType, FloatRange, IntRange, \
    HasIO, Parameter, Property, Drivable, PersistentMixin, PersistentParam, Done
from secop.io import BytesIO
from secop.errors import CommunicationFailedError, HardwareError, BadValueError, IsBusyError
from secop.rwhandler import ReadHandler, WriteHandler

MOTOR_STOP = 3
MOVE = 4
SET_AXIS_PAR = 5
GET_AXIS_PAR = 6
SET_GLOB_PAR = 9
GET_GLOB_PAR = 10
# STORE_GLOB_PAR = 11

BAUDRATES = [9600, 0, 19200, 0, 38400, 57600, 0, 115200]

FULL_STEP = 1.8
ANGLE_SCALE = FULL_STEP/256
# assume factory settings for pulse and ramp divisors:
SPEED_SCALE = 1E6 / 2 ** 15 * ANGLE_SCALE
MAX_SPEED = 2047 * SPEED_SCALE
ACCEL_SCALE = 1E12 / 2 ** 31 * ANGLE_SCALE
MAX_ACCEL = 2047 * ACCEL_SCALE
CURRENT_SCALE = 2.8/250
ENCODER_RESOLUTION = 360 / 1024

HW_ARGS = {
    # <parameter name>: (address, scale factor)
    'encoder_tolerance': (212, ANGLE_SCALE),
    'speed': (4, SPEED_SCALE),
    'minspeed': (130, SPEED_SCALE),
    'currentspeed': (3, SPEED_SCALE),
    'maxcurrent': (6, CURRENT_SCALE),
    'standby_current': (7, CURRENT_SCALE,),
    'acceleration': (5, ACCEL_SCALE),
    'target_reached': (8, 1),
    'move_status': (207, 1),
    'error_bits': (208, 1),
    'free_wheeling': (204, 0.01),
    'power_down_delay': (214, 0.01),
}

# special handling (adjust zero):
ENCODER_ADR = 209
STEPPOS_ADR = 1


def writable(*args, **kwds):
    """convenience function to create writable hardware parameters"""
    return PersistentParam(*args, readonly=False, poll=True, initwrite=True, **kwds)


class Motor(PersistentMixin, HasIO, Drivable):
    address = Property('module address', IntRange(0, 255), default=1)

    value = Parameter('motor position', FloatRange(unit='deg', fmtstr='%.3f'))
    zero = PersistentParam('zero point', FloatRange(unit='$'), readonly=False, default=0)
    encoder = PersistentParam('encoder reading', FloatRange(unit='$', fmtstr='%.1f'),
                              readonly=True, initwrite=False, poll=True)
    steppos = PersistentParam('position from motor steps', FloatRange(unit='$', fmtstr='%.3f'),
                              readonly=True, initwrite=False, poll=True)
    target = Parameter('', FloatRange(unit='$'), default=0)

    move_limit = Parameter('max. angle to drive in one go', FloatRange(unit='$'),
                           readonly=False, default=360, group='more')
    tolerance = Parameter('positioning tolerance', FloatRange(unit='$'),
                          readonly=False, default=0.9)
    encoder_tolerance = writable('the allowed deviation between steppos and encoder\n\nmust be > tolerance',
                                 FloatRange(0, 360., unit='$', fmtstr='%.3f'), group='more')
    speed = writable('max. speed', FloatRange(0, MAX_SPEED, unit='$/sec', fmtstr='%.1f'), default=40)
    minspeed = writable('min. speed', FloatRange(0, MAX_SPEED, unit='$/sec', fmtstr='%.1f'),
                        default=SPEED_SCALE, group='motorparam')
    currentspeed = Parameter('current speed', FloatRange(-MAX_SPEED, MAX_SPEED, unit='$/sec', fmtstr='%.1f'),
                             poll=True, group='motorparam')
    maxcurrent = writable('', FloatRange(0, 2.8, unit='A', fmtstr='%.2f'),
                          default=1.4, group='motorparam')
    standby_current = writable('', FloatRange(0, 2.8, unit='A', fmtstr='%.2f'),
                               default=0.1, group='motorparam')
    acceleration = writable('', FloatRange(4.6 * ACCEL_SCALE, MAX_ACCEL, unit='deg/s^2', fmtstr='%.1f'),
                            default=150., group='motorparam')
    target_reached = Parameter('', BoolType(), poll=True, group='hwstatus')
    move_status = Parameter('', IntRange(0, 3), poll=True, group='hwstatus')
    error_bits = Parameter('', IntRange(0, 255), poll=True, group='hwstatus')
    free_wheeling = writable('', FloatRange(0, 60., unit='sec', fmtstr='%.2f'),
                             default=0.1, group='motorparam')
    power_down_delay = writable('', FloatRange(0, 60., unit='sec', fmtstr='%.2f'),
                                default=0.1, group='motorparam')
    baudrate = Parameter('', EnumType({'%d' % v: i for i, v in enumerate(BAUDRATES)}),
                         readonly=False, default=0, poll=True, visibility=3, group='more')
    pollinterval = Parameter(group='more')

    ioClass = BytesIO
    fast_pollfactor = 0.001  # poll as fast as possible when busy
    _started = 0
    _calcTimeout = True
    _need_reset = None

    def comm(self, cmd, adr, value=0, bank=0):
        """set or get a parameter

        :param adr: parameter number
        :param cmd: SET command (in the GET case, 1 is added to this)
        :param bank: the bank
        :param value: if given, the parameter is written, else it is returned
        :return: the returned value
        """
        if self._calcTimeout and self.io._conn:
            self._calcTimeout = False
            baudrate = getattr(self.io._conn.connection, 'baudrate', None)
            if baudrate:
                if baudrate not in BAUDRATES:
                    raise CommunicationFailedError('unsupported baud rate: %d' % baudrate)
                self.io.timeout = 0.03 + 200 / baudrate

        exc = None
        byt = struct.pack('>BBBBi', self.address, cmd, adr, bank, round(value))
        byt += bytes([sum(byt) & 0xff])
        for itry in range(3,0,-1):
            try:
                reply = self.communicate(byt, 9)
                if sum(reply[:-1]) & 0xff != reply[-1]:
                    raise CommunicationFailedError('checksum error')
                    # will try again
            except Exception as e:
                if itry == 1:
                    raise
                exc = e
                continue
            break
        if exc:
            self.log.warning('tried %d times after %s', itry, exc)
        radr, modadr, status, rcmd, result = struct.unpack('>BBBBix', reply)
        if status != 100:
            self.log.warning('bad status from cmd %r %s: %d', cmd, adr, status)
        if radr != 2 or modadr != self.address or cmd != rcmd:
            raise CommunicationFailedError('bad reply %r to command %s %d' % (reply, cmd, adr))
        return result

    def startModule(self, start_events):
        super().startModule(start_events)

        def fix_encoder(self=self):
            try:
                # get encoder value from motor. at this stage self.encoder contains the persistent value
                encoder = self._read_axispar(ENCODER_ADR, ANGLE_SCALE) + self.zero
                self.fix_encoder(encoder)
            except Exception as e:
                self.log.error('fix_encoder failed with %r', e)

        start_events.queue(fix_encoder)

    def fix_encoder(self, encoder_from_hw):
        """fix encoder value

        :param encoder_from_hw: the encoder value read from the HW

        self.encoder is assumed to contain the last known (persistent) value
        if encoder has not changed modulo 360, adjust by an integer multiple of 360
        set status to error when encoder has changed be more than encoder_tolerance
        """
        # calculate nearest, most probable value
        adjusted_encoder = encoder_from_hw + round((self.encoder - encoder_from_hw) / 360.) * 360
        if abs(self.encoder - adjusted_encoder) >= self.encoder_tolerance:
            # encoder modulo 360 has changed
            self.log.error('saved encoder value (%.2f) does not match reading (%.2f %.2f)',
                           self.encoder, encoder_from_hw, adjusted_encoder)
            if adjusted_encoder != encoder_from_hw:
                self.log.info('take next closest encoder value (%.2f)' % adjusted_encoder)
            self._need_reset = True
            self.status = self.Status.ERROR, 'saved encoder value does not match reading'
        self._write_axispar(adjusted_encoder - self.zero, ENCODER_ADR, ANGLE_SCALE, readback=False)

    def _read_axispar(self, adr, scale=1):
        value = self.comm(GET_AXIS_PAR, adr)
        # do not apply scale when 1 (datatype might not be float)
        return value if scale == 1 else value * scale

    def _write_axispar(self, value, adr, scale=1, readback=True):
        rawvalue = round(value / scale)
        self.comm(SET_AXIS_PAR, adr, rawvalue)
        if readback:
            result = self.comm(GET_AXIS_PAR, adr)
            if result != rawvalue:
                raise HardwareError('result for adr=%d scale=%g does not match %g != %g'
                                    % (adr, scale, result * scale, value))
            return result * scale
        return rawvalue * scale

    @ReadHandler(HW_ARGS)
    def read_hwparam(self, pname):
        """handle read for HwParam"""
        args = HW_ARGS[pname]
        reply = self._read_axispar(*args)
        try:
            value = getattr(self, pname)
        except Exception:
            return reply
        if reply != value:
            if not self.parameters[pname].readonly:
                # this should not happen
                self.log.warning('hw parameter %s has changed from %r to %r, write again', pname, value, reply)
                self._write_axispar(value, *args, readback=False)
                reply = self._read_axispar(*args)
        return reply

    @WriteHandler(HW_ARGS)
    def write_hwparam(self, pname, value):
        """handler write for HwParam"""
        return self._write_axispar(value, *HW_ARGS[pname])

    def read_value(self):
        encoder = self.read_encoder()
        steppos = self.read_steppos()
        initialized = self.comm(GET_GLOB_PAR, 255, bank=2)
        if initialized:  # no power loss
            self.saveParameters()
        else:  # just powered up
            # get persistent values
            writeDict = self.loadParameters()
            self.log.info('set to previous saved values %r', writeDict)
            # self.encoder now contains the last known (persistent) value
            if self._need_reset is None:
                if self.status[0] == self.Status.IDLE:
                    # server started, power cycled and encoder value matches last one
                    self.reset()
            else:
                self.fix_encoder(encoder)
                self._need_reset = True
                self.status = self.Status.ERROR, 'power loss'
                # or should we just fix instead of error status?
                # self._write_axispar(self.steppos - self.zero, readback=False)
            self.comm(SET_GLOB_PAR, 255, 1, bank=2)  # set initialized flag
            self._started = 0

        return encoder if abs(encoder - steppos) > self.tolerance else steppos

    def read_status(self):
        oldpos = self.steppos
        self.read_value()  # make sure encoder and steppos are fresh
        if not self._started:
            if abs(self.encoder - self.steppos) > self.encoder_tolerance:
                self._need_reset = True
                if self.status[0] != self.Status.ERROR:
                    self.log.error('encoder (%.2f) does not match internal pos (%.2f)', self.encoder, self.steppos)
                    return self.Status.ERROR, 'encoder does not match internal pos'
            return self.status
        if oldpos != self.steppos or not (self.read_target_reached() or self.read_move_status()
                                          or self.read_error_bits()):
            return self.Status.BUSY, 'moving'
        # TODO: handle the different errors from move_status and error_bits
        diff = self.target - self.encoder
        if abs(diff) <= self.tolerance:
            self._started = 0
            return self.Status.IDLE, ''
        self.log.error('out of tolerance by %.3g', diff)
        self._started = 0
        return self.Status.ERROR, 'out of tolerance'

    def write_target(self, target):
        self.read_value()  # make sure encoder and steppos are fresh
        if abs(target - self.encoder) > self.move_limit:
            raise BadValueError('can not move more than %s deg' % self.move_limit)
        diff = self.encoder - self.steppos
        if self._need_reset:
            raise HardwareError('need reset (%s)' % self.status[1])
        if abs(diff) > self.tolerance:
            if abs(diff) > self.encoder_tolerance:
                self._need_reset = True
                self.status = self.Status.ERROR, 'encoder does not match internal pos'
                raise HardwareError('need reset (encoder does not match internal pos)')
            self._write_axispar(self.encoder - self.zero, STEPPOS_ADR, ANGLE_SCALE)
        self._started = time.time()
        self.log.info('move to %.1f', target)
        self.comm(MOVE, 0, (target - self.zero) / ANGLE_SCALE)
        self.status = self.Status.BUSY, 'changed target'
        return target

    def write_zero(self, value):
        self.zero = value
        self.read_value()  # apply zero to encoder, steppos and value
        return Done

    def read_encoder(self):
        return self._read_axispar(ENCODER_ADR, ANGLE_SCALE) + self.zero

    def read_steppos(self):
        return self._read_axispar(STEPPOS_ADR, ANGLE_SCALE) + self.zero

    @Command(FloatRange())
    def set_zero(self, value):
        """adjust zero"""
        self.write_zero(value - self.read_value())

    def read_baudrate(self):
        return self.comm(GET_GLOB_PAR, 65)

    def write_baudrate(self, value):
        self.comm(SET_GLOB_PAR, 65, int(value))

    @Command()
    def reset(self):
        """set steppos to encoder value, if not within tolerance"""
        if self._started:
            raise IsBusyError('can not reset while moving')
        tol = ENCODER_RESOLUTION * 1.1
        for itry in range(10):
            diff = self.read_encoder() - self.read_steppos()
            if abs(diff) <= tol:
                self._need_reset = False
                self.status = self.Status.IDLE, 'ok'
                return
            self._write_axispar(self.encoder - self.zero, STEPPOS_ADR, ANGLE_SCALE, readback=False)
            self.comm(MOVE, 0, (self.encoder - self.zero) / ANGLE_SCALE)
            time.sleep(0.1)
            if itry > 5:
                tol = self.tolerance
        self.status = self.Status.ERROR, 'reset failed'
        return

    @Command()
    def stop(self):
        """stop motor immediately"""
        self.comm(MOTOR_STOP, 0)
        self.status = self.Status.IDLE, 'stopped'
        self._started = 0

    @Command()
    def step_forward(self):
        """move one full step forwards

        for quick tests
        """
        self.comm(MOVE, 1, FULL_STEP / ANGLE_SCALE)

    @Command()
    def step_back(self):
        """move one full step backwards

        for quick tests
        """
        self.comm(MOVE, 1, - FULL_STEP / ANGLE_SCALE)

    @Command(IntRange(), result=IntRange())
    def get_axis_par(self, adr):
        """get arbitrary motor parameter"""
        return self.comm(GET_AXIS_PAR, adr)

    @Command((IntRange(), IntRange()), result=IntRange())
    def set_axis_par(self, adr, value):
        """set arbitrary motor parameter"""
        return self.comm(SET_AXIS_PAR, adr, value)
