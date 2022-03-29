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

from secop.core import Drivable, HasIO, Writable, \
    Parameter, Property, Readable, StringIO, Attached, Done, IDLE, nopoll
from secop.datatypes import EnumType, FloatRange, StringType, StructOf, BoolType
from secop.errors import HardwareError
from secop_psi.convergence import HasConvergence
from secop.lib.enum import Enum


VALUE_UNIT = re.compile(r'(.*\d|inf)([A-Za-z/%]*)$')
SELF = 0


def as_float(value):
    if isinstance(value, str):
        return float(VALUE_UNIT.match(value).group(1))
    return '%g' % value


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
    identification = [('*IDN?', r'IDN:OXFORD INSTRUMENTS:MERCURY*')]


class MercuryChannel(HasIO):
    slot = Property('''slot uids
    
                    example: DB6.T1,DB1.H1
                    slot ids for sensor (and control output)''',
                    StringType())
    channel_name = Parameter('mercury nick name', StringType(), default='')
    channel_type = ''  #: channel type(s) for sensor (and control) e.g. TEMP,HTR or PRES,AUX

    def _complete_adr(self, adr):
        """complete address from channel_type and slot"""
        head, sep, tail = adr.partition(':')
        for i, (channel_type, slot) in enumerate(zip(self.channel_type.split(','), self.slot.split(','))):
            if head == str(i):
                return 'DEV:%s:%s%s%s' % (slot, channel_type, sep, tail)
            if head == channel_type:
                return 'DEV:%s:%s%s%s' % (slot, head, sep, tail)
        return adr

    def multiquery(self, adr, names=(), convert=as_float):
        """get parameter(s) in mercury syntax

        :param adr: the 'address part' of the SCPI command
                    the DEV:<slot> is added automatically, when adr starts with the channel type
                    in addition, when adr starts with '0:' or '1:', channel type and slot are added
        :param names: the SCPI names of the parameter(s), for example ['TEMP']
        :param convert: a converter function (converts replied string to value)
        :return:  the values as tuple

        Example:
            adr='AUX:SIG'
            names = ('PERC',)
            self.channel_type='PRES,AUX'    # adr starts with 'AUX'
            self.slot='DB5.P1,DB3.G1'       # -> take second slot
        -> query command will be READ:DEV:DB3.G1:PRES:SIG:PERC
        """
        adr = self._complete_adr(adr)
        cmd = 'READ:%s:%s' % (adr, ':'.join(names))
        reply = self.communicate(cmd)
        head = 'STAT:%s:' % adr
        try:
            assert reply.startswith(head)
            replyiter = iter(reply[len(head):].split(':'))
            keys, result = zip(*zip(replyiter, replyiter))
            assert keys == tuple(names)
            return tuple(convert(r) for r in result)
        except (AssertionError, AttributeError, ValueError):
            raise HardwareError('invalid reply %r to cmd %r' % (reply, cmd)) from None

    def multichange(self, adr, values, convert=as_float):
        """set parameter(s) in mercury syntax

        :param adr: as in see multiquery method
        :param values: [(name1, value1), (name2, value2) ...]
        :param convert: a converter function (converts given value to string and replied string to value)
        :return:  the values as tuple

        Example:
            adr='0:LOOP'
            values = [('P', 5), ('I', 2), ('D', 0)]
            self.channel_type='TEMP,HTR'   # adr starts with 0: take TEMP
            self.slot='DB6.T1,DB1.H1'      # and take first slot
        -> change command will be SET:DEV:DB6.T1:TEMP:LOOP:P:5:I:2:D:0
        """
        adr = self._complete_adr(adr)
        params = ['%s:%s' % (k, convert(v)) for k, v in values]
        cmd = 'SET:%s:%s' % (adr, ':'.join(params))
        reply = self.communicate(cmd)
        head = 'STAT:SET:%s:' % adr

        try:
            assert reply.startswith(head)
            replyiter = iter(reply[len(head):].split(':'))
            keys, result, valid = zip(*zip(replyiter, replyiter, replyiter))
            assert keys == tuple(k for k, _ in values)
            assert any(v == 'VALID' for v in valid)
            return tuple(convert(r) for r in result)
        except (AssertionError, AttributeError, ValueError) as e:
            raise HardwareError('invalid reply %r to cmd %r' % (reply, cmd)) from e

    def query(self, adr, convert=as_float):
        """query a single parameter

        'adr' and 'convert' areg
        """
        adr, _, name = adr.rpartition(':')
        return self.multiquery(adr, [name], convert)[0]

    def change(self, adr, value, convert=as_float):
        adr, _, name = adr.rpartition(':')
        return self.multichange(adr, [(name, value)], convert)[0]

    def read_channel_name(self):
        if self.channel_name:
            return Done  # channel name will not change
        return self.query('0:NICK', as_string)


