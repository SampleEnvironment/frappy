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


class RLEFramer(Framer):
    data = b''
    frames_to_go = 0

    def encode(self, *frames):
        """add transport layer encapsulation/framing of messages"""
        # format is 'number of frames:[framelengt:frme]*N'
        frdata = ['%d:%s' % (len(frame), frame) for frame in frames]
        return b'%d:' + b''.join(frdata)

    def decode(self, data):
        """remove transport layer encapsulation/framing of messages

        returns a list of messageframes which got decoded from data!
        """
        self.data += data
        res = []
        while self.data:
            if frames_to_go == 0:
                if ':' in self.data:
                    # scan for and decode 'number of frames'
                    frnum, self.data = self.data.split(':', 1)
                    try:
                        self.frames_to_go = int(frnum)
                    except ValueError:
                        # can not recover, complain!
                        raise FramingError('invalid start of message found!')
                else:
                    # not enough data to decode number of frames,
                    # return what we have
                    return res
            while self.frames_to_go:
                # there are still some (partial) frames stuck inside self.data
                frlen, self.data = self.data.split(':', 1)
                if len(self.data) >= frlen:
                    res.append(self.data[:frlen])
                    self.data = self.data[frlen:]
                    self.frames_to_go -= 1
                else:
                    # not enough data for this frame, return what we have
                    return res

    def reset(self):
        self.data = b''
        self.frames_to_go = 0
