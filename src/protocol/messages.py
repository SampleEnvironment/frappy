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
        if names:
            raise TypeError('__init__() takes at least %d arguments (%d given)'
                            % len(self.ARGS), len(args)+len(kwds))
        self.NAME = (self.__class__.__name__[:-len(self.TYPE)] or
                     self.__class__.__name__)


class Request(Message):
    TYPE = REQUEST


class Reply(Message):
    TYPE = REPLY


class ErrorReply(Message):
    TYPE = ERROR


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
    ARGS = ['device', 'param', 'value', 'timestamp', 'error', 'unit']


class ListOfFeaturesRequest(Request):
    pass


class ListOfFeaturesReply(Reply):
    ARGS = ['features']


class ActivateFeatureRequest(Request):
    ARGS = ['feature']


class ActivateFeatureReply(Reply):
    # Ack style or Error
    # maybe should reply with active features?
    pass


class ProtocollError(ErrorReply):
    ARGS = ['msgtype', 'msgname', 'msgargs']


class ErrorReply(Reply):
    ARGS = ['error']


class NoSuchDeviceErrorReply(ErrorReply):
    ARGS = ['device']


class NoSuchParamErrorReply(ErrorReply):
    ARGS = ['device', 'param']


class ParamReadonlyErrorReply(ErrorReply):
    ARGS = ['device', 'param']


class UnsupportedFeatureErrorReply(ErrorReply):
    ARGS = ['feature']


class NoSuchCommandErrorReply(ErrorReply):
    ARGS = ['device', 'command']


class CommandFailedErrorReply(ErrorReply):
    ARGS = ['device', 'command']


class InvalidParamValueErrorReply(ErrorReply):
    ARGS = ['device', 'param', 'value']

# Fun!


class HelpRequest(Request):
    pass


class HelpReply(Reply):
    pass


FEATURES = [
    'Feature1',
    'Feature2',
    'Feature3',
    'Future',
]
