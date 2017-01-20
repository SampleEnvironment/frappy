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


class Message(object):
    """base class for messages"""
    is_request = False
    is_reply = False
    is_error = False
    qualifiers = {}
    origin = "<unknown source>"

    def __init__(self, **kwds):
        self.ARGS = set()
        for k, v in kwds.items():
            self.setvalue(k, v)

    def setvalue(self, key, value):
        setattr(self, key, value)
        self.ARGS.add(key)

    def __repr__(self):
        return self.__class__.__name__ + '(' + \
            ', '.join('%s=%s' % (k, repr(getattr(self, k)))
                      for k in sorted(self.ARGS)) + ')'

    def as_dict(self):
        """returns set parameters as dict"""
        return dict(map(lambda k: (k, getattr(self, k)), self.ARGS))


class Value(object):

    def __init__(self, module, parameter=None, command=None, value=Ellipsis,
                 **qualifiers):
        self.module = module
        self.parameter = parameter
        self.command = command
        self.value = value
        self.qualifiers = qualifiers
        self.msgtype = 'update'  # 'changed' or 'done'

    def __repr__(self):
        devspec = self.module
        if self.parameter:
            devspec = '%s:%s' % (devspec, self.parameter)
        elif self.command:
            devspec = '%s:%s()' % (devspec, self.command)
        return '%s:Value(%s)' % (devspec, ', '.join(
            [repr(self.value)] +
            ['%s=%s' % (k, format_time(v) if k == "timestamp" else repr(v)) for k, v in self.qualifiers.items()]))


class Request(Message):
    is_request = True

    def get_reply(self):
        """returns a Reply object prefilled with the attributes from this request."""
        m = Message()
        m.is_request = False
        m.is_reply = True
        m.is_error = False
        m.qualifiers = self.qualifiers
        m.origin = self.origin
        for k in self.ARGS:
            m.setvalue(k, self.__dict__[k])
        return m

    def get_error(self, errorclass, errorinfo):
        """returns a Reply object prefilled with the attributes from this request."""
        m = ErrorMessage()
        m.qualifiers = self.qualifiers
        m.origin = self.origin
        for k in self.ARGS:
            m.setvalue(k, self.__dict__[k])
        m.setvalue("errorclass", errorclass[:-5]
                   if errorclass.endswith('rror')
                   else errorclass)
        m.setvalue("errorinfo", errorinfo)
        return m


class IdentifyRequest(Request):
    pass


class IdentifyReply(Message):
    is_reply = True
    version_string = None


class DescribeRequest(Request):
    pass


class DescribeReply(Message):
    is_reply = True
    equipment_id = None
    description = None


class ActivateRequest(Request):
    pass


class ActivateReply(Message):
    is_reply = True


class DeactivateRequest(Request):
    pass


class DeactivateReply(Message):
    is_reply = True


class CommandRequest(Request):
    command = ''
    arguments = []


class CommandReply(Message):
    is_reply = True
    command = ''
    result = None


class WriteRequest(Request):
    module = None
    parameter = None
    value = None


class WriteReply(Message):
    is_reply = True
    module = None
    parameter = None
    value = None


class PollRequest(Request):
    is_request = True
    module = None
    parameter = None


class HeartbeatRequest(Request):
    nonce = 'alive'


class HeartbeatReply(Message):
    is_reply = True
    nonce = 'undefined'


class EventMessage(Message):
    # use Value directly for Replies !
    is_reply = True
    module = None
    parameter = None
    command = None
    value = None  # Value object ! (includes qualifiers!)


class ErrorMessage(Message):
    is_error = True
    errorclass = 'InternalError'
    errorinfo = None


class HelpMessage(Request):
    is_reply = True  # !sic!
