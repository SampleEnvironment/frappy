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

from __future__ import print_function


# Base class
class MessageEncoder(object):
    """en/decode a single Messageobject"""

    def encode(self, msg):
        """encodes the given message object into a frame"""
        raise NotImplementedError

    def decode(self, encoded):
        """decodes the given frame to a message object"""
        raise NotImplementedError


import re
import json

#from secop.lib.parsing import format_time
from secop.protocol.messages import Value, IdentifyRequest, IdentifyReply, \
    DescribeRequest, DescribeReply, ActivateRequest, ActivateReply, \
    DeactivateRequest, DeactivateReply, CommandRequest, CommandReply, \
    WriteRequest, WriteReply, PollRequest, HeartbeatRequest, HeartbeatReply, \
    ErrorMessage, HelpMessage
#from secop.protocol.errors import ProtocolError


# each message is like <messagetype> [ \space <messageargs> [ \space
# <json> ]] \lf

# note: the regex allow <> for spec for testing only!
SECOP_RE = re.compile(
    r"""^(?P<msgtype>[\*\?\w]+)(?:\s(?P<spec>[\w:<>]+)(?:\s(?P<json>.*))?)?$""",
    re.X)

#"""
# messagetypes:
IDENTREQUEST = '*IDN?'  # literal
# literal! first part is fixed!
#IDENTREPLY = 'SECoP, SECoPTCP, V2016-11-30, rc1'
#IDENTREPLY = 'SINE2020&ISSE,SECoP,V2016-11-30,rc1'
IDENTREPLY = 'SINE2020&ISSE,SECoP,V2017-01-25,rc1'
DESCRIPTIONSREQUEST = 'describe'  # literal
DESCRIPTIONREPLY = 'describing'  # +<id> +json
ENABLEEVENTSREQUEST = 'activate'  # literal
ENABLEEVENTSREPLY = 'active'  # literal, is end-of-initial-data-transfer
DISABLEEVENTSREQUEST = 'deactivate'  # literal
DISABLEEVENTSREPLY = 'inactive'  # literal
COMMANDREQUEST = 'do'  # +module:command +json args (if needed)
# +module:command +json args (if needed) # send after the command finished !
COMMANDREPLY = 'done'
# +module[:parameter] +json_value -> NO direct reply, calls TRIGGER internally!
WRITEREQUEST = 'change'
# +module[:parameter] +json_value # send with the read back value
WRITEREPLY = 'changed'
# +module[:parameter] -> NO direct reply, calls TRIGGER internally!
TRIGGERREQUEST = 'read'
EVENT = 'update'  # +module[:parameter] +json_value (value, qualifiers_as_dict)
HEARTBEATREQUEST = 'ping'  # +nonce_without_space
HEARTBEATREPLY = 'pong'  # +nonce_without_space
ERRORREPLY = 'error'  # +errorclass +json_extended_info
HELPREQUEST = 'help'  # literal
HELPREPLY = 'helping'  # +line number +json_text
ERRORCLASSES = [
    'NoSuchModule',
    'NoSuchParameter',
    'NoSuchCommand',
    'CommandFailed',
    'ReadOnly',
    'BadValue',
    'CommunicationFailed',
    'IsBusy',
    'IsError',
    'ProtocolError',
    'InternalError',
    'CommandRunning',
    'Disabled',
]

# note: above strings need to be unique in the sense, that none is/or
# starts with another


def encode_cmd_result(msgobj):
    q = msgobj.qualifiers.copy()
    if 't' in q:
        q['t'] = str(q['t'])
    return msgobj.result, q


def encode_value_data(vobj):
    q = vobj.qualifiers.copy()
    if 't' in q:
        q['t'] = str(q['t'])
    return vobj.value, q


def encode_error_msg(emsg):
    # note: result is JSON-ified....
    return [
        emsg.origin, dict((k, getattr(emsg, k)) for k in emsg.ARGS
                          if k != 'origin')
    ]


