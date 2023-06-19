#!/usr/bin/env python
#  -*- coding: utf-8 -*-
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
"""oxford instruments mercury family"""


import math
import re
import time

from frappy.core import Command, Drivable, HasIO, Writable, StatusType, \
    Parameter, Property, Readable, StringIO, Attached, IDLE, RAMPING, nopoll
from frappy.datatypes import EnumType, FloatRange, StringType, StructOf, BoolType, TupleOf
from frappy.errors import HardwareError, ProgrammingError, ConfigError
from frappy_psi.convergence import HasConvergence
from frappy.states import Retry, Finish
from frappy.mixins import HasOutputModule, HasControlledBy


VALUE_UNIT = re.compile(r'(.*\d|inf)([A-Za-z/%]*)$')
SELF = 0


def as_float(value):
    """converts string (with unit) to float and float to string"""
    if isinstance(value, str):
        return float(VALUE_UNIT.match(value).group(1))
    return f'{value:g}'


def as_string(value):
    return value


class Mapped:
    def __init__(self, **kwds):
        self.mapping = kwds
        self.mapping.update({v: k for k, v in kwds.items()})

    def __call__(self, value):
        return self.mapping[value]


off_on = Mapped(OFF=False, ON=True)
fast_slow = Mapped(ON=0, OFF=1)  # maps OIs slow=ON/fast=OFF to sample_rate.slow=0/sample_rate.fast=1


class IO(StringIO):
    identification = [('*IDN?', r'IDN:OXFORD INSTRUMENTS:*')]


class MercuryChannel(HasIO):
    slot = Property('comma separated slot id(s), e.g. DB6.T1', StringType())
    kind = ''  #: used slot kind(s)
    slots = ()  #: dict[<kind>] of <slot>

    def earlyInit(self):
        super().earlyInit()
        self.kinds = self.kind.split(',')
        slots = self.slot.split(',')
        if len(slots) != len(self.kinds):
            raise ConfigError(f'slot needs {len(self.kinds)} comma separated names')
        self.slots = dict(zip(self.kinds, slots))
        self.setProperty('slot', slots[0])

    def _complete_adr(self, adr):
        """insert slot to adr"""
        spl = adr.split(':')
        if spl[0] == 'DEV':
            if spl[1] == '':
                spl[1] = self.slots[spl[2]]
                return ':'.join(spl)
        elif spl[0] != 'SYS':
            raise ProgrammingError('using old style adr?')
        return adr

    def multiquery(self, adr, names=(), convert=as_float, debug=None):
        """get parameter(s) in mercury syntax

        :param adr: the 'address part' of the SCPI command
                    READ: is added automatically, slot is inserted when adr starts with DEV::
        :param names: the SCPI names of the parameter(s), for example ['TEMP']
        :param convert: a converter function (converts replied string to value)
        :return:  the values as tuple

        Example (kind=PRES,AUX slot=DB5.P1,DB3.G1):
            adr='DEV::AUX:SIG'
            names = ('PERC',)
        -> query command will be READ:DEV:DB3.G1:AUX:SIG:PERC
        """
        # TODO: if the need arises: allow convert to be a list
        adr = self._complete_adr(adr)
        cmd = f"READ:{adr}:{':'.join(names)}"
        msg = ''
        for _ in range(3):
            if msg:
                self.log.warning('%s', msg)
            reply = self.communicate(cmd)
            if debug is not None:
                debug.append(reply)
            head = f'STAT:{adr}:'
            try:
                assert reply.startswith(head)
                replyiter = iter(reply[len(head):].split(':'))
                keys, result = zip(*zip(replyiter, replyiter))
                assert keys == tuple(names)
                return tuple(convert(r) for r in result)
            except (AssertionError, AttributeError, ValueError):
                time.sleep(0.1)  # in case this was the answer of a previous command
                msg = f'invalid reply {reply!r} to cmd {cmd!r}'
        raise HardwareError(msg) from None

    def multichange(self, adr, values, convert=as_float, tolerance=0, n_retry=3, lazy=False):
        """set parameter(s) in mercury syntax

        :param adr: as in multiquery method. SET: is added automatically
        :param values: [(name1, value1), (name2, value2) ...]
        :param convert: a converter function (converts given value to string and replied string to value)
        :param tolerance: tolerance for readback check
        :param n_retry: number of retries or 0 for no readback check
        :param lazy: check direct reply only (no additional query)
        :return:  the values as tuple

        Example (kind=TEMP, slot=DB6.T1:
            adr='DEV::TEMP:LOOP'
            values = [('P', 5), ('I', 2), ('D', 0)]
        -> change command will be SET:DEV:DB6.T1:TEMP:LOOP:P:5:I:2:D:0
        """
        # TODO: if the need arises: allow convert and or tolerance to be a list
        adr = self._complete_adr(adr)
        params = [f'{k}:{convert(v)}' for k, v in values]
        cmd = f"SET:{adr}:{':'.join(params)}"
        givenkeys = tuple(v[0] for v in values)
        for _ in range(max(1, n_retry)):  # try n_retry times or until readback result matches
            reply = self.communicate(cmd)
            head = f'STAT:SET:{adr}:'
            try:
                assert reply.startswith(head)
                replyiter = iter(reply[len(head):].split(':'))
                # reshuffle reply=(k1, r1, v1, k2, r2, v1) --> keys = (k1, k2), result = (r1, r2), valid = (v1, v2)
                keys, result, valid = zip(*zip(replyiter, replyiter, replyiter))
                assert keys == givenkeys
                assert any(v == 'VALID' for v in valid)
                result = tuple(convert(r) for r in result)
            except (AssertionError, AttributeError, ValueError) as e:
                time.sleep(0.1)  # in case of missed replies this might help to skip garbage
                raise HardwareError(f'invalid reply {reply!r} to cmd {cmd!r}') from e
            if n_retry == 0:
                return [v for _, v in values]
            if lazy:
                debug = [reply]
                readback = [v for _, v in values]
            else:
                debug = []
                readback = list(self.multiquery(adr, givenkeys, convert, debug))
            failed = False
            for i, ((k, v), r, b) in enumerate(zip(values, result, readback)):
                if convert is as_float:
                    tol = max(abs(r) * 1e-3, abs(b) * 1e-3, tolerance)
                    if abs(b - v) > tol or abs(r - v) > tol:
                        readback[i] = None
                        failed = True
                elif b != v or r != v:
                    readback[i] = None
                    failed = True
            if not failed:
                return readback
        self.log.warning('sent: %s', cmd)
        self.log.warning('got: %s', debug[0])
        return tuple(v[1] if b is None else b for b, v in zip(readback, values))

    def query(self, adr, convert=as_float):
        """query a single parameter

        'adr' and 'convert' as in multiquery
        """
        adr, _, name = adr.rpartition(':')
        return self.multiquery(adr, [name], convert)[0]

    def change(self, adr, value, convert=as_float, tolerance=0, n_retry=3, lazy=False):
        adr, _, name = adr.rpartition(':')
        return self.multichange(adr, [(name, value)], convert, tolerance, n_retry, lazy)[0]


