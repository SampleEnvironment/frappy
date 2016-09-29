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
        for k,v in kwds.items():
            setattr(self, k, v)


class InternalError(SECOPError):
    pass


class ProtocollError(SECOPError):
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


class CommandFailedError(SECOPError):
    pass


class InvalidParamValueError(SECOPError):
    pass


if __name__ == '__main__':
    print("Minimal testing of errors....")

    print "OK"
    print
