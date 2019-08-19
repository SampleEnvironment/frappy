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
"""Define validated data types."""

# pylint: disable=abstract-method

from __future__ import division, print_function

from base64 import b64decode, b64encode

from secop.errors import ProgrammingError, ProtocolError, BadValueError
from secop.lib.enum import Enum
from secop.parse import Parser

try:
    # py2
    unicode
except NameError:
    # py3
    unicode = str  # pylint: disable=redefined-builtin


# Only export these classes for 'from secop.datatypes import *'
__all__ = [
    u'DataType',
    u'FloatRange', u'IntRange',
    u'BoolType', u'EnumType',
    u'BLOBType', u'StringType',
    u'TupleOf', u'ArrayOf', u'StructOf',
    u'CommandType',
]

# *DEFAULT* limits for IntRange/ScaledIntegers transport serialisation
DEFAULT_MIN_INT = -16777216
DEFAULT_MAX_INT = 16777216

Parser = Parser()

# base class for all DataTypes
class DataType(object):
    IS_COMMAND = False
    unit = u''
    fmtstr = u'%r'
    default = None

    def __call__(self, value):
        """check if given value (a python obj) is valid for this datatype

        returns the value or raises an appropriate exception"""
        raise NotImplementedError

    def from_string(self, text):
        """interprets a given string and returns a validated (internal) value"""
        # to evaluate values from configfiles, ui, etc...
        raise NotImplementedError

    def export_datatype(self):
        """return a python object which after jsonifying identifies this datatype"""
        raise NotImplementedError

    def export_value(self, value):
        """if needed, reformat value for transport"""
        return value

    def import_value(self, value):
        """opposite of export_value, reformat from transport to internal repr

        note: for importing from gui/configfile/commandline use :meth:`from_string`
        instead.
        """
        return value

    def format_value(self, value, unit=None):
        """format a value of this type into a unicode string

        This is intended for 'nice' formatting for humans and is NOT
        the opposite of :meth:`from_string`
        if unit is given, use it, else use the unit of the datatype (if any)"""
        raise NotImplementedError

    def setprop(self, key, value, default, func=lambda x:x):
        """set a datatype property and store the default"""
        self._defaults[key] = default
        if value is None:
            value = default
        setattr(self, key, func(value))

    def copy(self):
        """make a deep copy of the datatype"""

        # looks like the simplest way to make a deep copy
        return get_datatype(self.export_datatype())


class FloatRange(DataType):
    """Restricted float type"""

    def __init__(self, minval=None, maxval=None, unit=None, fmtstr=None,
                       absolute_resolution=None, relative_resolution=None,):
        self.default = 0 if minval <= 0 <= maxval else minval
        self._defaults = {}
        self.setprop('min', minval, float(u'-inf'), float)
        self.setprop('max', maxval, float(u'+inf'), float)
        self.setprop('unit', unit, u'', unicode)
        self.setprop('fmtstr', fmtstr, u'%g', unicode)
        self.setprop('absolute_resolution', absolute_resolution, 0.0, float)
        self.setprop('relative_resolution', relative_resolution, 1.2e-7, float)

        # check values
        if self.min > self.max:
            raise BadValueError(u'max must be larger then min!')
        if '%' not in self.fmtstr:
            raise BadValueError(u'Invalid fmtstr!')
        if self.absolute_resolution < 0:
            raise BadValueError(u'absolute_resolution MUST be >=0')
        if self.relative_resolution < 0:
            raise BadValueError(u'relative_resolution MUST be >=0')

    def export_datatype(self):
        return {u'double': {k: getattr(self, k) for k, v in self._defaults.items()
                            if v != getattr(self, k)}}

    def __call__(self, value):
        try:
            value = float(value)
        except Exception:
            raise BadValueError(u'Can not __call__ %r to float' % value)
        prec = max(abs(value * self.relative_resolution), self.absolute_resolution)
        if self.min - prec <= value <= self.max + prec:
            return min(max(value, self.min), self.max)
        raise BadValueError(u'%.14g should be a float between %.14g and %.14g' %
                         (value, self.min, self.max))

    def __repr__(self):
        items = [u'%s=%r' % (k,v) for k,v in self.export_datatype()['double'].items()]
        return u'FloatRange(%s)' % (', '.join(items))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return float(value)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return float(value)

    def from_string(self, text):
        value = float(text)
        return self(value)

    def format_value(self, value, unit=None):
        if unit is None:
            unit = self.unit
        if unit:
            return u' '.join([self.fmtstr % value, unit])
        return self.fmtstr % value


