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

from __future__ import print_function

try:
    # py2
    unicode
except NameError:
    # py3
    unicode = str  # pylint: disable=redefined-builtin

from base64 import b64encode, b64decode

from secop.lib.enum import Enum
from secop.errors import ProgrammingError, ParsingError
from secop.parse import Parser


Parser = Parser()

# Only export these classes for 'from secop.datatypes import *'
__all__ = [
    u'DataType',
    u'FloatRange', u'IntRange',
    u'BoolType', u'EnumType',
    u'BLOBType', u'StringType',
    u'TupleOf', u'ArrayOf', u'StructOf',
    u'Command',
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
            if minval is None and maxval is None:
                self.as_json = [u'double']
            else:
                self.as_json = [u'double', minval, maxval]
        else:
            raise ValueError(u'Max must be larger then min!')

    def validate(self, value):
        try:
            value = float(value)
        except:
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
                float(u'-inf') if self.min is None else self.min, self.max)
        if self.min is not None:
            return u'FloatRange(%r)' % self.min
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
        self.min = int(minval) if minval is not None else minval
        self.max = int(maxval) if maxval is not None else maxval
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(u'Max must be larger then min!')
        if self.min is None and self.max is None:
            self.as_json = [u'int']
        else:
            self.as_json = [u'int', self.min, self.max]

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
        except:
            raise ValueError(u'Can not validate %r to int' % value)

    def __repr__(self):
        if self.max is not None:
            return u'IntRange(%d, %d)' % (self.min, self.max)
        if self.min is not None:
            return u'IntRange(%d)' % self.min
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


class EnumType(DataType):
    def __init__(self, enum_or_name='', **kwds):
        self._enum = Enum(enum_or_name, **kwds)

    @property
    def as_json(self):
        return [u'enum'] + [dict((m.name, m.value) for m in self._enum.members)]

    def __repr__(self):
        return "EnumType(%r, %s" % (self._enum.name, ', '.join('%s=%d' %(m.name, m.value) for m in self._enum.members))

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
            raise ValueError('%r is not a member of enum %r' % (value, self._enum))

    def from_string(self, text):
        return self.validate(text)


class BLOBType(DataType):
    minsize = None
    maxsize = None
    def __init__(self, maxsize=None, minsize=0):

        if maxsize is None:
            raise ValueError(u'BLOBType needs a maximum number of Bytes count!')
        minsize, maxsize = min(minsize, maxsize), max(minsize, maxsize)
        self.minsize = minsize
        self.maxsize = maxsize
        if minsize < 0:
            raise ValueError(u'sizes must be bigger than or equal to 0!')
        if minsize:
            self.as_json = [u'blob', maxsize, minsize]
        else:
            self.as_json = [u'blob', maxsize]

    def __repr__(self):
        if self.minsize:
            return u'BLOB(%s, %s)' % (
                unicode(self.minsize) if self.minsize else u'unspecified',
                unicode(self.maxsize) if self.maxsize else u'unspecified')
        return u'BLOB(%s)' % (unicode(self.minsize) if self.minsize else u'unspecified')

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

    def __init__(self, maxsize=255, minsize=0):
        if maxsize is None:
            raise ValueError(u'StringType needs a maximum bytes count!')
        minsize, maxsize = min(minsize, maxsize), max(minsize, maxsize)

        if minsize < 0:
            raise ValueError(u'sizes must be >= 0')
        if minsize:
            self.as_json = [u'string', maxsize, minsize]
        else:
            self.as_json = [u'string', maxsize]
        self.minsize = minsize
        self.maxsize = maxsize

    def __repr__(self):
        if self.minsize:
            return u'StringType(%s, %s)' % (
                unicode(self.minsize) or u'unspecified', unicode(self.maxsize) or u'unspecified')
        return u'StringType(%s)' % unicode(self.maxsize)

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
    as_json = [u'bool']

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
    def __init__(self, subtype, maxsize=None, minsize=0):
        self.subtype = subtype
        if not isinstance(subtype, DataType):
            raise ValueError(
                u'ArrayOf only works with DataType objs as first argument!')

        if maxsize is None:
            raise ValueError(u'ArrayOf needs a maximum size')
        minsize, maxsize = min(minsize, maxsize), max(minsize, maxsize)
        if minsize < 0:
            raise ValueError(u'sizes must be > 0')
        if maxsize < 1:
            raise ValueError(u'Maximum size must be >= 1!')
        # if only one arg is given, it is maxsize!
        if minsize:
            self.as_json = [u'array', subtype.as_json, maxsize, minsize]
        else:
            self.as_json = [u'array', subtype.as_json, maxsize]
        self.minsize = minsize
        self.maxsize = maxsize

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
            raise ParsingError(u'trailing garbage: %r' % rem)
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
        self.as_json = [u'tuple', [subtype.as_json for subtype in subtypes]]

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
            raise ParsingError(u'trailing garbage: %r' % rem)
        return self.validate(value)


