#!/usr/bin/env python
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
"""oxford instruments mercury IPS power supply"""

import time
from frappy.core import Parameter, EnumType, FloatRange, BoolType, IntRange, Property, Module
from frappy.lib.enum import Enum
from frappy.errors import BadValueError, HardwareError
from frappy_psi.magfield import Magfield, SimpleMagfield, Status
from frappy_psi.mercury import MercuryChannel, off_on, Mapped
from frappy.states import Retry

Action = Enum(hold=0, run_to_set=1, run_to_zero=2, clamped=3)
hold_rtoz_rtos_clmp = Mapped(HOLD=Action.hold, RTOS=Action.run_to_set,
                             RTOZ=Action.run_to_zero, CLMP=Action.clamped)
CURRENT_CHECK_SIZE = 2


class SimpleField(MercuryChannel, SimpleMagfield):
    nunits = Property('number of IPS subunits', IntRange(1, 6), default=1)
    action = Parameter('action', EnumType(Action), readonly=False)
    setpoint = Parameter('field setpoint', FloatRange(unit='T'), default=0)
    voltage = Parameter('leads voltage', FloatRange(unit='V'), default=0)
    atob = Parameter('field to amp', FloatRange(0, unit='A/T'), default=0)
    working_ramp = Parameter('effective ramp', FloatRange(0, unit='T/min'), default=0)
    kind = 'PSU'
    slave_currents = None
    classdict = {}

    def __new__(cls, name, logger, cfgdict, srv):  # pylint: disable=arguments-differ
        nunits = cfgdict.get('nunits', 1)
        if isinstance(nunits, dict):
            nunits = nunits['value']
        if nunits == 1:
            return Module.__new__(cls, name, logger, cfgdict, srv)
        classname = cls.__name__ + str(nunits)
        newclass = cls.classdict.get(classname)
        if not newclass:
            # create individual current and voltage parameters dynamically
            attrs = {}
            for i in range(1, nunits + 1):
                attrs['I%d' % i] = Parameter('slave %s current' % i, FloatRange(unit='A'), default=0)
                attrs['V%d' % i] = Parameter('slave %s voltage' % i, FloatRange(unit='V'), default=0)

            newclass = type(classname, (cls,), attrs)
            cls.classdict[classname] = newclass
        return Module.__new__(newclass, name, logger, cfgdict, srv)

    def initModule(self):
        super().initModule()
        try:
            self.write_action(Action.hold)
        except Exception as e:
            self.log.error('can not set to hold %r', e)

    def read_value(self):
        return self.query('DEV::PSU:SIG:FLD')

    def read_ramp(self):
        return self.query('DEV::PSU:SIG:RFST')

    def write_ramp(self, value):
        return self.change('DEV::PSU:SIG:RFST', value)

    def read_action(self):
        return self.query('DEV::PSU:ACTN', hold_rtoz_rtos_clmp)

    def write_action(self, value):
        return self.change('DEV::PSU:ACTN', value, hold_rtoz_rtos_clmp)

    def read_atob(self):
        return self.query('DEV::PSU:ATOB')

    def read_voltage(self):
        return self.query('DEV::PSU:SIG:VOLT')

    def read_working_ramp(self):
        return self.query('DEV::PSU:SIG:RFLD')

    def read_setpoint(self):
        return self.query('DEV::PSU:SIG:FSET')

    def set_and_go(self, value):
        self.setpoint = self.change('DEV::PSU:SIG:FSET', value)
        assert self.write_action(Action.hold) == Action.hold
        assert self.write_action(Action.run_to_set) == Action.run_to_set

    def start_ramp_to_target(self, sm):
        # if self.action != Action.hold:
        #     assert self.write_action(Action.hold) == Action.hold
        #     return Retry
        self.set_and_go(sm.target)
        sm.try_cnt = 5
        return self.ramp_to_target

    def ramp_to_target(self, sm):
        try:
            return super().ramp_to_target(sm)
        except HardwareError:
            sm.try_cnt -= 1
            if sm.try_cnt < 0:
                raise
            self.set_and_go(sm.target)
            return Retry

    def final_status(self, *args, **kwds):
        self.write_action(Action.hold)
        return super().final_status(*args, **kwds)

    def on_restart(self, sm):
        self.write_action(Action.hold)
        return super().on_restart(sm)


