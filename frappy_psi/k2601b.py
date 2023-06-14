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
"""Keithley 2601B 4 quadrant source meter

* switching between voltage and current happens by setting their target
* switching output off by setting the active parameter of the controlling
  module to False.
* setting the active parameter to True raises an error
"""

from frappy.core import Attached, BoolType, Done, EnumType, FloatRange, \
    HasIO, Module, Parameter, Readable, StringIO, Writable


class K2601bIO(StringIO):
    identification = [('print(localnode.description)', 'Keithley Instruments SMU 2601B.*')]


SOURCECMDS = {
    0: 'reset()'
       ' smua.source.output = 0 print("ok")',
    1: 'reset()'
       ' smua.source.func = smua.OUTPUT_DCAMPS'
       ' display.smua.measure.func = display.MEASURE_DCVOLTS'
       ' smua.source.autorangei = 1'
       ' smua.source.output = 1 print("ok")',
    2: 'reset()'
       ' smua.source.func = smua.OUTPUT_DCVOLTS'
       ' display.smua.measure.func = display.MEASURE_DCAMPS'
       ' smua.source.autorangev = 1'
       ' smua.source.output = 1 print("ok")',
}


class SourceMeter(HasIO, Module):
    export = False  # export for tests only
    mode = Parameter('measurement mode', EnumType(off=0, current=1, voltage=2),
                     readonly=False, export=False)
    ilimit = Parameter('current limit', FloatRange(0, 2.0, unit='A'), default=2)
    vlimit = Parameter('voltage limit', FloatRange(0, 2.0, unit='V'), default=2)

    ioClass = K2601bIO

    def read_mode(self):
        return int(float(self.communicate('print((smua.source.func+1)*smua.source.output)')))

    def write_mode(self, value):
        assert self.communicate(SOURCECMDS[value]) == 'ok'
        if value == 'current':
            self.write_vlimit(self.vlimit)
        elif value == 'voltage':
            self.write_ilimit(self.ilimit)
        return self.read_mode()

    def read_ilimit(self):
        if self.mode == 'current':
            return self.ilimit
        return float(self.communicate('print(smua.source.limiti)'))

    def write_ilimit(self, value):
        if self.mode == 'current':
            return self.ilimit
        return float(self.communicate(f'smua.source.limiti = {value:g} print(smua.source.limiti)'))

    def read_vlimit(self):
        if self.mode == 'voltage':
            return self.ilimit
        return float(self.communicate('print(smua.source.limitv)'))

    def write_vlimit(self, value):
        if self.mode == 'voltage':
            return self.ilimit
        return float(self.communicate(f'smua.source.limitv = {value:g} print(smua.source.limitv)'))


class Power(HasIO, Readable):
    value = Parameter('readback power', FloatRange(unit='W'))
    ioClass = K2601bIO

    def read_value(self):
        return float(self.communicate('print(smua.measure.p())'))


class Resistivity(HasIO, Readable):
    value = Parameter('readback resistivity', FloatRange(unit='Ohm'))
    ioClass = K2601bIO

    def read_value(self):
        return float(self.communicate('print(smua.measure.r())'))


class Current(HasIO, Writable):
    sourcemeter = Attached()

    value = Parameter('measured current', FloatRange(unit='A'))
    target = Parameter('set current', FloatRange(unit='A'))
    active = Parameter('current is controlled', BoolType(), default=False)
    limit = Parameter('current limit', FloatRange(0, 2.0, unit='A'), default=2)

    def initModule(self):
        super().initModule()
        self.sourcemeter.registerCallbacks(self)

    def read_value(self):
        return float(self.communicate('print(smua.measure.i())'))

    def read_target(self):
        return float(self.communicate('print(smua.source.leveli)'))

    def write_target(self, value):
        if value > self.sourcemeter.ilimit:
            raise ValueError('current exceeds limit')
        if not self.active:
            self.sourcemeter.write_mode('current')   # triggers update_mode -> set active to True
        value = float(self.communicate(f'smua.source.leveli = {value:g} print(smua.source.leveli)'))
        return value

    def read_limit(self):
        return self.sourcemeter.read_ilimit()

    def write_limit(self, value):
        return self.sourcemeter.write_ilimit(value)

    def update_mode(self, mode):
        # will be called whenever the attached sourcemeters mode changes
        self.active = mode == 'current'

    def write_active(self, value):
        self.sourcemeter.read_mode()
        if value == self.value:
            return Done
        if value:
            raise ValueError('activate only by setting target')
        self.sourcemeter.write_mode('off')   # triggers update_mode -> set active to False
        return Done


class Voltage(HasIO, Writable):
    sourcemeter = Attached()

    value = Parameter('measured voltage', FloatRange(unit='V'))
    target = Parameter('set voltage', FloatRange(unit='V'))
    active = Parameter('voltage is controlled', BoolType())
    limit = Parameter('voltage limit', FloatRange(0, 2.0, unit='V'), default=2)

    def initModule(self):
        super().initModule()
        self.sourcemeter.registerCallbacks(self)

    def read_value(self):
        return float(self.communicate('print(smua.measure.v())'))

    def read_target(self):
        return float(self.communicate('print(smua.source.levelv)'))

    def write_target(self, value):
        if value > self.sourcemeter.vlimit:
            raise ValueError('voltage exceeds limit')
        if not self.active:
            self.sourcemeter.write_mode('voltage')  # triggers update_mode -> set active to True
        value = float(self.communicate(f'smua.source.levelv = {value:g} print(smua.source.levelv)'))
        return value

    def read_limit(self):
        return self.sourcemeter.read_vlimit()

    def write_limit(self, value):
        return self.sourcemeter.write_vlimit(value)

    def update_mode(self, mode):
        # will be called whenever the attached sourcemeters mode changes
        self.active = mode == 'voltage'

    def write_active(self, value):
        self.sourcemeter.read_mode()
        if value == self.value:
            return Done
        if value:
            raise ValueError('activate only by setting target')
        self.sourcemeter.write_mode('off')  # triggers update_mode -> set active to False
        return Done
