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
from __future__ import print_function

import json
from secop.protocol.errors import EXCEPTIONS

# allowed actions:

IDENTREQUEST = u'*IDN?'  # literal
# literal! first part is fixed!
IDENTREPLY = u'SINE2020&ISSE,SECoP,V2018-02-13,rc2'

DESCRIPTIONREQUEST = u'describe'  # literal
DESCRIPTIONREPLY = u'describing'  # +<id> +json

ENABLEEVENTSREQUEST = u'activate'  # literal + optional spec
ENABLEEVENTSREPLY = u'active'  # literal + optional spec, is end-of-initial-data-transfer

DISABLEEVENTSREQUEST = u'deactivate'  # literal + optional spec
DISABLEEVENTSREPLY = u'inactive'  # literal + optional spec

COMMANDREQUEST = u'do'  # +module:command +json args (if needed)
# +module:command +json args (if needed) # send after the command finished !
COMMANDREPLY = u'done'

# +module[:parameter] +json_value -> NO direct reply, calls POLL internally
WRITEREQUEST = u'change'
# +module[:parameter] +json_value # send with the read back value
WRITEREPLY = u'changed'

# +module[:parameter] -> NO direct reply, calls POLL internally!
POLLREQUEST = u'read'
EVENTREPLY = u'update'  # +module[:parameter] +json_value (value, qualifiers_as_dict)

HEARTBEATREQUEST = u'ping'  # +nonce_without_space
HEARTBEATREPLY = u'pong'  # +nonce_without_space

ERRORREPLY = u'error'  # +errorclass +json_extended_info

HELPREQUEST = u'help'  # literal
HELPREPLY = u'helping'  # +line number +json_text

# helper mapping to find the REPLY for a REQUEST
REQUEST2REPLY = {
    IDENTREQUEST:         IDENTREPLY,
    DESCRIPTIONREQUEST:   DESCRIPTIONREPLY,
    ENABLEEVENTSREQUEST:  ENABLEEVENTSREPLY,
    DISABLEEVENTSREQUEST: DISABLEEVENTSREPLY,
    COMMANDREQUEST:       COMMANDREPLY,
    WRITEREQUEST:         WRITEREPLY,
    POLLREQUEST:          EVENTREPLY,
    HEARTBEATREQUEST:     HEARTBEATREPLY,
    HELPREQUEST:          HELPREPLY,
}



class Message(object):
    """base class for messages"""
    origin = u'<unknown source>'
    action = u'<unknown message type>'
    specifier = None
    data = None

    # cooked versions
    module = None
    parameter = None
    command = None
    args = None

    # if set, these are used for generating the reply
    qualifiers = None  # will be rectified to dict() in __init__
    value = None  # also the result of a command

    # if set, these are used for generating the error msg
    errorclass = ''  # -> specifier
    errordescription = ''  # -> data[1] (data[0] is origin)
    errorinfo = {}  # -> data[2]

    def __init__(self, action, specifier=None, data=None, **kwds):
        self.qualifiers = {}
        self.action = action
        if data:
            data = json.loads(data)
        if specifier:
            self.module = specifier
            self.specifier = specifier
            if ':' in specifier:
                self.module, p = specifier.split(':',1)
                if action in (COMMANDREQUEST, COMMANDREPLY):
                    self.command = p
                    # XXX: extract args?
                    self.args = data
                else:
                    self.parameter = p
                    if data is not None:
                        self.data = data
            elif data is not None:
                self.data = data
        # record extra values
        self.__arguments = set()
        for k, v in kwds.items():
            self.setvalue(k, v)

    def setvalue(self, key, value):
        setattr(self, key, value)
        self.__arguments.add(key)

    def setqualifier(self, key, value):
        self.qualifiers[key] = value

    def __repr__(self):
        return u'Message(%r' % self.action + \
            u', '.join('%s=%s' % (k, repr(getattr(self, k)))
                      for k in sorted(self.__arguments)) + u')'

    def serialize(self):
        """return <action>,<specifier>,<jsonyfied_data> triple"""
        if self.errorclass:
            for k in self.__arguments:
                if k in (u'origin', u'errorclass', u'errorinfo', u'errordescription'):
                    if k in self.errorinfo:
                        del self.errorinfo[k]
                    continue
                self.errorinfo[k] = getattr(self, k)
            data = [self.origin, self.errordescription, self.errorinfo]
            print(repr(data))
            return ERRORREPLY, self.errorclass, json.dumps(data)
        elif self.value or self.qualifiers:
            data = [self.value, self.qualifiers]
        else:
            data = self.data

        try:
            data = json.dumps(data) if data else u''
        except TypeError:
            print('Can not serialze: %s' % repr(data))
            data = u'none'

        if self.specifier:
            specifier = self.specifier
        else:
            specifier = self.module
            if self.parameter:
                specifier = u'%s:%s' %(self.module, self.parameter)
            if self.command:
                specifier = u'%s:%s' %(self.module, self.command)
        return self.action, specifier, data

    def mkreply(self):
        self.action = REQUEST2REPLY.get(self.action, self.action)

    def set_error(self, errorclass, errordescription, errorinfo):
        if errorclass not in EXCEPTIONS:
            errordescription = '%s is not an official errorclass!\n%s' % (errorclass, errordescription)
            errorclass = u'Internal'
        # used to mark thes as an error message
        # XXX: check errorclass for allowed values !
        self.setvalue(u'errorclass', errorclass)  # a str
        self.setvalue(u'errordescription', errordescription)   # a str
        self.setvalue(u'errorinfo', errorinfo)  # a dict
        self.action = ERRORREPLY

    def set_result(self, value, qualifiers):
        # used to mark thes as an result reply message
        self.setvalue(u'value', value)
        self.qualifiers.update(qualifiers)
        self.__arguments.add(u'qualifier')



HelpMessage = u"""Try one of the following:
            '%s' to query protocol version
            '%s' to read the description
            '%s <module>[:<parameter>]' to request reading a value
            '%s <module>[:<parameter>] value' to request changing a value
            '%s <module>[:<command>]' to execute a command
            '%s <nonce>' to request a heartbeat response
            '%s' to activate async updates
            '%s' to deactivate updates
            """ % (IDENTREQUEST, DESCRIPTIONREQUEST, POLLREQUEST,
                   WRITEREQUEST, COMMANDREQUEST, HEARTBEATREQUEST,
                   ENABLEEVENTSREQUEST, DISABLEEVENTSREQUEST)