class TemperatureSensor(MercuryChannel, Readable):
    channel_type = 'TEMP'
    value = Parameter(unit='K')
    raw = Parameter('raw value', FloatRange(unit='Ohm'))

    def read_value(self):
        return self.query('TEMP:SIG:TEMP')

    def read_raw(self):
        return self.query('TEMP:SIG:RES')


class HasInput(MercuryChannel):
    controlled_by = Parameter('source of target value', EnumType(members={'self': SELF}), default=0)
    target = Parameter(readonly=False)
    input_modules = ()

    def add_input(self, modobj):
        if not self.input_modules:
            self.input_modules = []
        self.input_modules.append(modobj)
        prev_enum = self.parameters['controlled_by'].datatype._enum
        # add enum member, using autoincrement feature of Enum
        self.parameters['controlled_by'].datatype = EnumType(Enum(prev_enum, **{modobj.name: None}))

    def write_controlled_by(self, value):
        if self.controlled_by == value:
            return Done
        self.controlled_by = value
        if value == SELF:
            self.log.warning('switch to manual mode')
            for input_module in self.input_modules:
                if input_module.control_active:
                    input_module.write_control_active(False)
        return Done


class Loop(HasConvergence, MercuryChannel, Drivable):
    """common base class for loops"""
    control_active = Parameter('control mode', BoolType())
    output_module = Attached(HasInput, mandatory=False)
    ctrlpars = Parameter(
        'pid (proportional band, integral time, differential time',
        StructOf(p=FloatRange(0, unit='$'), i=FloatRange(0, unit='min'), d=FloatRange(0, unit='min')),
        readonly=False,
    )
    enable_pid_table = Parameter('', BoolType(), readonly=False)

    def initModule(self):
        super().initModule()
        if self.output_module:
            self.output_module.add_input(self)

    def set_output(self, active):
        if active:
            if self.output_module and self.output_module.controlled_by != self.name:
                self.output_module.controlled_by = self.name
        else:
            if self.output_module and self.output_module.controlled_by != SELF:
                self.output_module.write_controlled_by(SELF)
            status = IDLE, 'control inactive'
            if self.status != status:
                self.status = status

    def set_target(self, target):
        if self.control_active:
            self.set_output(True)
        else:
            self.log.warning('switch loop control on')
            self.write_control_active(True)
        self.target = target
        self.start_state()

    def read_enable_pid_table(self):
        return self.query('0:LOOP:PIDT', off_on)

    def write_enable_pid_table(self, value):
        return self.change('0:LOOP:PIDT', value, off_on)

    def read_ctrlpars(self):
        # read all in one go, in order to reduce comm. traffic
        pid = self.multiquery('0:LOOP', ('P', 'I', 'D'))
        return {k: float(v) for k, v in zip('pid', pid)}

    def write_ctrlpars(self, value):
        pid = self.multichange('0:LOOP', [(k, value[k.lower()]) for k in 'PID'])
        return {k.lower(): v for k, v in zip('PID', pid)}


