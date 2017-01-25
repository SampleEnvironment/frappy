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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************
"""Encoding/decoding Frames"""

from secop.protocol.framing import Framer


class DemoFramer(Framer):
    """Text based message framer

    frmes are delimited by '\n'
    messages are delimited by '\n\n'
    '\r' is ignored
    """

    def __init__(self):
        self.data = b''
        self.decoded = []

    def encode(self, frames):
        """add transport layer encapsulation/framing of messages"""
        if isinstance(frames, (tuple, list)):
            return b'\n'.join(frames) + b'\n\n'
        return b'%s\n\n' % frames

    def decode(self, data):
        """remove transport layer encapsulation/framing of messages

        returns a list of messageframes which got decoded from data!
        """
        self.data += data
        res = []
        while b'\n' in self.data:
            frame, self.data = self.data.split(b'\n', 1)
            if frame.endswith('\r'):
                frame = frame[:-1]
            if self.data.startswith('\r'):
                self.data = self.data[1:]
            res.append(frame)
        return res

    def decode2(self, data):
        """remove transport layer encapsulation/framing of messages

        returns a _list_ of messageframes which got decoded from data!
        """
        self.data += data.replace(b'\r', '')
        while b'\n' in self.data:
            frame, self.data = self.data.split(b'\n', 1)
            if frame:
                # not an empty line -> belongs to this set of messages
                self.decoded.append(frame)
            else:
                # empty line -> our set of messages is finished decoding
                res = self.decoded
                self.decoded = []
                return res
        return None

    def reset(self):
        self.data = b''
        self.decoded = []
