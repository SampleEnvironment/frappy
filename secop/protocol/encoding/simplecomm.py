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
from secop.lib.parsing import *

import re
import ast

SCPMESSAGE = re.compile(
    r'^(?:(?P<errorcode>[0-9@])\ )?(?P<device>[a-zA-Z0-9_\*]*)(?:/(?P<param>[a-zA-Z0-9_\*]*))+(?P<op>[-+=\?\ ])?(?P<value>.*)'
)


class SCPEncoder(MessageEncoder):

    def encode(self, msg):
        """msg object -> transport layer message"""
        # fun for Humans
        if isinstance(msg, HelpReply):
            r = []
            r.append("Try one of the following:")
            r.append("'/version?' to query the current version")
            r.append("'/modules?' to query the list of modules")
            r.append(
                "'<module>/parameters?' to query the list of params of a module"
            )
            r.append("'<module>/value?' to query the value of a module")
            r.append("'<module>/status?' to query the status of a module")
            r.append("'<module>/target=<new_value>' to move a module")
            r.append(
                "replies copy the request and are prefixed with an errorcode:")
            r.append(
                "0=OK,3=NoSuchCommand,4=NosuchDevice,5=NoSuchParam,6=SyntaxError,7=BadValue,8=Readonly,9=Forbidden,@=Async"
            )
            r.append("extensions: @-prefix as error-code,")
            r.append("'<module>/+' subscribe all params of module")
            r.append("'<module>/<param>+' subscribe a param of a module")
            r.append("use '-' instead of '+' to unsubscribe")
            r.append("'<module>/commands?' list of commands")
            r.append(
                "'<module>/<command>@[possible args] execute command (ex. 'stop@')"
            )
            return '\n'.join(r)

        return {
            ListDevicesRequest: lambda msg: "devices?",
            ListDevicesReply: lambda msg: "0 devices=" + repr(list(msg.list_of_devices)),
            GetVersionRequest: lambda msg: "version?",
            GetVersionReply: lambda msg: "0 version=%r" % msg.version,
            ListDeviceParamsRequest: lambda msg: "%s/parameters?" % msg.device,
            ListDeviceParamsReply: lambda msg: "0 %s/parameters=%r" % (msg.device, list(msg.params)),
            ReadValueRequest: lambda msg: "%s/value?" % msg.device,
            ReadValueReply: lambda msg: "0 %s/value?%r" % (msg.device, msg.value),
            WriteValueRequest: lambda msg: "%s/value=%r" % (msg.device, msg.value),
            WriteValueReply: lambda msg: "0 %s/value=%r" % (msg.device, msg.value),
            ReadParamRequest: lambda msg: "%s/%s?" % (msg.device, msg.param),
            ReadParamReply: lambda msg: "0 %s/%s?%r" % (msg.device, msg.param, msg.value),
            WriteParamRequest: lambda msg: "%s/%s=%r" % (msg.device, msg.param, msg.value),
            WriteParamReply: lambda msg: "0 %s/%s=%r" % (msg.device, msg.param, msg.readback_value),
            # extensions
            ReadAllDevicesRequest: lambda msg: "*/value?",
            ReadAllDevicesReply: lambda msg: ["0 %s/value=%s" % (m.device, m.value) for m in msg.readValueReplies],
            ListParamPropsRequest: lambda msg: "%s/%s/?" % (msg.device, msg.param),
            ListParamPropsReply: lambda msg: ["0 %s/%s/%s" % (msg.device, msg.param, p) for p in msg.props],
            AsyncDataUnit: lambda msg: "@ %s/%s=%r" % (msg.devname, msg.pname, msg.value),
            SubscribeRequest: lambda msg: "%s/%s+" % (msg.devname, msg.pname),
            # violates spec ! we would need the original request here....
            SubscribeReply: lambda msg: "0 / %r" % [repr(s) for s in msg.subscriptions],
            UnSubscribeRequest: lambda msg: "%s/%s+" % (msg.devname, msg.pname),
            # violates spec ! we would need the original request here....
            UnSubscribeReply: lambda msg: "0 / %r" % [repr(s) for s in msg.subscriptions],
            # errors
            # violates spec ! we would need the original request here....
            ErrorReply: lambda msg: "1 /%r" % msg.error,
            # violates spec ! we would need the original request here....
            InternalError: lambda msg: "1 /%r" % msg.error,
            # violates spec ! we would need the original request here....
            ProtocollError: lambda msg: "6 /%r" % msg.error,
            # violates spec ! we would need the original request here....
            CommandFailedError: lambda msg: "1 %s/%s" % (msg.device, msg.command),
            # violates spec ! we would need the original request here....
            NoSuchCommandError: lambda msg: "3 %s/%s" % (msg.device, msg.command),
            # violates spec ! we would need the original request here....
            NoSuchDeviceError: lambda msg: "4 %s/ %r" % (msg.device, msg.error),
            # violates spec ! we would need the original request here....
            NoSuchParamError: lambda msg: "5 %s/%s %r" % (msg.device, msg.param, msg.error),
            # violates spec ! we would need the original request here....
            ParamReadonlyError: lambda msg: "8 %s/%s %r" % (msg.device, msg.param, msg.error),
            # violates spec ! we would need the original request here....
            UnsupportedFeatureError: lambda msg: "3 / %r" % msg.feature,
            # violates spec ! we would need the original request here....
            InvalidParamValueError: lambda msg: "7 %s/%s=%r %r" % (msg.device, msg.param, msg.value, msg.error),
        }[msg.__class__](msg)

    def decode(self, encoded):
        """transport layer message -> msg object"""
        match = SCPMESSAGE.match(encoded)
        if not (match):
            return HelpRequest()
        err, dev, par, op, val = match.groups()
        if val is not None:
            try:
                val = ast.literal_eval(val)
            except Exception as e:
                return SyntaxError('while decoding %r: %s' % (encoded, e))
        if err == '@':
            # async
            if op == '=':
                return AsyncDataUnit(dev, par, val)
            return ProtocolError("Asyncupdates must have op = '='!")
        elif err is None:
            # request
            if op == '+':
                # subscribe
                if dev:
                    if par:
                        return SubscribeRequest(dev, par)
                    return SubscribeRequest(dev, '*')
            if op == '-':
                # unsubscribe
                if dev:
                    if par:
                        return UnsubscribeRequest(dev, par)
                    return UnsubscribeRequest(dev, '*')
            if op == '?':
                if dev is None:
                    # 'server' commands
                    if par == 'devices':
                        return ListDevicesRequest()
                    elif par == 'version':
                        return GetVersionRequest()
                    return ProtocolError()
                if par == 'parameters':
                    return ListDeviceParamsRequest(dev)
                elif par == 'value':
                    return ReadValueRequest(dev)
                elif dev == '*' and par == 'value':
                    return ReadAllDevicesRequest()
                else:
                    return ReadParamRequest(dev, par)
            elif op == '=':
                if dev and (par == 'value'):
                    return WriteValueRequest(dev, val)
                if par.endswith('/') and op == '?':
                    return ListParamPropsRequest(dev, par)
                return WriteParamRequest(dev, par, val)
        elif err == '0':
            # reply
            if dev == '':
                if par == 'devices':
                    return ListDevicesReply(val)
                elif par == 'version':
                    return GetVersionReply(val)
                return ProtocolError(encoded)
            if par == 'parameters':
                return ListDeviceParamsReply(dev, val)
            if par == 'value':
                if op == '?':
                    return ReadValueReply(dev, val)
                elif op == '=':
                    return WriteValueReply(dev, val)
                return ProtocolError(encoded)
            if op == '+':
                return SubscribeReply(ast.literal_eval(dev))
            if op == '-':
                return UnSubscribeReply(ast.literal_eval(dev))
            if op == '?':
                return ReadParamReply(dev, par, val)
            if op == '=':
                return WriteParamReply(dev, par, val)
            return ProtocolError(encoded)
        else:
            # error
            if err in ('1', '2'):
                return InternalError(encoded)
            elif err == '3':
                return NoSuchCommandError(dev, par)
            elif err == '4':
                return NoSuchDeviceError(dev, encoded)
            elif err == '5':
                return NoSuchParamError(dev, par, val)
            elif err == '7':
                return InvalidParamValueError(dev, par, val, encoded)
            elif err == '8':
                return ParamReadonlyError(dev, par, encoded)
            else:  # err == 6 or other stuff
                return ProtocollError(encoded)
