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


class SECOPError(RuntimeError):
    def __init__(self, *args, **kwds):
        self.args = args
        for k, v in kwds.items():
            setattr(self, k, v)

    def __repr__(self):
        args = ', '.join(map(repr, self.args))
        kwds = ', '.join(['%s=%r' % i for i in self.__dict__.items()])
        res = []
        if args:
            res.append(args)
        if kwds:
            res.append(kwds)
        return '%s(%s)' % (self.name, ', '.join(res))

    @property
    def name(self):
        return self.__class__.__name__[:-len('Error')]


class InternalError(SECOPError):
    pass


class ProtocolError(SECOPError):
    pass


# XXX: unifiy NoSuch...Error ?
class NoSuchModuleError(SECOPError):
    pass


class NoSuchParamError(SECOPError):
    pass


class NoSuchCommandError(SECOPError):
    pass


class ReadonlyError(SECOPError):
    pass


class BadValueError(SECOPError):
    pass


class CommandFailedError(SECOPError):
    pass


class InvalidParamValueError(SECOPError):
    pass


EXCEPTIONS = dict(
    Internal=InternalError,
    Protocol=ProtocolError,
    NoSuchModule=NoSuchModuleError,
    NoSuchParam=NoSuchParamError,
    NoSuchCommand=NoSuchCommandError,
    BadValue=BadValueError,
    Readonly=ReadonlyError,
    CommandFailed=CommandFailedError,
    InvalidParam=InvalidParamValueError, )

if __name__ == '__main__':
    print("Minimal testing of errors....")

    print "OK"
    print
