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
"""Andeen Hagerling capacitance bridge"""

from secop.core import Readable, Parameter, FloatRange, HasIodev, StringIO, Done


class Ah2700IO(StringIO):
    end_of_line = '\r\n'
    timeout = 5


class Capacitance(HasIodev, Readable):

    value = Parameter('capacitance', FloatRange(unit='pF'), poll=True)
    freq = Parameter('frequency', FloatRange(unit='Hz'), readonly=False, default=0)
    voltage = Parameter('voltage', FloatRange(unit='V'), readonly=False, default=0)
    loss = Parameter('loss', FloatRange(unit='deg'), default=0)

    iodevClass = Ah2700IO

    def parse_reply(self, reply):
        if reply.startswith('SI'):  # this is an echo
            self.sendRecv('SERIAL ECHO OFF')
            reply = self.sendRecv('SI')
        if not reply.startswith('F='):  # this is probably an error message like "LOSS TOO HIGH"
            self.status = [self.Status.ERROR, reply]
            return
        self.status = [self.Status.IDLE, '']
        # examples of replies:
        # 'F= 1000.0  HZ C= 0.000001    PF L> 0.0         DS V= 15.0     V'
        # 'F= 1000.0  HZ C= 0.0000059   PF L=-0.4         DS V= 15.0     V OVEN'
        # 'LOSS TOO HIGH'
        # make sure there is always a space after '=' and '>'
        # split() ignores multiple white space
        reply = reply.replace('=', '= ').replace('>', '> ').split()
        _, freq, _, _, cap, _, _, loss, lossunit, _, volt = reply[:11]
        self.freq = freq
        self.voltage = volt
        self.value = cap
        if lossunit == 'DS':
            self.loss = loss
        else:  # the unit was wrong, we want DS = tan(delta), not NS = nanoSiemens
            reply = self.sendRecv('UN DS').split()  # UN DS returns a reply similar to SI
            try:
                self.loss = reply[7]
            except IndexError:
                pass  # don't worry, loss will be updated next time

    def read_value(self):
        self.parse_reply(self.sendRecv('SI'))  # SI = single trigger
        return Done

    def read_freq(self):
        self.read_value()
        return Done

    def read_loss(self):
        self.read_value()
        return Done

    def read_volt(self):
        self.read_value()
        return Done

    def write_freq(self, value):
        self.parse_reply(self.sendRecv('FR %g;SI' % value))
        return Done

    def write_volt(self, value):
        self.parse_reply(self.sendRecv('V %g;SI' % value))
        return Done
