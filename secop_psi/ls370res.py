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
"""LakeShore Model 370 resistance channel"""

import time

from secop.modules import Module, Readable, Drivable, Parameter, Override, Property, Attached
from secop.metaclass import Done
from secop.datatypes import FloatRange, IntRange, EnumType, BoolType
from secop.stringio import HasIodev
from secop.poller import Poller, REGULAR
import secop.commandhandler

Status = Drivable.Status


class CmdHandler(secop.commandhandler.CmdHandler):
    CMDARGS = ['channel']
    CMDSEPARATOR = ';'

    def __init__(self, name, querycmd, replyfmt):
        changecmd = querycmd.replace('?', ' ')
        if not querycmd.endswith('?'):
            changecmd += ','
        super().__init__(name, querycmd, replyfmt, changecmd)


rdgrng = CmdHandler('rdgrng', 'RDGRNG?%(channel)d', '%d,%d,%d,%d,%d')
inset = CmdHandler('inset', 'INSET?%(channel)d', '%d,%d,%d,%d,%d')
filterhdl = CmdHandler('filt', 'FILTER?%(channel)d', '%d,%d,%d')
scan = CmdHandler('scan', 'SCAN?', '%d,%d')


STATUS_TEXT = {0: ''}
for bit, text in enumerate('CS_OVL VCM_OVL VMIX_OVL R_OVER R_UNDER T_OVER T_UNDER'.split()):
    for i in range(1 << bit, 2 << bit):
        STATUS_TEXT[i] = text


class StringIO(secop.stringio.StringIO):
    identification = [('*IDN?', 'LSCI,MODEL370,.*')]


class Main(HasIodev, Module):
    parameters = {
        'channel':
            Parameter('the current channel', poll=REGULAR, datatype=IntRange(), readonly=False, handler=scan),
        'autoscan':
            Parameter('whether to scan automatically', datatype=BoolType(), readonly=False, handler=scan),
        'pollinterval': Parameter('sleeptime between polls', default=5,
                                  readonly=False,
                                  datatype=FloatRange(0.1, 120),
                                 ),
    }

    pollerClass = Poller

    def analyze_scan(self, channel, autoscan):
        self.channel, self.autoscan = channel, autoscan

    def change_scan(self, new, *args):
        return new.channel, new.autoscan


