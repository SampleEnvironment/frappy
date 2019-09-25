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
"""basic validators (for properties)"""


import re

from secop.errors import ProgrammingError


def FloatProperty(value):
    return float(value)


def PositiveFloatProperty(value):
    value = float(value)
    if value > 0:
        return value
    raise ValueError('Value must be >0 !')


def NonNegativeFloatProperty(value):
    value = float(value)
    if value >= 0:
        return value
    raise ValueError('Value must be >=0 !')


def IntProperty(value):
    if int(value) == float(value):
        return int(value)
    raise ValueError('Can\'t convert %r to int!' % value)


def PositiveIntProperty(value):
    value = IntProperty(value)
    if value > 0:
        return value
    raise ValueError('Value must be >0 !')


def NonNegativeIntProperty(value):
    value = IntProperty(value)
    if value >= 0:
        return value
    raise ValueError('Value must be >=0 !')


def BoolProperty(value):
    try:
        if value.lower() in ['0', 'false', 'no', 'off',]:
            return False
        if value.lower() in ['1', 'true', 'yes', 'on', ]:
            return True
    except AttributeError: # was no string
        if bool(value) == value:
            return value
    raise ValueError('%r is no valid boolean: try one of True, False, "on", "off",...' % value)


def StringProperty(value):
    return str(value)


def UnitProperty(value):
    # probably too simple!
    for s in str(value):
        if s.lower() not in '°abcdefghijklmnopqrstuvwxyz':
            raise ValueError('%r is not a valid unit!')


def FmtStrProperty(value, regexp=re.compile(r'^%\.?\d+[efg]$')):
    value=str(value)
    if regexp.match(value):
        return value
    raise ValueError('%r is not a valid fmtstr!' % value)


def OneOfProperty(*args):
    # literally oneof!
    if not args:
        raise ProgrammingError('OneOfProperty needs some argumets to check against!')
    def OneOfChecker(value):
        if value not in args:
            raise ValueError('Value must be one of %r' % list(args))
        return value
    return OneOfChecker


def NoneOr(checker):
    if not callable(checker):
        raise ProgrammingError('NoneOr needs a basic validator as Argument!')
    def NoneOrChecker(value):
        if value is None:
            return None
        return checker(value)
    return NoneOrChecker


def EnumProperty(**kwds):
    if not kwds:
        raise ProgrammingError('EnumProperty needs a mapping!')
    def EnumChecker(value):
        if value in kwds:
            return kwds[value]
        if value in kwds.values():
            return value
        raise ValueError('Value must be one of %r' % list(kwds))
    return EnumChecker

def TupleProperty(*checkers):
    if not checkers:
        checkers = [None]
    for c in checkers:
        if not callable(c):
            raise ProgrammingError('TupleProperty needs basic validators as Arguments!')
    def TupleChecker(values):
        if len(values)==len(checkers):
            return tuple(c(v) for c, v in zip(checkers, values))
        raise ValueError('Value needs %d elements!' % len(checkers))
    return TupleChecker

def ListOfProperty(checker):
    if not callable(checker):
        raise ProgrammingError('ListOfProperty needs a basic validator as Argument!')
    def ListOfChecker(values):
        return [checker(v) for v in values]
    return ListOfChecker