class TemperatureSensor(MercuryChannel, Readable):
    kind = 'TEMP'
    value = Parameter(unit='K')
    raw = Parameter('raw value', FloatRange(unit='Ohm'))

    def read_value(self):
        return self.query('DEV::TEMP:SIG:TEMP')

    def read_raw(self):
        return self.query('DEV::TEMP:SIG:RES')


class HasInput(HasControlledBy, MercuryChannel):
    pass


class Loop(HasOutputModule, MercuryChannel, Drivable):
    """common base class for loops"""
    output_module = Attached(HasInput, mandatory=False)
    ctrlpars = Parameter(
        'pid (proportional band, integral time, differential time',
        StructOf(p=FloatRange(0, unit='$'), i=FloatRange(0, unit='min'), d=FloatRange(0, unit='min')),
        readonly=False,
    )
    enable_pid_table = Parameter('', BoolType(), readonly=False)

    def set_output(self, active, source=None):
        if active:
            self.activate_control()
        else:
            self.deactivate_control(source)

    def set_target(self, target):
        if not self.control_active:
            self.activate_control()
        self.target = target

    def read_enable_pid_table(self):
        return self.query(f'DEV::{self.kinds[0]}:LOOP:PIDT', off_on)

    def write_enable_pid_table(self, value):
        return self.change(f'DEV::{self.kinds[0]}:LOOP:PIDT', value, off_on)

    def read_ctrlpars(self):
        # read all in one go, in order to reduce comm. traffic
        pid = self.multiquery(f'DEV::{self.kinds[0]}:LOOP', ('P', 'I', 'D'))
        return {k: float(v) for k, v in zip('pid', pid)}

    def write_ctrlpars(self, value):
        pid = self.multichange(f'DEV::{self.kinds[0]}:LOOP', [(k, value[k.lower()]) for k in 'PID'])
        return {k.lower(): v for k, v in zip('PID', pid)}

    def read_status(self):
        return IDLE, ''

    @Command()
    def control_off(self):
        """switch control off"""
        # remark: this is needed in frappy_psi.trition.TemperatureLoop, as the heater
        # output is not available there. We define it here as a convenience for the user.
        self.write_control_active(False)


