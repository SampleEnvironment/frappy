# *****************************************************************************
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
# *****************************************************************************
"""generic persistent magnet driver"""

import time
from frappy.core import Drivable, Parameter, BUSY, Limit
from frappy.datatypes import FloatRange, EnumType, TupleOf, StatusType
from frappy.errors import ConfigError, HardwareError, DisabledError
from frappy.lib.enum import Enum
from frappy.states import Retry, HasStates, status_code

UNLIMITED = FloatRange()

Mode = Enum(
    DISABLED=0,
    PERSISTENT=30,
    DRIVEN=50,
)

Status = Enum(
    Drivable.Status,
    PREPARED=150,
    PREPARING=340,
    RAMPING=370,
    STABILIZING=380,
    FINALIZING=390,
)

OFF = 0
ON = 1


class SimpleMagfield(HasStates, Drivable):
    value = Parameter('magnetic field', datatype=FloatRange(unit='T'))
    target_min = Limit()
    target_max = Limit()
    ramp = Parameter(
        'wanted ramp rate for field', FloatRange(unit='$/min'), readonly=False)
    # export only when different from ramp:
    workingramp = Parameter(
        'effective ramp rate for field', FloatRange(unit='$/min'), export=False)
    tolerance = Parameter(
        'tolerance', FloatRange(0, unit='$'), readonly=False, default=0.0002)
    trained = Parameter(
        'trained field (positive)',
        TupleOf(FloatRange(-99, 0, unit='$'), FloatRange(0, unit='$')),
        readonly=False, default=(0, 0))
    wait_stable_field = Parameter(
        'wait time to ensure field is stable', FloatRange(0, unit='s'), readonly=False, default=31)
    ramp_tmo = Parameter(
        'timeout for field ramp progress',
        FloatRange(0, unit='s'), readonly=False, default=30)

    _last_target = None
    _symmetric_limits = False

    def earlyInit(self):
        super().earlyInit()
        # when limits are symmetric at init, we want auto symmetric limits
        self._symmetric_limits = self.target_min == -self.target_max

    def write_target_max(self, value):
        if self._symmetric_limits:
            self.target_min = -value
        return value

    def write_target_min(self, value):
        """when modified to other than a symmetric value, we assume the user does not want auto symmetric limits"""
        self._symmetric_limits = value == -self.target_max
        return value

    def checkProperties(self):
        dt = self.parameters['target'].datatype
        max_ = dt.max
        if max_ == UNLIMITED.max:
            raise ConfigError('target.max not configured')
        if dt.min == UNLIMITED.min:  # not given: assume bipolar symmetric
            dt.min = -max_
            self.target_min = max(dt.min, self.target_min)
            if 'target_max' in self.writeDict:
                self.writeDict.setdefault('target_min', -self.writeDict['target_max'])
        super().checkProperties()

    def stop(self):
        """keep field at current value"""
        # let the state machine do the needed steps to finish
        self.write_target(self.value)

    def last_target(self):
        """get best known last target

        as long as the guessed last target is within tolerance
        with repsect to the main value, it is used, as in general
        it has better precision
        """
        last = self._last_target
        if last is None:
            try:
                last = self.setpoint  # get read back from HW, if available
            except Exception:
                pass
        if last is None or abs(last - self.value) > self.tolerance:
            return self.value
        return last

    def write_target(self, target):
        self.start_machine(self.start_field_change, target=target)
        return target

    def init_progress(self, sm, value):
        sm.prev_point = sm.now, value

    def get_progress(self, sm, value):
        """return the time passed for at least one tolerance step"""
        t, v = sm.prev_point
        dif = abs(v - value)
        tdif = sm.now - t
        if dif > self.tolerance:
            sm.prev_point = sm.now, value
        return tdif

    @status_code(BUSY, 'start ramp to target')
    def start_field_change(self, sm):
        self.setFastPoll(True, 1.0)
        return self.start_ramp_to_target

    @status_code(BUSY, 'ramping field')
    def ramp_to_target(self, sm):
        if sm.init:
            self.init_progress(sm, self.value)
        # Remarks: assume there is a ramp limiting feature
        if abs(self.value - sm.target) > self.tolerance:
            if self.get_progress(sm, self.value) > self.ramp_tmo:
                raise HardwareError('no progress')
            sm.stabilize_start = None  # force reset
            return Retry
        sm.stabilize_start = time.time()
        return self.stabilize_field

    @status_code(BUSY, 'stabilizing field')
    def stabilize_field(self, sm):
        if sm.now - sm.stabilize_start < self.wait_stable_field:
            return Retry
        return self.final_status()

    def read_workingramp(self):
        return self.ramp


