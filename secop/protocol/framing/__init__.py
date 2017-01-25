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
from null import NullFramer
from eol import EOLFramer
from rle import RLEFramer
from demo import DemoFramer

FRAMERS = {
    'null': NullFramer,
    'eol': EOLFramer,
    'rle': RLEFramer,
    'demo': DemoFramer,
}

__ALL__ = ['FRAMERS']
