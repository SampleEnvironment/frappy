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

from secop.protocol.encoding import MessageEncoder
from secop.protocol.messages import *
from secop.protocol.errors import ProtocolError

import ast
import re


def floatify(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        try:
            return float(s)
        except (ValueError, TypeError):
            return s


def devspec(msg, result=''):
    if isinstance(msg, Message):
        devs = ','.join(msg.devs)
        pars = ','.join(msg.pars)
        props = ','.join(msg.props)
    else:
        devs = msg.dev
        pars = msg.par
        props = msg.prop
    if devs:
        result = '%s %s' % (result, devs)
        if pars:
            result = '%s:%s' % (result, pars)
            if props:
                result = '%s:%s' % (result, props)
    return result.strip()


def encode_value(value, prefix='', targetvalue='', cmd=''):
    result = [prefix]
    if value.dev:
        result.append(' ')
        result.append(value.dev)
        if value.param:
            result.append(':%s' % value.param)
            if value.prop:
                result.append(':%s' % value.prop)
    # only needed for WriteMessages
    if targetvalue:
        result.append('=%s' % repr(targetvalue))
    # only needed for CommandMessages
    if cmd:
        result.append(':%s' % cmd)
    if value.value != Ellipsis:
        # results always have a ';'
        result.append('=%s;' % repr(value.value))
        result.append(';'.join('%s=%s' % (qn, repr(qv))
                               for qn, qv in value.qualifiers.items()))
    return ''.join(result).strip()


DEMO_RE_ERROR = re.compile(
    r"""^error\s(?P<errortype>\w+)\s(?P<msgtype>\w+)?(?:\s(?P<devs>\*|[\w,]+)(?:\:(?P<pars>\*|[\w,]+)(?:\:(?P<props>\*|[\w,]+))?)?)?(?:(?:\=(?P<target>[^=;\s"]*))|(?:\((?P<cmdargs>[^\)]*)\)))?(?:\s"(?P<errorstring>[^"]*)")$""",
    re.X)
DEMO_RE_OTHER = re.compile(
    r"""^(?P<msgtype>\w+)(?:\s(?P<devs>\*|[\w,]+)(?:\:(?P<pars>\*|[\w,]+)(?:\:(?P<props>\*|[\w,]+))?)?)?(?:(?:\=(?P<target>[^=;]*))|(?::(?P<cmd>\w+)\((?P<args>[^\)]*)\)))?(?:=(?P<readback>[^;]+);(?P<qualifiers>.*))?$""",
    re.X)


class DemoEncoder(MessageEncoder):

    def __init__(self, *args, **kwds):
        MessageEncoder.__init__(self, *args, **kwds)
        self.result = []  # for decoding
        self.expect_lines = 1
        # self.tests()

    def encode(self, msg):
        """msg object -> transport layer message"""
        # fun for Humans
        if isinstance(msg, HelpMessage):
            r = ['#5']
            r.append("help Try one of the following:")
            r.append("help 'list' to query a list of modules")
            r.append("help 'read <module>' to read a module")
            r.append("help 'list <module>' to query a list of parameters")
            r.append("help ... more to come")
            return '\n'.join(r)

        if isinstance(msg, (ListMessage, SubscribeMessage, UnsubscribeMessage,
                            TriggerMessage)):
            msgtype = msg.MSGTYPE
            if msg.result:
                if msg.devs:
                    # msg.result is always a list!
                    return "%s=%s" % (devspec(msg, msgtype),
                                      ','.join(map(str, msg.result)))
                return "%s=%s" % (msgtype, ','.join(map(str, msg.result)))
            return devspec(msg, msgtype).strip()

        if isinstance(msg, (ReadMessage, PollMessage, EventMessage)):
            msgtype = msg.MSGTYPE
            result = []
            if len(msg.result or []) > 1:
                result.append("#%d" % len(msg.result))
            for val in msg.result or []:
                # encode 1..N replies
                result.append(encode_value(val, msgtype))
            if not msg.result:
                # encode a request (no results -> reply, else an error would
                # have been sent)
                result.append(devspec(msg, msgtype))
            return '\n'.join(result)

        if isinstance(msg, WriteMessage):
            result = []
            if len(msg.result or []) > 1:
                result.append("#%d" % len(msg.result))
            for val in msg.result or []:
                # encode 1..N replies
                result.append(
                    encode_value(
                        val, 'write', targetvalue=msg.target))
            if not msg.result:
                # encode a request (no results -> reply, else an error would
                # have been sent)
                result.append('%s=%r' % (devspec(msg, 'write'), msg.target))
            return '\n'.join(result)

        if isinstance(msg, CommandMessage):
            result = []
            if len(msg.result or []) > 1:
                result.append("#%d" % len(msg.result))
            for val in msg.result or []:
                # encode 1..N replies
                result.append(
                    encode_value(
                        val,
                        'command',
                        cmd='%s(%s)' % (msg.cmd, ','.join(msg.args))))
            if not msg.result:
                # encode a request (no results -> reply, else an error would
                # have been sent)
                result.append('%s:%s(%s)' % (devspec(msg, 'command'), msg.cmd,
                                             ','.join(msg.args)))
            return '\n'.join(result)

        if isinstance(msg, ErrorMessage):
            return ('%s %s' % (devspec(msg, 'error %s' % msg.errortype),
                               msg.errorstring)).strip()

        return 'Can not handle object %r!' % msg

    def decode(self, encoded):
        if encoded.startswith('#'):
            # XXX: check if last message was complete
            self.expect_lines = int(encoded[1:])
            if self.result:
                # XXX: also flag an error?
                self.result = []
            return None

        if encoded == '':
            return HelpMessage()
        # now decode the message and append to self.result
        msg = self.decode_single_message(encoded)
        if msg:
            # XXX: check if messagetype is the same as the already existing,
            # else error
            self.result.append(msg)
        else:
            # XXX: flag an error?
            return HelpMessage()

        self.expect_lines -= 1
        if self.expect_lines <= 0:
            # reconstruct a multi-reply-message from the entries
            # return the first message, but extend the result list first
            # if there is only 1 message, just return this
            res = self.result.pop(0)
            while self.result:
                m = self.result.pop(0)
                res.result.append(m.result[0])
            self.expect_lines = 1
            return res

        # no complete message yet
        return None

    def decode_single_message(self, encoded):
        # just decode a single message line

        # 1) check for error msgs (more specific first)
        m = DEMO_RE_ERROR.match(encoded)
        if m:
            return ErrorMessage(**m.groupdict())

        # 2) check for 'normal' message
        m = DEMO_RE_OTHER.match(encoded)
        if m:
            mgroups = m.groupdict()
            msgtype = mgroups.pop('msgtype')

            # reformat devspec
            def helper(stuff, sep=','):
                if not stuff:
                    return []
                if sep in stuff:
                    return stuff.split(sep)
                return [stuff]

            devs = helper(mgroups.pop('devs'))
            pars = helper(mgroups.pop('pars'))
            props = helper(mgroups.pop('props'))

            # sugar for listing stuff:
            # map list -> list *
            # map list x -> list x:*
            # map list x:y -> list x:y:*
            if msgtype == LIST:
                if not devs:
                    devs = ['*']
                elif devs[0] != '*':
                    if not pars:
                        pars = ['*']
                    elif pars[0] != '*':
                        if not props:
                            props = ['*']

            # reformat cmdargs
            args = ast.literal_eval(mgroups.pop('args') or '()')
            if msgtype == COMMAND:
                mgroups['args'] = args

            # reformat qualifiers
            print(mgroups)
            quals = dict(
                qual.split('=', 1)
                for qual in helper(mgroups.pop('qualifiers', ';')))

            # reformat value
            result = []
            readback = mgroups.pop('readback')
            if readback or quals:
                valargs = dict()
                if devs:
                    valargs['dev'] = devs[0]
                if pars:
                    valargs['par'] = pars[0]
                if props:
                    valargs['prop'] = props[0]
                result = [Value(floatify(readback), quals, **valargs)]
            if msgtype == LIST and result:
                result = [n.strip() for n in readback.split(',')]

            # construct messageobj
            if msgtype in MESSAGE:
                return MESSAGE[msgtype](devs=devs,
                                        pars=pars,
                                        props=props,
                                        result=result,
                                        **mgroups)

        return ErrorMessage(
            errortype="SyntaxError", errorstring="Can't handle %r" % encoded)

    def tests(self):
        testmsg = [
            'list',
            'list *',
            'list device',
            'list device:param1,param2',
            'list *:*',
            'list *=ts,tcoil,mf,lhe,ln2;',
            'read blub=12;t=3',
            'command ts:stop()',
            'command mf:quench(1,"now")',
            'error GibbetNich query x:y:z=9 "blubub blah"',
            '#3',
            'read blub:a=12;t=3',
            'read blub:b=13;t=3.1',
            'read blub:c=14;t=3.3',
        ]
        for m in testmsg:
            print(repr(m))
            print(self.decode(m))
            print()


DEMO_RE_MZ = re.compile(
    r"""^(?P<type>[a-z]+)?       # request type word (read/write/list/...)
                         \ ?                    # optional space
                         (?P<device>[a-z][a-z0-9_]*)?  # optional devicename
                         (?:\:(?P<param>[a-z0-9_]*) # optional ':'+paramname
                            (?:\:(?P<prop>[a-z0-9_]*))?)? # optinal ':' + propname
                         (?:(?P<op>[=\?])(?P<value>[^;]+)(?:\;(?P<quals>.*))?)?$""",
    re.X)


class DemoEncoder_MZ(MessageEncoder):

    def decode(sef, encoded):
        m = DEMO_RE_MZ.match(encoded)
        if m:
            print("implement me !")
        return HelpRequest()

    def encode(self, msg):
        """msg object -> transport layer message"""
        # fun for Humans
        if isinstance(msg, HelpReply):
            r = []
            r.append("Try one of the following:")
            r.append("'list' to query a list of modules")
            r.append("'read <module>' to read a module")
            r.append("'list <module>' to query a list of parameters")
            r.append("... more to come")
            return '\n'.join(r)

        return {
            ListModulesRequest: lambda msg: "list",
            ListModulesReply: lambda msg: "list=%s" % ','.join(sorted(msg.list_of_devices)),
            GetVersionRequest: lambda msg: "version",
            GetVersionReply: lambda msg: "version=%r" % msg.version,
            ListModuleParamsRequest: lambda msg: "list %s" % msg.device,
            # do not include a '.' as param name!
            ListModuleParamsReply: lambda msg: "list %s=%s" % (msg.device, ','.join(sorted(msg.params.keys()))),
            ReadValueRequest: lambda msg: "read %s" % msg.device,
            ReadValueReply: lambda msg: "read %s=%r" % (msg.device, msg.value),
            WriteValueRequest: lambda msg: "write %s=%r" % (msg.device, msg.value),
            WriteValueReply: lambda msg: "write %s=%r" % (msg.device, msg.readback_value),
            ReadParamRequest: lambda msg: "read %s:%s" % (msg.device, msg.param),
            ReadParamReply: lambda msg: "read %s:%s=%r" % (msg.device, msg.param, msg.value),
            WriteParamRequest: lambda msg: "write %s:%s=%r" % (msg.device, msg.param, msg.value),
            WriteParamReply: lambda msg: "write %s:%s=%r" % (msg.device, msg.param, msg.readback_value),
            # extensions
            ReadAllModulesRequest: lambda msg: "",
            ReadAllModulesReply: lambda msg: "",
            ListParamPropsRequest: lambda msg: "readprop %s:%s" % (msg.device, msg.param),
            ListParamPropsReply: lambda msg: ["readprop %s:%s" % (msg.device, msg.param)] + ["%s:%s:%s=%s" % (msg.device, msg.param, k, v) for k, v in sorted(msg.props.items())],
            ReadPropertyRequest: lambda msg: "readprop %s:%s:%s" % (msg.device, msg.param, msg.prop),
            ReadPropertyReply: lambda msg: "readprop %s:%s:%s=%s" % (msg.device, msg.param, msg.prop, msg.value),
            AsyncDataUnit: lambda msg: "",
            SubscribeRequest: lambda msg: "subscribe %s:%s" % (msg.device, msg.param) if msg.param else ("subscribe %s" % msg.device),
            SubscribeReply: lambda msg: "subscribe %s:%s" % (msg.device, msg.param) if msg.param else ("subscribe %s" % msg.device),
            UnSubscribeRequest: lambda msg: "",
            UnSubscribeReply: lambda msg: "",
            CommandRequest: lambda msg: "command %s:%s" % (msg.device, msg.command),
            CommandReply: lambda msg: "command %s:%s" % (msg.device, msg.command),
            # errors
            ErrorReply: lambda msg: "",
            InternalError: lambda msg: "",
            ProtocolError: lambda msg: "",
            CommandFailedError: lambda msg: "error CommandError %s:%s %s" % (msg.device, msg.param, msg.error),
            NoSuchCommandError: lambda msg: "error NoSuchCommand %s:%s" % (msg.device, msg.param, msg.error),
            NoSuchModuleError: lambda msg: "error NoSuchModule %s" % msg.device,
            NoSuchParamError: lambda msg: "error NoSuchParameter %s:%s" % (msg.device, msg.param),
            ParamReadonlyError: lambda msg: "",
            UnsupportedFeatureError: lambda msg: "",
            InvalidParamValueError: lambda msg: "",
        }[msg.__class__](msg)