class StructOf(DataType):

    def __init__(self, **named_subtypes):
        if not named_subtypes:
            raise ValueError(u'Empty structs are not allowed!')
        for name, subtype in list(named_subtypes.items()):
            if not isinstance(subtype, DataType):
                raise ProgrammingError(
                    u'StructOf only works with named DataType objs as keyworded arguments!')
            if not isinstance(name, (unicode, str)):
                raise ProgrammingError(
                    u'StructOf only works with named DataType objs as keyworded arguments!')
        self.named_subtypes = named_subtypes
        self.as_json = [u'struct', dict((n, s.as_json)
                                       for n, s in list(named_subtypes.items()))]

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
            raise ParsingError(u'trailing garbage: %r' % rem)
        return self.validate(dict(value))


# idea to mix commands and params, not yet used....
class Command(DataType):
    IS_COMMAND = True

    def __init__(self, argtypes=tuple(), resulttype=None):
        for arg in argtypes:
            if not isinstance(arg, DataType):
                raise ValueError(u'Command: Argument types must be DataTypes!')
        if resulttype is not None:
            if not isinstance(resulttype, DataType):
                raise ValueError(u'Command: result type must be DataTypes!')
        self.argtypes = argtypes
        self.resulttype = resulttype

        if resulttype is not None:
            self.as_json = [u'command',
                            [t.as_json for t in argtypes],
                            resulttype.as_json]
        else:
            self.as_json = [u'command',
                            [t.as_json for t in argtypes],
                            None]  # XXX: or NoneType ???

    def __repr__(self):
        argstr = u', '.join(repr(arg) for arg in self.argtypes)
        if self.resulttype is None:
            return u'Command(%s)' % argstr
        return u'Command(%s)->%s' % (argstr, repr(self.resulttype))

    def validate(self, value):
        """return the validated arguments value or raise"""
        try:
            if len(value) != len(self.argtypes):
                raise ValueError(
                    u'Illegal number of Arguments! Need %d arguments.' %
                        len(self.argtypes))
            # validate elements and return
            return [t.validate(v) for t, v in zip(self.argtypes, value)]
        except Exception as exc:
            raise ValueError(u'Can not validate %s: %s' % (repr(value), unicode(exc)))

    def export_value(self, value):
        raise ProgrammingError(u'values of type command can not be transported!')

    def import_value(self, value):
        raise ProgrammingError(u'values of type command can not be transported!')

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ParsingError(u'trailing garbage: %r' % rem)
        return self.validate(value)


# XXX: derive from above classes automagically!
DATATYPES = dict(
    bool=BoolType,
    int=lambda _min=None, _max=None: IntRange(_min, _max),
    double=lambda _min=None, _max=None: FloatRange(_min, _max),
    blob=lambda _max=None, _min=0: BLOBType(_max, _min),
    string=lambda _max=None, _min=0: StringType(_max, _min),
    array=lambda subtype, _max=None, _min=0: ArrayOf(get_datatype(subtype), _max, _min),
    tuple=lambda subtypes: TupleOf(*map(get_datatype, subtypes)),
    enum=lambda kwds: EnumType('', **kwds),
    struct=lambda named_subtypes: StructOf(
        **dict((n, get_datatype(t)) for n, t in list(named_subtypes.items()))),
    command=Command,
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
    if len(json) < 1:
        raise ValueError(u'can not validate %r' % json)
    base = json[0]
    if base in DATATYPES:
        if base in (u'enum', u'struct'):
            if len(json) > 1:
                args = json[1:]
            else:
                args = []
        else:
            args = json[1:]
        try:
            return DATATYPES[base](*args)
        except (TypeError, AttributeError):
            raise ValueError(u'Invalid datatype descriptor in %r' % json)
    raise ValueError(u'can not convert %r to datatype' % json)
