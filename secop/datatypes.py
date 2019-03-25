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

from __future__ import division, print_function

from base64 import b64decode, b64encode

from secop.errors import ProgrammingError, ProtocolError
from secop.lib.enum import Enum
from secop.parse import Parser

try:
    # py2
    unicode
except NameError:
    # py3
    unicode = str  # pylint: disable=redefined-builtin


Parser = Parser()

# Only export these classes for 'from secop.datatypes import *'
__all__ = [
    u'DataType',
    u'FloatRange', u'IntRange',
    u'BoolType', u'EnumType',
    u'BLOBType', u'StringType',
    u'TupleOf', u'ArrayOf', u'StructOf',
    u'CommandType',
]

# base class for all DataTypes


class DataType(object):
    as_json = [u'undefined']
    IS_COMMAND = False

    def validate(self, value):
        """check if given value (a python obj) is valid for this datatype

        returns the value or raises an appropriate exception"""
        raise NotImplementedError

    def from_string(self, text):
        """interprets a given string and returns a validated (internal) value"""
        # to evaluate values from configfiles, ui, etc...
        raise NotImplementedError

    def export_datatype(self):
        """return a python object which after jsonifying identifies this datatype"""
        return self.as_json

    def export_value(self, value):
        """if needed, reformat value for transport"""
        return value

    def import_value(self, value):
        """opposite of export_value, reformat from transport to internal repr

        note: for importing from gui/configfile/commandline use :meth:`from_string`
        instead.
        """
        return value


class FloatRange(DataType):
    """Restricted float type"""

    def __init__(self, minval=None, maxval=None):
        self.min = None if minval is None else float(minval)
        self.max = None if maxval is None else float(maxval)
        # note: as we may compare to Inf all comparisons would be false
        if (self.min or float(u'-inf')) <= (self.max or float(u'+inf')):
            self.as_json = [u'double', dict()]
            if self.min:
                self.as_json[1]['min'] = self.min
            if self.max:
                self.as_json[1]['max'] = self.max
        else:
            raise ValueError(u'Max must be larger then min!')

    def validate(self, value):
        try:
            value = float(value)
        except Exception:
            raise ValueError(u'Can not validate %r to float' % value)
        if self.min is not None and value < self.min:
            raise ValueError(u'%r should not be less then %s' %
                             (value, self.min))
        if self.max is not None and value > self.max:
            raise ValueError(u'%r should not be greater than %s' %
                             (value, self.max))
        if None in (self.min, self.max):
            return value
        if self.min <= value <= self.max:
            return value
        raise ValueError(u'%r should be an float between %.3f and %.3f' %
                         (value, self.min, self.max))

    def __repr__(self):
        if self.max is not None:
            return u'FloatRange(%r, %r)' % (
                float(u'-inf') if self.min is None else self.min,
                float(u'inf') if self.max is None else self.max)
        return u'FloatRange()'

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return float(value)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return float(value)

    def from_string(self, text):
        value = float(text)
        return self.validate(value)


class IntRange(DataType):
    """Restricted int type"""

    def __init__(self, minval=None, maxval=None):
        self.min = -16777216 if minval is None else int(minval)
        self.max = 16777216 if maxval is None else int(maxval)
        if self.min > self.max:
            raise ValueError(u'Max must be larger then min!')
        if None in (self.min, self.max):
            raise ValueError(u'Limits can not be None!')
        self.as_json = [u'int', {'min':self.min, 'max':self.max}]

    def validate(self, value):
        try:
            value = int(value)
            if self.min is not None and value < self.min:
                raise ValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min, self.max or 0))
            if self.max is not None and value > self.max:
                raise ValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min or 0, self.max))
            return value
        except Exception:
            raise ValueError(u'Can not validate %r to int' % value)

    def __repr__(self):
        if self.max is not None:
            return u'IntRange(%d, %d)' % (self.min, self.max)
        return u'IntRange()'

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return int(value)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return int(value)

    def from_string(self, text):
        value = int(text)
        return self.validate(value)


