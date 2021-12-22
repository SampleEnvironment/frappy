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
from math import log10

from secop.core import BoolType, Command, EnumType, FloatRange, IntRange, \
    HasIodev, Parameter, Property, Drivable, PersistentMixin, PersistentParam
from secop.io import BytesIO
from secop.errors import CommunicationFailedError, HardwareError, BadValueError, IsBusyError


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


class HwParam(PersistentParam):
    adr = Property('parameter address', IntRange(0, 255), export=False)
    scale = Property('scale factor (physical value / unit)', FloatRange(), export=False)

    def __init__(self, description, datatype, adr, scale=1, poll=True,
                 readonly=True, persistent=None, **kwds):
        """hardware parameter"""
        if persistent is None:
            persistent = not readonly
        if isinstance(datatype, FloatRange) and datatype.fmtstr == '%g':
            datatype.fmtstr = '%%.%df' % max(0, 1 - int(log10(scale) + 0.01))
        super().__init__(description, datatype, poll=poll, adr=adr, scale=scale,
                         persistent=persistent, readonly=readonly, **kwds)

    def copy(self):
        res = HwParam(self.description, self.datatype.copy(), self.adr)
        res.name = self.name
        res.init(self.propertyValues)
        return res


class Motor(PersistentMixin, HasIodev, Drivable):
    address = Property('module address', IntRange(0, 255), default=1)

    value = Parameter('motor position', FloatRange(unit='deg', fmtstr='%.3f'))
    zero = PersistentParam('zero point', FloatRange(unit='$'), readonly=False, default=0)
    encoder = HwParam('encoder reading', FloatRange(unit='$', fmtstr='%.1f'),
                      209, ANGLE_SCALE, readonly=True, initwrite=False, persistent=True)
    steppos = HwParam('position from motor steps', FloatRange(unit='$'),
                      1, ANGLE_SCALE, readonly=True, initwrite=False)
    target = Parameter('', FloatRange(unit='$'), default=0)

    movelimit = Parameter('max. angle to drive in one go', FloatRange(unit='$'),
                          readonly=False, default=360, group='more')
    tolerance = Parameter('positioning tolerance', FloatRange(unit='$'),
                          readonly=False, default=0.9)
    encoder_tolerance = HwParam('the allowed deviation between steppos and encoder\n\nmust be > tolerance',
                                FloatRange(0, 360., unit='$'),
                                212, ANGLE_SCALE, readonly=False, group='more')
    speed = HwParam('max. speed', FloatRange(0, MAX_SPEED, unit='$/sec'),
                    4, SPEED_SCALE, readonly=False)
    minspeed = HwParam('min. speed', FloatRange(0, MAX_SPEED, unit='$/sec'),
                       130, SPEED_SCALE, readonly=False, default=SPEED_SCALE, group='motorparam')
    currentspeed = HwParam('current speed', FloatRange(-MAX_SPEED, MAX_SPEED, unit='$/sec'),
                           3, SPEED_SCALE, readonly=True, group='motorparam')
    maxcurrent = HwParam('', FloatRange(0, 2.8, unit='A'),
                         6, CURRENT_SCALE, readonly=False, group='motorparam')
    standby_current = HwParam('', FloatRange(0, 2.8, unit='A'),
                              7, CURRENT_SCALE, readonly=False, group='motorparam')
    acceleration = HwParam('', FloatRange(4.6 * ACCEL_SCALE, MAX_ACCEL, unit='deg/s^2'),
                           5, ACCEL_SCALE, readonly=False, group='motorparam')
    target_reached = HwParam('', BoolType(), 8, group='hwstatus')
    move_status = HwParam('', IntRange(0, 3),
                          207, readonly=True, group='hwstatus')
    error_bits = HwParam('', IntRange(0, 255),
                         208, readonly=True, group='hwstatus')
    # the doc says msec, but I believe the scale is 10 msec
    free_wheeling = HwParam('', FloatRange(0, 60., unit='sec'),
                            204, 0.01, default=0.1, readonly=False, group='motorparam')
    power_down_delay = HwParam('', FloatRange(0, 60., unit='sec'),
                               214, 0.01, default=0.1, readonly=False, group='motorparam')
    baudrate = Parameter('', EnumType({'%d' % v: i for i, v in enumerate(BAUDRATES)}),
                         readonly=False, default=0, poll=True, visibility=3, group='more')
    pollinterval = Parameter(group='more')

    iodevClass = BytesIO
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
        if self._calcTimeout:
            self._calcTimeout = False
            baudrate = getattr(self._iodev._conn.connection, 'baudrate', None)
            if baudrate:
                if baudrate not in BAUDRATES:
                    raise CommunicationFailedError('unsupported baud rate: %d' % baudrate)
                self._iodev.timeout = 0.03 + 200 / baudrate

        exc = None
        byt = struct.pack('>BBBBi', self.address, cmd, adr, bank, round(value))
        byt += bytes([sum(byt) & 0xff])
        for itry in range(3,0,-1):
            try:
                reply = self._iodev.communicate(byt, 9)
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

    def get(self, pname):
        """get parameter"""
        pobj = self.parameters[pname]
        value = self.comm(GET_AXIS_PAR, pobj.adr)
        # do not apply scale when 1 (datatype might not be float)
        return value if pobj.scale == 1 else value * pobj.scale

    def set(self, pname, value, check=True):
        """set parameter and check result"""
        pobj = self.parameters[pname]
        scale = pobj.scale
        rawvalue = round(value / scale)
        self.comm(SET_AXIS_PAR, pobj.adr, rawvalue)
        if check:
            result = self.comm(GET_AXIS_PAR, pobj.adr)
            if result != rawvalue:
                raise HardwareError('result does not match %d != %d' % (result, rawvalue))
            value = result * scale
        return value

    def startModule(self, start_events):
        # get encoder value from motor. at this stage self.encoder contains the persistent value
        encoder = self.get('encoder')
        encoder += self.zero
        self.fix_encoder(encoder)
        super().startModule(start_events)

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
            # encoder module0 360 has changed
            self.log.error('saved encoder value (%.2f) does not match reading (%.2f %.2f)',
                           self.encoder, encoder_from_hw, adjusted_encoder)
            if adjusted_encoder != encoder_from_hw:
                self.log.info('take next closest encoder value (%.2f)' % adjusted_encoder)
            self._need_reset = True
            self.status = self.Status.ERROR, 'saved encoder value does not match reading'
        self.set('encoder', adjusted_encoder - self.zero, check=False)

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
                # self.set('steppos', self.steppos - self.zero, check=False)
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
        diff = self.target - self.encoder
        if abs(diff) <= self.tolerance:
            self._started = 0
            return self.Status.IDLE, ''
        self.log.error('out of tolerance by %.3g', diff)
        self._started = 0
        return self.Status.ERROR, 'out of tolerance'

    def write_target(self, target):
        self.read_value()  # make sure encoder and steppos are fresh
        if abs(target - self.encoder) > self.movelimit:
            raise BadValueError('can not move more than %s deg' % self.movelimit)
        diff = self.encoder - self.steppos
        if self._need_reset:
            raise HardwareError('need reset (%s)' % self.status[1])
        if abs(diff) > self.tolerance:
            if abs(diff) > self.encoder_tolerance:
                self._need_reset = True
                self.status = self.Status.ERROR, 'encoder does not match internal pos'
                raise HardwareError('need reset (encoder does not match internal pos)')
            self.set('steppos', self.encoder - self.zero)
        self._started = time.time()
        self.log.info('move to %.1f', target)
        self.comm(MOVE, 0, (target - self.zero) / ANGLE_SCALE)
        self.status = self.Status.BUSY, 'changed target'
        return target

    def write_zero(self, value):
        diff = value - self.zero
        self.encoder += diff
        self.steppos += diff
        self.value += diff
        return value

    def read_encoder(self):
        return self.get('encoder') + self.zero

    def read_steppos(self):
        return self.get('steppos') + self.zero

    def read_encoder_tolerance(self):
        return self.get('encoder_tolerance')

    def write_encoder_tolerance(self, value):
        return self.set('encoder_tolerance', value)

    def read_target_reached(self):
        return self.get('target_reached')

    def read_speed(self):
        return self.get('speed')

    def write_speed(self, value):
        return self.set('speed', value)

    def read_minspeed(self):
        return self.get('minspeed')

    def write_minspeed(self, value):
        return self.set('minspeed', value)

    def read_currentspeed(self):
        return self.get('currentspeed')

    def read_acceleration(self):
        return self.get('acceleration')

    def write_acceleration(self, value):
        return self.set('acceleration', value)

    def read_maxcurrent(self):
        return self.get('maxcurrent')

    def write_maxcurrent(self, value):
        return self.set('maxcurrent', value)

    def read_standby_current(self):
        return self.get('standby_current')

    def write_standby_current(self, value):
        return self.set('standby_current', value)

    def read_free_wheeling(self):
        return self.get('free_wheeling')

    def write_free_wheeling(self, value):
        return self.set('free_wheeling', value)

    def read_power_down_delay(self):
        return self.get('power_down_delay')

    def write_power_down_delay(self, value):
        return self.set('power_down_delay', value)

    def read_move_status(self):
        return self.get('move_status')

    def read_error_bits(self):
        return self.get('error_bits')

    @Command(FloatRange())
    def set_zero(self, value):
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
            self.set('steppos', self.encoder - self.zero, check=False)
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

    @Command((IntRange(), FloatRange()), result=IntRange())
    def set_axis_par(self, adr, value):
        """set arbitrary motor parameter"""
        return self.comm(SET_AXIS_PAR, adr, value)
