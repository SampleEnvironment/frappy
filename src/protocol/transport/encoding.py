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

from protocol import messages


# Base classes
class MessageEncoder(object):
    """en/decode a single Messageobject"""

    def encode(self, messageobj):
        """encodes the given message object into a frame"""
        raise NotImplemented

    def decode(self, frame):
        """decodes the given frame to a message object"""
        raise NotImplemented

# now some Implementations
try:
    import cPickle as pickle
except ImportError:
    import pickle

import protocol.messages


class PickleEncoder(MessageEncoder):

    def encode(self, messageobj):
        """msg object -> transport layer message"""
        return pickle.dumps(messageobj)

    def decode(self, encoded):
        """transport layer message -> msg object"""
        return pickle.loads(encoded)


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
        if isinstance(messageobj, messages.HelpReply):
            return "Error: try one of the following requests:\n" + \
                   '\n'.join(['%s(%s)' % (getattr(messages, m).__name__,
                                          ', '.join(getattr(messages, m).ARGS))
                              for m in dir(messages)
                              if m.endswith('Request')])
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
            return messages.HelpRequest()


def format_time(ts):
    return float(ts)  # XXX: switch to iso!

import re

DEMO_RE = re.compile(
    r'^([!+-])?(\*|[a-z_][a-z_0-9]*)?(?:\:(\*|[a-z_][a-z_0-9]*))?(?:\:(\*|[a-z_][a-z_0-9]*))?(?:\=(.*))?')


def parse_str(s):
    # QnD Hack! try to parse lists/tuples/ints/floats, ignore dicts, specials
    # XXX: replace by proper parsing. use ast?
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        # evaluate inner
        return [parse_str(part) for part in s[1:-1].split(',')]
    if s.startswith('(') and s.endswith(')'):
        # evaluate inner
        return [parse_str(part) for part in s[1:-1].split(',')]
    if s.startswith('"') and s.endswith('"'):
        # evaluate inner
        return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        # evaluate inner
        return s[1:-1]
    for conv in (int, float, lambda x: x):
        try:
            return conv(s)
        except ValueError:
            pass


class DemoEncoder(MessageEncoder):

    def decode(sef, encoded):
        # match [!][*|devicename][: *|paramname [: *|propname]] [=value]
        match = DEMO_RE.match(encoded)
        if match:
            novalue, devname, pname, propname, assign = match.groups()
            if assign:
                print "parsing", assign,
                assign = parse_str(assign)
                print "->", assign
            return messages.DemoRequest(
                novalue, devname, pname, propname, assign)
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

    def _encode_AsyncDataUnit(self, devname, pname, value, timestamp,
                              error=None, unit=''):
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
        return ['Help not yet implemented!',
                'ask Markus Zolliker about the protocol']


ENCODERS = {
    'pickle': PickleEncoder,
    'text': TextEncoder,
    'demo': DemoEncoder,
}


__ALL__ = ['ENCODERS']
