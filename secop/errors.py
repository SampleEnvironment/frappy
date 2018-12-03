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
"""Define (internal) SECoP Errors"""

from __future__ import division, print_function


class SECoPError(RuntimeError):

    def __init__(self, *args, **kwds):
        RuntimeError.__init__(self)
        self.args = args
        for k, v in list(kwds.items()):
            setattr(self, k, v)

    def __repr__(self):
        args = ', '.join(map(repr, self.args))
        kwds = ', '.join(['%s=%r' % i for i in list(self.__dict__.items())])
        res = []
        if args:
            res.append(args)
        if kwds:
            res.append(kwds)
        return '%s(%s)' % (self.name, ', '.join(res))

    @property
    def name(self):
        return self.__class__.__name__[:-len('Error')]


class SECoPServerError(SECoPError):
    name = 'InternalError'


class InternalError(SECoPError):
    name = 'InternalError'


class ProgrammingError(SECoPError):
    name = 'InternalError'


class ConfigError(SECoPError):
    name = 'InternalError'


class ProtocolError(SECoPError):
    name = 'ProtocolError'


class NoSuchModuleError(SECoPError):
    name = 'NoSuchModule'


class NoSuchParameterError(SECoPError):
    pass


class NoSuchCommandError(SECoPError):
    pass


class ReadOnlyError(SECoPError):
    pass


class BadValueError(SECoPError):
    pass


class CommandFailedError(SECoPError):
    pass


class CommandRunningError(SECoPError):
    pass


class CommunicationFailedError(SECoPError):
    pass


class IsBusyError(SECoPError):
    pass


class IsErrorError(SECoPError):
    pass


class DisabledError(SECoPError):
    pass


class HardwareError(SECoPError):
    pass



EXCEPTIONS = dict(
    NoSuchModule=NoSuchModuleError,
    NoSuchParameter=NoSuchParameterError,
    NoSuchCommand=NoSuchCommandError,
    CommandFailed=CommandFailedError,
    CommandRunning=CommandRunningError,
    Readonly=ReadOnlyError,
    BadValue=BadValueError,
    CommunicationFailed=CommunicationFailedError,
    HardwareError=HardwareError,
    IsBusy=IsBusyError,
    IsError=IsErrorError,
    Disabled=DisabledError,
    SyntaxError=ProtocolError,
    InternalError=InternalError,
# internal short versions (candidates for spec)
    Protocol=ProtocolError,
    Internal=InternalError,
)
