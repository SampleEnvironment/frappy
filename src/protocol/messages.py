#  -*- coding: utf-8 -*-
# *****************************************************************************
#
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

"""Define SECoP Messages"""

REQUEST = 'request'
REPLY = 'reply'
ERROR = 'error'


# base classes
class Message(object):
    ARGS = []

    def __init__(self, *args, **kwds):
        names = self.ARGS[:]
        if len(args) > len(names):
            raise TypeError('%s.__init__() takes only %d argument(s) (%d given)' %
                            (self.__class__, len(names), len(args)))
        for arg in args:
            self.__dict__[names.pop(0)] = arg
        # now check keyworded args if any
        for k, v in kwds.items():
            if k not in names:
                if k in self.ARGS:
                    raise TypeError('__init__() got multiple values for '
                                    'keyword argument %r' % k)
                raise TypeError('__init__() got an unexpected keyword '
                                'argument %r' % k)
            names.remove(k)
            self.__dict__[k] = v
        for name in names:
            self.__dict__[name] = None
#        if names:
#            raise TypeError('__init__() takes at least %d arguments (%d given)'
#                            % (len(self.ARGS), len(args)+len(kwds)))
        self.NAME = (self.__class__.__name__[:-len(self.TYPE)] or
                     self.__class__.__name__)

    def __repr__(self):
        return self.__class__.__name__ + '(' + \
            ', '.join('%s=%r' % (k, getattr(self, k))
                      for k in self.ARGS if getattr(self, k) is not None) + ')'


class Request(Message):
    TYPE = REQUEST


class Reply(Message):
    TYPE = REPLY


class ErrorReply(Message):
    TYPE = ERROR

# for DEMO


class DemoRequest(Request):
    ARGS = ['novalue', 'devname', 'paramname', 'propname', 'assign']


class DemoReply(Reply):
    ARGS = ['lines']


# actuall message objects
class ListDevicesRequest(Request):
    pass


class ListDevicesReply(Reply):
    ARGS = ['list_of_devices', 'descriptive_data']


class ListDeviceParamsRequest(Request):
    ARGS = ['device']


class ListDeviceParamsReply(Reply):
    ARGS = ['device', 'params']


class ReadValueRequest(Request):
    ARGS = ['device', 'maxage']


class ReadValueReply(Reply):
    ARGS = ['device', 'value', 'timestamp', 'error', 'unit']


class WriteValueRequest(Request):
    ARGS = ['device', 'value', 'unit']  # unit???


class WriteValueReply(Reply):
    ARGS = ['device', 'value', 'timestamp', 'error', 'unit']


class ReadAllDevicesRequest(Request):
    ARGS = ['maxage']


class ReadAllDevicesReply(Reply):
    ARGS = ['readValueReplies']


class ListParamPropsRequest(Request):
    ARGS = ['device', 'param']


class ListParamPropsReply(Request):
    ARGS = ['device', 'param', 'props']


class ReadParamRequest(Request):
    ARGS = ['device', 'param', 'maxage']


class ReadParamReply(Reply):
    ARGS = ['device', 'param', 'value', 'timestamp', 'error', 'unit']


class WriteParamRequest(Request):
    ARGS = ['device', 'param', 'value']


class WriteParamReply(Reply):
    ARGS = ['device', 'param', 'readback_value', 'timestamp', 'error', 'unit']


class RequestAsyncDataRequest(Request):
    ARGS = ['device', 'params']


class RequestAsyncDataReply(Reply):
    ARGS = ['device', 'paramvalue_list']


class AsyncDataUnit(ReadParamReply):
    ARGS = ['devname', 'pname', 'value', 'timestamp', 'error', 'unit']


# ERRORS
########

class ErrorReply(Reply):
    ARGS = ['error']


class InternalError(ErrorReply):
    ARGS = ['error']


class ProtocollError(ErrorReply):
    ARGS = ['error']


class NoSuchDeviceError(ErrorReply):
    ARGS = ['device']


class NoSuchParamError(ErrorReply):
    ARGS = ['device', 'param']


class ParamReadonlyError(ErrorReply):
    ARGS = ['device', 'param']


class UnsupportedFeatureError(ErrorReply):
    ARGS = ['feature']


class NoSuchCommandError(ErrorReply):
    ARGS = ['device', 'command']


class CommandFailedError(ErrorReply):
    ARGS = ['device', 'command']


class InvalidParamValueError(ErrorReply):
    ARGS = ['device', 'param', 'value', 'error']

# Fun!


class HelpRequest(Request):
    pass


class HelpReply(Reply):
    pass