class HeaterOutput(HasInput, MercuryChannel, Writable):
    """heater output

    Remark:
    The hardware calculates the power from the voltage and the configured
    resistivity. As the measured heater current is available, the resistivity
    will be adjusted automatically, when true_power is True.
    """
    channel_type = 'HTR'
    value = Parameter('heater output', FloatRange(unit='W'), readonly=False)
    target = Parameter('heater output', FloatRange(0, 100, unit='$'), readonly=False)
    resistivity = Parameter('heater resistivity', FloatRange(10, 1000, unit='Ohm'),
                            readonly=False)
    true_power = Parameter('calculate power from measured current', BoolType(), readonly=False, default=True)
    limit = Parameter('heater output limit', FloatRange(0, 1000, unit='W'), readonly=False)
    volt = 0.0  # target voltage
    _last_target = None
    _volt_target = None

    def read_limit(self):
        return self.query('HTR:VLIM') ** 2 / self.resistivity

    def write_limit(self, value):
        result = self.change('HTR:VLIM', math.sqrt(value * self.resistivity))
        return result ** 2 / self.resistivity

    def read_resistivity(self):
        if self.true_power:
            return self.resistivity
        return max(10, self.query('HTR:RES'))

    def write_resistivity(self, value):
        self.resistivity = self.change('HTR:RES', max(10, value))
        if self._last_target is not None:
            if not self.true_power:
                self._volt_target = math.sqrt(self._last_target * self.resistivity)
            self.change('HTR:SIG:VOLT', self._volt_target)
        return Done

    def read_status(self):
        status = IDLE, ('true power' if self.true_power else 'fixed resistivity')
        if self.status != status:
            return status
        return Done

    def read_value(self):
        if self._last_target is None:  # on init
            self.read_target()
        if not self.true_power:
            volt = self.query('HTR:SIG:VOLT')
            return volt ** 2 / max(10, self.resistivity)
        volt, current = self.multiquery('HTR:SIG', ('VOLT', 'CURR'))
        if volt > 0 and current > 0.0001 and self._last_target:
            res = volt / current
            tol = res * max(max(0.0003, abs(volt - self._volt_target)) / volt, 0.0001 / current, 0.0001)
            if abs(res - self.resistivity) > tol + 0.07 and self._last_target:
                self.write_resistivity(round(res, 1))
                if self.controlled_by == 0:
                    self._volt_target = math.sqrt(self._last_target * self.resistivity)
                    self.change('HTR:SIG:VOLT', self._volt_target)
        return volt * current

    def read_target(self):
        if self.controlled_by != 0 and self.target:
            return 0
        if self._last_target is not None:
            return Done
        self._volt_target = self.query('HTR:SIG:VOLT')
        self.resistivity = max(10, self.query('HTR:RES'))
        self._last_target = self._volt_target ** 2 / max(10, self.resistivity)
        return self._last_target

    def set_target(self, value):
        """set the target without switching to manual

        might be used by a software loop
        """
        self._volt_target = math.sqrt(value * self.resistivity)
        self.change('HTR:SIG:VOLT', self._volt_target)
        self._last_target = value
        return value

    def write_target(self, value):
        self.write_controlled_by(SELF)
        return self.set_target(value)


