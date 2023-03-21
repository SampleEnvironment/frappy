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
"""LakeShore Model 370 resistance channel

implements autoscan and autorange by software.
when the autoscan or autorange button is pressed, the state is toggled,
and the hardware mode switched off again.
At startup, the configurable default mode is set, independent of
the hardware state.
"""

import time
from ast import literal_eval

import frappy.io
from frappy.datatypes import BoolType, EnumType, FloatRange, IntRange, StatusType
from frappy.lib import formatStatusBits
from frappy.core import Done, Drivable, Parameter, Property, CommonReadHandler, CommonWriteHandler
from frappy.io import HasIO
from frappy_psi.channelswitcher import Channel, ChannelSwitcher

Status = Drivable.Status


STATUS_BIT_LABELS = 'CS_OVL VCM_OVL VMIX_OVL VDIF_OVL R_OVER R_UNDER T_OVER T_UNDER'.split()


class StringIO(frappy.io.StringIO):
    identification = [('*IDN?', 'LSCI,MODEL370,.*')]
    wait_before = 0.05


class Switcher(HasIO, ChannelSwitcher):
    value = Parameter(datatype=IntRange(1, 16))
    target = Parameter(datatype=IntRange(1, 16))
    use_common_delays = Parameter('use switch_delay and measure_delay instead of the channels pause and dwell',
                                  BoolType(), readonly=False, default=False)
    common_pause = Parameter('pause with common delays', FloatRange(3, 200, unit='s'), readonly=False, default=3)
    ioClass = StringIO
    fast_poll = 1
    _measure_delay = None
    _switch_delay = None

    def startModule(self, start_events):
        super().startModule(start_events)
        # disable unused channels
        for ch in range(1, 16):
            if ch not in self._channels:
                self.communicate('INSET %d,0,0,0,0,0;INSET?%d' % (ch, ch))
        channelno, autoscan = literal_eval(self.communicate('SCAN?'))
        if channelno in self._channels and self._channels[channelno].enabled:
            if not autoscan:
                return  # nothing to do
        else:
            channelno = self.next_channel(channelno)
            if channelno is None:
                self.status = 'ERROR', 'no enabled channel'
                return
        self.communicate('SCAN %d,0;SCAN?' % channelno)

    def doPoll(self):
        """poll buttons

        and check autorange during filter time
        """
        super().doPoll()
        self._channels[self.target]._read_value()  # check range or read
        channelno, autoscan = literal_eval(self.communicate('SCAN?'))
        if autoscan:
            # pressed autoscan button: switch off HW autoscan and toggle soft autoscan
            self.autoscan = not self.autoscan
            self.communicate('SCAN %d,0;SCAN?' % self.value)
        if channelno != self.value:
            # channel changed by keyboard, do not yet return new channel
            self.write_target(channelno)
        chan = self._channels.get(channelno)
        if chan is None:
            channelno = self.next_channel(channelno)
            if channelno is None:
                raise ValueError('no channels enabled')
            self.write_target(channelno)
            chan = self._channels.get(self.value)
        chan.read_autorange()
        chan.fix_autorange()  # check for toggled autorange button
        return Done

    def write_switch_delay(self, value):
        self._switch_delay = value
        return super().write_switch_delay(value)

    def write_measure_delay(self, value):
        self._measure_delay = value
        return super().write_measure_delay(value)

    def write_use_common_delays(self, value):
        if value:
            # use values from a previous change, instead of
            # the values from the current channel
            if self._measure_delay is not None:
                self.measure_delay = self._measure_delay
            if self._switch_delay is not None:
                self.switch_delay = self._switch_delay
        return value

    def set_delays(self, chan):
        if self.use_common_delays:
            if chan.dwell != self.measure_delay:
                chan.write_dwell(self.measure_delay)
            if chan.pause != self.common_pause:
                chan.write_pause(self.common_pause)
            filter_ = max(0, self.switch_delay - self.common_pause)
            if chan.filter != filter_:
                chan.write_filter(filter_)
        else:
            # switch_delay and measure_delay is changing with channel
            self.switch_delay = chan.pause + chan.filter
            self.measure_delay = chan.dwell

    def set_active_channel(self, chan):
        self.communicate('SCAN %d,0;SCAN?' % chan.channel)
        chan._last_range_change = time.monotonic()
        self.set_delays(chan)