class ConvLoop(HasConvergence, Loop):
    def deactivate_control(self, source=None):
        if self.control_active:
            super().deactivate_control(source)
            self.convergence_state.start(self.inactive_state)
            if self.pollInfo:
                self.pollInfo.trigger(True)

    def inactive_state(self, state):
        self.convergence_state.status = IDLE, 'control inactive'
        return Finish


class HeaterOutput(HasInput, Writable):
    """heater output

    Remark:
    The hardware calculates the power from the voltage and the configured
    resistivity. As the measured heater current is available, the resistivity
    will be adjusted automatically, when true_power is True.
    """
    kind = 'HTR'
    value = Parameter('heater output', FloatRange(unit='W'), readonly=False)
    status = Parameter(update_unchanged='never')
    target = Parameter('heater output', FloatRange(0, 100, unit='$'), readonly=False, update_unchanged='never')
    resistivity = Parameter('heater resistivity', FloatRange(10, 1000, unit='Ohm'),
                            readonly=False)
    true_power = Parameter('calculate power from measured current', BoolType(), readonly=False, default=True)
    limit = Parameter('heater output limit', FloatRange(0, 1000, unit='W'), readonly=False)
    volt = 0.0  # target voltage
    _last_target = None
    _volt_target = None

    def read_limit(self):
        return self.query('DEV::HTR:VLIM') ** 2 / self.resistivity

    def write_limit(self, value):
        result = self.change('DEV::HTR:VLIM', math.sqrt(value * self.resistivity))
        return result ** 2 / self.resistivity

    def read_resistivity(self):
        if self.true_power:
            return self.resistivity
        return max(10.0, self.query('DEV::HTR:RES'))

    def write_resistivity(self, value):
        self.resistivity = self.change('DEV::HTR:RES', max(10.0, value))
        if self._last_target is not None:
            if not self.true_power:
                self._volt_target = math.sqrt(self._last_target * self.resistivity)
            self.change('DEV::HTR:SIG:VOLT', self._volt_target, tolerance=2e-4)
        return self.resistivity

    def read_status(self):
        return IDLE, ('true power' if self.true_power else 'fixed resistivity')

    def read_value(self):
        if self._last_target is None:  # on init
            self.read_target()
        if not self.true_power:
            volt = self.query('DEV::HTR:SIG:VOLT')
            return volt ** 2 / max(10.0, self.resistivity)
        volt, current = self.multiquery('DEV::HTR:SIG', ('VOLT', 'CURR'))
        if volt > 0 and current > 0.0001 and self._last_target:
            res = volt / current
            tol = res * max(max(0.0003, abs(volt - self._volt_target)) / volt, 0.0001 / current, 0.0001)
            if abs(res - self.resistivity) > tol + 0.07 and self._last_target:
                self.write_resistivity(round(res, 1))
                if self.controlled_by == 0:
                    self._volt_target = math.sqrt(self._last_target * self.resistivity)
                    self.change('DEV::HTR:SIG:VOLT', self._volt_target, tolerance=2e-4)
        return volt * current

    def read_target(self):
        if self.controlled_by != 0 or self._last_target is not None:
            # read back only when not yet initialized
            return self.target
        self._volt_target = self.query('DEV::HTR:SIG:VOLT')
        self.resistivity = max(10.0, self.query('DEV::HTR:RES'))
        self._last_target = self._volt_target ** 2 / max(10.0, self.resistivity)
        return self._last_target

    def set_target(self, target):
        """set the target without switching to manual

        might be used by a software loop
        """
        self._volt_target = math.sqrt(target * self.resistivity)
        self.change('DEV::HTR:SIG:VOLT', self._volt_target, tolerance=2e-4)
        self._last_target = target
        return target

    def write_target(self, value):
        self.self_controlled()
        return self.set_target(value)


