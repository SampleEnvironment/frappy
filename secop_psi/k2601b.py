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
"""Keithley 2601B source meter

not tested yet"""

from secop.core import Writable, Module, Parameter, Override, Attached,\
    BoolType, FloatRange, EnumType, HasIodev, StringIO


class K2601bIO(StringIO):
    identification = [('print(localnode.description)', 'Keithley Instruments SMU 2601B.*')]


SOURCECMDS = {
    1: 'reset()'
       'smua.source.func = smua.OUTPUT_DCVOLTS '
       'display.smua.measure.func = display.MEASURE_DCAMP '
       'smua.source.autorangev = 1',
    2: 'reset()'
       'smua.source.func = smua.OUTPUT_DCAMPS '
       'smua.source.autorangei = 1',
}


class SourceMeter(HasIodev, Module):
    parameters = {
        'resistivity': Parameter('readback resistivity', FloatRange(unit='Ohm'), poll=True),
        'power': Parameter('readback power', FloatRange(unit='W'), poll=True),
        'mode': Parameter('measurement mode', EnumType(off=0, current=1, voltage=2),
                          readonly=False, default=0),
        'active': Parameter('output enable', BoolType(), readonly=False, poll=True),
    }
    iodevClass = K2601bIO

    def read_resistivity(self):
        return self.sendRecv('print(smua.measure.r())')

    def read_power(self):
        return self.sendRecv('print(smua.measure.p())')

    def read_active(self):
        return self.sendRecv('print(smua.source.output)')

    def write_active(self, value):
        return self.sendRecv('smua.source.output = %d print(smua.source.output)' % value)

    # for now, mode will not be read from hardware

    def write_mode(self, value):
        if value == 0:
            self.write_active(0)
        else:
            self.sendRecv(SOURCECMDS[value] + ' print(0)')
        return value


class Current(HasIodev, Writable):
    properties = {
        'sourcemeter': Attached(),
    }
    parameters = {
        'value': Override('measured current', FloatRange(unit='A'), poll=True),
        'target': Override('set current', FloatRange(unit='A'), poll=True),
        'active': Parameter('current is controlled', BoolType(), default=False),  # polled from Current/Voltage
        'limit': Parameter('current limit', FloatRange(0, 2.0, unit='A'), default=2, poll=True),
    }

    def read_value(self):
        return self.sendRecv('print(smua.measure.i())')

    def read_target(self):
        return self.sendRecv('print(smua.source.leveli)')

    def write_target(self, value):
        if not self.active:
            raise ValueError('current source is disabled')
        if value > self.limit:
            raise ValueError('current exceeds limit')
        return self.sendRecv('smua.source.leveli = %g print(smua.source.leveli)' % value)

    def read_limit(self):
        if self.active:
            return self.limit
        return self.sendRecv('print(smua.source.limiti)')

    def write_limit(self, value):
        if self.active:
            return value
        return self.sendRecv('smua.source.limiti = %g print(smua.source.limiti)' % value)

    def read_active(self):
        return self._sourcemeter.mode == 1 and self._sourcemeter.read_active()

    def write_active(self, value):
        if self._sourcemeter.mode != 1:
            if value:
                self._sourcemeter.write_mode(1)  # switch to current
            else:
                return 0
        return self._sourcemeter.write_active(value)


class Voltage(HasIodev, Writable):
    properties = {
        'sourcemeter': Attached(),
    }
    parameters = {
        'value': Override('measured voltage', FloatRange(unit='V'), poll=True),
        'target': Override('set voltage', FloatRange(unit='V'), poll=True),
        'active': Parameter('voltage is controlled', BoolType(), poll=True),
        'limit': Parameter('current limit', FloatRange(0, 2.0, unit='V'), default=2, poll=True),
    }

    def read_value(self):
        return self.sendRecv('print(smua.measure.v())')

    def read_target(self):
        return self.sendRecv('print(smua.source.levelv)')

    def write_target(self, value):
        if not self.active:
            raise ValueError('voltage source is disabled')
        if value > self.limit:
            raise ValueError('voltage exceeds limit')
        return self.sendRecv('smua.source.levelv = %g print(smua.source.levelv)' % value)

    def read_limit(self):
        if self.active:
            return self.limit
        return self.sendRecv('print(smua.source.limitv)')

    def write_limit(self, value):
        if self.active:
            return value
        return self.sendRecv('smua.source.limitv = %g print(smua.source.limitv)' % value)

    def read_active(self):
        return self._sourcemeter.mode == 2 and self._sourcemeter.read_active()

    def write_active(self, value):
        if self._sourcemeter.mode != 2:
            if value:
                self._sourcemeter.write_mode(2) # switch to voltage
            else:
                return 0
        return self._sourcemeter.write_active(value)
