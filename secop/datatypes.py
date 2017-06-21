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

# a Validator returns a validated object or raises an ValueError
# also validators should have a __repr__ returning a 'python' string
# which recreates them

# if a validator does a mapping, it normally maps to the
# internal representation with method :meth:`validate`
# to get the external representation (aöso for logging),
# call method :meth:`export`


from .errors import ProgrammingError
from collections import OrderedDict


# base class for all DataTypes
class DataType(object):
    as_json = ['undefined']

    def validate(self, value):
        """validate a external representation and return an internal one"""
        raise NotImplemented

    def export(self, value):
        """returns a python object fit for external serialisation or logging"""
        raise NotImplemented

    # goodie: if called, validate
    def __call__(self, value):
        return self.validate(value)


class FloatRange(DataType):
    """Restricted float type"""

    def __init__(self, min=None, max=None):
        self.min = float('-Inf') if min is None else float(min)
        self.max = float('+Inf') if max is None else float(max)
        # note: as we may compare to Inf all comparisons would be false
        if self.min <= self.max:
            self.as_json = ['double', min, max]
        else:
            raise ValueError('Max must be larger then min!')

    def validate(self, value):
        try:
            value = float(value)
            if self.min <= value <= self.max:
                return value
            raise ValueError('%r should be an float between %.3f and %.3f' %
                             (value, self.min, self.max))
        except:
            raise ValueError('Can not validate %r to float' % value)

    def __repr__(self):
        return "FloatRange(%f, %f)" % (self.min, self.max)

    def export(self, value):
        """returns a python object fit for serialisation"""
        return float(value)


class IntRange(DataType):
    """Restricted int type"""
    def __init__(self, min=None, max=None):
        self.min = int(min) if min is not None else min
        self.max = int(max) if max is not None else max
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError('Max must be larger then min!')
        self.as_json = ['int', self.min, self.max]

    def validate(self, value):
        try:
            value = int(value)
            if self.min is not None and value < self.min:
                raise ValueError('%r should be an int between %d and %d' %
                             (value, self.min, self.max or 0))
            if self.max is not None and value > self.max:
                raise ValueError('%r should be an int between %d and %d' %
                             (value, self.min or 0, self.max))
            return value
        except:
            raise ValueError('Can not validate %r to int' % value)

    def __repr__(self):
        return "IntRange(%d, %d)" % (self.min, self.max)

    def export(self, value):
        """returns a python object fit for serialisation"""
        return int(value)


class EnumType(DataType):
    as_json = ['enum']
    def __init__(self, *args, **kwds):
        # enum keys are ints! check
        self.entries = {}
        num = 0
        for arg in args:
            if type(args) != str:
                raise ValueError('EnumType entries MUST be strings!')
            self.entries[num] = arg
            num += 1
        for k, v in kwds.items():
            v = int(v)
            if v in self.entries:
                raise ValueError('keyword argument %r=%d is already assigned %r', k, v, self.entries[v])
            self.entries[v] = k
        if len(self.entries) == 0:
            raise ValueError('Empty enums ae not allowed!')
        self.reversed = {}
        for k,v in self.entries.items():
            if v in self.reversed:
                raise ValueError('Mapping for %r=%r is not Unique!', v, k)
            self.reversed[v] = k
        self.as_json = ['enum', self.reversed.copy()]

    def __repr__(self):
        return "EnumType(%s)" % ', '.join(['%r=%d' % (v,k) for k,v in self.entries.items()])

    def export(self, value):
        """returns a python object fit for serialisation"""
        if value in self.reversed:
            return self.reversed[value]
        if int(value) in self.entries:
            return int(value)
        raise ValueError('%r is not one of %s', str(value), ', '.join(self.reversed.keys()))

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if value in self.reversed:
            return value
        if int(value) in self.entries:
            return self.entries[int(value)]
        raise ValueError('%r is not one of %s', str(value), ', '.join(map(str,self.entries.keys())))


