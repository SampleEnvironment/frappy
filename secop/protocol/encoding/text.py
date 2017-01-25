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

from secop.protocol.encoding import MessageEncoder
from secop.protocol import messages
from secop.lib.parsing import *


class TextEncoder(MessageEncoder):
    def __init__(self):
        # build safe namespace
        ns = dict()
        for n in dir(messages):
            if n.endswith(('Request', 'Reply')):
                ns[n] = getattr(messages, n)
        self.namespace = ns

    def encode(self, messageobj):
        """msg object -> transport layer message"""
        # fun for Humans
        if isinstance(messageobj, messages.HelpMessage):
            return "Error: try one of the following requests:\n" + \
                   '\n'.join(['%s(%s)' % (getattr(messages, m).__name__,
                                          ', '.join(getattr(messages, m).ARGS))
                              for m in dir(messages)
                              if m.endswith('Request') and len(m) > len("Request")])
        res = []
        for k in messageobj.ARGS:
            res.append('%s=%r' % (k, getattr(messageobj, k, None)))
        result = '%s(%s)' % (messageobj.__class__.__name__, ', '.join(res))
        return result

    def decode(self, encoded):
        """transport layer message -> msg object"""
        # WARNING: highly unsafe!
        # think message='import os\nos.unlink('\')\n'
        try:
            return eval(encoded, self.namespace, {})
        except SyntaxError:
            return messages.HelpMessage()
