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
"""a very simple simulator for a LakeShore Model 370"""

from secop.modules import Communicator

class Ls370Sim(Communicator):
    CHANNEL_COMMANDS = [
        ('RDGR?%d', '1.0'),
        ('RDGST?%d', '0'),
        ('RDGRNG?%d', '0,5,5,0,0'),
        ('INSET?%d', '1,5,5,0,0'),
        ('FILTER?%d', '1,5,80'),
    ]
    OTHER_COMMANDS = [
        ('*IDN?', 'LSCI,MODEL370,370184,05302003'),
        ('SCAN?', '3,1'),
    ]
    def earlyInit(self):
        self._data = dict(self.OTHER_COMMANDS)
        for fmt, v in self.CHANNEL_COMMANDS:
            for chan in range(1,17):
                self._data[fmt % chan] = v
        # mkthread(self.run)

    def communicate(self, command):
        # simulation part, time independent
        for channel in range(1,17):
            _, _, _, _, excoff = self._data['RDGRNG?%d' % channel].split(',')
            if excoff == '1':
                self._data['RDGST?%d' % channel] = '6'
            else:
                self._data['RDGST?%d' % channel] = '0'

        chunks = command.split(';')
        reply = []
        for chunk in chunks:
            if '?' in chunk:
                reply.append(self._data[chunk])
            else:
                for nqarg in (1,0):
                    if nqarg == 0:
                        qcmd, arg = chunk.split(' ', 1)
                        qcmd += '?'
                    else:
                        qcmd, arg = chunk.split(',', nqarg)
                        qcmd = qcmd.replace(' ', '?', 1)
                    if qcmd in self._data:
                        self._data[qcmd] = arg
                        break
        #if command.startswith('R'):
        #    print('> %s\t< %s' % (command, reply))
        return ';'.join(reply)