class BLOBType(DataType):
    def __init__(self, minsize=0, maxsize=None):
        self.minsize = minsize
        self.maxsize = maxsize
        if minsize or maxsize:
            self.as_json = ['blob', minsize, maxsize]
        else:
            self.as_json = ['blob']
        if minsize is not None and maxsize is not None and minsize > maxsize:
            raise ValueError('maxsize must be bigger than minsize!')

    def __repr__(self):
        if self.minsize or self.maxsize:
            return 'BLOB(%d, %s)' % (self.minsize, self.maxsize)
        return 'BLOB()'

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in [str, unicode]:
            raise ValueError('%r has the wrong type!', value)
        size = len(value)
        if size < self.minsize:
            raise ValueError('%r must be at least %d bytes long!', value, self.minsize)
        if self.maxsize is not None:
            if size > self.maxsize:
                raise ValueError('%r must be at most %d bytes long!', value, self.maxsize)
        return value

    def export(self, value):
        """returns a python object fit for serialisation"""
        return b'%s' % value


class StringType(DataType):
    as_json = ['string']
    def __init__(self, minsize=0, maxsize=None):
        self.minsize = minsize
        self.maxsize = maxsize
        if (minsize, maxsize) == (0, None):
            self.as_json = ['string']
        else:
            self.as_json = ['string', minsize, maxsize]
        if minsize is not None and maxsize is not None and minsize > maxsize:
            raise ValueError('maxsize must be bigger than minsize!')

    def __repr__(self):
        return 'StringType(%d, %s)' % (self.minsize, self.maxsize)

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if type(value) not in [str, unicode]:
            raise ValueError('%r has the wrong type!', value)
        size = len(value)
        if size < self.minsize:
            raise ValueError('%r must be at least %d bytes long!', value, self.minsize)
        if self.maxsize is not None:
            if size > self.maxsize:
                raise ValueError('%r must be at most %d bytes long!', value, self.maxsize)
        if '\0' in value:
            raise ValueError('Strings are not allowed to embed a \\0! Use a Blob instead!')
        return value

    def export(self, value):
        """returns a python object fit for serialisation"""
        return '%s' % value

# Bool is a special enum
class BoolType(DataType):
    as_json = ['bool']
    def __repr__(self):
        return 'BoolType()'

    def validate(self, value):
        """return the validated (internal) value or raise"""
        if value in [0, '0', 'False', 'false', 'no', 'off', False]:
            return False
        if value in [1, '1', 'True', 'true', 'yes', 'on', True]:
            return True
        raise ValueError('%r is not a boolean value!', value)

    def export(self, value):
        """returns a python object fit for serialisation"""
        return True if self.validate(value) else False


#
# nested types
#
class ArrayOf(DataType):
    def __init__(self, subtype, minsize_or_size=None, maxsize=None):
        if maxsize is None:
            maxsize = minsize_or_size
        self.minsize = minsize_or_size
        self.maxsize = maxsize
        if self.minsize is not None and self.maxsize is not None and \
            self.minsize > self.maxsize:
                raise ValueError('minsize must be less than or equal to maxsize!')
        if not isinstance(subtype, DataType):
            raise ValueError('ArrayOf only works with DataType objs as first argument!')
        self.subtype = subtype
        self.as_json = ['array', self.subtype.as_json, self.minsize, self.maxsize]
        if self.minsize is not None and self.minsize < 0:
            raise ValueError('Minimum size must be >= 0!')
        if self.maxsize is not None and self.maxsize < 1:
            raise ValueError('Maximum size must be >= 1!')
        if self.minsize is not None and self.maxsize is not None and self.minsize > self.maxsize:
            raise ValueError('Maximum size must be >= Minimum size')

    def validate(self, value):
        """validate a external representation to an internal one"""
        if isinstance(value, (tuple, list)):
            # check number of elements
            if self.minsize is not None and len(value) < self.minsize:
                raise ValueError('Array too small, needs at least %d elements!', self.minsize)
            if self.maxsize is not None and len(value) > self.maxsize:
                raise ValueError('Array too big, holds at most %d elements!', self.minsize)
            # apply subtype valiation to all elements and return as list
            return [self.subtype.validate(elem) for elem in value]
        raise ValueError('Can not convert %s to ArrayOf DataType!', repr(value))

    def export(self, value):
        """returns a python object fit for serialisation"""
        return [self.subtype.export(elem) for elem in value]


