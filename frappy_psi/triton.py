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
"""oxford instruments triton (kelvinoxjt dil)"""

from math import sqrt
from frappy.core import Writable, Parameter, Readable, Drivable, IDLE, WARN, BUSY, ERROR, \
    Done, Property
from frappy.datatypes import EnumType, FloatRange, StringType
from frappy.lib.enum import Enum
from frappy_psi.mercury import MercuryChannel, Mapped, off_on, HasInput
from frappy_psi import mercury

actions = Enum(none=0, condense=1, circulate=2, collect=3)
open_close = Mapped(CLOSE=0, OPEN=1)
actions_map = Mapped(STOP=actions.none, COND=actions.condense, COLL=actions.collect)
actions_map.mapping['NONE'] = actions.none  # when writing, STOP is used instead of NONE


class Action(MercuryChannel, Writable):
    kind = 'ACTN'
    cooldown_channel = Property('cool down channel', StringType(), 'T5')
    mix_channel = Property('mix channel', StringType(), 'T5')
    value = Parameter('running action', EnumType(actions))
    target = Parameter('action to do', EnumType(none=0, condense=1, collect=3), readonly=False)
    _target = 0

    def read_value(self):
        return self.query('SYS:DR:ACTN', actions_map)

    def read_target(self):
        return self._target

    def write_target(self, value):
        self._target = value
        self.change('SYS:DR:CHAN:COOL', self.cooldown_channel, str)
        # self.change('SYS:DR:CHAN:MC', self.mix_channel, str)
        # self.change('DEV:T5:TEMP:MEAS:ENAB', 'ON', str)
        return self.change('SYS:DR:ACTN', value, actions_map)

    # actions:
    # NONE (no action)
    # COND (condense mixture)
    # COLL (collect mixture)
    # STOP (go to NONE)
    #
    # not yet used (would need a subclass of Action):
    # CLDN (cool down)
    # PCL (precool automation)
    # PCOND (pause pre-cool (not condense?) automation)
    # RCOND (resume pre-cool (not condense?) automation)
    # WARM (warm-up)
    # EPCL (empty pre-cool automation)


class Valve(MercuryChannel, Drivable):
    kind = 'VALV'
    value = Parameter('valve state', EnumType(closed=0, opened=1))
    target = Parameter('valve target', EnumType(close=0, open=1))

    _try_count = None

    def doPoll(self):
        self.read_status()

    def read_value(self):
        return self.query('DEV::VALV:SIG:STATE', open_close)

    def read_status(self):
        pos = self.read_value()
        if self._try_count is None:  # not switching
            return IDLE, ''
        if pos == self.target:
            # success
            if self._try_count:
                # make sure last sent command was not opposite
                self.change('DEV::VALV:SIG:STATE', self.target, open_close)
            self._try_count = None
            self.setFastPoll(False)
            return IDLE, ''
        self._try_count += 1
        if self._try_count % 4 == 0:
            # send to opposite position in order to unblock
            self.change('DEV::VALV:SIG:STATE', pos, open_close)
            return BUSY, 'unblock'
        if self._try_count > 9:
            # make sure system does not toggle later
            self.change('DEV::VALV:SIG:STATE', pos, open_close)
            return ERROR, 'can not %s valve' % self.target.name
        self.change('DEV::VALV:SIG:STATE', self.target, open_close)
        return BUSY, 'waiting'

    def write_target(self, value):
        if value != self.read_value():
            self._try_count = 0
            self.setFastPoll(True, 0.25)
            self.change('DEV::VALV:SIG:STATE', value, open_close)
            self.status = BUSY, self.target.name
        return value


class Pump(MercuryChannel, Writable):
    kind = 'PUMP'
    value = Parameter('pump state', EnumType(off=0, on=1))
    target = Parameter('pump target', EnumType(off=0, on=1))

    def read_value(self):
        return self.query('DEV::PUMP:SIG:STATE', off_on)

    def write_target(self, value):
        return self.change('DEV::PUMP:SIG:STATE', value, off_on)

    def read_status(self):
        return IDLE, ''


class TurboPump(Pump):
    power = Parameter('pump power', FloatRange(unit='W'))
    freq = Parameter('pump frequency', FloatRange(unit='Hz'))
    powerstage_temp = Parameter('temperature of power stage', FloatRange(unit='K'))
    motor_temp = Parameter('temperature of motor', FloatRange(unit='K'))
    bearing_temp = Parameter('temperature of bearing', FloatRange(unit='K'))
    pumpbase_temp = Parameter('temperature of pump base', FloatRange(unit='K'))
    electronics_temp = Parameter('temperature of electronics', FloatRange(unit='K'))

    def read_status(self):
        status = self.query('DEV::PUMP:STATUS', str)
        if status == 'OK':
            return IDLE, ''
        return WARN, status

    def read_power(self):
        return self.query('DEV::PUMP:SIG:POWR')

    def read_freq(self):
        return self.query('DEV::PUMP:SIG:SPD')

    def read_powerstage_temp(self):
        return self.query('DEV::PUMP:SIG:PST')

    def read_motor_temp(self):
        return self.query('DEV::PUMP:SIG:MT')

    def read_bearing_temp(self):
        return self.query('DEV::PUMP:SIG:BT')

    def read_pumpbase_temp(self):
        return self.query('DEV::PUMP:SIG:PBT')

    def read_electronics_temp(self):
        return self.query('DEV::PUMP:SIG:ET')


