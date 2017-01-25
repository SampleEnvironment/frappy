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

import re

DEMO_RE = re.compile(
    r'^([!+-])?(\*|[a-z_][a-z_0-9]*)?(?:\:(\*|[a-z_][a-z_0-9]*))?(?:\:(\*|[a-z_][a-z_0-9]*))?(?:\=(.*))?'
)


class DemoEncoder(MessageEncoder):
    def decode(sef, encoded):
        # match [!][*|devicename][: *|paramname [: *|propname]] [=value]
        match = DEMO_RE.match(encoded)
        if match:
            novalue, devname, pname, propname, assign = match.groups()
            if assign:
                print "parsing", assign,
                assign = parse_args(assign)
                print "->", assign
            return messages.DemoRequest(novalue, devname, pname, propname,
                                        assign)
        return messages.HelpRequest()

    def encode(self, msg):
        if isinstance(msg, messages.DemoReply):
            return msg.lines
        handler_name = '_encode_' + msg.__class__.__name__
        handler = getattr(self, handler_name, None)
        if handler is None:
            print "Handler %s not yet implemented!" % handler_name
        try:
            args = dict((k, msg.__dict__[k]) for k in msg.ARGS)
            result = handler(**args)
        except Exception as e:
            print "Error encoding %r with %r!" % (msg, handler)
            print e
            return '~InternalError~'
        return result

    def _encode_AsyncDataUnit(self,
                              devname,
                              pname,
                              value,
                              timestamp,
                              error=None,
                              unit=''):
        return '#%s:%s=%s;t=%.3f' % (devname, pname, value, timestamp)

    def _encode_Error(self, error):
        return '~Error~ %r' % error

    def _encode_InternalError(self, error):
        return '~InternalError~ %r' % error

    def _encode_ProtocollError(self, msgtype, msgname, msgargs):
        return '~ProtocolError~ %s.%s.%r' % (msgtype, msgname, msgargs)

    def _encode_NoSuchDeviceError(self, device):
        return '~NoSuchDeviceError~ %s' % device

    def _encode_NoSuchParamError(self, device, param):
        return '~NoSuchParameterError~ %s:%s' % (device, param)

    def _encode_ParamReadonlyError(self, device, param):
        return '~ParamReadOnlyError~ %s:%s' % (device, param)

    def _encode_NoSuchCommandError(self, device, command):
        return '~NoSuchCommandError~ %s.%s' % (device, command)

    def _encode_CommandFailedError(self, device, command):
        return '~CommandFailedError~ %s.%s' % (device, command)

    def _encode_InvalidParamValueError(self, device, param, value):
        return '~InvalidValueForParamError~ %s:%s=%r' % (device, param, value)

    def _encode_HelpReply(self):
        return [
            'Help not yet implemented!',
            'ask Markus Zolliker about the protocol'
        ]
