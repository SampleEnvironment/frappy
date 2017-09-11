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

# Request Types
REQUEST = 'request'
REPLY = 'reply'
ERROR = 'error'

# Message types ('actions') hint: fetch is list+read
LIST = 'list'
READ = 'read'
WRITE = 'write'
COMMAND = 'command'
POLL = 'poll'
SUBSCRIBE = 'subscribe'
UNSUBSCRIBE = 'unsubscribe'
TRIGGER = 'trigger'
EVENT = 'event'
ERROR = 'error'
HELP = 'help'

# base class for messages


class Message(object):

    MSGTYPE = 'Undefined'
    devs = None
    pars = None
    props = None
    result = None
    error = None
    ARGS = None
    errortype = None

    def __init__(self, **kwds):
        self.devs = []
        self.pars = []
        self.props = []
        self.result = []
        self.ARGS = set()
        for k, v in kwds.items():
            self.setvalue(k, v)

    def setvalue(self, key, value):
        setattr(self, key, value)
        self.ARGS.add(key)

    @property
    def NAME(self):
        # generate sensible name
        r = 'Message'
        if self.props:
            r = 'Property' if self.props != ['*'] else 'Properties'
        elif self.pars:
            r = 'Parameter' if self.pars != ['*'] else 'Parameters'
        elif self.devs:
            r = 'Module' if self.devs != ['*'] else 'Modules'

        t = ''
        if self.MSGTYPE in [
                LIST, READ, WRITE, COMMAND, POLL, SUBSCRIBE, UNSUBSCRIBE, HELP
        ]:
            t = 'Request' if not self.result else 'Reply'

        if self.errortype is None:
            return self.MSGTYPE.title() + r + t
        else:
            return self.errortype + 'Error'

    def __repr__(self):
        return self.NAME + '(' + \
            ', '.join('%s=%r' % (k, getattr(self, k))
                      for k in self.ARGS if getattr(self, k) is not None) + ')'


class Value(object):

    def __init__(self, value=Ellipsis, qualifiers=None, **kwds):
        self.dev = ''
        self.param = ''
        self.prop = ''
        self.value = value
        self.qualifiers = qualifiers or dict()
        self.__dict__.update(kwds)

    def __repr__(self):
        devspec = self.dev
        if self.param:
            devspec = '%s:%s' % (devspec, self.param)
        if self.prop:
            devspec = '%s:%s' % (devspec, self.prop)
        return '%s:Value(%s)' % (
            devspec,
            ', '.join([repr(self.value)] +
                      ['%s=%r' % (k, v) for k, v in self.qualifiers.items()]))


class ListMessage(Message):
    MSGTYPE = LIST


class ReadMessage(Message):
    MSGTYPE = READ  # return cached value


class WriteMessage(Message):
    MSGTYPE = WRITE  # write value to some spec
    target = None  # actually float or string


class CommandMessage(Message):
    MSGTYPE = COMMAND
    cmd = ''  # always string
    args = []
    result = []


class PollMessage(Message):
    MSGTYPE = POLL  # read HW and return hw_value


class SubscribeMessage(Message):
    MSGTYPE = SUBSCRIBE


class UnsubscribeMessage(Message):
    MSGTYPE = UNSUBSCRIBE


class TriggerMessage(Message):
    MSGTYPE = TRIGGER


class EventMessage(Message):
    MSGTYPE = EVENT


class ErrorMessage(Message):
    MSGTYPE = ERROR
    errorstring = 'an unhandled error occured'
    errortype = 'UnknownError'


class HelpMessage(Message):
    MSGTYPE = HELP


class NoSuchModuleError(ErrorMessage):

    def __init__(self, *devs):
        ErrorMessage.__init__(
            self,
            devs=devs,
            errorstring="Module %r does not exist" % devs[0],
            errortype='NoSuchModule')


class NoSuchParamError(ErrorMessage):

    def __init__(self, dev, *params):
        ErrorMessage.__init__(
            self,
            devs=(dev, ),
            params=params,
            errorstring="Module %r has no parameter %r" % (dev, params[0]),
            errortype='NoSuchParam')


class ParamReadonlyError(ErrorMessage):

    def __init__(self, dev, *params):
        ErrorMessage.__init__(
            self,
            devs=(dev, ),
            params=params,
            errorstring="Module %r, parameter %r is not writeable!" %
            (dev, params[0]),
            errortype='ParamReadOnly')


class InvalidParamValueError(ErrorMessage):

    def __init__(self, dev, param, value, e):
        ErrorMessage.__init__(
            self,
            devs=(dev, ),
            params=params,
            values=(value),
            errorstring=str(e),
            errortype='InvalidParamValueError')


class InternalError(ErrorMessage):

    def __init__(self, err, **kwds):
        ErrorMessage.__init__(
            self, errorstring=str(err), errortype='InternalError', **kwds)


MESSAGE = dict((cls.MSGTYPE, cls)
               for cls in [
                   HelpMessage, ErrorMessage, EventMessage, TriggerMessage,
                   UnsubscribeMessage, SubscribeMessage, PollMessage,
                   CommandMessage, WriteMessage, ReadMessage, ListMessage
])

if __name__ == '__main__':
    print("Minimal testing of messages....")
    m = Message(MSGTYPE='test', a=1, b=2, c='x')
    print m
    print ReadMessage(devs=['a'], result=[Value(12.3)])

    print "OK"
    print