# class PulseTubeCompressor(MercuryChannel, Writable):
#     kind = 'PTC'
#     value = Parameter('compressor state', EnumType(closed=0, opened=1))
#     target = Parameter('compressor target', EnumType(close=0, open=1))
#     water_in_temp = Parameter('temperature of water inlet', FloatRange(unit='K'))
#     water_out_temp = Parameter('temperature of water outlet', FloatRange(unit='K'))
#     helium_temp = Parameter('temperature of helium', FloatRange(unit='K'))
#     helium_low_pressure = Parameter('helium pressure (low side)', FloatRange(unit='mbar'))
#     helium_high_pressure = Parameter('helium pressure (high side)', FloatRange(unit='mbar'))
#     motor_current = Parameter('motor current', FloatRange(unit='A'))
#
#     def read_value(self):
#         return self.query('DEV::PTC:SIG:STATE', off_on)
#
#     def write_target(self, value):
#         return self.change('DEV::PTC:SIG:STATE', value, off_on)
#
#     def read_status(self):
#         # TODO: check possible status values
#         return self.WARN, self.query('DEV::PTC:SIG:STATUS')
#
#     def read_water_in_temp(self):
#         return self.query('DEV::PTC:SIG:WIT')
#
#     def read_water_out_temp(self):
#         return self.query('DEV::PTC:SIG:WOT')
#
#     def read_helium_temp(self):
#         return self.query('DEV::PTC:SIG:HT')
#
#     def read_helium_low_pressure(self):
#         return self.query('DEV::PTC:SIG:HLP')
#
#     def read_helium_high_pressure(self):
#         return self.query('DEV::PTC:SIG:HHP')
#
#     def read_motor_current(self):
#         return self.query('DEV::PTC:SIG:MCUR')


class FlowMeter(MercuryChannel, Readable):
    kind = 'FLOW'

    def read_value(self):
        return self.query('DEV::FLOW:SIG:FLOW')


class ScannerChannel(MercuryChannel):
    # TODO: excitation, enable
    # TODO: switch on/off filter, check
    filter_time = Parameter('filter time', FloatRange(1, 200, unit='sec'), readonly=False)
    dwell_time = Parameter('dwell time', FloatRange(1, 200, unit='sec'), readonly=False)
    pause_time = Parameter('pause time', FloatRange(3, 200, unit='sec'), readonly=False)

    def read_filter_time(self):
        return self.query('DEV::TEMP:FILT:TIME')

    def write_filter_time(self, value):
        self.change('DEV::TEMP:FILT:WIN', 80)
        return self.change('DEV::TEMP:FILT:TIME', value)

    def read_dwell_time(self):
        return self.query('DEV::TEMP:MEAS:DWEL')

    def write_dwell_time(self, value):
        self.change('DEV::TEMP:FILT:WIN', 80)
        return self.change('DEV::TEMP:MEAS:DWEL', value)

    def read_pause_time(self):
        return self.query('DEV::TEMP:MEAS:PAUS')

    def write_pause_time(self, value):
        return self.change('DEV::TEMP:MEAS:PAUS', value)


class TemperatureSensor(ScannerChannel, mercury.TemperatureSensor):
    pass


class TemperatureLoop(ScannerChannel, mercury.TemperatureLoop):
    ENABLE = 'TEMP:LOOP:MODE'
    ENABLE_RAMP = 'TEMP:LOOP:RAMP:ENAB'
    RAMP_RATE = 'TEMP:LOOP:RAMP:RATE'

    enable_pid_table = None  # remove, does not work on triton
    ctrlpars = Parameter('pid (gain, integral (inv. time), differential time')
    system_channel = Property('system channel name', StringType(), 'MC')

    def set_control_active(self, active):
        if self.system_channel:
            self.change('SYS:DR:CHAN:%s' % self.system_channel, self.slot.split(',')[0], str)
        if active:
            self.change('DEV::TEMP:LOOP:FILT:ENAB', 'ON', str)
            if self.output_module:
                limit = self.output_module.read_limit()
                self.output_module.write_limit(limit)


class HeaterOutput(HasInput, MercuryChannel, Writable):
    """heater output"""
    kind = 'HTR'
    value = Parameter('heater output', FloatRange(unit='uW'))
    target = Parameter('heater output', FloatRange(0, unit='$'), readonly=False)
    resistivity = Parameter('heater resistivity', FloatRange(unit='Ohm'))

    def read_resistivity(self):
        return self.query('DEV::HTR:RES')

    def read_value(self):
        return round(self.query('DEV::HTR:SIG:POWR'), 3)

    def read_target(self):
        if self.controlled_by != 0:
            return Done
        return self.value

    def write_target(self, value):
        self.self_controlled()
        if self.resistivity:
            # round to the next voltage step
            value = round(sqrt(value * self.resistivity)) ** 2 / self.resistivity
        return round(self.change('DEV::HTR:SIG:POWR', value), 3)


class HeaterOutputWithRange(HeaterOutput):
    """heater output with heater range"""
    kind = 'HTR,TEMP'

    limit = Parameter('max. heater power', FloatRange(unit='uW'), readonly=False)

    def read_limit(self):
        maxcur = self.query('DEV::TEMP:LOOP:RANGE')  # mA
        if maxcur == 0:
            maxcur = 100  # mA
        return self.read_resistivity() * maxcur ** 2  # uW

    def write_limit(self, value):
        maxcur = sqrt(value / self.read_resistivity())
        for cur in 0.0316, 0.1, 0.316, 1, 3.16, 10, 31.6, 100:
            if cur > maxcur * 0.999:
                maxcur = cur
                break
        else:
            maxcur = cur
        self.change('DEV::TEMP:LOOP:RANGE', maxcur)
        return self.read_limit()
