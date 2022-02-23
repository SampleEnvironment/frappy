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

import secop.iohandler
from secop.datatypes import BoolType, EnumType, FloatRange, IntRange
from secop.lib import formatStatusBits
from secop.modules import Attached, Done, \
    Drivable, Parameter, Property, Readable
from secop.io import HasIO

Status = Drivable.Status


class IOHandler(secop.iohandler.IOHandler):
    CMDARGS = ['channel']
    CMDSEPARATOR = ';'

    def __init__(self, name, querycmd, replyfmt):
        changecmd = querycmd.replace('?', ' ')
        if not querycmd.endswith('?'):
            changecmd += ','
        super().__init__(name, querycmd, replyfmt, changecmd)


rdgrng = IOHandler('rdgrng', 'RDGRNG?%(channel)d', '%d,%d,%d,%d,%d')
inset = IOHandler('inset', 'INSET?%(channel)d', '%d,%d,%d,%d,%d')
filterhdl = IOHandler('filter', 'FILTER?%(channel)d', '%d,%d,%d')
scan = IOHandler('scan', 'SCAN?', '%d,%d')


STATUS_BIT_LABELS = 'CS_OVL VCM_OVL VMIX_OVL VDIF_OVL R_OVER R_UNDER T_OVER T_UNDER'.split()


class StringIO(secop.io.StringIO):
    identification = [('*IDN?', 'LSCI,MODEL370,.*')]
    wait_before = 0.05


class Main(HasIO, Drivable):

    value = Parameter('the current channel', datatype=IntRange(0, 17))
    target = Parameter('channel to select', datatype=IntRange(0, 17))
    autoscan = Parameter('whether to scan automatically', datatype=BoolType(), readonly=False, default=False)
    pollinterval = Parameter(default=1, export=False)

    ioClass = StringIO
    _channel_changed = 0  # time of last channel change
    _channels = None  # dict <channel no> of <module object>

    def earlyInit(self):
        super().earlyInit()
        self._channels = {}

    def register_channel(self, modobj):
        self._channels[modobj.channel] = modobj

    def startModule(self, start_events):
        super().startModule(start_events)
        for ch in range(1, 16):
            if ch not in self._channels:
                self.communicate('INSET %d,0,0,0,0,0;INSET?%d' % (ch, ch))

    def read_value(self):
        channel, auto = scan.send_command(self)
        if channel not in self._channels:
            return channel
        if not self._channels[channel].enabled:
            # channel was disabled recently, but still selected
            nextchannel = 0
            for ch, mobj in self._channels.items():
                if mobj.enabled:
                    if ch > channel:
                        nextchannel = ch
                        break
                    if nextchannel == 0:
                        nextchannel = ch
            if nextchannel:
                self.write_target(nextchannel)
                return 0

        now = time.time()
        if channel != self.target:
            self._channel_changed = now
            self.target = channel
        self.autoscan = int(auto)
        if now < self._channel_changed + self._channels[channel].pause + self._channels[channel].filter:
            self.status = [Status.BUSY, 'switching']
            return 0
        self.status = [Status.IDLE, '']
        return channel

    def write_target(self, channel):
        scan.send_change(self, channel, self.autoscan)
        # self.communicate('SCAN %d,%d;SCAN?' % (channel, self.autoscan))
        if channel != self.value:
            self.value = 0
            self._channel_changed = time.time()
            self.status = [Status.BUSY, 'switching']
        return channel

    def write_autoscan(self, value):
        scan.send_change(self, self.value, value)
        # self.communicate('SCAN %d,%d;SCAN?' % (channel, self.autoscan))
        return value