class Field(SimpleField, Magfield):
    persistent_field = Parameter(
        'persistent field at last switch off', FloatRange(unit='$'), readonly=False)
    wait_switch_on = Parameter(
        'wait time to ensure switch is on', FloatRange(0, unit='s'), readonly=True, default=60)
    wait_switch_off = Parameter(
        'wait time to ensure switch is off', FloatRange(0, unit='s'), readonly=True, default=60)
    forced_persistent_field = Parameter(
        'manual indication that persistent field is bad', BoolType(), readonly=False, default=False)

    _field_mismatch = None
    __persistent_field = None  # internal value of persistent field
    __switch_fixed_until = 0

    def doPoll(self):
        super().doPoll()
        self.read_current()

    def startModule(self, start_events):
        # on restart, assume switch is changed long time ago, if not, the mercury
        # will complain and this will be handled in start_ramp_to_field
        self.switch_on_time = 0
        self.switch_off_time = 0
        self.switch_heater = self.query('DEV::PSU:SIG:SWHT', off_on)
        super().startModule(start_events)

    def read_value(self):
        current = self.query('DEV::PSU:SIG:FLD')
        if self.switch_heater == self.switch_heater.on:
            self.__persistent_field = current
            self.forced_persistent_field = False
            return current
        pf = self.query('DEV::PSU:SIG:PFLD')
        if self.__persistent_field is None:
            self.__persistent_field = pf
            self._field_mismatch = False
        else:
            self._field_mismatch = abs(self.__persistent_field - pf) > self.tolerance * 10
        self.persistent_field = self.__persistent_field
        return self.__persistent_field

    def _check_adr(self, adr):
        """avoid complains about bad slot"""
        if adr.startswith('DEV:PSU.M'):
            return
        super()._check_adr(adr)

    def read_current(self):
        if self.slave_currents is None:
            self.slave_currents = [[] for _ in range(self.nunits + 1)]
        if self.nunits > 1:
            for i in range(1, self.nunits + 1):
                curri = self.query(f'DEV:PSU.M{i}:PSU:SIG:CURR')
                volti = self.query(f'DEV:PSU.M{i}:PSU:SIG:VOLT')
                setattr(self, f'I{i}', curri)
                setattr(self, f'V{i}', volti)
                self.slave_currents[i].append(curri)
            current = self.query('DEV::PSU:SIG:CURR')
            self.slave_currents[0].append(current)
            min_ = min(self.slave_currents[0]) / self.nunits
            max_ = max(self.slave_currents[0]) / self.nunits
            # keep one element more for the total current (first and last measurement is a total)
            self.slave_currents[0] = self.slave_currents[0][-CURRENT_CHECK_SIZE-1:]
            for i in range(1, self.nunits + 1):
                min_i = min(self.slave_currents[i])
                max_i = max(self.slave_currents[i])
                if len(self.slave_currents[i]) > CURRENT_CHECK_SIZE:
                    self.slave_currents[i] = self.slave_currents[i][-CURRENT_CHECK_SIZE:]
                    if min_i - 0.1 > max_ or min_ > max_i + 0.1:  # use an arbitrary 0.1 A tolerance
                        self.log.warning('individual currents mismatch %r', self.slave_currents)
        else:
            current = self.query('DEV::PSU:SIG:CURR')
        if self.atob:
            return current / self.atob
        return 0

    def write_persistent_field(self, value):
        if self.forced_persistent_field or abs(self.__persistent_field - value) <= self.tolerance * 10:
            self._field_mismatch = False
            self.__persistent_field = value
            return value
        raise BadValueError('changing persistent field needs forced_persistent_field=True')

    def write_target(self, target):
        if self._field_mismatch:
            self.forced_persistent_field = True
            raise BadValueError('persistent field does not match - set persistent field to guessed value first')
        return super().write_target(target)

    def read_switch_heater(self):
        value = self.query('DEV::PSU:SIG:SWHT', off_on)
        now = time.time()
        if value != self.switch_heater:
            if now < self.__switch_fixed_until:
                self.log.debug('correct fixed switch time')
                # probably switch heater was changed, but IPS reply is not yet updated
                if self.switch_heater:
                    self.switch_on_time = time.time()
                else:
                    self.switch_off_time = time.time()
                return self.switch_heater
        return value

    def read_wait_switch_on(self):
        return self.query('DEV::PSU:SWONT') * 0.001

    def read_wait_switch_off(self):
        return self.query('DEV::PSU:SWOFT') * 0.001

    def write_switch_heater(self, value):
        if value == self.read_switch_heater():
            self.log.info('switch heater already %r', value)
            # we do not want to restart the timer
            return value
        self.__switch_fixed_until = time.time() + 10
        self.log.debug('switch time fixed for 10 sec')
        result = self.change('DEV::PSU:SIG:SWHT', value, off_on, n_retry=0)  # no readback check
        return result

    def start_ramp_to_field(self, sm):
        if abs(self.current - self.__persistent_field) <= self.tolerance:
            self.log.info('leads %g are already at %g', self.current, self.__persistent_field)
            return self.ramp_to_field
        try:
            self.set_and_go(self.__persistent_field)
        except (HardwareError, AssertionError) as e:
            if self.switch_heater:
                self.log.warn('switch is already on!')
                return self.ramp_to_field
            self.log.warn('wait first for switch off current=%g pf=%g %r', self.current, self.__persistent_field, e)
            sm.after_wait = self.ramp_to_field
            return self.wait_for_switch
        return self.ramp_to_field

    def start_ramp_to_target(self, sm):
        sm.try_cnt = 5
        try:
            self.set_and_go(sm.target)
        except (HardwareError, AssertionError) as e:
            self.log.warn('switch not yet ready %r', e)
            self.status = Status.PREPARING, 'wait for switch on'
            sm.after_wait = self.ramp_to_target
            return self.wait_for_switch
        return self.ramp_to_target

    def ramp_to_field(self, sm):
        try:
            return super().ramp_to_field(sm)
        except HardwareError:
            sm.try_cnt -= 1
            if sm.try_cnt < 0:
                raise
            self.set_and_go(self.__persistent_field)
            return Retry

    def wait_for_switch(self, sm):
        if not sm.delta(10):
            return Retry
        try:
            self.log.warn('try again')
            # try again
            self.set_and_go(self.__persistent_field)
        except (HardwareError, AssertionError):
            return Retry
        return sm.after_wait

    def wait_for_switch_on(self, sm):
        self.read_switch_heater()  # trigger switch_on/off_time
        if self.switch_heater == self.switch_heater.off:
            if sm.init:  # avoid too many states chained
                return Retry
            self.log.warning('switch turned off manually?')
            return self.start_switch_on
        return super().wait_for_switch_on(sm)

    def wait_for_switch_off(self, sm):
        self.read_switch_heater()
        if self.switch_heater == self.switch_heater.on:
            if sm.init:  # avoid too many states chained
                return Retry
            self.log.warning('switch turned on manually?')
            return self.start_switch_off
        return super().wait_for_switch_off(sm)

    def start_ramp_to_zero(self, sm):
        pf = self.query('DEV::PSU:SIG:PFLD')
        if abs(pf - self.value) > self.tolerance * 10:
            self.log.warning('persistent field %g does not match %g after switch off', pf, self.value)
        try:
            assert self.write_action(Action.hold) == Action.hold
            assert self.write_action(Action.run_to_zero) == Action.run_to_zero
        except (HardwareError, AssertionError) as e:
            self.log.warn('switch not yet ready %r', e)
            self.status = Status.PREPARING, 'wait for switch off'
            sm.after_wait = self.ramp_to_zero
            return self.wait_for_switch
        return self.ramp_to_zero

    def ramp_to_zero(self, sm):
        try:
            return super().ramp_to_zero(sm)
        except HardwareError:
            sm.try_cnt -= 1
            if sm.try_cnt < 0:
                raise
            assert self.write_action(Action.hold) == Action.hold
            assert self.write_action(Action.run_to_zero) == Action.run_to_zero
            return Retry
