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
from secop.protocol.messages import *
from secop.protocol.errors import ProtocollError

import ast
import re
import json

# each message is like <messagetype> [ \space <messageargs> [ \space <json> ]] \lf

# note: the regex allow <> for spec for testing only!
DEMO_RE = re.compile(
    r"""^(?P<msgtype>[\*\?\w]+)(?:\s(?P<spec>[\w:<>]+)(?:\s(?P<json>.*))?)?$""", re.X)

#"""
# messagetypes:
IDENTREQUEST = '*IDN?'  # literal
IDENTREPLY = 'Sine2020WP7.1&ISSE, SECoP, V2016-11-30, rc1'  # literal
DESCRIPTIONSREQUEST = 'describe'  # literal
DESCRIPTIONREPLY = 'describing'  # +<id> +json
ENABLEEVENTSREQUEST = 'activate' # literal
ENABLEEVENTSREPLY = 'active'  # literal, is end-of-initial-data-transfer
DISABLEEVENTSREQUEST = 'deactivate'  # literal
DISABLEEVENTSREPLY = 'inactive'  # literal
COMMANDREQUEST = 'do'  # +module:command +json args (if needed)
COMMANDREPLY = 'doing'  # +module:command +json args (if needed)
WRITEREQUEST = 'change'  # +module[:parameter] +json_value -> NO direct reply, calls TRIGGER internally!
WRITEREPLY = 'changing'  # +module[:parameter] +json_value -> NO direct reply, calls TRIGGER internally!
TRIGGERREQUEST = 'read'  # +module[:parameter] -> NO direct reply, calls TRIGGER internally!
HEARTBEATREQUEST = 'ping'  # +nonce_without_space
HEARTBEATREPLY = 'pong'  # +nonce_without_space
EVENTTRIGGERREPLY = 'update'  # +module[:parameter] +json_result_value_with_qualifiers  NO REQUEST (use WRITE/TRIGGER)
EVENTCOMMANDREPLY = 'done'  # +module:command +json result (if needed)
#EVENTWRITEREPLY = 'changed'  # +module[:parameter] +json_result_value_with_qualifiers  NO REQUEST (use WRITE/TRIGGER)
ERRORREPLY = 'ERROR'  # +errorclass +json_extended_info
HELPREQUEST = 'help' # literal
HELPREPLY = 'helping'  # +line number +json_text
ERRORCLASSES = ['NoSuchDevice', 'NoSuchParameter', 'NoSuchCommand', 
                'CommandFailed', 'ReadOnly', 'BadValue', 'CommunicationFailed',
                'IsBusy', 'IsError', 'SyntaxError', 'InternalError',
                'CommandRunning', 'Disabled',]
# note: above strings need to be unique in the sense, that none is/or starts with another

