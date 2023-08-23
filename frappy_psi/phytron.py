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

"""driver for phytron motors

limits switches are not yet implemented
"""

import time
from frappy.core import Done, Command, EnumType, FloatRange, IntRange, \
    HasIO, Parameter, Property, Drivable, PersistentMixin, PersistentParam, \
    StringIO, StringType, IDLE, BUSY, ERROR, Limit
from frappy.errors import CommunicationFailedError, HardwareError
from frappy.features import HasOffset
from frappy.states import HasStates, status_code, Retry


class PhytronIO(StringIO):
    end_of_line = '\x03'  # ETX
    timeout = 0.5
    identification = [('0IVR', 'MCC Minilog .*')]

    def communicate(self, command):
        ntry = 5
        warn = None
        for itry in range(ntry):
            try:
                _, _, reply = super().communicate('\x02' + command).partition('\x02')
                if reply[0] == '\x06':  # ACK
                    break
                raise CommunicationFailedError(f'missing ACK {reply!r} (cmd: {command!r})')
            except Exception as e:
                if itry < ntry - 1:
                    warn = e
                else:
                    raise
        if warn:
            self.log.warning('needed %d retries after %r', itry, warn)
        return reply[1:]


class Motor(HasOffset, HasStates, PersistentMixin, HasIO, Drivable):
    axis = Property('motor axis X or Y', StringType(), default='X')
    address = Property('address', IntRange(0, 15), default=0)
    circumference = Property('cirumference for rotations or zero for linear', FloatRange(0), default=360)

    encoder_mode = Parameter('how to treat the encoder', EnumType('encoder', NO=0, READ=1, CHECK=2),
                             default=1, readonly=False)
    value = PersistentParam('angle', FloatRange(unit='deg'))
    status = PersistentParam()
    target = Parameter('target angle', FloatRange(unit='deg'), readonly=False)
    speed = Parameter('', FloatRange(0, 20, unit='deg/s'), readonly=False)
    accel = Parameter('', FloatRange(2, 250, unit='deg/s/s'), readonly=False)
    encoder_tolerance = Parameter('', FloatRange(unit='deg'), readonly=False, default=0.01)
    sign = PersistentParam('', IntRange(-1,1), readonly=False, default=1)
    encoder = Parameter('encoder reading', FloatRange(unit='deg'))
    backlash = PersistentParam("""backlash compensation\n
                               offset for always approaching from the same side""",
                               FloatRange(unit='deg'), readonly=False, default=0)
    target_min = Limit()
    target_max = Limit()
    alive_time = PersistentParam('alive time for detecting restarts',
                                 FloatRange(), default=0, export=False)

    ioClass = PhytronIO
    _step_size = None  # degree / step
    _blocking_error = None  # None or a string indicating the reason of an error needing clear_errors
    _running = False  # status indicates motor is running
    _prev_diff = 0  # for checking progress
    _intermediate_target = 0
    _stopped_at = 0

    STATUS_MAP = {
        '08': (IDLE, ''),
        '01': (ERROR, 'power stage failure'),
        '02': (ERROR, 'power too low'),
        '04': (ERROR, 'power stage over temperature'),
        '07': (ERROR, 'no power stage'),
        '80': (ERROR, 'encoder failure'),
    }

    def get(self, cmd):
        return self.communicate(f'{self.address:x}{self.axis}{cmd}')

    def set(self, cmd, value):
        # make sure e format is not used, max 8 characters
        strvalue = f'{value:.6g}'
        if 'e' in strvalue:
            if abs(value) <= 1:  # very small number
                strvalue = f'{value:.7f}'
            elif abs(value) < 99999999:  # big number
                strvalue = f'{value:.0f}'
            else:
                raise ValueError(f'number ({value}) must not have more than 8 digits')
        self.communicate(f'{self.address:x}{self.axis}{cmd}{strvalue}')

    def set_get(self, cmd, value, query):
        self.set(cmd, value)
        return self.get(query)

    def read_alive_time(self):
        now = time.time()
        axisbit = 1 << int(self.axis == 'Y')
        active_axes = int(self.get('P37R'))  # adr 37 is a custom address with no internal meaning
        if not axisbit & active_axes:  # power cycle detected and this axis not yet active
            self.set('P37S', axisbit | active_axes)  # activate axis
            if now < self.alive_time + 7 * 24 * 3600:  # the device was running within last week
                # inform the user about the loss of position by the need of doing clear_errors
                self._blocking_error = 'lost position'
            else:  # do silently
                self.clear_errors()
        self.alive_time = now
        self.saveParameters()
        return now

    def read_value(self):
        return float(self.get('P20R')) * self.sign

    def read_encoder(self):
        if self.encoder_mode == 'NO':
            return self.value
        return float(self.get('P22R')) * self.sign

    def write_sign(self, value):
        self.sign = value
        self.saveParameters()
        return Done

    def get_step_size(self):
        self._step_size = float(self.get('P03R'))

    def read_speed(self):
        if self._step_size is None:
            # avoid repeatedly reading step size, as this is polled and will not change
            self.get_step_size()
        return float(self.get('P14R')) * self._step_size

    def write_speed(self, value):
        self.get_step_size()  # read step size anyway, it does not harm
        return float(self.set_get('P14S', round(value / self._step_size), 'P14R')) * self._step_size

    def read_accel(self):
        if not self._step_size:
            self.get_step_size()
        return float(self.get('P15R')) * self._step_size

    def write_accel(self, value):
        self.get_step_size()
        return float(self.set_get('P15S', round(value / self._step_size), 'P15R')) * self._step_size

    def check_target(self, value):
        self.checkLimits(value)
        self.checkLimits(value + self.backlash)

    def write_target(self, value):
        self.read_alive_time()
        if self._blocking_error:
            self.status = ERROR, 'clear_errors needed after ' + self._blocking_error
            raise HardwareError(self.status[1])
        self.saveParameters()
        self.start_machine(self.starting, target=value)
        return value

    def hw_stop(self):
        self._stopped_at = time.time()
        self.get('S')

    def doPoll(self):
        super().doPoll()
        if self._running and not self.isBusy():
            if time.time() > self._stopped_at + 5:
                self.log.warning('stop motor not started by us')
                self.hw_stop()

    def read_status(self):
        for _ in range(3):
            sysstatus = self.communicate(f'{self.address:x}SE')
            try:
                sysstatus = sysstatus[1:4] if self.axis == 'X' else sysstatus[5:8]
                status = self.STATUS_MAP[sysstatus[1:]]
            except Exception:  # can not interprete the reply, probably communication error
                self.log.warning('bad status reply %r', sysstatus)
                continue
            break
        else:
            status = (ERROR, f'unknown status after 3 tries {sysstatus!r}')
        self._running = sysstatus[0] != '1'
        if status[0] == ERROR:
            self._blocking_error = status[1]
            return status
        return super().read_status()  # status from state machine

    def check_moving(self):
        """checks while motor is moving

        - in case motor is moving properly return Retry
        - in case motor is moving in the wrong direction, return self.stopping_for_restart
        - in case encoder does not follow steps, raise a blocking error
        """
        prev_enc = self.encoder
        if self.encoder_mode != 'NO':
            enc = self.read_encoder()
        else:
            enc = self.value
        if not self._running:  # at target (self._running is updated in self.read_status())
            return False
        diff = abs(self.value - self._intermediate_target)
        if diff > self._prev_diff and diff > self.encoder_tolerance:
            # when the motor was started while running, without stopping first
            # it happend that the motor run (almost) endless beyond the target!
            # add this is to catch similar errors
            self.hw_stop()
            self.log.warning('motor is moving the wrong way')
            return self.stopping_for_restart
        self._prev_diff = diff
        if self.encoder_mode != 'CHECK':
            return Retry
        tol = self.encoder_tolerance + abs(enc - prev_enc)
        if abs(self.value - enc) <= tol:
            return Retry
        self.log.error('encoder lag: steps %g deviate by more than %g from encoder %g',
                       self.value, tol, enc)
        self.hw_stop()
        self.saveParameters()
        self._blocking_error = 'encoder lag error'
        raise HardwareError(self._blocking_error)

    def start_motor(self, target):
        if self.backlash and (target - self.value) * self.backlash > 0:
            # drive first to target + backlash
            target += self.backlash
        self._prev_diff = abs(target - self.value)
        self._intermediate_target = target
        self.set('A', self.sign * target)

    @status_code(BUSY)
    def stopping_for_restart(self, sm):
        self.read_status()
        if self._running:
            return Retry
        self.start_motor(sm.target)
        return self.driving

    @status_code(BUSY)
    def starting(self, sm):
        self.read_status()
        if self._running:
            self.hw_stop()
            return self.stopping_for_restart
        self.start_motor(sm.target)
        return self.driving

    @status_code(BUSY)
    def driving(self, sm):
        self.read_status()
        result = self.check_moving()
        if result:
            return result  # Retry or self.stopping_for_restart
        if self._intermediate_target != self.target:
            self._intermediate_target = self.target
            # drive to real target after intermediate target
            self.start_motor(self.target)
            return self.driving_to_final_position
        return self.finishing

    @status_code(BUSY)
    def driving_to_final_position(self, sm):
        result = self.check_moving()
        if result:
            return result  # Retry or self.stopping_for_restart
        return self.finishing

    @status_code(BUSY)
    def finishing(self, sm):
        if sm.init:
            sm.mismatch_count = 0
        # finish
        pos = self.read_value()
        enc = self.read_encoder()
        if (self.encoder_mode == 'CHECK' and
                abs(enc - pos) > self.encoder_tolerance):
            if sm.mismatch_count > 2:
                self.log.error('encoder mismatch: abs(%g - %g) < %g',
                               enc, pos, self.encoder_tolerance)
                self._blocking_error = 'encoder does not match pos'
                raise HardwareError(self._blocking_error)
            sm.mismatch_count += 1
            return Retry
        self.saveParameters()
        return self.final_status(IDLE, '')

    @status_code(BUSY)
    def stopping(self, sm):
        if self._running:
            return Retry
        return self.final_status(IDLE, 'stopped')

    @Command
    def stop(self):
        self.hw_stop()
        self.start_machine(self.stopping, status=(BUSY, 'stopping'))

    @Command
    def clear_errors(self):
        """Reset error, set position to encoder"""
        self.read_value()
        if self._blocking_error:
            newenc = enc = self.read_encoder()
            pos = self.value
            if abs(enc - pos) > self.encoder_tolerance or self.encoder_mode == 'NO':
                if self.circumference:
                    # bring encoder value either within or as close as possible to the given range
                    if enc < self.target_min:
                        mid = self.target_min + 0.5 * min(self.target_max - self.target_min, self.circumference)
                    elif enc > self.target_max:
                        mid = self.target_max - 0.5 * min(self.target_max - self.target_min, self.circumference)
                    else:
                        mid = enc
                    newenc += round((mid - enc) / self.circumference) * self.circumference
                if newenc != enc and self.encoder_mode != 'NO':
                    self.log.info(f'enc {enc} -> {newenc}')
                    self.set('P22S', newenc * self.sign)
            if newenc != pos:
                self.log.info(f'pos {pos} -> {newenc}')
                self.set('P20S', newenc * self.sign)  # set pos to encoder
            self.read_value()
            self.status = 'IDLE', 'after error reset'
            self._blocking_error = None
            self.target = self.value  # clear error in target