class ResChannel(HasIodev, Readable):
    '''temperature channel on Lakeshore 336'''

    RES_RANGE = {key: i+1 for i, key in list(
        enumerate(mag % val for mag in ['%gmOhm', '%gOhm', '%gkOhm', '%gMOhm']
            for val in [2, 6.32, 20, 63.2, 200, 632]))[:-2]}
    RES_SCALE = [2 * 10 ** (0.5 * i) for i in range(-7,16)] # RES_SCALE[0] is not used
    CUR_RANGE = {key: i + 1 for i, key in list(
        enumerate(mag % val for mag in ['%gpA', '%gnA', '%guA', '%gmA']
            for val in [1, 3.16, 10, 31.6, 100, 316]))[:-2]}
    VOLT_RANGE = {key: i + 1 for i, key in list(
        enumerate(mag % val for mag in ['%guV', '%gmV']
            for val in [2, 6.32, 20, 63.2, 200, 632]))}

    pollerClass = Poller

    properties = {
        'channel':
            Property('the Lakeshore channel', datatype=IntRange(), export=False),
        'main':
            Attached()
    }

    parameters = {
        'value':
            Override(datatype=FloatRange(unit='Ohm')),
        'pollinterval':
            Override(visibility=3),
        'range':
            Parameter('reading range', readonly=False,
                       datatype=EnumType(**RES_RANGE), handler=rdgrng),
        'minrange':
            Parameter('minimum range for software autorange', readonly=False, default=1,
                       datatype=EnumType(**RES_RANGE)),
        'autorange':
            Parameter('autorange', datatype=EnumType(off=0, hard=1, soft=2),
                      readonly=False, handler=rdgrng, default=2),
        'iexc':
            Parameter('current excitation', datatype=EnumType(off=0, **CUR_RANGE), readonly=False, handler=rdgrng),
        'vexc':
            Parameter('voltage excitation', datatype=EnumType(off=0, **VOLT_RANGE), readonly=False, handler=rdgrng),
        'enable':
            Parameter('is this channel enabled?', datatype=BoolType(), readonly=False, handler=inset),
        'pause':
            Parameter('pause after channel change', datatype=IntRange(), readonly=False, handler=inset),
        'dwell':
            Parameter('dwell time with autoscan', datatype=IntRange(), readonly=False, handler=inset),
        'filter':
            Parameter('filter time', datatype=IntRange(), readonly=False, handler=filterhdl),
    }

    def startModule(self, started_callback):
        self._last_range_change = 0
        self._main = self.DISPATCHER.get_module(self.main)
        super().startModule(started_callback)

    def read_value(self):
        if self.channel != self._main.channel:
            return Done
        result = self.sendRecv('RDGR?%d' % self.channel)
        result = float(result)
        if self.autorange == 'soft':
            now = time.time()
            if now > self._last_range_change + self.pause:
                rng = int(max(self.minrange, self.range)) # convert from enum to int
                if self.status[1] == '':
                    if abs(result) > self.RES_SCALE[rng]:
                        if rng < 22:
                            rng += 1
                        self.log.info('chan %d: increased range to %.3g' %
                                      (self.channel, self.RES_SCALE[rng]))
                    else:
                        lim = 0.2
                        while rng > self.minrange and abs(result) < lim * self.RES_SCALE[rng]:
                            rng -= 1
                            lim -= 0.05 # not more than 4 steps at once
                        # effectively: <0.16 %: 4 steps, <1%: 3 steps, <5%: 2 steps, <20%: 1 step
                        if lim != 0.2:
                            self.log.info('chan %d: lowered range to %.3g' %
                                          (self.channel, self.RES_SCALE[rng]))
                elif rng < 22:
                    rng = min(22, rng + 1)
                    self.log.info('chan: %d, %s, increased range to %.3g' %
                                  (self.channel, self.status[1], self.RES_SCALE[rng]))
                if rng != self.range:
                    self.write_range(rng)
                    self._last_range_change = now
        return result

    def read_status(self):
        if self.channel != self._main.channel:
            return Done
        result = int(self.sendRecv('RDGST?%d' % self.channel))
        result &= 0x37 # mask T_OVER and T_UNDER (change this when implementing temperatures instead of resistivities)
        statustext = STATUS_TEXT[result]
        if statustext:
            return [self.Status.ERROR, statustext]
        return [self.Status.IDLE, '']

    def analyze_rdgrng(self, iscur, exc, rng, autorange, excoff):
        if excoff:
            self.iexc, self.vexc = 0,0
        elif iscur:
            self.iexc, self.vexc = exc, 0
        else:
            self.iexc, self.vexc = 0, exc
        if autorange:
            self.autorange = 'hard'
        else:
            if self.autorange == 'hard':
                self.autorange = 'soft'
            else:
                self.autorange = self.autorange
        self.range = rng

    def change_rdgrng(self, new, iscur, exc, rng, autorange, excoff):
        if new.vexc != self.vexc: # in case vext is changed, do not consider iexc
            new.iexc = 0
        if new.iexc != 0: # we need '!= 0' here, as bool(enum) is always True!
            iscur = 1
            exc = new.iexc
            excoff = 0
        elif new.vexc != 0: # we need '!= 0' here, as bool(enum) is always True!
            iscur = 0
            exc = new.vexc
            excoff = 0
        else:
            excoff = 1
        rng = new.range
        if new.autorange == 'hard':
            autorange = 1
        else:
            autorange = 0
            if new.autorange == 'soft':
                if rng < new.minrange:
                    rng = new.minrange
        return iscur, exc, rng, autorange, excoff

    def analyze_inset(self, on, dwell, pause, curve, tempco):
        self.enabled, self.dwell, self.pause = on, dwell, pause

    def change_inset(self, new, on, dwell, pause, curve, tempco):
        return new.enable, new.dwell, new.pause, curve, tempco

    def analyze_filt(self, on, settle, window):
        self.filter = settle if on else 0

    def change_filt(self, new, on, settle, window):
        if new.filter:
            return 1, new.filter, 80 # always use 80% filter
        return 0, settle, window