class ResChannel(Channel):
    """temperature channel on Lakeshore 370"""

    RES_RANGE = {key: i+1 for i, key in list(
        enumerate(mag % val for mag in ['%gmOhm', '%gOhm', '%gkOhm', '%gMOhm']
                  for val in [2, 6.32, 20, 63.2, 200, 632]))[:-2]}
    CUR_RANGE = {key: i + 1 for i, key in list(
        enumerate(mag % val for mag in ['%gpA', '%gnA', '%guA', '%gmA']
                  for val in [1, 3.16, 10, 31.6, 100, 316]))[:-2]}
    VOLT_RANGE = {key: i + 1 for i, key in list(
        enumerate(mag % val for mag in ['%guV', '%gmV']
                  for val in [2, 6.32, 20, 63.2, 200, 632]))}
    RES_SCALE = [2 * 10 ** (0.5 * i) for i in range(-7, 16)]  # RES_SCALE[0] is not used
    MAX_RNG = len(RES_SCALE) - 1

    channel = Property('the Lakeshore channel', datatype=IntRange(1, 16), export=False)

    value = Parameter(datatype=FloatRange(unit='Ohm'))
    status = Parameter(datatype=StatusType(Drivable, 'DISABLED'))
    pollinterval = Parameter(visibility=3, default=1)
    range = Parameter('reading range', readonly=False,
                      datatype=EnumType(**RES_RANGE))
    minrange = Parameter('minimum range for software autorange', readonly=False, default=1,
                         datatype=EnumType(**RES_RANGE))
    autorange = Parameter('autorange', datatype=BoolType(),
                          readonly=False, default=1)
    iexc = Parameter('current excitation', datatype=EnumType(off=0, **CUR_RANGE), readonly=False)
    vexc = Parameter('voltage excitation', datatype=EnumType(off=0, **VOLT_RANGE), readonly=False)
    enabled = Parameter('is this channel enabled?', datatype=BoolType(), readonly=False)
    pause = Parameter('pause after channel change', datatype=FloatRange(3, 60, unit='s'), readonly=False)
    dwell = Parameter('dwell time with autoscan', datatype=FloatRange(1, 200, unit='s'), readonly=False)
    filter = Parameter('filter time', datatype=FloatRange(1, 200, unit='s'), readonly=False)

    _toggle_autorange = 'init'
    _prev_rdgrng = (1, 1)  # last read values for icur and exc
    _last_range_change = 0
    rdgrng_params = 'range', 'iexc', 'vexc'
    inset_params = 'enabled', 'pause', 'dwell'

    def communicate(self, command):
        return self.switcher.communicate(command)

    def read_status(self):
        if not self.enabled:
            return [self.Status.DISABLED, 'disabled']
        if not self.channel == self.switcher.value == self.switcher.target:
            return Done
        result = int(self.communicate('RDGST?%d' % self.channel))
        result &= 0x37  # mask T_OVER and T_UNDER (change this when implementing temperatures instead of resistivities)
        statustext = ' '.join(formatStatusBits(result, STATUS_BIT_LABELS))
        if statustext:
            return [self.Status.ERROR, statustext]
        return [self.Status.IDLE, '']

    def _read_value(self):
        """read value, without update"""
        now = time.monotonic()
        if now + 0.5 < max(self._last_range_change, self.switcher._start_switch) + self.pause:
            return None
        result = self.communicate('RDGR?%d' % self.channel)
        result = float(result)
        if self.autorange:
            self.fix_autorange()
            if now + 0.5 > self._last_range_change + self.pause:
                rng = int(max(self.minrange, self.range))  # convert from enum to int
                if self.status[1] == '':
                    if abs(result) > self.RES_SCALE[rng]:
                        if rng < 22:
                            rng += 1
                    else:
                        lim = 0.2
                        while rng > self.minrange and abs(result) < lim * self.RES_SCALE[rng]:
                            rng -= 1
                            lim -= 0.05  # not more than 4 steps at once
                        # effectively: <0.16 %: 4 steps, <1%: 3 steps, <5%: 2 steps, <20%: 1 step
                elif rng < self.MAX_RNG:
                    rng = min(self.MAX_RNG, rng + 1)
                if rng != self.range:
                    self.write_range(rng)
                    self._last_range_change = now
        return result

    def read_value(self):
        if self.channel == self.switcher.value == self.switcher.target:
            return self._read_value()
        return Done  # return previous value

    def is_switching(self, now, last_switch, switch_delay):
        last_switch = max(last_switch, self._last_range_change)
        if now + 0.5 > last_switch + self.pause:
            self._read_value()  # adjust range only
        return super().is_switching(now, last_switch, switch_delay)

    @CommonReadHandler(rdgrng_params)
    def read_rdgrng(self):
        iscur, exc, rng, autorange, excoff = literal_eval(
            self.communicate('RDGRNG?%d' % self.channel))
        self._prev_rdgrng = iscur, exc
        if autorange:  # pressed autorange button
            if not self._toggle_autorange:
                self._toggle_autorange = True
        iexc = 0 if excoff or not iscur else exc
        vexc = 0 if excoff or iscur else exc
        if (rng, iexc, vexc) != (self.range, self.iexc, self.vexc):
            self._last_range_change = time.monotonic()
        self.range, self.iexc, self.vexc = rng, iexc, vexc

    @CommonWriteHandler(rdgrng_params)
    def write_rdgrng(self, change):
        self.read_range()  # make sure autorange is handled
        if 'vexc' in change:  # in case vext is changed, do not consider iexc
            change['iexc'] = 0
        if change['iexc'] != 0:  # we need '!= 0' here, as bool(enum) is always True!
            iscur = 1
            exc = change['iexc']
            excoff = 0
        elif change['vexc'] != 0:  # we need '!= 0' here, as bool(enum) is always True!
            iscur = 0
            exc = change['vexc']
            excoff = 0
        else:
            iscur, exc = self._prev_rdgrng  # set to last read values
            excoff = 1
        rng = change['range']
        if self.autorange:
            if rng < self.minrange:
                rng = self.minrange
        self.communicate('RDGRNG %d,%d,%d,%d,%d,%d;*OPC?' % (
            self.channel, iscur, exc, rng, 0, excoff))
        self.read_range()

    def fix_autorange(self):
        if self._toggle_autorange:
            if self._toggle_autorange == 'init':
                self.write_autorange(True)
            else:
                self.write_autorange(not self.autorange)
            self._toggle_autorange = False

    @CommonReadHandler(inset_params)
    def read_inset(self):
        # ignore curve no and temperature coefficient
        enabled, dwell, pause, _, _ = literal_eval(
            self.communicate('INSET?%d' % self.channel))
        self.enabled = enabled
        self.dwell = dwell
        self.pause = pause

    @CommonWriteHandler(inset_params)
    def write_inset(self, change):
        _, _, _, curve, tempco = literal_eval(
            self.communicate('INSET?%d' % self.channel))
        self.enabled, self.dwell, self.pause, _, _ = literal_eval(
            self.communicate('INSET %d,%d,%d,%d,%d,%d;INSET?%d' % (
                self.channel, change['enabled'], change['dwell'], change['pause'], curve, tempco,
                self.channel)))
        if 'enabled' in change and change['enabled']:
            # switch to enabled channel
            self.switcher.write_target(self.channel)
        elif self.switcher.target == self.channel:
            self.switcher.set_delays(self)

    def read_filter(self):
        on, settle, _ = literal_eval(self.communicate('FILTER?%d' % self.channel))
        return settle if on else 0

    def write_filter(self, value):
        on = 1 if value else 0
        value = max(1, value)
        on, settle, _ = literal_eval(self.communicate(
            'FILTER %d,%d,%g,80;FILTER?%d' % (self.channel, on, value, self.channel)))
        if not on:
            settle = 0
        return settle