class Magfield(SimpleMagfield):
    status = Parameter(datatype=StatusType(Status))
    mode = Parameter('persistent mode', EnumType(Mode), readonly=False, default=Mode.PERSISTENT)
    switch_heater = Parameter('switch heater', EnumType(off=OFF, on=ON),
                              readonly=False, default=0)
    current = Parameter(
        'leads current (in units of field)', FloatRange(unit='$'))
    # TODO: time_to_target
    # profile = Parameter(
    #     'ramp limit table', ArrayOf(TupleOf(FloatRange(unit='$'), FloatRange(unit='$/min'))),
    #     readonly=False)
    # profile_training = Parameter(
    #     'ramp limit table when in training',
    #     ArrayOf(TupleOf(FloatRange(unit='$'), FloatRange(unit='$/min'))), readonly=False)
    # TODO: the following parameters should be changed into properties after tests
    wait_switch_on = Parameter(
        'wait time to ensure switch is on', FloatRange(0, unit='s'), readonly=False, default=61)
    wait_switch_off = Parameter(
        'wait time to ensure switch is off', FloatRange(0, unit='s'), readonly=False, default=61)
    wait_stable_leads = Parameter(
        'wait time to ensure current is stable', FloatRange(0, unit='s'), readonly=False, default=6)
    persistent_limit = Parameter(
        'above this limit, lead currents are not driven to 0',
        FloatRange(0, unit='$'), readonly=False, default=99)
    leads_ramp_tmo = Parameter(
        'timeout for leads ramp progress',
        FloatRange(0, unit='s'), readonly=False, default=30)
    init_persistency = True
    switch_on_time = None
    switch_off_time = None

    def doPoll(self):
        if self.init_persistency:
            if self.read_switch_heater() and self.mode != Mode.DRIVEN:
                # switch heater is on on startup: got to persistent mode
                # do this after some delay, so the user might continue
                # driving without delay after a restart
                self.start_machine(self.go_persistent_soon, mode=self.mode)
            self.init_persistency = False
        super().doPoll()

    def initModule(self):
        super().initModule()
        self.registerCallbacks(self)  # for update_switch_heater

    def write_mode(self, value):
        self.init_persistency = False
        target = self.last_target()
        func = self.start_field_change
        if value == Mode.DISABLED:
            target = 0
            if abs(self.value) < self.tolerance:
                func = self.start_switch_off
        elif value == Mode.PERSISTENT:
            func = self.start_switch_off
        self.target = target
        self.start_machine(func, target=target, mode=value)
        return value

    def write_target(self, target):
        self.init_persistency = False
        if self.mode == Mode.DISABLED:
            if target == 0:
                return 0
            raise DisabledError('disabled')
        self.start_machine(self.start_field_change, target=target, mode=self.mode)
        return target

    def on_error(self, sm):  # sm is short for statemachine
        if self.switch_heater == ON:
            self.read_value()
            if sm.mode != Mode.DRIVEN:
                self.log.warning('turn switch heater off')
                self.write_switch_heater(OFF)
        return super().on_error(sm)

    @status_code(Status.WARN)
    def go_persistent_soon(self, sm):
        if sm.delta(60):
            self.target = sm.target = self.last_target()
            return self.start_field_change
        return Retry

    @status_code(Status.PREPARING)
    def start_field_change(self, sm):
        self.setFastPoll(True, 1.0)
        if (sm.target == self.last_target() and
                abs(sm.target - self.value) <= self.tolerance and
                abs(self.current - self.value) < self.tolerance and
                (self.mode != Mode.DRIVEN or self.switch_heater == ON)):  # short cut
            return self.check_switch_off
        if self.switch_heater == ON:
            return self.start_switch_on
        return self.start_ramp_to_field

    @status_code(Status.PREPARING)
    def start_ramp_to_field(self, sm):
        """start ramping current to persistent field

        initiate ramp to persistent field (with corresponding ramp rate)
        the implementation should return ramp_to_field
        """
        raise NotImplementedError

    @status_code(Status.PREPARING, 'ramp leads to match field')
    def ramp_to_field(self, sm):
        if sm.init:
            sm.stabilize_start = 0  # in case current is already at field
            self.init_progress(sm, self.current)
        dif = abs(self.current - self.value)
        if dif > self.tolerance:
            tdif = self.get_progress(sm, self.current)
            if tdif > self.leads_ramp_tmo:
                raise HardwareError('no progress')
            sm.stabilize_start = None  # force reset
            return Retry
        if sm.stabilize_start is None:
            sm.stabilize_start = sm.now
        return self.stabilize_current

    @status_code(Status.PREPARING)
    def stabilize_current(self, sm):
        if sm.now - sm.stabilize_start < self.wait_stable_leads:
            return Retry
        return self.start_switch_on

    def update_switch_heater(self, value):
        """is called whenever switch heater was changed"""
        if value == 0:
            if self.switch_off_time is None:
                self.log.info('restart switch_off_time')
                self.switch_off_time = time.time()
            self.switch_on_time = None
        else:
            if self.switch_on_time is None:
                self.log.info('restart switch_on_time')
                self.switch_on_time = time.time()
            self.switch_off_time = None

    @status_code(Status.PREPARING)
    def start_switch_on(self, sm):
        if (sm.target == self.last_target() and
                abs(sm.target - self.value) <= self.tolerance):  # short cut
            return self.check_switch_off
        if self.read_switch_heater() == OFF:
            try:
                self.write_switch_heater(ON)
            except Exception as e:
                self.log.warning('write_switch_heater %r', e)
                return Retry
        return self.wait_for_switch_on

    @status_code(Status.PREPARING)
    def wait_for_switch_on(self, sm):
        if sm.now - self.switch_on_time < self.wait_switch_on:
            if sm.delta(10):
                self.log.info('waited for %g sec', sm.now - self.switch_on_time)
            return Retry
        self._last_target = sm.target
        return self.start_ramp_to_target

    @status_code(Status.RAMPING)
    def start_ramp_to_target(self, sm):
        """start ramping current to target field

        initiate ramp to target
        the implementation should return ramp_to_target
        """
        raise NotImplementedError

    @status_code(Status.RAMPING)
    def ramp_to_target(self, sm):
        dif = abs(self.value - sm.target)
        if sm.init:
            sm.stabilize_start = 0  # in case current is already at target
            self.init_progress(sm, self.value)
        if dif > self.tolerance:
            sm.stabilize_start = sm.now
            tdif = self.get_progress(sm, self.value)
            if tdif > self.workingramp / self.tolerance * 60 + self.ramp_tmo:
                self.log.warn('no progress')
                raise HardwareError('no progress')
            sm.stabilize_start = None
            return Retry
        if sm.stabilize_start is None:
            sm.stabilize_start = sm.now
        return self.stabilize_field

    @status_code(Status.STABILIZING)
    def stabilize_field(self, sm):
        if sm.now < sm.stabilize_start + self.wait_stable_field:
            return Retry
        return self.check_switch_off

    def check_switch_off(self, sm):
        if sm.mode == Mode.DRIVEN:
            return self.final_status(Status.PREPARED, 'driven')
        return self.start_switch_off

    @status_code(Status.FINALIZING)
    def start_switch_off(self, sm):
        if self.switch_heater == ON:
            self.write_switch_heater(OFF)
        return self.wait_for_switch_off

    @status_code(Status.FINALIZING)
    def wait_for_switch_off(self, sm):
        if sm.now - self.switch_off_time < self.wait_switch_off:
            return Retry
        if abs(self.value) > self.persistent_limit:
            return self.final_status(Status.IDLE, 'leads current at field, switch off')
        return self.start_ramp_to_zero

    @status_code(Status.FINALIZING)
    def start_ramp_to_zero(self, sm):
        """start ramping current to zero

        initiate ramp to zero (with corresponding ramp rate)
        the implementation should return ramp_to_zero
        """
        raise NotImplementedError

    @status_code(Status.FINALIZING)
    def ramp_to_zero(self, sm):
        """ramp field to zero"""
        if sm.init:
            self.init_progress(sm, self.current)
        if abs(self.current) > self.tolerance:
            if self.get_progress(sm, self.current) > self.leads_ramp_tmo:
                raise HardwareError('no progress')
            return Retry
        if sm.mode == Mode.DISABLED and abs(self.value) < self.tolerance:
            return self.final_status(Status.DISABLED, 'disabled')
        return self.final_status(Status.IDLE, 'persistent mode')