class ResChannel(HasIO, Readable):
    """temperature channel on Lakeshore 336"""

    RES_RANGE = {key: i+1 for i, key in list(
        enumerate(mag % val for mag in ['%gmOhm', '%gOhm', '%gkOhm', '%gMOhm']
                  for val in [2, 6.32, 20, 63.2, 200, 632]))[:-2]}
    RES_SCALE = [2 * 10 ** (0.5 * i) for i in range(-7, 16)]  # RES_SCALE[0] is not used
    CUR_RANGE = {key: i + 1 for i, key in list(
        enumerate(mag % val for mag in ['%gpA', '%gnA', '%guA', '%gmA']
                  for val in [1, 3.16, 10, 31.6, 100, 316]))[:-2]}
    VOLT_RANGE = {key: i + 1 for i, key in list(
        enumerate(mag % val for mag in ['%guV', '%gmV']
                  for val in [2, 6.32, 20, 63.2, 200, 632]))}

    ioClass = StringIO
    _main = None  # main module
    _last_range_change = 0  # time of last range change

    channel = Property('the Lakeshore channel', datatype=IntRange(1, 16), export=False)
    main = Attached()

    value = Parameter(datatype=FloatRange(unit='Ohm'))
    pollinterval = Parameter(visibility=3, default=1, export=False)
    range = Parameter('reading range', readonly=False,
                      datatype=EnumType(**RES_RANGE), handler=rdgrng)
    minrange = Parameter('minimum range for software autorange', readonly=False, default=1,
                         datatype=EnumType(**RES_RANGE))
    autorange = Parameter('autorange', datatype=EnumType(off=0, hard=1, soft=2),
                          readonly=False, handler=rdgrng, default=2)
    iexc = Parameter('current excitation', datatype=EnumType(off=0, **CUR_RANGE), readonly=False, handler=rdgrng)
    vexc = Parameter('voltage excitation', datatype=EnumType(off=0, **VOLT_RANGE), readonly=False, handler=rdgrng)
    enabled = Parameter('is this channel enabled?', datatype=BoolType(), readonly=False, handler=inset)
    pause = Parameter('pause after channel change', datatype=FloatRange(3, 60), readonly=False, handler=inset)
    dwell = Parameter('dwell time with autoscan', datatype=FloatRange(1, 200), readonly=False, handler=inset)
    filter = Parameter('filter time', datatype=FloatRange(1, 200), readonly=False, handler=filterhdl)

    _trigger_read = False

    def initModule(self):
        super().initModule()
        self._main = self.DISPATCHER.get_module(self.main)
        self._main.register_channel(self)

    def read_value(self):
        if not self.enabled:
            self.status = [self.Status.DISABLED, 'disabled']
            return Done
        if self.channel != self._main.value:
            if self.channel == self._main.target:
                self._trigger_read = True
                return Done
            if not self._trigger_read:
                return Done
            # we got here, when we missed the idle state of self._main
        self._trigger_read = False
        result = self.communicate('RDGR?%d' % self.channel)
        result = float(result)
        if self.autorange == 'soft':
            now = time.time()
            if now > self._last_range_change + self.pause:
                rng = int(max(self.minrange, self.range))  # convert from enum to int
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
                            lim -= 0.05  # not more than 4 steps at once
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
        if not self.enabled:
            return [self.Status.DISABLED, 'disabled']
        if self.channel != self.main.value:
            return Done
        result = int(self.communicate('RDGST?%d' % self.channel))
        result &= 0x37  # mask T_OVER and T_UNDER (change this when implementing temperatures instead of resistivities)
        statustext = ' '.join(formatStatusBits(result, STATUS_BIT_LABELS))
        if statustext:
            return [self.Status.ERROR, statustext]
        return [self.Status.IDLE, '']

    def analyze_rdgrng(self, iscur, exc, rng, autorange, excoff):
        result = dict(range=rng)
        if autorange:
            result['autorange'] = 'hard'
        # else: do not change autorange
        self.log.debug('%s range %r %r %r' % (self.name, rng, autorange, self.autorange))
        if excoff:
            result.update(iexc=0, vexc=0)
        elif iscur:
            result.update(iexc=exc, vexc=0)
        else:
            result.update(iexc=0, vexc=exc)
        return result

    def change_rdgrng(self, change):
        iscur, exc, rng, autorange, excoff = change.readValues()
        if change.doesInclude('vexc'):  # in case vext is changed, do not consider iexc
            change.iexc = 0
        if change.iexc != 0:  # we need '!= 0' here, as bool(enum) is always True!
            iscur = 1
            exc = change.iexc
            excoff = 0
        elif change.vexc != 0:  # we need '!= 0' here, as bool(enum) is always True!
            iscur = 0
            exc = change.vexc
            excoff = 0
        else:
            excoff = 1
        rng = change.range
        if change.autorange == 'hard':
            autorange = 1
        else:
            autorange = 0
            if change.autorange == 'soft':
                if rng < self.minrange:
                    rng = self.minrange
        self.autorange = change.autorange
        return iscur, exc, rng, autorange, excoff

    def analyze_inset(self, on, dwell, pause, curve, tempco):
        return dict(enabled=on, dwell=dwell, pause=pause)

    def change_inset(self, change):
        _, _, _, curve, tempco = change.readValues()
        return change.enabled, change.dwell, change.pause, curve, tempco

    def analyze_filter(self, on, settle, window):
        return dict(filter=settle if on else 0)

    def change_filter(self, change):
        _, settle, window = change.readValues()
        if change.filter:
            return 1, change.filter, 80  # always use 80% filter
        return 0, settle, window

    def write_enabled(self, value):
        inset.write(self, 'enabled', value)
        if value:
            self.main.write_target(self.channel)
        return Done
