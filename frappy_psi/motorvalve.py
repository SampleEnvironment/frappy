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

"""motor valve using a trinamic PD-1161 motor

the valve has an end switch connected to the 'home' digital input
of the motor controller. Motor settings for the currently used valve:

[valve_motor]
description = valve motor
class = frappy_psi.trinamic.Motor
maxcurrent=0.3   # a value corresponding to the torque needed to firmly close the valve.
move_limit=9999  # no move limit needed
acceleration=150
encoder_tolerance=3.6  # typical value
auto_reset=True   # motor stalls on closing

[valve]
description = trinamic angular motor valve
class = frappy_psi.motorvalve.MotorValve
motor = valve_motor
turns = 9      # number of turns needed to open fully
speed = 400    # close to max. speed
lowspeed = 50  # speed for final closing / reference run
"""

from frappy.core import Drivable, Parameter, EnumType, Attached, FloatRange, \
    Command, IDLE, BUSY, WARN, ERROR, Done, PersistentParam, PersistentMixin
from frappy.errors import HardwareError
from frappy_psi.trinamic import Motor
from frappy.lib.statemachine import StateMachine, Retry, Stop


class MotorValve(PersistentMixin, Drivable):
    motor = Attached(Motor)
    value = Parameter('current state', EnumType(
        closed=0, opened=1, undefined=-1), default=-1)
    target = Parameter('target state', EnumType(close=0, open=1))
    turns = Parameter('number of turns to open', FloatRange(), readonly=False, group='settings')
    speed = Parameter('speed for far moves', FloatRange(), readonly=False, group='settings')
    lowspeed = Parameter('speed for finding closed position', FloatRange(), readonly=False, group='settings')
    closed_pos = PersistentParam('fully closed position', FloatRange(),
                                 persistent='auto', export=True, default=-999)  # TODO: export=False
    pollinterval = Parameter(group='settings')

    _state = None

    # remark: the home button must be touched when the motor is at zero

    def earlyInit(self):
        super().earlyInit()
        self._state = StateMachine(logger=self.log, count=3, cleanup=self.handle_error)

    def write_target(self, target):
        if self.status[0] == ERROR:
            raise HardwareError('%s: need refrun' % self.status[1])
        self.target = target
        self._state.start(self.goto_target, count=3)
        return Done

    def goto_target(self, state):
        self.value = 'undefined'
        if self.motor.isBusy():
            mot_target = 0 if self.target == self.target.close else self.turns * 360
            if abs(mot_target - self.motor.target) > self.motor.tolerance:
                self.motor.stop()
        return self.open_valve if self.target == self.target.open else self.close_valve

    def read_value(self):
        """determine value and status"""
        if self.status[0] == ERROR:
            return 'undefined'
        if self.motor.isBusy():
            return Done
        motpos = self.motor.read_value()
        if self.motor.read_home():
            if motpos > 360:
                self.status = ERROR, 'home button must be released at this position'
            elif motpos > 5:
                if self.status[0] != ERROR:
                    self.status = WARN, 'position undefined'
            elif motpos < -360:
                self.status = ERROR, 'motor must not reach -1 turn!'
            elif abs(motpos - self.closed_pos) < self.motor.tolerance:
                self.status = IDLE, 'closed'
                return 'closed'
            self.status = WARN, 'nearly closed'
            return 'undefined'
        if abs(motpos - self.turns * 360) < 5:
            self.status = IDLE, 'opened'
            return 'opened'
        if motpos < 5:
            self.status = ERROR, 'home button must be engaged at this position'
        elif self.status[0] != ERROR:
            self.status = WARN, 'position undefined'
        return 'undefined'

    def open_valve(self, state):
        if state.init:
            self.closed_pos = -999
            self.value = 'undefined'
            self.status = BUSY, 'opening'
            self.motor.write_speed(self.speed)
            self.motor.write_target(self.turns * 360)
        if self.motor.isBusy():
            if self.motor.home and self.motor.value > 360:
                self.motor.stop()
                self.status = ERROR, 'opening valve failed (home switch not released)'
                return None
            return Retry
        motvalue = self.motor.read_value()
        if abs(motvalue - self.turns * 360) < 5:
            self.read_value()  # value = opened, status = IDLE
        else:
            if state.count > 0:
                state.count -= 1
                self.log.info('target %g not reached, try again', motvalue)
                return self.goto_target
            self.status = ERROR, 'opening valve failed (motor target not reached)'
        return None

    def close_valve(self, state):
        if state.init:
            self.closed_pos = -999
            self.status = BUSY, 'closing'
            self.motor.write_speed(self.speed)
            self.motor.write_target(0)
        if self.motor.isBusy():
            if self.motor.home:
                return self.find_closed
            return Retry
        motvalue = self.motor.read_value()
        if abs(motvalue) > 5:
            if state.count > 0:
                state.count -= 1
                self.log.info('target %g not reached, try again', motvalue)
                return self.goto_target
            self.status = ERROR, 'closing valve failed (zero not reached)'
            return None
        if self.read_value() == self.value.undefined:
            if self.status[0] != ERROR:
                return self.find_closed
        return None

    def find_closed(self, state):
        """drive with low speed until motor stalls"""
        if state.init:
            self.motor.write_speed(self.lowspeed)
            state.prev = self.motor.value
            self.motor.write_target(-360)
        if self.motor.isBusy():
            if not self.motor.home:
                self.motor.stop()
                return None
            return Retry
        motvalue = self.motor.read_value()
        if motvalue < -360:
            self.read_value()  # status -> error
            return None
        if motvalue < state.prev - 5:
            # moved by more than 5 deg
            state.prev = self.motor.value
            self.motor.write_target(-360)
            return Retry
        if motvalue > 5:
            self.status = ERROR, 'closing valve failed (zero not reached)'
            return None
        if motvalue < -355:
            self.status = ERROR, 'closing valve failed (does not stop)'
            return None
        self.closed_pos = motvalue
        self.read_value()  # value = closed, status = IDLE
        return None

    @Command
    def ref_run(self):
        """start reference run"""
        self.target = 'close'
        self._state.start(self.ref_home, count=3)

    @Command
    def stop(self):
        self._state.stop()
        self.motor.stop()

    def ref_home(self, state):
        if state.init:
            self.closed_pos = -999
            self.motor.write_speed(self.lowspeed)
            if self.motor.read_home():
                self.status = BUSY, 'refrun: release home'
                self.motor.write_target(self.motor.read_value() + 360)
                return self.ref_released
            self.status = BUSY, 'refrun: find home'
            self.motor.write_target(self.motor.read_value() - (self.turns + 1) * 360)
        if not self.motor.isBusy():
            self.status = ERROR, 'ref run failed, can not find home switch'
            return None
        if not self.motor.home:
            return Retry
        self.motor.write_speed(self.lowspeed)
        state.prev = self.motor.read_value()
        self.motor.write_target(state.prev - 360)
        self.status = BUSY, 'refrun: find closed'
        return self.ref_closed

    def ref_released(self, state):
        if self.motor.isBusy():
            if self.motor.home:
                return Retry
        elif self.motor.read_home():
            if state.count > 0:
                state.count -= 1
                self.log.info('home switch not released, try again')
                self.motor.write_target(self.motor.target)
                return Retry
            self.status = ERROR, 'ref run failed, can not release home switch'
            return None
        return self.ref_home

    def ref_closed(self, state):
        if self.motor.isBusy():
            if not self.motor.home:
                self.motor.stop()
                return None
            return Retry
        self.motor.set_zero(max(-50, (self.motor.read_value() - state.prev) * 0.5))
        self.read_value()  # check home button is valid
        if abs(self.motor.target - self.motor.value) < 5:
            self.status = ERROR, 'ref run failed, does not stop'
        if self.status[0] == ERROR:
            return None
        self.log.info('refrun successful')
        return self.close_valve

    def handle_error(self, state):
        if state.stopped:  # stop or restart case
            if state.stopped is Stop:
                self.status = WARN, 'stopped'
            return None
        if state.count > 0:
            state.count -= 1
            self.log.info('error %r, try again', state.last_error)
            state.default_cleanup(state)  # log error cause
            state.last_error = None
            return self.goto_target  # try again
        self.status = ERROR, str(state.last_error)
        return state.default_cleanup(state)