class TemperatureLoop(TemperatureSensor, ConvLoop):
    kind = 'TEMP'
    output_module = Attached(HasInput, mandatory=False)
    ramp = Parameter('ramp rate', FloatRange(0, unit='$/min'), readonly=False)
    enable_ramp = Parameter('enable ramp rate', BoolType(), readonly=False)
    setpoint = Parameter('working setpoint (differs from target when ramping)', FloatRange(0, unit='$'))
    status = Parameter(datatype=StatusType(Drivable, 'RAMPING'))  # add ramping status
    tolerance = Parameter(default=0.1)
    _last_setpoint_change = None
    __status = IDLE, ''
    __ramping = False
    # overridden in subclass frappy_psi.triton.TemperatureLoop
    ENABLE = 'TEMP:LOOP:ENAB'
    ENABLE_RAMP = 'TEMP:LOOP:RENA'
    RAMP_RATE = 'TEMP:LOOP:RSET'

    def doPoll(self):
        super().doPoll()
        self.read_setpoint()

    def set_control_active(self, active):
        super().set_control_active(active)
        self.change(f'DEV::{self.ENABLE}', active, off_on)

    def initialReads(self):
        # initialize control active from HW
        active = self.query(f'DEV::{self.ENABLE}', off_on)
        super().set_output(active, 'HW')

    @nopoll  # polled by read_setpoint
    def read_target(self):
        if self.read_enable_ramp():
            return self.target
        self.setpoint = self.query('DEV::TEMP:LOOP:TSET')
        return self.setpoint

    def read_setpoint(self):
        setpoint = self.query('DEV::TEMP:LOOP:TSET')
        if self.enable_ramp:
            if setpoint == self.target:
                self.__ramping = False
            elif setpoint == self.setpoint:
                # update target when working setpoint does no longer change
                if self._last_setpoint_change is not None:
                    unchanged_since = time.time() - self._last_setpoint_change
                    if unchanged_since > max(12.0, 0.06 / max(1e-4, self.ramp)):
                        self.__ramping = False
                        self.target = self.setpoint
                return setpoint
            self._last_setpoint_change = time.time()
        else:
            self.__ramping = False
            self.target = setpoint
        return setpoint

    def set_target(self, target):
        self.change(f'DEV::{self.ENABLE}', True, off_on)
        super().set_target(target)

    def deactivate_control(self, source=None):
        if self.__ramping:
            self.__ramping = False
            # stop ramping setpoint
            self.change('DEV::TEMP:LOOP:TSET', self.read_setpoint(), lazy=True)
        super().deactivate_control(source)

    def ramping_state(self, state):
        self.read_setpoint()
        if self.__ramping:
            return Retry
        return self.convergence_approach

    def write_target(self, value):
        target = self.change('DEV::TEMP:LOOP:TSET', value, lazy=True)
        if self.enable_ramp:
            self._last_setpoint_change = None
            self.__ramping = True
            self.set_target(value)
            self.convergence_state.status = RAMPING, 'ramping'
            self.read_status()
            self.convergence_state.start(self.ramping_state)
        else:
            self.set_target(target)
            self.convergence_start()
        self.read_status()
        return self.target

    def read_enable_ramp(self):
        return self.query(f'DEV::{self.ENABLE_RAMP}', off_on)

    def write_enable_ramp(self, value):
        if self.enable_ramp < value:  # ramp_enable was off: start from current value
            self.change('DEV::TEMP:LOOP:TSET', self.value, lazy=True)
        result = self.change(f'DEV::{self.ENABLE_RAMP}', value, off_on)
        if self.isDriving() and value != self.enable_ramp:
            self.enable_ramp = value
            self.write_target(self.target)
        return result

    def read_ramp(self):
        result = self.query(f'DEV::{self.RAMP_RATE}')
        return min(9e99, result)

    def write_ramp(self, value):
        # use 0 or a very big value for switching off ramp
        if not value:
            self.write_enable_ramp(0)
            return 0
        if value >= 9e99:
            self.change(f'DEV::{self.RAMP_RATE}', 'inf', as_string)
            self.write_enable_ramp(0)
            return 9e99
        self.write_enable_ramp(1)
        return self.change(f'DEV::{self.RAMP_RATE}', max(1e-4, value))


class PressureSensor(MercuryChannel, Readable):
    kind = 'PRES'
    value = Parameter(unit='mbar')

    def read_value(self):
        return self.query('DEV::PRES:SIG:PRES')


class ValvePos(HasInput, Drivable):
    kind = 'PRES,AUX'
    value = Parameter('value pos', FloatRange(unit='%'), readonly=False)
    target = Parameter('valve pos target', FloatRange(0, 100, unit='$'), readonly=False)

    def doPoll(self):
        self.read_status()

    def read_value(self):
        return self.query(f'DEV:{self.slots["AUX"]}:AUX:SIG:PERC')

    def read_status(self):
        self.read_value()
        if abs(self.value - self.target) < 0.01:
            return 'IDLE', 'at target'
        return 'BUSY', 'moving'

    def read_target(self):
        return self.query('DEV::PRES:LOOP:FSET')

    def write_target(self, value):
        self.self_controlled()
        return self.change('DEV::PRES:LOOP:FSET', value)