class IntRange(DataType):
    """Restricted int type"""

    def __init__(self, minval=None, maxval=None):
        self.min = DEFAULT_MIN_INT if minval is None else int(minval)
        self.max = DEFAULT_MAX_INT if maxval is None else int(maxval)
        self.default = 0 if minval <= 0 <= maxval else minval

        # check values
        if self.min > self.max:
            raise BadValueError(u'Max must be larger then min!')

    def export_datatype(self):
        return {u'int': {"min": self.min, "max": self.max}}

    def __call__(self, value):
        try:
            value = int(value)
            if value < self.min:
                raise BadValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min, self.max or 0))
            if value > self.max:
                raise BadValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min or 0, self.max))
            return value
        except Exception:
            raise BadValueError(u'Can not convert %r to int' % value)

    def __repr__(self):
        return u'IntRange(%d, %d)' % (self.min, self.max)

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return int(value)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return int(value)

    def from_string(self, text):
        value = int(text)
        return self(value)

    def format_value(self, value, unit=None):
        return u'%d' % value


class ScaledInteger(DataType):
    """Scaled integer int type

    note: limits are for the scaled value (i.e. the internal value)
          the scale is only used for calculating to/from transport serialisation"""

    def __init__(self, scale, minval=None, maxval=None, unit=None, fmtstr=None,
                       absolute_resolution=None, relative_resolution=None,):
        self.default = 0 if minval <= 0 <= maxval else minval
        self._defaults = {}
        self.scale = float(scale)
        if not self.scale > 0:
            raise BadValueError(u'Scale MUST be positive!')
        self.setprop('unit', unit, u'', unicode)
        self.setprop('fmtstr', fmtstr, u'%g', unicode)
        self.setprop('absolute_resolution', absolute_resolution, self.scale, float)
        self.setprop('relative_resolution', relative_resolution, 1.2e-7, float)

        self.min = DEFAULT_MIN_INT * self.scale if minval is None else float(minval)
        self.max = DEFAULT_MAX_INT * self.scale if maxval is None else float(maxval)

        # check values
        if self.min > self.max:
            raise BadValueError(u'Max must be larger then min!')
        if '%' not in self.fmtstr:
            raise BadValueError(u'Invalid fmtstr!')
        if self.absolute_resolution < 0:
            raise BadValueError(u'absolute_resolution MUST be >=0')
        if self.relative_resolution < 0:
            raise BadValueError(u'relative_resolution MUST be >=0')
        # Remark: Datatype.copy() will round min, max to a multiple of self.scale
        # this should be o.k.

    def export_datatype(self):
        info = {k: getattr(self, k) for k, v in self._defaults.items()
                if v != getattr(self, k)}
        info['scale'] = self.scale
        info['min'] = int((self.min + self.scale * 0.5) // self.scale)
        info['max'] = int((self.max + self.scale * 0.5) // self.scale)
        return {u'scaled': info}

    def __call__(self, value):
        try:
            value = float(value)
        except Exception:
            raise BadValueError(u'Can not convert %r to float' % value)
        prec = max(self.scale, abs(value * self.relative_resolution),
                   self.absolute_resolution)
        if self.min - prec <= value <= self.max + prec:
            value = min(max(value, self.min), self.max)
        else:
            raise BadValueError(u'%g should be a float between %g and %g' %
                             (value, self.min, self.max))
        intval = int((value + self.scale * 0.5) // self.scale)
        value = float(intval * self.scale)
        return value  # return 'actual' value (which is more discrete than a float)

    def __repr__(self):
        hints = self.export_datatype()['scaled']
        hints.pop('scale')
        items = ['%g' % self.scale]
        for k,v in hints.items():
            items.append(u'%s=%r' % (k,v))
        return u'ScaledInteger(%s)' % (', '.join(items))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        # note: round behaves different in Py2 vs. Py3, so use floor division
        return int((value + self.scale * 0.5) // self.scale)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self.scale * int(value)

    def from_string(self, text):
        value = float(text)
        return self(value)

    def format_value(self, value, unit=None):
        if unit is None:
            unit = self.unit
        if unit:
            return u' '.join([self.fmtstr % value, unit])
        return self.fmtstr % value


class EnumType(DataType):

    def __init__(self, enum_or_name='', **kwds):
        if u'members' in kwds:
            kwds = dict(kwds)
            kwds.update(kwds[u'members'])
            kwds.pop(u'members')
        self._enum = Enum(enum_or_name, **kwds)
        self.default = self._enum[self._enum.members[0]]

    def copy(self):
        # as the name is not exported, we have to implement copy ourselfs
        return EnumType(self._enum)

    def export_datatype(self):
        return {u'enum': {u"members":dict((m.name, m.value) for m in self._enum.members)}}

    def __repr__(self):
        return u"EnumType(%r, %s)" % (self._enum.name, ', '.join(u'%s=%d' %(m.name, m.value) for m in self._enum.members))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return int(self(value))

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self(value)

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        try:
            return self._enum[value]
        except (KeyError, TypeError): # TypeError will be raised when value is not hashable
            raise BadValueError(u'%r is not a member of enum %r' % (value, self._enum))

    def from_string(self, text):
        return self(text)

    def format_value(self, value, unit=None):
        return u'%s<%s>' % (self._enum[value].name, self._enum[value].value)


class BLOBType(DataType):
    minsize = None
    maxsize = None

    def __init__(self, minsize=0, maxsize=None):
        # if only one argument is given, use exactly that many bytes
        # if nothing is given, default to 255
        if maxsize is None:
            maxsize = minsize or 255
        self.minsize = int(minsize)
        self.maxsize = int(maxsize)
        if self.minsize < 0:
            raise BadValueError(u'sizes must be bigger than or equal to 0!')
        elif self.minsize > self.maxsize:
            raise BadValueError(u'maxsize must be bigger than or equal to minsize!')
        self.default = b'\0' * self.minsize

    def export_datatype(self):
        return {u'blob': dict(min=self.minsize, max=self.maxsize)}

    def __repr__(self):
        return u'BLOB(%d, %d)' % (self.minsize, self.maxsize)

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in [unicode, str]:
            raise BadValueError(u'%r has the wrong type!' % value)
        size = len(value)
        if size < self.minsize:
            raise BadValueError(
                u'%r must be at least %d bytes long!' % (value, self.minsize))
        if size > self.maxsize:
            raise BadValueError(
                u'%r must be at most %d bytes long!' % (value, self.maxsize))
        return value

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return b64encode(value)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return b64decode(value)

    def from_string(self, text):
        value = text
        # XXX:
        return self(value)

    def format_value(self, value, unit=None):
        return repr(value)


class StringType(DataType):
    minsize = None
    maxsize = None

    def __init__(self, minsize=0, maxsize=None):
        if maxsize is None:
            maxsize = minsize or 100
        self.minsize = int(minsize)
        self.maxsize = int(maxsize)
        if self.minsize < 0:
            raise BadValueError(u'sizes must be bigger than or equal to 0!')
        elif self.minsize > self.maxsize:
            raise BadValueError(u'maxsize must be bigger than or equal to minsize!')
        self.default = u' ' * self.minsize

    def export_datatype(self):
        return {u'string': dict(min=self.minsize, max=self.maxsize)}

    def __repr__(self):
        return u'StringType(%d, %d)' % (self.minsize, self.maxsize)

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in (unicode, str):
            raise BadValueError(u'%r has the wrong type!' % value)
        size = len(value)
        if size < self.minsize:
            raise BadValueError(
                u'%r must be at least %d bytes long!' % (value, self.minsize))
        if size > self.maxsize:
            raise BadValueError(
                u'%r must be at most %d bytes long!' % (value, self.maxsize))
        if u'\0' in value:
            raise BadValueError(
                u'Strings are not allowed to embed a \\0! Use a Blob instead!')
        return value

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return u'%s' % value

    def import_value(self, value):
        """returns a python object from serialisation"""
        # XXX: do we keep it as unicode str, or convert it to something else? (UTF-8 maybe?)
        return unicode(value)

    def from_string(self, text):
        value = unicode(text)
        return self(value)

    def format_value(self, value, unit=None):
        return repr(value)


# TextType is a special StringType intended for longer texts (i.e. embedding \n),
# whereas StringType is supposed to not contain '\n'
# unfortunately, SECoP makes no distinction here....
# note: content is supposed to follow the format of a git commit message, i.e. a line of text, 2 '\n' + a longer explanation
class TextType(StringType):
    def __init__(self, maxsize=None):
        if maxsize is None:
            maxsize = 8000
        super(TextType, self).__init__(0, maxsize)

    def __repr__(self):
        return u'TextType(%d, %d)' % (self.minsize, self.maxsize)

    def copy(self):
        # DataType.copy will not work, because it is exported as 'string'
        return TextType(self.maxsize)


# Bool is a special enum
class BoolType(DataType):
    default = False

    def export_datatype(self):
        return {u'bool': {}}

    def __repr__(self):
        return u'BoolType()'

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        if value in [0, u'0', u'False', u'false', u'no', u'off', False]:
            return False
        if value in [1, u'1', u'True', u'true', u'yes', u'on', True]:
            return True
        raise BadValueError(u'%r is not a boolean value!' % value)

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return True if self(value) else False

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self(value)

    def from_string(self, text):
        value = text
        return self(value)


    def format_value(self, value, unit=None):
        return repr(bool(value))

#
# nested types
#


class ArrayOf(DataType):
    minsize = None
    maxsize = None
    members = None

    def __init__(self, members, minsize=0, maxsize=None, unit=None):
        if not isinstance(members, DataType):
            raise BadValueError(
                u'ArrayOf only works with a DataType as first argument!')
        # one argument -> exactly that size
        # argument default to 100
        if maxsize is None:
            maxsize = minsize or 100
        self.members = members
        if unit:
            self.members.unit = unit

        self.minsize = int(minsize)
        self.maxsize = int(maxsize)
        if self.minsize < 0:
            raise BadValueError(u'sizes must be > 0')
        elif self.maxsize < 1:
            raise BadValueError(u'Maximum size must be >= 1!')
        elif self.minsize > self.maxsize:
            raise BadValueError(u'maxsize must be bigger than or equal to minsize!')
        self.default = [members.default] * self.minsize

    def export_datatype(self):
        return {u'array': dict(min=self.minsize, max=self.maxsize,
                               members=self.members.export_datatype())}

    def __repr__(self):
        return u'ArrayOf(%s, %s, %s)' % (
            repr(self.members), self.minsize, self.maxsize)

    def __call__(self, value):
        """validate an external representation to an internal one"""
        if isinstance(value, (tuple, list)):
            # check number of elements
            if self.minsize is not None and len(value) < self.minsize:
                raise BadValueError(
                    u'Array too small, needs at least %d elements!' %
                    self.minsize)
            if self.maxsize is not None and len(value) > self.maxsize:
                raise BadValueError(
                    u'Array too big, holds at most %d elements!' % self.minsize)
            # apply subtype valiation to all elements and return as list
            return [self.members(elem) for elem in value]
        raise BadValueError(
            u'Can not convert %s to ArrayOf DataType!' % repr(value))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return [self.members.export_value(elem) for elem in value]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return [self.members.import_value(elem) for elem in value]

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self(value)

    def format_value(self, value, unit=None):
        if unit is None:
            unit = self.unit or self.members.unit
        res = u'[%s]' % (', '.join([self.members.format_value(elem, u'') for elem in value]))
        if unit:
            return ' '.join([res, unit])
        return res


class TupleOf(DataType):

    def __init__(self, *members):
        if not members:
            raise BadValueError(u'Empty tuples are not allowed!')
        for subtype in members:
            if not isinstance(subtype, DataType):
                raise BadValueError(
                    u'TupleOf only works with DataType objs as arguments!')
        self.members = members
        self.default = tuple(el.default for el in members)

    def export_datatype(self):
        return {u'tuple': dict(members=[subtype.export_datatype() for subtype in self.members])}

    def __repr__(self):
        return u'TupleOf(%s)' % u', '.join([repr(st) for st in self.members])

    def __call__(self, value):
        """return the validated value or raise"""
        # keep the ordering!
        try:
            if len(value) != len(self.members):
                raise BadValueError(
                    u'Illegal number of Arguments! Need %d arguments.' %
                        (len(self.members)))
            # validate elements and return as list
            return [sub(elem)
                    for sub, elem in zip(self.members, value)]
        except Exception as exc:
            raise BadValueError(u'Can not validate:', unicode(exc))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return [sub.export_value(elem) for sub, elem in zip(self.members, value)]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return [sub.import_value(elem) for sub, elem in zip(self.members, value)]

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self(value)

    def format_value(self, value, unit=None):
        return u'(%s)' % (', '.join([sub.format_value(elem)
                                     for sub, elem in zip(self.members, value)]))


class StructOf(DataType):

    def __init__(self, optional=None, **members):
        self.members = members
        if not members:
            raise BadValueError(u'Empty structs are not allowed!')
        self.optional = list(optional or [])
        for name, subtype in list(members.items()):
            if not isinstance(subtype, DataType):
                raise ProgrammingError(
                    u'StructOf only works with named DataType objs as keyworded arguments!')
            if not isinstance(name, (unicode, str)):
                raise ProgrammingError(
                    u'StructOf only works with named DataType objs as keyworded arguments!')
        for name in self.optional:
            if name not in members:
                raise ProgrammingError(
                    u'Only members of StructOf may be declared as optional!')
        self.default = dict((k,el.default) for k, el in members.items())

    def export_datatype(self):
        res = {u'struct': dict(members=dict((n, s.export_datatype())
                                       for n, s in list(self.members.items())))}
        if self.optional:
            res['struct']['optional'] = self.optional
        return res

    def __repr__(self):
        return u'StructOf(%s)' % u', '.join(
            [u'%s=%s' % (n, repr(st)) for n, st in list(self.members.items())])

    def __call__(self, value):
        """return the validated value or raise"""
        try:
            # XXX: handle optional elements !!!
            if len(list(value.keys())) != len(list(self.members.keys())):
                raise BadValueError(
                    u'Illegal number of Arguments! Need %d arguments.' %
                        len(list(self.members.keys())))
            # validate elements and return as dict
            return dict((unicode(k), self.members[k](v))
                        for k, v in list(value.items()))
        except Exception as exc:
            raise BadValueError(u'Can not validate %s: %s' % (repr(value), unicode(exc)))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        if len(list(value.keys())) != len(list(self.members.keys())):
            raise BadValueError(
                u'Illegal number of Arguments! Need %d arguments.' % len(
                    list(self.members.keys())))
        return dict((unicode(k), self.members[k].export_value(v))
                    for k, v in list(value.items()))

    def import_value(self, value):
        """returns a python object from serialisation"""
        if len(list(value.keys())) != len(list(self.members.keys())):
            raise BadValueError(
                u'Illegal number of Arguments! Need %d arguments.' % len(
                    list(self.members.keys())))
        return dict((unicode(k), self.members[k].import_value(v))
                    for k, v in list(value.items()))

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self(dict(value))

    def format_value(self, value, unit=None):
        return u'{%s}' % (', '.join(['%s=%s' % (k, self.members[k].format_value(v)) for k, v in sorted(value.items())]))


class CommandType(DataType):
    IS_COMMAND = True
    argument = None
    result = None

    def __init__(self, argument=None, result=None):
        if argument is not None:
            if not isinstance(argument, DataType):
                raise BadValueError(u'CommandType: Argument type must be a DataType!')
        if result is not None:
            if not isinstance(result, DataType):
                raise BadValueError(u'CommandType: Result type must be a DataType!')
        self.argument = argument
        self.result = result

    def export_datatype(self):
        a, r = self.argument, self.result
        props = {}
        if a is not None:
            props['argument'] = a.export_datatype()
        if r is not None:
            props['result'] = r.export_datatype()
        return {u'command': props}

    def __repr__(self):
        argstr = repr(self.argument) if self.argument else ''
        if self.result is None:
            return u'CommandType(%s)' % argstr
        return u'CommandType(%s)->%s' % (argstr, repr(self.result))

    def __call__(self, value):
        """return the validated argument value or raise"""
        return self.argument(value)

    def export_value(self, value):
        raise ProgrammingError(u'values of type command can not be transported!')

    def import_value(self, value):
        raise ProgrammingError(u'values of type command can not be transported!')

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self(value)

    def format_value(self, value, unit=None):
        # actually I have no idea what to do here!
        raise NotImplementedError


# internally used datatypes (i.e. only for programming the SEC-node
class DataTypeType(DataType):
    def __call__(self, value):
        """check if given value (a python obj) is a valid datatype

        returns the value or raises an appropriate exception"""
        if isinstance(value, DataType):
            return value
        raise ProgrammingError(u'%r should be a DataType!' % value)

    def export_value(self, value):
        """if needed, reformat value for transport"""
        return value.export_datatype()

    def import_value(self, value):
        """opposite of export_value, reformat from transport to internal repr

        note: for importing from gui/configfile/commandline use :meth:`from_string`
        instead.
        """
        raise NotImplementedError


class ValueType(DataType):
    """validates any python value"""
    def __call__(self, value):
        """check if given value (a python obj) is valid for this datatype

        returns the value or raises an appropriate exception"""
        return value

    def export_value(self, value):
        """if needed, reformat value for transport"""
        return value

    def import_value(self, value):
        """opposite of export_value, reformat from transport to internal repr

        note: for importing from gui/configfile/commandline use :meth:`from_string`
        instead.
        """
        raise NotImplementedError

class NoneOr(DataType):
    """validates a None or smth. else"""
    default = None

    def __init__(self, other):
        self.other = other

    def __call__(self, value):
        return None if value is None else self.other(value)

    def export_value(self, value):
        if value is None:
            return None
        return self.other.export_value(value)


class OrType(DataType):
    def __init__(self, *types):
        self.types = types
        self.default = self.types[0].default

    def __call__(self, value):
        for t in self.types:
            try:
                return t(value)
            except Exception:
                pass
        raise BadValueError(u"Invalid Value, must conform to one of %s" % (', '.join((str(t) for t in self.types))))


Int8   = IntRange(-(1 << 7),  (1 << 7) - 1)
Int16  = IntRange(-(1 << 15), (1 << 15) - 1)
Int32  = IntRange(-(1 << 31), (1 << 31) - 1)
Int64  = IntRange(-(1 << 63), (1 << 63) - 1)
UInt8  = IntRange(0, (1 << 8) - 1)
UInt16 = IntRange(0, (1 << 16) - 1)
UInt32 = IntRange(0, (1 << 32) - 1)
UInt64 = IntRange(0, (1 << 64) - 1)


# Goodie: Convenience Datatypes for Programming
class LimitsType(StructOf):
    def __init__(self, _min=None, _max=None):
        StructOf.__init__(self, min=FloatRange(_min,_max), max=FloatRange(_min, _max))

    def __call__(self, value):
        limits = StructOf.__call__(self, value)
        if limits['max'] < limits['min']:
            raise BadValueError(u'Maximum Value %s must be greater than minimum value %s!' % (limits['max'], limits['min']))
        return limits


class Status(TupleOf):
    # shorten initialisation and allow acces to status enumMembers from status values
    def __init__(self, enum):
        TupleOf.__init__(self, EnumType(enum), StringType())
        self.enum = enum

    def __getattr__(self, key):
        enum = TupleOf.__getattr__(self, 'enum')
        if hasattr(enum, key):
            return getattr(enum, key)
        return TupleOf.__getattr__(self, key)


# argumentnames to lambda from spec!
DATATYPES = dict(
    bool    =BoolType,
    int     =lambda min, max, **kwds: IntRange(minval=min, maxval=max, **kwds),
    scaled  =lambda scale, min, max, **kwds: ScaledInteger(scale=scale, minval=min*scale, maxval=max*scale, **kwds),
    double  =lambda min=None, max=None, **kwds: FloatRange(minval=min, maxval=max, **kwds),
    blob    =lambda max, min=0: BLOBType(minsize=min, maxsize=max),
    string  =lambda max, min=0: StringType(minsize=min, maxsize=max),
    array   =lambda max, members, min=0: ArrayOf(get_datatype(members), minsize=min, maxsize=max),
    tuple   =lambda members: TupleOf(*map(get_datatype, members)),
    enum    =lambda members: EnumType('', members=members),
    struct  =lambda members, optional=None: StructOf(optional,
        **dict((n, get_datatype(t)) for n, t in list(members.items()))),
    command = lambda argument=None, result=None: CommandType(get_datatype(argument), get_datatype(result)),
)


# important for getting the right datatype from formerly jsonified descr.
def get_datatype(json):
    """returns a DataType object from description

    inverse of <DataType>.export_datatype()
    """
    if json is None:
        return json
    if isinstance(json, list) and len(json) == 2:
        base, args = json # still allow old syntax
    elif isinstance(json, dict) and len(json) == 1:
        base, args = tuple(json.items())[0]
    else:
        raise BadValueError('a data descriptor must be a dict (len=1), not %r' % json)
    try:
        return DATATYPES[base](**args)
    except (TypeError, AttributeError, KeyError):
        raise BadValueError(u'invalid data descriptor: %r' % json)
