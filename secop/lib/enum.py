#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2016 by the authors, see LICENSE
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
"""Enum class"""

from __future__ import division, print_function

__ALL__ = ['Enum']

try:
    text_type = unicode  # Py2
except NameError:
    text_type = str  # Py3
    unicode = str  # pylint: disable=redefined-builtin

class EnumMember(object):
    """represents one member of an Enum

    has an int-type value and attributes 'name' and 'value'
    """
    __slots__ = ['name', 'value', 'enum']
    def __init__(self, enum, name, value):
        if not isinstance(enum, Enum):
            raise TypeError('1st Argument must be an instance of class Enum()')
        self.value = int(value)
        self.enum = enum
        self.name = name or 'unnamed'

    # to behave like an int for comparisons
    def __cmp__(self, other):
        if isinstance(other, EnumMember):
            other = other.value
        if isinstance(other, (str, unicode)):
            if other in self.enum:
                other = self.enum[other].value
        try:
            other = int(other)
        except Exception:
            #raise TypeError('%r can not be compared to %r!' %(other, self))
            return -1  # XXX:!
        if self.value < other:
            return -1
        elif self.value > other:
            return 1
        return 0

    def __lt__(self, other):
        return self.__cmp__(other.value if isinstance(other, EnumMember) else other) == -1
    def __le__(self, other):
        return self.__cmp__(other.value if isinstance(other, EnumMember) else other) < 1
    def __eq__(self, other):
        if isinstance(other, (EnumMember)):
            return other.value == self.value
        if isinstance(other, int):
            return other == self.value
        # compare by name (for (in)equality only)
        if isinstance(other, (str, unicode)):
            if other in self.enum:
                return self.name == other
            return False
        return self.__cmp__(other.value if isinstance(other, EnumMember) else other) == 0
    def __ne__(self, other):
        return not self.__eq__(other)
    def __ge__(self, other):
        return self.__cmp__(other.value if isinstance(other, EnumMember) else other) > -1
    def __gt__(self, other):
        return self.__cmp__(other.value if isinstance(other, EnumMember) else other) == 1

    # to be useful in indexing
    def __hash__(self):
        return self.value.__hash__()

    # be read-only (except during initialization)
    def __setattr__(self, key, value):
        if key in self.__slots__ and not getattr(self, 'name', None):
            return object.__setattr__(self, key, value)
        raise TypeError('Modifying EnumMember\'s is not allowed!')

    # allow access to other EnumMembers (via the Enum)
    def __getattr__(self, key):
        enum = object.__getattribute__(self, 'enum')
        if key in enum:
            return enum[key]
        return object.__getattribute__(self, key)

    # be human readable (for debugging)
    def __repr__(self):
        return '<%s.%s (%d)>' % (self.enum.name, self.name, self.value)


    # numeric operations: delegate to int. Do we really need any of those?
    def __add__(self, other):
        return self.value.__add__(other.value if isinstance(other, EnumMember) else other)
    def __sub__(self, other):
        return self.value.__sub__(other.value if isinstance(other, EnumMember) else other)
    def __mul__(self, other):
        return self.value.__mul__(other.value if isinstance(other, EnumMember) else other)
    def __div__(self, other):
        return self.value.__div__(other.value if isinstance(other, EnumMember) else other)
    def __truediv__(self, other):
        return self.value.__truediv__(other.value if isinstance(other, EnumMember) else other)
    def __floordiv__(self, other):
        return self.value.__floordiv__(other.value if isinstance(other, EnumMember) else other)
    def __mod__(self, other):
        return self.value.__mod__(other.value if isinstance(other, EnumMember) else other)
    def __divmod__(self, other):
        return self.value.__divmod__(other.value if isinstance(other, EnumMember) else other)
    def __pow__(self, other, *args):
        return self.value.__pow__(other, *args)
    def __lshift__(self, other):
        return self.value.__lshift__(other.value if isinstance(other, EnumMember) else other)
    def __rshift__(self, other):
        return self.value.__rshift__(other.value if isinstance(other, EnumMember) else other)

    def __radd__(self, other):
        return self.value.__radd__(other.value if isinstance(other, EnumMember) else other)
    def __rsub__(self, other):
        return self.value.__rsub__(other.value if isinstance(other, EnumMember) else other)
    def __rmul__(self, other):
        return self.value.__rmul__(other.value if isinstance(other, EnumMember) else other)
    def __rdiv__(self, other):
        return self.value.__rdiv__(other.value if isinstance(other, EnumMember) else other)
    def __rtruediv__(self, other):
        return self.value.__rtruediv__(other.value if isinstance(other, EnumMember) else other)
    def __rfloordiv__(self, other):
        return self.value.__rfloordiv__(other.value if isinstance(other, EnumMember) else other)
    def __rmod__(self, other):
        return self.value.__rmod__(other.value if isinstance(other, EnumMember) else other)
    def __rdivmod__(self, other):
        return self.value.__rdivmod__(other.value if isinstance(other, EnumMember) else other)
    def __rpow__(self, other, *args):
        return self.value.__rpow__(other, *args)
    def __rlshift__(self, other):
        return self.value.__rlshift__(other.value if isinstance(other, EnumMember) else other)
    def __rrshift__(self, other):
        return self.value.__rrshift__(other.value if isinstance(other, EnumMember) else other)

    # logical operations
    def __and__(self, other):
        return self.value.__and__(other.value if isinstance(other, EnumMember) else other)
    def __xor__(self, other):
        return self.value.__xor__(other.value if isinstance(other, EnumMember) else other)
    def __or__(self, other):
        return self.value.__or__(other.value if isinstance(other, EnumMember) else other)
    def __rand__(self, other):
        return self.value.__rand__(other.value if isinstance(other, EnumMember) else other)
    def __rxor__(self, other):
        return self.value.__rxor__(other.value if isinstance(other, EnumMember) else other)
    def __ror__(self, other):
        return self.value.__ror__(other.value if isinstance(other, EnumMember) else other)
    # other stuff
    def __neg__(self):
        return self.value.__neg__()
    def __pos__(self):
        return self.value.__pos__()
    def __abs__(self):
        return self.value.__abs__()
    def __invert__(self):
        return self.value.__invert__()
    def __int__(self):
        return self.value.__int__()
    def __float__(self):
        return self.value.__float__()
        #return NotImplemented  # makes no sense
    def __oct__(self):
        return self.value.__oct__()
    def __hex__(self):
        return self.value.__hex__()
    def __index__(self):
        return self.value.__index__()

    # note: we do not implement the __i*__ methods as they modify our value
    # inplace and we want to have a const
    def __forbidden__(self, *args):
        raise TypeError('Operation is forbidden!')
    __iadd__ = __isub__ = __imul__ = __idiv__ = __itruediv__ = __ifloordiv__ = \
        __imod__ = __ipow__ = __ilshift__ = __irshift__ = __iand__ = \
        __ixor__ = __ior__ = __forbidden__


