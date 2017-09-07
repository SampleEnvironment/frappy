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
"""Encoding/decoding Messages"""

# implement as class as they may need some internal 'state' later on
# (think compressors)

# Base classes


class MessageEncoder(object):
    """en/decode a single Messageobject"""

    def encode(self, messageobj):
        """encodes the given message object into a frame"""
        raise NotImplemented

    def decode(self, frame):
        """decodes the given frame to a message object"""
        raise NotImplemented


from .demo_v2 import DemoEncoder as DemoEncoderV2
from .demo_v3 import DemoEncoder as DemoEncoderV3
from .demo_v4 import DemoEncoder as DemoEncoderV4
from .demo_v5 import DemoEncoder as DemoEncoderV5
from .text import TextEncoder
from .pickle import PickleEncoder
from .simplecomm import SCPEncoder

ENCODERS = {
    'pickle': PickleEncoder,
    'text': TextEncoder,
    'demo_v2': DemoEncoderV2,
    'demo_v3': DemoEncoderV3,
    'demo_v4': DemoEncoderV4,
    'demo_v5': DemoEncoderV5,
    'demo': DemoEncoderV5,
    'scp': SCPEncoder,
}

__ALL__ = ['ENCODERS']