class TemperatureLoop(TemperatureSensor, Loop, Drivable):
    channel_type = 'TEMP,HTR'
    output_module = Attached(HeaterOutput, mandatory=False)
    ramp = Parameter('ramp rate', FloatRange(0, unit='K/min'), readonly=False)
    enable_ramp = Parameter('enable ramp rate', BoolType(), readonly=False)
    setpoint = Parameter('working setpoint (differs from target when ramping)', FloatRange(0, unit='$'))
    auto_flow = Parameter('enable auto flow', BoolType(), readonly=False)
    _last_setpoint_change = None

    def doPoll(self):
        super().doPoll()
        self.read_setpoint()

    def read_control_active(self):
        active = self.query('TEMP:LOOP:ENAB', off_on)
        self.set_output(active)
        return active

    def write_control_active(self, value):
        self.set_output(value)
        return self.change('TEMP:LOOP:ENAB', value, off_on)

    @nopoll  # polled by read_setpoint
    def read_target(self):
        if self.read_enable_ramp():
            return self.target
        self.setpoint = self.query('TEMP:LOOP:TSET')
        return self.setpoint

    def read_setpoint(self):
        setpoint = self.query('TEMP:LOOP:TSET')
        if self.enable_ramp:
            if setpoint == self.setpoint:
                # update target when working setpoint does no longer change
                if setpoint != self.target and self._last_setpoint_change is not None:
                    unchanged_since = time.time() - self._last_setpoint_change
                    if unchanged_since > max(12.0, 0.06 / max(1e-4, self.ramp)):
                        self.target = self.setpoint
                return setpoint
            self._last_setpoint_change = time.time()
        else:
            self.target = setpoint
        return setpoint

    def write_target(self, value):
        target = self.change('TEMP:LOOP:TSET', value)
        if self.enable_ramp:
            self._last_setpoint_change = None
            self.set_target(value)
        else:
            self.set_target(target)
        return Done

    def read_enable_ramp(self):
        return self.query('TEMP:LOOP:RENA', off_on)

    def write_enable_ramp(self, value):
        return self.change('TEMP:LOOP:RENA', value, off_on)

    def read_auto_flow(self):
        return self.query('TEMP:LOOP:FAUT', off_on)

    def write_auto_flow(self, value):
        return self.change('TEMP:LOOP:FAUT', value, off_on)

    def read_ramp(self):
        result = self.query('TEMP:LOOP:RSET')
        return min(9e99, result)

    def write_ramp(self, value):
        # use 0 or a very big value for switching off ramp
        if not value:
            self.write_enable_ramp(0)
            return 0
        if value >= 9e99:
            self.change('TEMP:LOOP:RSET', 'inf', as_string)
            self.write_enable_ramp(0)
            return 9e99
        self.write_enable_ramp(1)
        return self.change('TEMP:LOOP:RSET', max(1e-4, value))


class PressureSensor(MercuryChannel, Readable):
    channel_type = 'PRES'
    value = Parameter(unit='mbar')

    def read_value(self):
        return self.query('PRES:SIG:PRES')


class ValvePos(HasInput, MercuryChannel, Drivable):
    channel_type = 'PRES,AUX'
    value = Parameter('value pos', FloatRange(unit='%'), readonly=False)
    target = Parameter('valve pos target', FloatRange(0, 100, unit='$'), readonly=False)

    def doPoll(self):
        self.read_status()

    def read_value(self):
        return self.query('AUX:SIG:PERC')

    def read_status(self):
        self.read_value()
        if abs(self.value - self.target) < 0.01:
            return 'IDLE', 'at target'
        return 'BUSY', 'moving'

    def read_target(self):
        return self.query('PRES:LOOP:FSET')

    def write_target(self, value):
        self.write_controlled_by(SELF)
        return self.change('PRES:LOOP:FSET', value)


class PressureLoop(PressureSensor, Loop, Drivable):
    channel_type = 'PRES,AUX'
    output_module = Attached(ValvePos, mandatory=False)

    def read_control_active(self):
        active = self.query('PRES:LOOP:FAUT', off_on)
        self.set_output(active)
        return active

    def write_control_active(self, value):
        self.set_output(value)
        return self.change('PRES:LOOP:FAUT', value, off_on)

    def read_target(self):
        return self.query('PRES:LOOP:PRST')

    def write_target(self, value):
        target = self.change('PRES:LOOP:PRST', value)
        self.set_target(target)
        return Done


class HeLevel(MercuryChannel, Readable):
    """He level meter channel

    The Mercury system does not support automatic switching between fast
    (when filling) and slow (when consuming). We have to handle this by software.
    """
    channel_type = 'LVL'
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
        return self.check_rate(self.query('LVL:HEL:PULS:SLOW', fast_slow))

    def write_sample_rate(self, value):
        self.check_rate(value)
        return self.change('LVL:HEL:PULS:SLOW', value, fast_slow)

    def read_value(self):
        level = self.query('LVL:SIG:HEL:LEV')
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
    channel_type = 'LVL'

    def read_value(self):
        return self.query('LVL:SIG:NIT:LEV')


# TODO: magnet power supply