class Enum(dict):
    """The Enum class

    use instance of this like this:
    >>> status = Enum('status', idle=1, busy=2, error=3)

    you may create an extended Enum:
    >>> moveable_status = Enum(status, alarm=5)
    >>> yet_another_enum = Enum('X', dict(a=1, b=2), c=3)
    last example 'extends' the definition given by the dict with c=3.

    accessing the members:
    >>> status['idle'] == status.idle == status('idle')
    >>> status[1] == status.idle == status(1)

    Each member can be used like an int, so:
    >>> status.idle == 1 is True
    >>> status.error +5

    You can neither modify members nor Enums.
    You only can create an extended Enum.
    """
    name = ''
    def __init__(self, name='', parent=None, **kwds):
        super(Enum, self).__init__()
        if isinstance(name, (dict, Enum)) and parent is None:
            # swap if only parent is given as positional argument
            name, parent = '', name
        # parent may be dict, or Enum....
        if not name:
            if isinstance(parent, Enum):
                # if name was not given, use that of the parent
                # this means, an extended Enum behaves like the parent
                # THIS MAY BE CONFUSING SOMETIMES!
                name=parent.name
#            else:
#                raise TypeError('Enum instances need a name or an Enum parent!')
        if not isinstance(name, (str, text_type)):
            raise TypeError('1st argument to Enum must be a name or an Enum!')

        names = set()
        values = set()
        # pylint: disable=dangerous-default-value
        def add(self, k, v, names = names, value = values):
            """helper for creating the enum members"""
            if v is None:
                # sugar: take the next free number if value was None
                v = max(values or [0]) + 1
            # sugar: if value is a name of another member,
            # auto-assign the smallest free number which is bigger
            # then that assigned to that name
            if v in names:
                v = self[v].value
                while v in values:
                    v +=1

            # check that the value is an int
            _v = int(v)
            if _v != v:
                raise TypeError('Values must be integers!')
            v = _v

            # check for duplicates
            if k in names:
                raise TypeError('duplicate name %r' % k)
            if v in values:
                raise TypeError('duplicate value %d (key=%r)' % (v, k))

            # remember it
            self[v] = self[k] = EnumMember(self, k, v)
            names.add(k)
            values.add(v)

        if isinstance(parent, Enum):
            for m in parent.members:
                add(self, m.name, m.value)
        elif isinstance(parent, dict):
            for k, v in parent.items():
                add(self, k, v)
        elif parent != None:
            raise TypeError('parent (if given) MUST be a dict or an Enum!')
        for k, v in kwds.items():
            add(self, k, v)
        self.members = tuple(sorted(self[n] for n in names))
        self.name = name

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        if self.name and key != 'name':
            raise TypeError('Enum %r can not be changed!' % self.name)
        super(Enum, self).__setattr__(key, value)

    def __setitem__(self, key, value):
        if self.name:
            raise TypeError('Enum %r can not be changed!' % self.name)
        super(Enum, self).__setitem__(key, value)

    def __delitem__(self, key):
        raise TypeError('Enum %r can not be changed!' % self.name)

    def __repr__(self):
        return '<Enum %r (%d values)>' % (self.name, len(self)/2)

    def __call__(self, key):
        return self[key]