class PressureLoop(PressureSensor, HasControlledBy, ConvLoop):
    kind = 'PRES'
    output_module = Attached(ValvePos, mandatory=False)
    tolerance = Parameter(default=0.1)

    def set_control_active(self, active):
        super().set_control_active(active)
        if not active:
            self.self_controlled()  # switches off auto flow
        return self.change('DEV::PRES:LOOP:FAUT', active, off_on)

    def initialReads(self):
        # initialize control active from HW
        active = self.query('DEV::PRES:LOOP:FAUT', off_on)
        super().set_output(active, 'HW')

    def read_target(self):
        return self.query('DEV::PRES:LOOP:PRST')

    def set_target(self, target):
        """set the target without switching to manual

        might be used by a software loop
        """
        self.change('DEV::PRES:LOOP:PRST', target)
        super().set_target(target)

    def write_target(self, value):
        self.self_controlled()
        self.set_target(value)
        return value


class HasAutoFlow:
    needle_valve = Attached(PressureLoop, mandatory=False)
    auto_flow = Parameter('enable auto flow', BoolType(), readonly=False, default=0)
    flowpars = Parameter('Tdif(min, max), FlowSet(min, max)',
                         TupleOf(TupleOf(FloatRange(unit='K'), FloatRange(unit='K')),
                                 TupleOf(FloatRange(unit='mbar'), FloatRange(unit='mbar'))),
                         readonly=False, default=((1, 5), (4, 20)))

    def read_value(self):
        value = super().read_value()
        if self.auto_flow:
            (dmin, dmax), (fmin, fmax) = self.flowpars
            flowset = min(dmax - dmin, max(0, value - self.target - dmin)) / (dmax - dmin) * (fmax - fmin) + fmin
            self.needle_valve.set_target(flowset)
        return value

    def initModule(self):
        super().initModule()
        if self.needle_valve:
            self.needle_valve.register_input(self.name, self.auto_flow_off)

    def write_auto_flow(self, value):
        if self.needle_valve:
            if value:
                self.needle_valve.controlled_by = self.name
            else:
                if self.needle_valve.control_active:
                    self.needle_valve.set_target(self.flowpars[1][0])  # flow min
                if self.needle_valve.controlled_by != SELF:
                    self.needle_valve.controlled_by = SELF
        return value

    def auto_flow_off(self, source=None):
        if self.auto_flow:
            self.log.warning(f'switched auto flow off by {source or self.name}')
            self.write_auto_flow(False)


class TemperatureAutoFlow(HasAutoFlow, TemperatureLoop):
    pass


class HeLevel(MercuryChannel, Readable):
    """He level meter channel

    The Mercury system does not support automatic switching between fast
    (when filling) and slow (when consuming). We have to handle this by software.
    """
    kind = 'LVL'
    value = Parameter(unit='%')
    sample_rate = Parameter('_', EnumType(slow=0, fast=1), readonly=False)
    hysteresis = Parameter('hysteresis for detection of increase', FloatRange(0, 100, unit='%'),
                           default=5, readonly=False)
    fast_timeout = Parameter('time to switch to slow after last increase', FloatRange(0, unit='sec'),
                             default=300, readonly=False)
    _min_level = 999
    _max_level = -999
    _last_increase = None  # None when in slow mode, last increase time in fast mode

    def check_rate(self, sample_rate):
        """check changes in rate

        :param sample_rate:  (int or enum) 0: slow, 1: fast
        initialize affected attributes
        """
        if sample_rate != 0:  # fast
            if not self._last_increase:
                self._last_increase = time.time()
                self._max_level = -999
        elif self._last_increase:
            self._last_increase = None
            self._min_level = 999
        return sample_rate

    def read_sample_rate(self):
        return self.check_rate(self.query('DEV::LVL:HEL:PULS:SLOW', fast_slow))

    def write_sample_rate(self, value):
        self.check_rate(value)
        return self.change('DEV::LVL:HEL:PULS:SLOW', value, fast_slow)

    def read_value(self):
        level = self.query('DEV::LVL:SIG:HEL:LEV')
        # handle automatic switching depending on increase
        now = time.time()
        if self._last_increase:  # fast mode
            if level > self._max_level:
                self._last_increase = now
                self._max_level = level
            elif now > self._last_increase + self.fast_timeout:
                # no increase since fast timeout -> slow
                self.write_sample_rate(self.sample_rate.slow)
        else:
            if level > self._min_level + self.hysteresis:
                # substantial increase -> fast
                self.write_sample_rate(self.sample_rate.fast)
            else:
                self._min_level = min(self._min_level, level)
        return level


class N2Level(MercuryChannel, Readable):
    kind = 'LVL'
    value = Parameter(unit='%')

    def read_value(self):
        return self.query('DEV::LVL:SIG:NIT:LEV')