class SECoPEncoder(MessageEncoder):
    # map of msg to msgtype string as defined above.
    ENCODEMAP = {
        IdentifyRequest: (IDENTREQUEST, ),
        IdentifyReply: (IDENTREPLY, ),
        DescribeRequest: (DESCRIPTIONSREQUEST, ),
        DescribeReply: (
            DESCRIPTIONREPLY,
            'equipment_id',
            'description', ),
        ActivateRequest: (ENABLEEVENTSREQUEST, ),
        ActivateReply: (ENABLEEVENTSREPLY, ),
        DeactivateRequest: (DISABLEEVENTSREQUEST, ),
        DeactivateReply: (DISABLEEVENTSREPLY, ),
        CommandRequest: (
            COMMANDREQUEST,
            lambda msg: "%s:%s" % (msg.module, msg.command),
            'arguments', ),
        CommandReply: (
            COMMANDREPLY,
            lambda msg: "%s:%s" % (msg.module, msg.command),
            encode_cmd_result, ),
        WriteRequest: (
            WRITEREQUEST,
            lambda msg: "%s:%s" % (
                msg.module, msg.parameter) if msg.parameter else msg.module,
            'value', ),
        WriteReply: (
            WRITEREPLY,
            lambda msg: "%s:%s" % (
                msg.module, msg.parameter) if msg.parameter else msg.module,
            'value', ),
        PollRequest: (
            TRIGGERREQUEST,
            lambda msg: "%s:%s" % (
                msg.module, msg.parameter) if msg.parameter else msg.module,
        ),
        HeartbeatRequest: (
            HEARTBEATREQUEST,
            'nonce', ),
        HeartbeatReply: (
            HEARTBEATREPLY,
            'nonce', ),
        HelpMessage: (HELPREQUEST, ),
        ErrorMessage: (
            ERRORREPLY,
            "errorclass",
            encode_error_msg, ),
        Value: (
            EVENT,
            lambda msg: "%s:%s" % (msg.module, msg.parameter or (
                msg.command + '()')) if msg.parameter or msg.command else msg.module,
            encode_value_data, ),
    }
    DECODEMAP = {
        IDENTREQUEST: lambda spec, data: IdentifyRequest(),
        # handled specially, listed here for completeness
        # IDENTREPLY: lambda spec, data: IdentifyReply(encoded),
        DESCRIPTIONSREQUEST: lambda spec, data: DescribeRequest(),
        DESCRIPTIONREPLY: lambda spec, data: DescribeReply(equipment_id=spec[0], description=data),
        ENABLEEVENTSREQUEST: lambda spec, data: ActivateRequest(),
        ENABLEEVENTSREPLY: lambda spec, data: ActivateReply(),
        DISABLEEVENTSREQUEST: lambda spec, data: DeactivateRequest(),
        DISABLEEVENTSREPLY: lambda spec, data: DeactivateReply(),
        COMMANDREQUEST: lambda spec, data: CommandRequest(module=spec[0], command=spec[1], arguments=data),
        COMMANDREPLY: lambda spec, data: CommandReply(module=spec[0], command=spec[1], result=data),
        WRITEREQUEST: lambda spec, data: WriteRequest(module=spec[0], parameter=spec[1], value=data),
        WRITEREPLY: lambda spec, data: WriteReply(module=spec[0], parameter=spec[1], value=data),
        TRIGGERREQUEST: lambda spec, data: PollRequest(module=spec[0], parameter=spec[1]),
        HEARTBEATREQUEST: lambda spec, data: HeartbeatRequest(nonce=spec[0]),
        HEARTBEATREPLY: lambda spec, data: HeartbeatReply(nonce=spec[0]),
        HELPREQUEST: lambda spec, data: HelpMessage(),
        #        HELPREPLY: lambda spec, data:None,  # ignore this
        ERRORREPLY: lambda spec, data: ErrorMessage(errorclass=spec[0], errorinfo=data),
        EVENT: lambda spec, data: Value(module=spec[0], parameter=spec[1], value=data[0],
                                        qualifiers=data[1] if len(data) > 1 else {}),
    }

    def __init__(self, *args, **kwds):
        MessageEncoder.__init__(self, *args, **kwds)
        # self.tests()

    def encode(self, msg):
        """msg object -> transport layer message"""
        # fun for Humans
        if isinstance(msg, HelpMessage):
            text = """Try one of the following:
            '%s' to query protocol version
            '%s' to read the description
            '%s <module>[:<parameter>]' to request reading a value
            '%s <module>[:<parameter>] value' to request changing a value
            '%s <module>[:<command>()]' to execute a command
            '%s <nonce>' to request a heartbeat response
            '%s' to activate async updates
            '%s' to deactivate updates
            """ % (IDENTREQUEST, DESCRIPTIONSREQUEST, TRIGGERREQUEST,
                   WRITEREQUEST, COMMANDREQUEST, HEARTBEATREQUEST,
                   ENABLEEVENTSREQUEST, DISABLEEVENTSREQUEST)
            return '\n'.join('%s %d %s' % (HELPREPLY, i + 1, l.strip())
                             for i, l in enumerate(text.split('\n')[:-1]))
        if isinstance(msg, HeartbeatRequest):
            if msg.nonce:
                return 'ping %s' % msg.nonce
            return 'ping'
        if isinstance(msg, HeartbeatReply):
            if msg.nonce:
                return 'pong %s' % msg.nonce
            return 'pong'
        for msgcls, parts in self.ENCODEMAP.items():
            if isinstance(msg, msgcls):
                # resolve lambdas
                parts = [parts[0]] + [
                    p(msg) if callable(p) else getattr(msg, p)
                    for p in parts[1:]
                ]
                if len(parts) > 1:
                    parts[1] = str(parts[1])
                if len(parts) == 3:
                    parts[2] = json.dumps(parts[2])
                return ' '.join(parts)

    def decode(self, encoded):
        # first check beginning
        match = SECOP_RE.match(encoded)
        if not match:
            print(repr(encoded), repr(IDENTREPLY))
            if encoded == IDENTREPLY:  # XXX:better just check the first 2 parts...
                return IdentifyReply(version_string=encoded)

            return HelpMessage()
