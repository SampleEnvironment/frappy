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


# Base class
class Framer(object):
    """Frames and unframes an encoded message

    also transforms the encoded message to the 'wire-format' (and vise-versa)

    note: not all MessageEncoders can use all Framers,
          but the intention is to have this for as many as possible.
    """
    def encode(self, *frames):
        """return the wire-data for the given messageframes"""
        raise NotImplemented

    def decode(self, data):
        """return a list of messageframes found in data"""
        raise NotImplemented

    def reset(self):
        """resets the de/encoding stage (clears internal information)"""
        raise NotImplemented


# now some Implementations

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


FRAMERS = {
    'eol': EOLFramer,
    'rle': RLEFramer,
}

__ALL__ = ['FRAMERS']
