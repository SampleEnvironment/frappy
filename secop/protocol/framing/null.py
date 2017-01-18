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


class NullFramer(Framer):
    """do-nothing-framer

    assumes messages are framed by themselfs or the interface does it already.
    """

    def encode(self, *frames):
        """add transport layer encapsulation/framing of messages"""
        return ''.join(frames)

    def decode(self, data):
        """remove transport layer encapsulation/framing of messages"""
        return [data]