#            return ErrorMessage(errorclass='Protocol',
#                                errorinfo='Regex did not match!',
#                                is_request=True)
        msgtype, msgspec, data = match.groups()
        if msgspec is None and data:
            return ErrorMessage(
                errorclass='Internal',
                errorinfo='Regex matched json, but not spec!',
                is_request=True,
                origin=encoded)

        if msgtype in self.DECODEMAP:
            if msgspec and ':' in msgspec:
                msgspec = msgspec.split(':', 1)
            else:
                msgspec = (msgspec, None)
            if data:
                try:
                    data = json.loads(data)
                except ValueError as err:
                    return ErrorMessage(
                        errorclass='BadValue',
                        errorinfo=[repr(err), str(encoded)],
                        origin=encoded)
            msg = self.DECODEMAP[msgtype](msgspec, data)
            msg.setvalue("origin", encoded)
            return msg
        return ErrorMessage(
            errorclass='Protocol',
            errorinfo='%r: No Such Messagetype defined!' % encoded,
            is_request=True,
            origin=encoded)

    def tests(self):
        print("---- Testing encoding  -----")
        for msgclass in sorted(self.ENCODEMAP):
            print(msgclass)
            e = self.encode(
                msgclass(
                    module='<module>',
                    parameter='<paramname>',
                    value=2.718,
                    equipment_id='<id>',
                    description='descriptive data',
                    command='<cmd>',
                    arguments='<arguments>',
                    nonce='<nonce>',
                    errorclass='InternalError',
                    errorinfo='nix'))
            print(e)
            print(self.decode(e))
            print()
        print("---- Testing decoding  -----")
        for msgtype, _ in sorted(self.DECODEMAP.items()):
            msg = '%s a:b 3' % msgtype
            if msgtype == EVENT:
                msg = '%s a:b [3,{"t":193868}]' % msgtype
            print(msg)
            d = self.decode(msg)
            print(d)
            print(self.encode(d))
            print()
        print("---- Testing done -----")


ENCODERS = {
    'secop': SECoPEncoder,
}

__ALL__ = ['ENCODERS']
