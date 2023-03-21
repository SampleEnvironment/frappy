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
"""Define (internal) SECoP Errors

all error classes inherited from SECoPError should be placed in this module,
else they might not be registered and can therefore not be rebuilt on the client side
"""

import re


class SECoPError(RuntimeError):
    silent = False   # silent = True indicates that the error is already logged
    clsname2class = {}  # needed to convert error reports back to classes
    name = 'InternalError'
    name2class = {}

    def __init_subclass__(cls):
        cls.clsname2class[cls.__name__] = cls
        if 'name' in cls.__dict__:
            cls.name2class[cls.name] = cls

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
        return '%s(%s)' % (self.name or type(self).__name__, ', '.join(res))


class InternalError(SECoPError):
    """uncatched error"""
    name = 'InternalError'


class ProgrammingError(SECoPError):
    """catchable programming error"""


class ConfigError(SECoPError):
    """invalid configuration"""


class ProtocolError(SECoPError):
    """A malformed request or on unspecified message was sent

    This includes non-understood actions and malformed specifiers.
    Also if the message exceeds an implementation defined maximum size.
    """
    name = 'ProtocolError'


class NoSuchModuleError(SECoPError):
    """missing module

    The action can not be performed as the specified module is non-existent"""
    name = 'NoSuchModule'


class NotImplementedSECoPError(NotImplementedError, SECoPError):
    """not (yet) implemented

    A (not yet) implemented action or combination of action and specifier
    was requested. This should not be used in productive setups, but is very
    helpful during development."""
    name = 'NotImplemented'


class NoSuchParameterError(SECoPError):
    """missing parameter

    The action can not be performed as the specified parameter is non-existent.
    Also raised when trying to use a command name in a 'read' or 'change' message.
    """
    name = 'NoSuchParameter'


class NoSuchCommandError(SECoPError):
    """The specified command does not exist

    Also raised when trying to use a parameter name in a 'do' message.
    """
    name = 'NoSuchCommand'


class ReadOnlyError(SECoPError):
    """The requested write can not be performed on a readonly value"""
    name = 'ReadOnly'


class BadValueError(SECoPError):
    """do not raise, but might used for instance checks (WrongTypeError, RangeError)"""


class RangeError(ValueError, BadValueError):
    """data out of range

    The requested parameter change or Command can not be performed as the
    argument value is not in the allowed range specified by the datainfo
    property. This also happens if an unspecified Enum variant is tried
    to be used, the size of a Blob or String does not match the limits
    given in the descriptive data, or if the number of elements in an
    array does not match the limits given in the descriptive data."""
    name = 'RangeError'


class BadJSONError(SECoPError):
    """The data part of the message can not be parsed, i.e. the JSON-data is no valid JSON.

    not used in Frappy, but might appear on the client side from a foreign SEC Node
    """
    # TODO: check whether this should not be removed from specs!
    name = 'BadJSON'


class WrongTypeError(TypeError, BadValueError):
    """Wrong data type

    The requested parameter change or Command can not be performed as the
    argument has the wrong type. (i.e. a string where a number is expected.)
    It may also be used if an incomplete struct is sent, but a complete
    struct is expected."""
    name = 'WrongType'


class DiscouragedConversion(ProgrammingError):
    """the discouraged conversion string - > float happened"""
    log_message = True


class CommandFailedError(SECoPError):
    name = 'CommandFailed'


class CommandRunningError(SECoPError):
    """The command is already executing.

    request may be retried after the module is no longer BUSY
    (retryable)"""
    name = 'CommandRunning'


class CommunicationFailedError(SECoPError):
    """Some communication (with hardware controlled by this SEC node) failed
    (retryable)"""
    name = 'CommunicationFailed'


class SilentCommunicationFailedError(CommunicationFailedError):
    silent = True


class IsBusyError(SECoPError):
    """The requested action can not be performed while the module is Busy
    or the command still running"""
    name = 'IsBusy'


class IsErrorError(SECoPError):
    """The requested action can not be performed while the module is in error state"""
    name = 'IsError'


class DisabledError(SECoPError):
    """The requested action can not be performed while the module is disabled"""
    name = 'disabled'


class ImpossibleError(SECoPError):
    """The requested action can not be performed at the moment"""
    name = 'Impossible'


class ReadFailedError(SECoPError):
    """The requested parameter can not be read just now"""
    name = 'ReadFailed'


class OutOfRangeError(SECoPError):
    """The requested parameter can not be read just now"""
    name = 'OutOfRange'


class HardwareError(SECoPError):
    """The connected hardware operates incorrect or may not operate at all
    due to errors inside or in connected components."""
    name = 'HardwareError'


class TimeoutSECoPError(TimeoutError, SECoPError):
    """Some initiated action took longer than the maximum allowed time (retryable)"""
    name = 'TimeoutError'


FRAPPY_ERROR = re.compile(r'(\w*): (.*)$')


def make_secop_error(name, text):
    """create an instance of SECoPError from an error report

    :param name: the error class from the SECoP error report
    :param text: the second item of a SECoP error report
    :return: the built instance of SECoPError
    """
    match = FRAPPY_ERROR.match(text)
    if match:
        clsname, errtext = match.groups()
        errcls = SECoPError.clsname2class.get(clsname)
        if errcls:
            return errcls(errtext)
    return SECoPError.name2class.get(name, InternalError)(text)


def secop_error(exc):
    """turn into InternalError, if not already a SECoPError"""
    if isinstance(exc, SECoPError):
        if SECoPError.name2class.get(exc.name) != type(exc):
            return type(exc)('%s: %s' % (type(exc).__name__, exc))
        return exc
    return InternalError('%s: %s' % (type(exc).__name__, exc))


# TODO: check if these are really needed:
SECoPError.name2class.update(
    SyntaxError=ProtocolError,
    # internal short versions (candidates for spec)
    Protocol=ProtocolError,
    Internal=InternalError,
)