class ScaledInteger(DataType):
    """Scaled integer int type

    note: limits are for the scaled value (i.e. the internal value)
          the scale is only used for calculating to/from transport serialisation"""

    def __init__(self, scale, minval=-16777216, maxval=16777216):
        self.min = int(minval)
        self.max = int(maxval)
        self.scale = float(scale)
        if self.min > self.max:
            raise ValueError(u'Max must be larger then min!')
        if not self.scale > 0:
            raise ValueError(u'Scale MUST be positive!')
        self.as_json = [u'scaled', dict(min=int(round(minval/scale)), max=int(round(maxval/scale)), scale=scale)]

    def validate(self, value):
        try:
            value = int(value)
            if value < self.min:
                raise ValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min, self.max))
            if value > self.max:
                raise ValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min, self.max))
            return value
        except Exception:
            raise ValueError(u'Can not validate %r to int' % value)

    def __repr__(self):
        return u'ScaledInteger(%f, %d, %d)' % (self.scale, self.min, self.max)

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        # XXX: rounds toward even !!! (i.e. 12.5 -> 12, 13.5 -> 14)
        return round(value / self.scale)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self.scale * int(value)

    def from_string(self, text):
        value = int(text)
        return self.validate(value)


class EnumType(DataType):
    def __init__(self, enum_or_name='', **kwds):
        if 'members' in kwds:
            kwds = dict(kwds)
            kwds.update(kwds['members'])
            kwds.pop('members')
        self._enum = Enum(enum_or_name, **kwds)

    @property
    def as_json(self):
        return [u'enum'] + [{"members":dict((m.name, m.value) for m in self._enum.members)}]

    def __repr__(self):
        return u"EnumType(%r, %s)" % (self._enum.name, ', '.join(u'%s=%d' %(m.name, m.value) for m in self._enum.members))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return int(self.validate(value))

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self.validate(value)

    def validate(self, value):
        """return the validated (internal) value or raise"""
        try:
            return self._enum[value]
        except KeyError:
            raise ValueError(u'%r is not a member of enum %r' % (value, self._enum))

    def from_string(self, text):
        return self.validate(text)


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
            raise ValueError(u'sizes must be bigger than or equal to 0!')
        elif self.minsize > self.maxsize:
            raise ValueError(u'maxsize must be bigger than or equal to minsize!')
        self.as_json = [u'blob', dict(min=minsize, max=maxsize)]

    def __repr__(self):
        return u'BLOB(%s, %s)' % (unicode(self.minsize), unicode(self.maxsize))

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in [unicode, str]:
            raise ValueError(u'%r has the wrong type!' % value)
        size = len(value)
        if size < self.minsize:
            raise ValueError(
                u'%r must be at least %d bytes long!' % (value, self.minsize))
        if self.maxsize is not None:
            if size > self.maxsize:
                raise ValueError(
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
        return self.validate(value)


class StringType(DataType):
    as_json = [u'string']
    minsize = None
    maxsize = None

    def __init__(self, minsize=0, maxsize=None):
        if maxsize is None:
            maxsize = minsize or 255
        self.minsize = int(minsize)
        self.maxsize = int(maxsize)
        if self.minsize < 0:
            raise ValueError(u'sizes must be bigger than or equal to 0!')
        elif self.minsize > self.maxsize:
            raise ValueError(u'maxsize must be bigger than or equal to minsize!')
        self.as_json = [u'string', dict(min=minsize, max=maxsize)]

    def __repr__(self):
        return u'StringType(%s, %s)' % (unicode(self.minsize), unicode(self.maxsize))

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in (unicode, str):
            raise ValueError(u'%r has the wrong type!' % value)
        size = len(value)
        if size < self.minsize:
            raise ValueError(
                u'%r must be at least %d bytes long!' % (value, self.minsize))
        if self.maxsize is not None:
            if size > self.maxsize:
                raise ValueError(
                    u'%r must be at most %d bytes long!' % (value, self.maxsize))
        if u'\0' in value:
            raise ValueError(
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
        return self.validate(value)

# Bool is a special enum


class BoolType(DataType):

    def __init__(self):
        self.as_json = [u'bool', dict()]

    def __repr__(self):
        return u'BoolType()'

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if value in [0, u'0', u'False', u'false', u'no', u'off', False]:
            return False
        if value in [1, u'1', u'True', u'true', u'yes', u'on', True]:
            return True
        raise ValueError(u'%r is not a boolean value!' % value)

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return True if self.validate(value) else False

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self.validate(value)

    def from_string(self, text):
        value = text
        return self.validate(value)

#
# nested types
#


class ArrayOf(DataType):
    minsize = None
    maxsize = None
    subtype = None

    def __init__(self, members, minsize=0, maxsize=None):
        # one argument -> exactly that size
        # argument default to 10
        if maxsize is None:
            maxsize = minsize or 10
        if not isinstance(members, DataType):
            raise ValueError(
                u'ArrayOf only works with a DataType as first argument!')
        self.subtype = members

        self.minsize = int(minsize)
        self.maxsize = int(maxsize)
        if self.minsize < 0:
            raise ValueError(u'sizes must be > 0')
        elif self.maxsize < 1:
            raise ValueError(u'Maximum size must be >= 1!')
        elif self.minsize > self.maxsize:
            raise ValueError(u'maxsize must be bigger than or equal to minsize!')
        # if only one arg is given, it is maxsize!
        self.as_json = [u'array', dict(min=minsize, max=maxsize, members=members.as_json)]

    def __repr__(self):
        return u'ArrayOf(%s, %s, %s)' % (
            repr(self.subtype), self.minsize or u'unspecified', self.maxsize or u'unspecified')

    def validate(self, value):
        """validate a external representation to an internal one"""
        if isinstance(value, (tuple, list)):
            # check number of elements
            if self.minsize is not None and len(value) < self.minsize:
                raise ValueError(
                    u'Array too small, needs at least %d elements!' %
                    self.minsize)
            if self.maxsize is not None and len(value) > self.maxsize:
                raise ValueError(
                    u'Array too big, holds at most %d elements!' % self.minsize)
            # apply subtype valiation to all elements and return as list
            return [self.subtype.validate(elem) for elem in value]
        raise ValueError(
            u'Can not convert %s to ArrayOf DataType!' % repr(value))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return [self.subtype.export_value(elem) for elem in value]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return [self.subtype.import_value(elem) for elem in value]

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self.validate(value)


class TupleOf(DataType):

    def __init__(self, *subtypes):
        if not subtypes:
            raise ValueError(u'Empty tuples are not allowed!')
        for subtype in subtypes:
            if not isinstance(subtype, DataType):
                raise ValueError(
                    u'TupleOf only works with DataType objs as arguments!')
        self.subtypes = subtypes
        self.as_json = [u'tuple', dict(members=[subtype.as_json for subtype in subtypes])]

    def __repr__(self):
        return u'TupleOf(%s)' % u', '.join([repr(st) for st in self.subtypes])

    def validate(self, value):
        """return the validated value or raise"""
        # keep the ordering!
        try:
            if len(value) != len(self.subtypes):
                raise ValueError(
                    u'Illegal number of Arguments! Need %d arguments.' %
                        (len(self.subtypes)))
            # validate elements and return as list
            return [sub.validate(elem)
                    for sub, elem in zip(self.subtypes, value)]
        except Exception as exc:
            raise ValueError(u'Can not validate:', unicode(exc))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return [sub.export_value(elem) for sub, elem in zip(self.subtypes, value)]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return [sub.import_value(elem) for sub, elem in zip(self.subtypes, value)]

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self.validate(value)


class StructOf(DataType):

    def __init__(self, optional=None, **members):
        self.named_subtypes = members
        if not members:
            raise ValueError(u'Empty structs are not allowed!')
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
        self.as_json = [u'struct', dict(members=dict((n, s.as_json)
                                       for n, s in list(members.items())))]
        if optional:
            self.as_json[1]['optional'] = self.optional


    def __repr__(self):
        return u'StructOf(%s)' % u', '.join(
            [u'%s=%s' % (n, repr(st)) for n, st in list(self.named_subtypes.items())])

    def validate(self, value):
        """return the validated value or raise"""
        try:
            if len(list(value.keys())) != len(list(self.named_subtypes.keys())):
                raise ValueError(
                    u'Illegal number of Arguments! Need %d arguments.' %
                        len(list(self.named_subtypes.keys())))
            # validate elements and return as dict
            return dict((unicode(k), self.named_subtypes[k].validate(v))
                        for k, v in list(value.items()))
        except Exception as exc:
            raise ValueError(u'Can not validate %s: %s' % (repr(value), unicode(exc)))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        if len(list(value.keys())) != len(list(self.named_subtypes.keys())):
            raise ValueError(
                u'Illegal number of Arguments! Need %d arguments.' % len(
                    list(self.namd_subtypes.keys())))
        return dict((unicode(k), self.named_subtypes[k].export_value(v))
                    for k, v in list(value.items()))

    def import_value(self, value):
        """returns a python object from serialisation"""
        if len(list(value.keys())) != len(list(self.named_subtypes.keys())):
            raise ValueError(
                u'Illegal number of Arguments! Need %d arguments.' % len(
                    list(self.namd_subtypes.keys())))
        return dict((unicode(k), self.named_subtypes[k].import_value(v))
                    for k, v in list(value.items()))

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self.validate(dict(value))


class CommandType(DataType):
    IS_COMMAND = True
    argtype = None
    resulttype = None

    def __init__(self, argument=None, result=None):
        if argument is not None:
            if not isinstance(argument, DataType):
                raise ValueError(u'CommandType: Argument type must be a DataType!')
        if result is not None:
            if not isinstance(result, DataType):
                raise ValueError(u'CommandType: Result type must be a DataType!')
        self.argtype = argument
        self.resulttype = result

        if argument:
            argument = argument.as_json
        if result:
            result = result.as_json
        self.as_json = [u'command', dict(argument=argument, result=result)]

    def __repr__(self):
        argstr = repr(self.argtype) if self.argtype else ''
        if self.resulttype is None:
            return u'CommandType(%s)' % argstr
        return u'CommandType(%s)->%s' % (argstr, repr(self.resulttype))

    def validate(self, value):
        """return the validated argument value or raise"""
        return self.argtype.validate(value)

    def export_value(self, value):
        raise ProgrammingError(u'values of type command can not be transported!')

    def import_value(self, value):
        raise ProgrammingError(u'values of type command can not be transported!')

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(u'trailing garbage: %r' % rem)
        return self.validate(value)


# Goodie: Convenience Datatypes for Programming
class LimitsType(StructOf):
    def __init__(self, _min=None, _max=None):
        StructOf.__init__(self, min=FloatRange(_min,_max), max=FloatRange(_min, _max))

    def validate(self, value):
        limits = StructOf.validate(self, value)
        if limits.max < limits.min:
            raise ValueError(u'Maximum Value %s must be greater than minimum value %s!' % (limits['max'], limits['min']))
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
    int     =lambda min, max: IntRange(minval=min,maxval=max),
    scaled  =lambda scale, min, max: ScaledInteger(scale=scale,minval=min*scale,maxval=max*scale),
    double  =lambda min=None, max=None: FloatRange(minval=min, maxval=max),
    blob    =lambda min=0, max=None: BLOBType(minsize=min, maxsize=max),
    string  =lambda min=0, max=None: StringType(minsize=min, maxsize=max),
    array   =lambda min, max, members: ArrayOf(get_datatype(members), minsize=min, maxsize=max),
    tuple   =lambda members=[]: TupleOf(*map(get_datatype, members)),
    enum    =lambda members={}: EnumType('', members=members),
    struct  =lambda members: StructOf(
        **dict((n, get_datatype(t)) for n, t in list(members.items()))),
    command = lambda argument, result: CommandType(get_datatype(argument), get_datatype(result)),
)


# important for getting the right datatype from formerly jsonified descr.
def get_datatype(json):
    """returns a DataType object from description

    inverse of <DataType>.export_datatype()
    """
    if json is None:
        return json
    if not isinstance(json, list):
        raise ValueError(
            u'Can not interpret datatype %r, it should be a list!' % json)
    if len(json) != 2:
        raise ValueError(u'Can not interpret datatype %r, it should be a list of 2 elements!' % json)
    base, args = json
    if base in DATATYPES:
        try:
            return DATATYPES[base](**args)
        except (TypeError, AttributeError):
            raise ValueError(u'Invalid datatype descriptor in %r' % json)
    raise ValueError(u'can not convert %r to datatype: unknown descriptor!' % json)
