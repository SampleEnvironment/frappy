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

# *DEFAULT* limits for IntRange/ScaledIntegers transport serialisation
DEFAULT_MIN_INT = -16777216
DEFAULT_MAX_INT = 16777216

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

    unit = u''
    fmtstr = u'%f'
    def __init__(self, minval=None, maxval=None, unit=u'', fmtstr=u'',
                       absolute_precision=None, relative_precision=None,):
        # store hints
        self.hints = {}
        self.unit = unicode(unit)
        self.fmtstr = unicode(fmtstr or u'%f')
        self.abs_prec = float(absolute_precision or 0.0)
        self.rel_prec = float(relative_precision or 1.2e-7)

        # store values for the validator
        self.min = float(u'-inf') if minval is None else float(minval)
        self.max = float(u'+inf') if maxval is None else float(maxval)

        # check values
        if self.min > self.max:
            raise ValueError(u'Max must be larger then min!')
        if '%' not in self.fmtstr:
            raise ValueError(u'Invalid fmtstr!')
        if self.abs_prec < 0:
            raise ValueError(u'absolute_precision MUST be >=0')
        if self.rel_prec < 0:
            raise ValueError(u'relative_precision MUST be >=0')

        info = {}
        if self.min != float(u'-inf'):
            info[u'min'] = self.min
        if self.max != float(u'inf'):
            info[u'max'] = self.max
        if unit:
            self.hints[u'unit'] = self.unit
        if fmtstr:
            self.hints[u'fmtstr'] = self.fmtstr
        if absolute_precision is not None:
            self.hints[u'absolute_precision'] = self.abs_prec
        if relative_precision is not None:
            self.hints[u'relative_precision'] = self.rel_prec
        info.update(self.hints)
        self.as_json = [u'double', info]

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
        items = [] if self.max or self.min is None else \
                [u'-inf' if self.min == float(u'-inf') else self.fmtstr % self.min,
                 u'inf' if self.max == float(u'inf') else self.fmtstr % self.max]
        for k,v in self.hints.items():
            items.append(u'%s=%r' % (k,v))
        return u'FloatRange(%s)' % (', '.join(items))

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

    unit = u''
    fmtstr = u'%f'
    def __init__(self, minval=None, maxval=None, fmtstr=u'%d', unit=u''):
        self.hints = {}
        self.fmtstr = unicode(fmtstr)
        self.unit = unicode(unit)
        self.min = DEFAULT_MIN_INT if minval is None else int(minval)
        self.max = DEFAULT_MAX_INT if maxval is None else int(maxval)

        # check values
        if self.min > self.max:
            raise ValueError(u'Max must be larger then min!')
        if '%' not in self.fmtstr:
            raise ValueError(u'Invalid fmtstr!')

        info = {}
        self.hints = {}
        info[u'min'] = self.min
        info[u'max'] = self.max
        if unit:
            self.hints[u'unit'] = self.unit
        if fmtstr != u'%d':
            self.hints[u'fmtstr'] = self.fmtstr
        info.update(self.hints)
        self.as_json = [u'int', info]

    def validate(self, value):
        try:
            value = int(value)
            if value < self.min:
                raise ValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min, self.max or 0))
            if value > self.max:
                raise ValueError(u'%r should be an int between %d and %d' %
                                 (value, self.min or 0, self.max))
            return value
        except Exception:
            raise ValueError(u'Can not validate %r to int' % value)

    def __repr__(self):
        items = [u"%d, %d" % (self.min, self.max)]
        for k, v in self.hints.items():
            items.append(u'%s=%r' % (k, v))
        return u'IntRange(%s)' % (u', '.join(items))

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

    unit = u''
    fmtstr = u'%f'
    def __init__(self, scale, minval=None, maxval=None, unit=u'', fmtstr=u'',
                       absolute_precision=None, relative_precision=None,):
        self.scale = float(scale)
        if not self.scale > 0:
            raise ValueError(u'Scale MUST be positive!')

        # store hints
        self.hints = {}
        self.unit = unicode(unit)
        self.fmtstr = unicode(fmtstr or u'%f')
        self.abs_prec = float(absolute_precision or self.scale)
        self.rel_prec = float(relative_precision or 0)

        self.min = DEFAULT_MIN_INT * self.scale if minval is None else float(minval)
        self.max = DEFAULT_MAX_INT * self.scale if maxval is None else float(maxval)

        # check values
        if self.min > self.max:
            raise ValueError(u'Max must be larger then min!')
        if '%' not in self.fmtstr:
            raise ValueError(u'Invalid fmtstr!')
        if self.abs_prec < 0:
            raise ValueError(u'absolute_precision MUST be >=0')
        if self.rel_prec < 0:
            raise ValueError(u'relative_precision MUST be >=0')

        info = {}
        self.hints = {}
        info[u'min'] = int(self.min // self.scale)
        info[u'max'] = int((self.max + self.scale * 0.5) // self.scale)
        info[u'scale'] = self.scale
        if unit:
            self.hints[u'unit'] = self.unit
        if fmtstr:
            self.hints[u'fmtstr'] = self.fmtstr
        if absolute_precision is not None:
            self.hints[u'absolute_precision'] = self.abs_prec
        if relative_precision is not None:
            self.hints[u'relative_precision'] = self.rel_prec
        info.update(self.hints)
        self.as_json = [u'scaled', info]

    def validate(self, value):
        try:
            value = float(value)
        except Exception:
            raise ValueError(u'Can not validate %r to float' % value)
        if value < self.min:
            raise ValueError(u'%r should be a float between %d and %d' %
                             (value, self.min, self.max))
        if value > self.max:
            raise ValueError(u'%r should be a float between %d and %d' %
                             (value, self.min, self.max))
        intval = int((value + self.scale * 0.5) // self.scale)
        value = float(intval * self.scale)
        return value  # return 'actual' value (which is more discrete than a float)

    def __repr__(self):
        items = [self.fmtstr % self.scale, self.fmtstr % self.min, self.fmtstr % self.max]
        for k,v in self.hints.items():
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
        value = int(text)
        return self.validate(value)


class EnumType(DataType):

    def __init__(self, enum_or_name='', **kwds):
        if u'members' in kwds:
            kwds = dict(kwds)
            kwds.update(kwds[u'members'])
            kwds.pop(u'members')
        self._enum = Enum(enum_or_name, **kwds)

    @property
    def as_json(self):
        return [u'enum'] + [{u"members":dict((m.name, m.value) for m in self._enum.members)}]

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
        return u'BLOB(%d, %d)' % (self.minsize, self.maxsize)

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in [unicode, str]:
            raise ValueError(u'%r has the wrong type!' % value)
        size = len(value)
        if size < self.minsize:
            raise ValueError(
                u'%r must be at least %d bytes long!' % (value, self.minsize))
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
        return u'StringType(%d, %d)' % (self.minsize, self.maxsize)

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in (unicode, str):
            raise ValueError(u'%r has the wrong type!' % value)
        size = len(value)
        if size < self.minsize:
            raise ValueError(
                u'%r must be at least %d bytes long!' % (value, self.minsize))
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
        self.as_json = [u'bool', {}]

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
        if not isinstance(members, DataType):
            raise ValueError(
                u'ArrayOf only works with a DataType as first argument!')
        # one argument -> exactly that size
        # argument default to 10
        if maxsize is None:
            maxsize = minsize or 10
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
    int     =lambda min, max, **kwds: IntRange(minval=min, maxval=max, **kwds),
    scaled  =lambda scale, min, max, **kwds: ScaledInteger(scale=scale, minval=min*scale, maxval=max*scale, **kwds),
    double  =lambda min=None, max=None, **kwds: FloatRange(minval=min, maxval=max, **kwds),
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
