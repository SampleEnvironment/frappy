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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""Define (internal) SECoP Errors"""


class SECoPError(RuntimeError):
    silent = False   # silent = True indicates that the error is already logged

    def __init__(self, *args, **kwds):
        super().__init__()
        self.args = args
        for k, v in list(kwds.items()):
            setattr(self, k, v)

    def __repr__(self):
        args = ', '.join(map(repr, self.args))
        kwds = ', '.join(['%s=%r' % i for i in list(self.__dict__.items())
                          if i[0] != 'silent'])
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


# pylint: disable=redefined-builtin
class NotImplementedError(NotImplementedError, SECoPError):
    pass


class NoSuchParameterError(SECoPError):
    pass


class NoSuchCommandError(SECoPError):
    pass


class ReadOnlyError(SECoPError):
    pass


class BadValueError(ValueError, SECoPError):
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
    name = 'HardwareError'


def make_secop_error(name, text):
    errcls = EXCEPTIONS.get(name, InternalError)
    return errcls(text)


def secop_error(exception):
    if isinstance(exception, SECoPError):
        return exception
    return InternalError(repr(exception))


EXCEPTIONS = dict(
    NoSuchModule=NoSuchModuleError,
    NoSuchParameter=NoSuchParameterError,
    NoSuchCommand=NoSuchCommandError,
    CommandFailed=CommandFailedError,
    CommandRunning=CommandRunningError,
    ReadOnly=ReadOnlyError,
    BadValue=BadValueError,
    CommunicationFailed=CommunicationFailedError,
    HardwareError=HardwareError,
    IsBusy=IsBusyError,
    IsError=IsErrorError,
    Disabled=DisabledError,
    SyntaxError=ProtocolError,
    NotImplemented=NotImplementedError,
    ProtocolError=ProtocolError,
    InternalError=InternalError,
    # internal short versions (candidates for spec)
    Protocol=ProtocolError,
    Internal=InternalError,
)