class DemoEncoder(MessageEncoder):
    # map of msg to msgtype string as defined above.
    ENCODEMAP = {
        IdentifyRequest : (IDENTREQUEST,),
        IdentifyReply : (IDENTREPLY,),
        DescribeRequest : (DESCRIPTIONSREQUEST,),
        DescribeReply : (DESCRIPTIONREPLY, 'equipment_id', 'description',),
        ActivateRequest : (ENABLEEVENTSREQUEST,),
        ActivateReply : (ENABLEEVENTSREPLY,),
        DeactivateRequest: (DISABLEEVENTSREQUEST,),
        DeactivateReply : (DISABLEEVENTSREPLY,),
        CommandRequest : (COMMANDREQUEST, lambda msg: "%s:%s" % (msg.module, msg.command), 'arguments',),
        CommandReply : (COMMANDREPLY, lambda msg: "%s:%s" % (msg.module, msg.command), 'arguments',),
        WriteRequest : (WRITEREQUEST, lambda msg: "%s:%s" % (msg.module, msg.parameter) if msg.parameter else msg.module, 'value',),
        WriteReply : (WRITEREPLY, lambda msg: "%s:%s" % (msg.module, msg.parameter) if msg.parameter else msg.module, 'value',),
        PollRequest : (TRIGGERREQUEST, lambda msg: "%s:%s" % (msg.module, msg.parameter) if msg.parameter else msg.module, ),
        HeartbeatRequest : (HEARTBEATREQUEST, 'nonce',),
        HeartbeatReply : (HEARTBEATREPLY, 'nonce',),
        HelpMessage: (HELPREQUEST, ),
#        EventMessage : (EVENTREPLY, lambda msg: "%s:%s" % (msg.module, msg.parameter or (msg.command+'()')) 
#                                                if msg.parameter or msg.command else msg.module, 'value',),
        ErrorMessage : (ERRORREPLY, 'errorclass', 'errorinfo',),
        Value: (EVENTTRIGGERREPLY, lambda msg: "%s:%s" % (msg.module, msg.parameter or (msg.command+'()')) 
                                                if msg.parameter or msg.command else msg.module, 
                            lambda msg: [msg.value, msg.qualifiers] if msg.qualifiers else [msg.value]),
    }
    DECODEMAP = {
        IDENTREQUEST : lambda spec, data: IdentifyRequest(),
        IDENTREPLY :  lambda spec, data: IdentifyReply(encoded), # handled specially, listed here for completeness
        DESCRIPTIONSREQUEST : lambda spec, data: DescribeRequest(),
        DESCRIPTIONREPLY : lambda spec, data: DescribeReply(equipment_id=spec[0], description=data),
        ENABLEEVENTSREQUEST : lambda spec, data: ActivateRequest(),
        ENABLEEVENTSREPLY: lambda spec, data:ActivateReply(),
        DISABLEEVENTSREQUEST: lambda spec, data:DeactivateRequest(),
        DISABLEEVENTSREPLY: lambda spec, data:DeactivateReply(),
        COMMANDREQUEST: lambda spec, data:CommandRequest(module=spec[0], command=spec[1], arguments=data),
        COMMANDREPLY: lambda spec, data: CommandReply(module=spec[0], command=spec[1], arguments=data),
        WRITEREQUEST: lambda spec, data: WriteRequest(module=spec[0], parameter=spec[1], value=data),
        WRITEREPLY:lambda spec, data:WriteReply(module=spec[0], parameter=spec[1], value=data),
        TRIGGERREQUEST:lambda spec, data:PollRequest(module=spec[0], parameter=spec[1]),
        HEARTBEATREQUEST:lambda spec, data:HeartbeatRequest(nonce=spec[0]),
        HEARTBEATREPLY:lambda spec, data:HeartbeatReply(nonce=spec[0]),
        HELPREQUEST: lambda spec, data:HelpMessage(),
#        HELPREPLY: lambda spec, data:None,  # ignore this
        ERRORREPLY:lambda spec, data:ErrorMessage(errorclass=spec[0], errorinfo=data),
        EVENTTRIGGERREPLY:lambda spec, data:Value(module=spec[0], parameter=spec[1], value=data[0], qualifiers=data[1] if len(data)>1 else {}),
        EVENTCOMMANDREPLY: lambda spec, data:None,  # ignore this
#        EVENTWRITEREPLY:lambda spec, data:Value(module=spec[0], parameter=spec[1], value=data[0], qualifiers=data[1] if len(data)>1 else {}),
        }

    def __init__(self, *args, **kwds):
        MessageEncoder.__init__(self, *args, **kwds)
        self.tests()

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
            """ %(IDENTREQUEST, DESCRIPTIONSREQUEST, TRIGGERREQUEST, 
                WRITEREQUEST, COMMANDREQUEST, HEARTBEATREQUEST,
                ENABLEEVENTSREQUEST, DISABLEEVENTSREQUEST)
            return '\n'.join('%s %d %s' %(HELPREPLY, i+1, l.strip()) for i,l in enumerate(text.split('\n')[:-1]))
        for msgcls, parts in self.ENCODEMAP.items():
            if isinstance(msg, msgcls):
                # resolve lambdas
                parts = [parts[0]] + [p(msg) if callable(p) else getattr(msg, p) for p in parts[1:]]
                if len(parts) > 1:
                    parts[1] = str(parts[1])
                if len(parts) == 3:
                    parts[2] = json.dumps(parts[2])
                return ' '.join(parts)
                

    def decode(self, encoded):
        # first check beginning
        match = DEMO_RE.match(encoded)
        if not match:
            print repr(encoded), repr(IDENTREPLY)
            if encoded == IDENTREPLY:  # XXX:better just check the first 2 parts...
                return IdentifyReply(version_string=encoded)
        
            return HelpMessage()
            return ErrorMessage(errorclass='SyntaxError', 
                                errorinfo='Regex did not match!',
                                is_request=True)
        msgtype, msgspec, data = match.groups()
        if msgspec is None and data:
            return ErrorMessage(errorclass='InternalError', 
                                errorinfo='Regex matched json, but not spec!',
                                is_request=True)
                                
        if msgtype in self.DECODEMAP:
            if msgspec and ':' in msgspec:
                msgspec = msgspec.split(':', 1)
            else:
                msgspec = (msgspec, None)
            if data:
                try:
                    data = json.loads(data)
                except ValueError as err:
                    return ErrorMessage(errorclass='BadValue',
                                        errorinfo=[repr(err), str(encoded)])
            return self.DECODEMAP[msgtype](msgspec, data)
        return ErrorMessage(errorclass='SyntaxError', 
                            errorinfo='%r: No Such Messagetype defined!' % encoded,
                            is_request=True)


    def tests(self):
        print "---- Testing encoding  -----"
        for msgclass, parts in sorted(self.ENCODEMAP.items()):
            print msgclass
            e=self.encode(msgclass(module='<module>',parameter='<paramname>',value=2.718,equipment_id='<id>',description='descriptive data',command='<cmd>',arguments='<arguments>',nonce='<nonce>',errorclass='InternalError',errorinfo='nix'))
            print e
            print self.decode(e)
            print
        print "---- Testing decoding  -----"
        for msgtype, _ in sorted(self.DECODEMAP.items()):
            msg = '%s a:b 3' % msgtype
            if msgtype in [EVENTTRIGGERREPLY]:#, EVENTWRITEREPLY]:
                msg = '%s a:b [3,{"t":193868}]' % msgtype
            print msg
            d=self.decode(msg)
            print d
            print self.encode(d)
            print
        print "---- Testing done -----"
        