class TupleOf(DataType):
    def __init__(self, *subtypes):
        if not subtypes:
            raise ValueError('Empty tuples are not allowed!')
        for subtype in subtypes:
            if not isinstance(subtype, DataType):
                raise ValueError('TupleOf only works with DataType objs as arguments!')
        self.subtypes = subtypes
        self.as_json = ['tuple', [subtype.as_json for subtype in subtypes]]

    def validate(self, value):
        """return the validated value or raise"""
        # keep the ordering!
        try:
            if len(value) != len(self.subtypes):
                raise ValueError('Illegal number of Arguments! Need %d arguments.', len(self.subtypes))
            # validate elements and return as list
            return [sub.validate(elem) for sub,elem in zip(self.subtypes, value)]
        except Exception as exc:
            raise ValueError('Can not validate:', str(exc))

    def export(self, value):
        """returns a python object fit for serialisation"""
        return [sub.export(elem) for sub,elem in zip(self.subtypes, value)]


class StructOf(DataType):
    def __init__(self, **named_subtypes):
        if not named_subtypes:
            raise ValueError('Empty structs are not allowed!')
        for name, subtype in named_subtypes.items():
            if not isinstance(subtype, DataType):
                raise ProgrammingError('StructOf only works with named DataType objs as keyworded arguments!')
            if not isinstance(name, (str, unicode)):
                raise ProgrammingError('StructOf only works with named DataType objs as keyworded arguments!')
        self.named_subtypes = named_subtypes
        self.as_json = ['struct', dict((n,s.as_json) for n,s in named_subtypes.items())]

    def validate(self, value):
        """return the validated value or raise"""
        try:
            if len(value.keys()) != len(self.named_subtypes.keys()):
                raise ValueError('Illegal number of Arguments! Need %d arguments.', len(self.namd_subtypes.keys()))
            # validate elements and return as dict
            return dict((str(k), self.named_subtypes[k].validate(v))
                        for k,v in value.items())
        except Exception as exc:
            raise ValueError('Can not validate %s: %s', repr(value),str(exc))

    def export(self, value):
        """returns a python object fit for serialisation"""
        if len(value.keys()) != len(self.named_subtypes.keys()):
            raise ValueError('Illegal number of Arguments! Need %d arguments.', len(self.namd_subtypes.keys()))
        return dict((str(k),self.named_subtypes[k].export(v))
                    for k,v in value.items())





# XXX: derive from above classes automagically!
DATATYPES = dict(
    bool   = lambda : BoolType(),
    int    = lambda _min=None, _max=None: IntRange(_min, _max),
    double = lambda _min=None, _max=None: FloatRange(_min, _max),
    blob   = lambda _min=None, _max=None: BLOBType(_min, _max),
    string = lambda _min=None, _max=None: StringType(_min, _max),
    array  = lambda subtype, _min=None, _max=None: ArrayOf(get_datatype(subtype), _min, _max),
    tuple  = lambda subtypes: TupleOf(*map(get_datatype,subtypes)),
    enum   = lambda kwds: EnumType(**kwds),
    struct = lambda named_subtypes: StructOf(**dict((n,get_datatype(t)) for n,t in named_subtypes.items())),
)


# probably not needed...
def export_datatype(datatype):
    return datatype.as_json

# important for getting the right datatype from formerly jsonified descr.
def get_datatype(json):
    if not isinstance(json, list):
        raise ValueError('Argument must be a properly formatted list!')
    if len(json)<1:
        raise ValueError('can not validate %r', json)
    base = json[0]
    if base in DATATYPES:
        if base in ('enum', 'struct'):
            if len(json) > 1:
                args = json[1:]
            else:
                args = []
        else:
            args = json[1:]
        try:
            return DATATYPES[base](*args)
        except (TypeError, AttributeError) as exc:
            raise ValueError('Invalid datatype descriptor')
    raise ValueError('can not validate %r', json)
