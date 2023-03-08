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

import re
from ast import literal_eval


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


class BadValueError(SECoPError):
    """do not raise, but might used for instance checks (WrongTypeError, RangeError)"""


class RangeError(ValueError, BadValueError):
    name = 'RangeError'


class WrongTypeError(TypeError, BadValueError):
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


FRAPPY_ERROR = re.compile(r'(.*)\(.*\)$')


def make_secop_error(name, text):
    """create an instance of SECoPError from an error report

    :param name: the error class from the SECoP error report
    :param text: the second item of a SECoP error report
    :return: the built instance of SECoPError
    """
    try:
        # try to interprete the error text as a repr(<instance of SECoPError>)
        # as it would be created by a Frappy server
        cls, textarg = FRAPPY_ERROR.match(text).groups()
        errcls = locals()[cls]
        if errcls.name == name:
            # convert repr(<string>) to <string>
            text = literal_eval(textarg)
    except Exception:
        # probably not a Frappy server, or running a different version
        errcls = EXCEPTIONS.get(name, InternalError)
    return errcls(text)


def secop_error(exception):
    if isinstance(exception, SECoPError):
        return exception
    return InternalError(repr(exception))


EXCEPTIONS = {e().name: e for e in [
    NoSuchModuleError,
    NoSuchParameterError,
    NoSuchCommandError,
    CommandFailedError,
    CommandRunningError,
    ReadOnlyError,
    BadValueError,
    RangeError,
    WrongTypeError,
    CommunicationFailedError,
    HardwareError,
    IsBusyError,
    IsErrorError,
    DisabledError,
    ProtocolError,
    NotImplementedError,
    InternalError]}

# TODO: check if these are really needed:
EXCEPTIONS.update(
    SyntaxError=ProtocolError,
    # internal short versions (candidates for spec)
    Protocol=ProtocolError,
    Internal=InternalError,
)
