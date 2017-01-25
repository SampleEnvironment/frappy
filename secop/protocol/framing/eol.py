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


class EOLFramer(Framer):
    """Text based message framer

    messages are delimited by '\r\n'
    upon reception the end of a message is detected by '\r\n','\n' or '\n\r'
    """
    data = b''

    def encode(self, *frames):
        """add transport layer encapsulation/framing of messages"""
        return b'%s\r\n' % b'\r\n'.join(frames)

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

    def reset(self):
        self.data = b''
