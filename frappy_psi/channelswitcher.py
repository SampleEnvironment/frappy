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
"""channel switcher Mixin

Example Config File:

[sw]
description=the switcher for blabla channels
class=frappy_facility.module.YourChannelSwitcher
uri=...

[chan1]
description=channel 1
class=frappy_facility.module.YourChannel
switcher=sw

[chan2]
...
"""

import time

from frappy.datatypes import IntRange, BoolType, FloatRange
from frappy.core import Attached, Property, Drivable, Parameter, Readable, Done


class ChannelSwitcher(Drivable):
    """base class for the channel switcher

    minimum implementation:
    - override :meth:`set_active_channel`

    - <channel>.read_value() and <channel>.read_status() is called periodically
      every <channel>.pollinterval on the active channel only
    - <channel>.is_switching(...) is called every <switcher>.pollinterval
      during switching period, until it is returning False
    """
    value = Parameter('the current channel number', IntRange(), needscfg=False)
    target = Parameter('channel to select', IntRange(), needscfg=False)
    autoscan = Parameter('whether to scan automatically',
                         BoolType(), readonly=False, default=True)
    pollinterval = Parameter(default=1, export=False)
    switch_delay = Parameter('the time needed to switch between channels',
                             FloatRange(0, None), readonly=False, default=5)
    measure_delay = Parameter('the time for staying at a channel',
                              FloatRange(0, None), readonly=False,  default=2)

    fast_poll = 0.1
    _channels = None  # dict <channel no> of <module object>
    _start_measure = 0
    _last_measure = 0
    _start_switch = 0
    _time_tol = 0.5

    def earlyInit(self):
        super().earlyInit()
        self._channels = {}

    def register_channel(self, mod):
        """register module"""
        self._channels[mod.channel] = mod

    def set_active_channel(self, chan):
        """tell the HW the active channel

        :param chan: a channel object

        to be implemented
        """
        raise NotImplementedError

    def next_channel(self, channelno):
        next_channel = channelno
        first_channel = None
        for ch, mod in self._channels.items():
            if mod.enabled:
                if first_channel is None:
                    first_channel = ch
                if next_channel == ch:
                    next_channel = None
                elif next_channel is None:
                    next_channel = ch
                    break
        else:
            next_channel = first_channel
        return next_channel

    def read_status(self):
        now = time.monotonic()
        if self.status[0] == 'BUSY':
            chan = self._channels[self.target]
            if chan.is_switching(now, self._start_switch, self.switch_delay):
                return Done
            self.setFastPoll(False)
            self.status = 'IDLE', 'measure'
            self.value = self.target
            self._start_measure = self._last_measure = now
            chan.read_value()
            chan.read_status()
            if self.measure_delay > self._time_tol:
                return Done
        else:
            chan = self._channels[self.value]
            self.read_value()  # this might modify autoscan or deadline!
            if chan.enabled:
                if self.target != self.value:  # may happen after startup
                    self.target = self.value
                next_measure = self._last_measure + chan.pollinterval
                if now + self._time_tol > next_measure:
                    chan.read_value()
                    chan.read_status()
                    self._last_measure = next_measure
                if not self.autoscan or now + self._time_tol < self._start_measure + self.measure_delay:
                    return Done
        next_channel = self.next_channel(self.value)
        if next_channel == self.value:
            return 'IDLE', 'single channel'
        if next_channel is None:
            return 'ERROR', 'no enabled channel'
        self.write_target(next_channel)
        return self.status

    def write_pollinterval(self, value):
        self._time_tol = min(1, value) * 0.5
        return value

    def write_target(self, channel):
        if channel not in self._channels:
            raise ValueError('%r is no valid channel' % channel)
        if channel == self.target and self._channels[channel].enabled:
            return channel
        chan = self._channels[channel]
        chan.enabled = True
        self.set_active_channel(chan)
        self._start_switch = time.monotonic()
        self.status = 'BUSY', 'change channel'
        self.setFastPoll(True, self.fast_poll)
        return channel


class Channel(Readable):
    """base class for channels

    you should override the datatype of the channel property,
    in order to match the datatype of the switchers value
    """
    switcher = Attached()
    channel = Property('channel number', IntRange())
    enabled = Parameter('enabled flag', BoolType(), default=True)
    value = Parameter(needscfg=False)

    def initModule(self):
        super().initModule()
        self.switcher.register_channel(self)

    def doPoll(self):
        """value and status are polled by switcher"""

    def is_switching(self, now, last_switch, switch_delay):
        """returns True when switching is done"""
        return now + self.switcher._time_tol < last_switch + switch_delay
