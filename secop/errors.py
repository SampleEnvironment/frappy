#!/usr/bin/env python
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
"""error class for our little framework"""

# base class
class SECoPServerError(Exception):
    errorclass = 'InternalError'


# those errors should never be seen remotely!
# just in case they are, these are flagged as InternalError
class ConfigError(SECoPServerError):
    pass


class ProgrammingError(SECoPServerError):
    pass


class ParsingError(SECoPServerError):
    pass


# to be exported for remote operation
class SECoPError(SECoPServerError):
    pass


class NoSuchModuleError(SECoPError):
    errorclass = 'NoSuchModule'


class NoSuchParameterError(SECoPError):
    errorclass = 'NoSuchParameter'


class NoSuchCommandError(SECoPError):
    errorclass = 'NoSuchCommand'


class CommandFailedError(SECoPError):
    errorclass = 'CommandFailed'


class CommandRunningError(SECoPError):
    errorclass = 'CommandRunning'


class ReadOnlyError(SECoPError):
    errorclass = 'ReadOnly'


class BadValueError(SECoPError):
    errorclass = 'BadValue'


class CommunicationError(SECoPError):
    errorclass = 'CommunicationFailed'


class TimeoutError(SECoPError):
    errorclass = 'CommunicationFailed'  # XXX: add to SECop messages


class HardwareError(SECoPError):
    errorclass = 'CommunicationFailed'  # XXX: Add to SECoP messages


class IsBusyError(SECoPError):
    errorclass = 'IsBusy'


class IsErrorError(SECoPError):
    errorclass = 'IsError'


class DisabledError(SECoPError):
    errorclass = 'Disabled'
