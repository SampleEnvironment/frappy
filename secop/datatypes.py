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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""Define validated data types."""

# pylint: disable=abstract-method, too-many-lines


import sys
from base64 import b64decode, b64encode

from secop.errors import BadValueError, \
    ConfigError, ProgrammingError, ProtocolError
from secop.lib import clamp, generalConfig
from secop.lib.enum import Enum
from secop.parse import Parser
from secop.properties import HasProperties, Property

# *DEFAULT* limits for IntRange/ScaledIntegers transport serialisation
DEFAULT_MIN_INT = -16777216
DEFAULT_MAX_INT = 16777216
UNLIMITED = 1 << 64  # internal limit for integers, is probably high enough for any datatype size

Parser = Parser()


class DiscouragedConversion(BadValueError):
    """the discouraged conversion string - > float happened"""
    log_message = True


# base class for all DataTypes
class DataType(HasProperties):
    """base class for all data types"""
    IS_COMMAND = False
    unit = ''
    default = None

    def __call__(self, value):
        """check if given value (a python obj) is valid for this datatype

        returns the (possibly converted) value or raises an appropriate exception"""
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
        """format a value of this type into a str string

        This is intended for 'nice' formatting for humans and is NOT
        the opposite of :meth:`from_string`
        if unit is given, use it, else use the unit of the datatype (if any)"""
        raise NotImplementedError

    def set_properties(self, **kwds):
        """init datatype properties"""
        try:
            for k, v in kwds.items():
                self.setProperty(k, v)
            self.checkProperties()
        except Exception as e:
            raise ProgrammingError(str(e)) from None

    def get_info(self, **kwds):
        """prepare dict for export or repr

        get a dict with all items different from default
        plus mandatory keys from kwds"""
        result = self.exportProperties()
        result.update(kwds)
        return result

    def copy(self):
        """make a deep copy of the datatype"""

        # looks like the simplest way to make a deep copy
        return get_datatype(self.export_datatype())

    def compatible(self, other):
        """check other for compatibility

        raise an exception if <other> is not compatible, i.e. there
        exists a value which is valid for ourselfs, but not for <other>
        """
        raise NotImplementedError


class Stub(DataType):
    """incomplete datatype, to be replaced with a proper one later during module load

    this workaround because datatypes need properties with datatypes defined later
    """
    def __init__(self, datatype_name, *args):
        super().__init__()
        self.name = datatype_name
        self.args = args

    def __call__(self, value):
        """validate"""
        return value

    @classmethod
    def fix_datatypes(cls):
        """replace stubs with real datatypes

        for all DataType classes in this module
        to be called after all involved datatypes are defined
        """
        for dtcls in globals().values():
            if isinstance(dtcls, type) and issubclass(dtcls, DataType):
                for prop in dtcls.propertyDict.values():
                    stub = prop.datatype
                    if isinstance(stub, cls):
                        prop.datatype = globals()[stub.name](*stub.args)


# SECoP types:

class FloatRange(DataType):
    """(restricted) float type

    :param minval: (property **min**)
    :param maxval: (property **max**)
    :param kwds: any of the properties below
    """
    min = Property('low limit', Stub('FloatRange'), extname='min', default=-sys.float_info.max)
    max = Property('high limit', Stub('FloatRange'), extname='max', default=sys.float_info.max)
    unit = Property('physical unit', Stub('StringType'), extname='unit', default='')
    fmtstr = Property('format string', Stub('StringType'), extname='fmtstr', default='%g')
    absolute_resolution = Property('absolute resolution', Stub('FloatRange', 0),
                                   extname='absolute_resolution', default=0.0)
    relative_resolution = Property('relative resolution', Stub('FloatRange', 0),
                                   extname='relative_resolution', default=1.2e-7)

    def __init__(self, minval=None, maxval=None, **kwds):
        super().__init__()
        kwds['min'] = minval if minval is not None else -sys.float_info.max
        kwds['max'] = maxval if maxval is not None else sys.float_info.max
        self.set_properties(**kwds)

    def checkProperties(self):
        self.default = 0 if self.min <= 0 <= self.max else self.min
        super().checkProperties()
        if '%' not in self.fmtstr:
            raise ConfigError('Invalid fmtstr!')

    def export_datatype(self):
        return self.get_info(type='double')

    def __call__(self, value):
        try:
            value += 0.0  # do not accept strings here
        except Exception:
            try:
                value = float(value)
            except Exception:
                raise BadValueError('Can not convert %r to float' % value) from None
            if not generalConfig.lazy_number_validation:
                raise DiscouragedConversion('automatic string to float conversion no longer supported') from None

        # map +/-infty to +/-max possible number
        value = clamp(-sys.float_info.max, value, sys.float_info.max)

        # now check the limits
        prec = max(abs(value * self.relative_resolution), self.absolute_resolution)
        if self.min - prec <= value <= self.max + prec:
            return min(max(value, self.min), self.max)
        raise BadValueError('%.14g should be a float between %.14g and %.14g' %
                            (value, self.min, self.max))

    def __repr__(self):
        hints = self.get_info()
        if 'min' in hints:
            hints['minval'] = hints.pop('min')
        if 'max' in hints:
            hints['maxval'] = hints.pop('max')
        return 'FloatRange(%s)' % (', '.join('%s=%r' % (k, v) for k, v in hints.items()))

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
            return ' '.join([self.fmtstr % value, unit])
        return self.fmtstr % value

    def problematic_range(self, target_type):
        """check problematic range

        returns True when self.min or self.max is given, not 0 and equal to the same limit on target_type.
        """
        value_info = self.get_info()
        target_info = target_type.get_info()
        minval = value_info.get('min')  # None when -infinite
        maxval = value_info.get('max')  # None when +infinite
        return ((minval and minval == target_info.get('min')) or
                (maxval and maxval == target_info.get('max')))

    def compatible(self, other):
        if not isinstance(other, (FloatRange, ScaledInteger)):
            raise BadValueError('incompatible datatypes')
        # avoid infinity
        other(max(sys.float_info.min, self.min))
        other(min(sys.float_info.max, self.max))


class IntRange(DataType):
    """restricted int type

    :param minval: (property **min**)
    :param maxval: (property **max**)
    """
    min = Property('minimum value', Stub('IntRange', -UNLIMITED, UNLIMITED), extname='min', mandatory=True)
    max = Property('maximum value', Stub('IntRange', -UNLIMITED, UNLIMITED), extname='max', mandatory=True)
    # a unit on an int is now allowed in SECoP, but do we need them in Frappy?
    # unit = Property('physical unit', StringType(), extname='unit', default='')

    def __init__(self, minval=None, maxval=None):
        super().__init__()
        self.set_properties(min=DEFAULT_MIN_INT if minval is None else minval,
                            max=DEFAULT_MAX_INT if maxval is None else maxval)

    def checkProperties(self):
        self.default = 0 if self.min <= 0 <= self.max else self.min
        super().checkProperties()

    def export_datatype(self):
        return self.get_info(type='int')

    def __call__(self, value):
        try:
            fvalue = value + 0.0  # do not accept strings here
            value = int(value)
        except Exception:
            try:
                fvalue = float(value)
                value = int(value)
            except Exception:
                raise BadValueError('Can not convert %r to int' % value) from None
            if not generalConfig.lazy_number_validation:
                raise DiscouragedConversion('automatic string to float conversion no longer supported') from None
        if not self.min <= value <= self.max or round(fvalue) != fvalue:
            raise BadValueError('%r should be an int between %d and %d' %
                                (value, self.min, self.max))
        return value

    def __repr__(self):
        args = (self.min, self.max)
        if args[1] == DEFAULT_MAX_INT:
            args = args[:1]
            if args[0] == DEFAULT_MIN_INT:
                args = ()
        return 'IntRange%s' % repr(args)

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
        return '%d' % value

    def compatible(self, other):
        if isinstance(other, (IntRange, FloatRange, ScaledInteger)):
            other(self.min)
            other(self.max)
            return
        if isinstance(other, (EnumType, BoolType)):
            # the following loop will not cycle more than the number of Enum elements
            for i in range(self.min, self.max + 1):
                other(i)
        raise BadValueError('incompatible datatypes')


class ScaledInteger(DataType):
    """scaled integer (= fixed resolution float) type

    :param minval: (property **min**)
    :param maxval: (property **max**)
    :param kwds: any of the properties below

    note: limits are for the scaled float value
          the scale is only used for calculating to/from transport serialisation
    """
    scale = Property('scale factor', FloatRange(sys.float_info.min), extname='scale', mandatory=True)
    min = Property('low limit', FloatRange(), extname='min', mandatory=True)
    max = Property('high limit', FloatRange(), extname='max', mandatory=True)
    unit = Property('physical unit', Stub('StringType'), extname='unit', default='')
    fmtstr = Property('format string', Stub('StringType'), extname='fmtstr', default='%g')
    absolute_resolution = Property('absolute resolution', FloatRange(0),
                                   extname='absolute_resolution', default=0.0)
    relative_resolution = Property('relative resolution', FloatRange(0),
                                   extname='relative_resolution', default=1.2e-7)

    def __init__(self, scale, minval=None, maxval=None, absolute_resolution=None, **kwds):
        super().__init__()
        scale = float(scale)
        if absolute_resolution is None:
            absolute_resolution = scale
        self.set_properties(
            scale=scale,
            min=DEFAULT_MIN_INT * scale if minval is None else float(minval),
            max=DEFAULT_MAX_INT * scale if maxval is None else float(maxval),
            absolute_resolution=absolute_resolution,
            **kwds)

    def checkProperties(self):
        self.default = 0 if self.min <= 0 <= self.max else self.min
        super().checkProperties()

        # check values
        if '%' not in self.fmtstr:
            raise BadValueError('Invalid fmtstr!')
        # Remark: Datatype.copy() will round min, max to a multiple of self.scale
        # this should be o.k.

    def exportProperties(self):
        result = super().exportProperties()
        if self.absolute_resolution == 0:
            result['absolute_resolution'] = 0
        elif self.absolute_resolution == self.scale:
            result.pop('absolute_resolution', 0)
        return result

    def setProperty(self, key, value):
        if key == 'scale' and self.absolute_resolution == self.scale:
            super().setProperty('absolute_resolution', value)
        super().setProperty(key, value)

    def export_datatype(self):
        return self.get_info(type='scaled',
                             min=int((self.min + self.scale * 0.5) // self.scale),
                             max=int((self.max + self.scale * 0.5) // self.scale))

    def __call__(self, value):
        try:
            value += 0.0  # do not accept strings here
        except Exception:
            try:
                value = float(value)
            except Exception:
                raise BadValueError('Can not convert %r to float' % value) from None
            if not generalConfig.lazy_number_validation:
                raise DiscouragedConversion('automatic string to float conversion no longer supported') from None
        prec = max(self.scale, abs(value * self.relative_resolution),
                   self.absolute_resolution)
        if self.min - prec <= value <= self.max + prec:
            value = min(max(value, self.min), self.max)
        else:
            raise BadValueError('%g should be a float between %g and %g' %
                                (value, self.min, self.max))
        intval = int((value + self.scale * 0.5) // self.scale)
        value = float(intval * self.scale)
        return value  # return 'actual' value (which is more discrete than a float)

    def __repr__(self):
        hints = self.get_info(scale=float('%g' % self.scale),
                              min=int((self.min + self.scale * 0.5) // self.scale),
                              max=int((self.max + self.scale * 0.5) // self.scale))
        return 'ScaledInteger(%s)' % (', '.join('%s=%r' % kv for kv in hints.items()))

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
            return ' '.join([self.fmtstr % value, unit])
        return self.fmtstr % value

    def compatible(self, other):
        if not isinstance(other, (FloatRange, ScaledInteger)):
            raise BadValueError('incompatible datatypes')
        other(self.min)
        other(self.max)


class EnumType(DataType):
    """enumeration

    :param enum_or_name: the name of the Enum or an Enum to inherit from
    :param members: members dict or None when using kwds only
    :param kwds: (additional) members
    """
    def __init__(self, enum_or_name='', *, members=None, **kwds):
        super().__init__()
        if members is not None:
            kwds.update(members)
        if isinstance(enum_or_name, str):
            self._enum = Enum(enum_or_name, kwds)  # allow 'self' as name
        else:
            self._enum = Enum(enum_or_name, **kwds)
        self.default = self._enum[self._enum.members[0]]

    def copy(self):
        # as the name is not exported, we have to implement copy ourselfs
        return EnumType(self._enum)

    def export_datatype(self):
        return {'type': 'enum', 'members': dict((m.name, m.value) for m in self._enum.members)}

    def __repr__(self):
        return "EnumType(%r, %s)" % (self._enum.name,
                                     ', '.join('%s=%d' % (m.name, m.value) for m in self._enum.members))

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
        except (KeyError, TypeError):  # TypeError will be raised when value is not hashable
            raise BadValueError('%r is not a member of enum %r' % (value, self._enum)) from None

    def from_string(self, text):
        return self(text)

    def format_value(self, value, unit=None):
        return '%s<%s>' % (self._enum[value].name, self._enum[value].value)

    def set_name(self, name):
        self._enum.name = name

    def compatible(self, other):
        for m in self._enum.members:
            other(m)


class BLOBType(DataType):
    """binary large object

    internally treated as bytes
    """

    minbytes = Property('minimum number of bytes', IntRange(0), extname='minbytes',
                        default=0)
    maxbytes = Property('maximum number of bytes', IntRange(0), extname='maxbytes',
                        mandatory=True)

    def __init__(self, minbytes=0, maxbytes=None):
        super().__init__()
        # if only one argument is given, use exactly that many bytes
        # if nothing is given, default to 255
        if maxbytes is None:
            maxbytes = minbytes or 255
        self.set_properties(minbytes=minbytes, maxbytes=maxbytes)

    def checkProperties(self):
        self.default = b'\0' * self.minbytes
        super().checkProperties()

    def export_datatype(self):
        return self.get_info(type='blob')

    def __repr__(self):
        return 'BLOBType(%d, %d)' % (self.minbytes, self.maxbytes)

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        if not isinstance(value, bytes):
            raise BadValueError('%s has the wrong type!' % repr(value))
        size = len(value)
        if size < self.minbytes:
            raise BadValueError(
                '%r must be at least %d bytes long!' % (value, self.minbytes))
        if size > self.maxbytes:
            raise BadValueError(
                '%r must be at most %d bytes long!' % (value, self.maxbytes))
        return value

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return b64encode(value).decode('ascii')

    def import_value(self, value):
        """returns a python object from serialisation"""
        return b64decode(value)

    def from_string(self, text):
        value = text
        # XXX: what should we do here?
        return self(value)

    def format_value(self, value, unit=None):
        return repr(value)

    def compatible(self, other):
        try:
            if self.minbytes < other.minbytes or self.maxbytes > other.maxbytes:
                raise BadValueError('incompatible datatypes')
        except AttributeError:
            raise BadValueError('incompatible datatypes') from None


class StringType(DataType):
    """string

    for parameters see properties below
    """
    minchars = Property('minimum number of character points', IntRange(0, UNLIMITED),
                        extname='minchars', default=0)
    maxchars = Property('maximum number of character points', IntRange(0, UNLIMITED),
                        extname='maxchars', default=UNLIMITED)
    isUTF8 = Property('flag telling whether encoding is UTF-8 instead of ASCII',
                      Stub('BoolType'), extname='isUTF8', default=False)

    def __init__(self, minchars=0, maxchars=None, **kwds):
        super().__init__()
        if maxchars is None:
            maxchars = minchars or UNLIMITED
        self.set_properties(minchars=minchars, maxchars=maxchars, **kwds)

    def checkProperties(self):
        self.default = ' ' * self.minchars
        super().checkProperties()

    def export_datatype(self):
        return self.get_info(type='string')

    def __repr__(self):
        return 'StringType(%s)' % (', '.join('%s=%r' % kv for kv in self.get_info().items()))

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        if not isinstance(value, str):
            raise BadValueError('%s has the wrong type!' % repr(value))
        if not self.isUTF8:
            try:
                value.encode('ascii')
            except UnicodeEncodeError:
                raise BadValueError('%r contains non-ascii character!' % value) from None
        size = len(value)
        if size < self.minchars:
            raise BadValueError(
                '%r must be at least %d bytes long!' % (value, self.minchars))
        if size > self.maxchars:
            raise BadValueError(
                '%r must be at most %d bytes long!' % (value, self.maxchars))
        if '\0' in value:
            raise BadValueError(
                'Strings are not allowed to embed a \\0! Use a Blob instead!')
        return value

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return '%s' % value

    def import_value(self, value):
        """returns a python object from serialisation"""
        return str(value)

    def from_string(self, text):
        value = str(text)
        return self(value)

    def format_value(self, value, unit=None):
        return repr(value)

    def compatible(self, other):
        try:
            if self.minchars < other.minchars or self.maxchars > other.maxchars or \
                    self.isUTF8 > other.isUTF8:
                raise BadValueError('incompatible datatypes')
        except AttributeError:
            raise BadValueError('incompatible datatypes') from None


# TextType is a special StringType intended for longer texts (i.e. embedding \n),
# whereas StringType is supposed to not contain '\n'
# unfortunately, SECoP makes no distinction here....
# note: content is supposed to follow the format of a git commit message,
# i.e. a line of text, 2 '\n' + a longer explanation
class TextType(StringType):
    def __init__(self, maxchars=None):
        if maxchars is None:
            maxchars = UNLIMITED
        super().__init__(0, maxchars)

    def __repr__(self):
        if self.maxchars == UNLIMITED:
            return 'TextType()'
        return 'TextType(%d)' % self.maxchars

    def copy(self):
        # DataType.copy will not work, because it is exported as 'string'
        return TextType(self.maxchars)


class BoolType(DataType):
    """boolean"""
    default = False

    def export_datatype(self):
        return {'type': 'bool'}

    def __repr__(self):
        return 'BoolType()'

    def __call__(self, value):
        """return the validated (internal) value or raise"""
        if value in [0, '0', 'False', 'false', 'no', 'off', False]:
            return False
        if value in [1, '1', 'True', 'true', 'yes', 'on', True]:
            return True
        raise BadValueError('%r is not a boolean value!' % value)

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return self(value)

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self(value)

    def from_string(self, text):
        value = text
        return self(value)

    def format_value(self, value, unit=None):
        return repr(bool(value))

    def compatible(self, other):
        other(False)
        other(True)


Stub.fix_datatypes()

#
# nested types
#


class ArrayOf(DataType):
    """data structure with fields of homogeneous type

    :param members: the datatype of the elements
    """
    minlen = Property('minimum number of elements', IntRange(0), extname='minlen',
                      default=0)
    maxlen = Property('maximum number of elements', IntRange(0), extname='maxlen',
                      mandatory=True)

    def __init__(self, members, minlen=0, maxlen=None):
        super().__init__()
        if not isinstance(members, DataType):
            raise BadValueError(
                'ArrayOf only works with a DataType as first argument!')
        # one argument -> exactly that size
        # argument default to 100
        if maxlen is None:
            maxlen = minlen or 100
        self.members = members
        self.set_properties(minlen=minlen, maxlen=maxlen)

    def copy(self):
        """DataType.copy does not work when members are enums"""
        return ArrayOf(self.members.copy(), self.minlen, self.maxlen)

    def checkProperties(self):
        self.default = [self.members.default] * self.minlen
        super().checkProperties()

    def getProperties(self):
        """get also properties of members"""
        res = {}
        res.update(super().getProperties())
        res.update(self.members.getProperties())
        return res

    def setProperty(self, key, value):
        """set also properties of members"""
        if key in self.propertyDict:
            super().setProperty(key, value)
        else:
            self.members.setProperty(key, value)

    def export_datatype(self):
        return dict(type='array', minlen=self.minlen, maxlen=self.maxlen,
                    members=self.members.export_datatype())

    def __repr__(self):
        return 'ArrayOf(%s, %s, %s)' % (
            repr(self.members), self.minlen, self.maxlen)

    def __call__(self, value):
        """validate an external representation to an internal one"""
        if isinstance(value, (tuple, list)):
            # check number of elements
            if self.minlen is not None and len(value) < self.minlen:
                raise BadValueError(
                    'Array too small, needs at least %d elements!' %
                    self.minlen)
            if self.maxlen is not None and len(value) > self.maxlen:
                raise BadValueError(
                    'Array too big, holds at most %d elements!' % self.minlen)
            # apply subtype valiation to all elements and return as list
            return tuple(self.members(elem) for elem in value)
        raise BadValueError(
            'Can not convert %s to ArrayOf DataType!' % repr(value))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return [self.members.export_value(elem) for elem in value]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return tuple(self.members.import_value(elem) for elem in value)

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError('trailing garbage: %r' % rem)
        return self(value)

    def format_value(self, value, unit=None):
        if unit is None:
            unit = self.unit or self.members.unit
        res = '[%s]' % (', '.join([self.members.format_value(elem, '') for elem in value]))
        if unit:
            return ' '.join([res, unit])
        return res

    def compatible(self, other):
        try:
            if self.minlen < other.minlen or self.maxlen > other.maxlen:
                raise BadValueError('incompatible datatypes')
            self.members.compatible(other.members)
        except AttributeError:
            raise BadValueError('incompatible datatypes') from None


class TupleOf(DataType):
    """data structure with fields of inhomogeneous type

    types are given as positional arguments
    """
    def __init__(self, *members):
        super().__init__()
        if not members:
            raise BadValueError('Empty tuples are not allowed!')
        for subtype in members:
            if not isinstance(subtype, DataType):
                raise BadValueError(
                    'TupleOf only works with DataType objs as arguments!')
        self.members = members
        self.default = tuple(el.default for el in members)

    def copy(self):
        """DataType.copy does not work when members contain enums"""
        return TupleOf(*(m.copy() for m in self.members))

    def export_datatype(self):
        return dict(type='tuple', members=[subtype.export_datatype() for subtype in self.members])

    def __repr__(self):
        return 'TupleOf(%s)' % ', '.join([repr(st) for st in self.members])

    def __call__(self, value):
        """return the validated value or raise"""
        # keep the ordering!
        try:
            if len(value) != len(self.members):
                raise BadValueError(
                    'Illegal number of Arguments! Need %d arguments.' % len(self.members))
            # validate elements and return as list
            return tuple(sub(elem)
                         for sub, elem in zip(self.members, value))
        except Exception as exc:
            raise BadValueError('Can not validate:', str(exc)) from None

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return [sub.export_value(elem) for sub, elem in zip(self.members, value)]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return tuple(sub.import_value(elem) for sub, elem in zip(self.members, value))

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError('trailing garbage: %r' % rem)
        return self(value)

    def format_value(self, value, unit=None):
        return '(%s)' % (', '.join([sub.format_value(elem)
                                   for sub, elem in zip(self.members, value)]))

    def compatible(self, other):
        if not isinstance(other, TupleOf):
            raise BadValueError('incompatible datatypes')
        if len(self.members) != len(other.members):
            raise BadValueError('incompatible datatypes')
        for a, b in zip(self.members, other.members):
            a.compatible(b)


class ImmutableDict(dict):
    def _no(self, *args, **kwds):
        raise TypeError('a struct can not be modified, please overwrite instead')
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _no


class StructOf(DataType):
    """data structure with named fields

    :param optional: a list of optional members
    :param members: names as keys and types as values for all members
    """
    # Remark: assignment of parameters containing partial structs in their datatype
    # are (and can) not be handled here! This has to be done manually in the write method
    def __init__(self, optional=None, **members):
        super().__init__()
        self.members = members
        if not members:
            raise BadValueError('Empty structs are not allowed!')
        self.optional = list(optional or [])
        for name, subtype in list(members.items()):
            if not isinstance(subtype, DataType):
                raise ProgrammingError(
                    'StructOf only works with named DataType objs as keyworded arguments!')
        for name in self.optional:
            if name not in members:
                raise ProgrammingError(
                    'Only members of StructOf may be declared as optional!')
        self.default = dict((k, el.default) for k, el in members.items())

    def copy(self):
        """DataType.copy does not work when members contain enums"""
        return StructOf(self.optional, **{k: v.copy() for k, v in self.members.items()})

    def export_datatype(self):
        res = dict(type='struct', members=dict((n, s.export_datatype())
                                               for n, s in list(self.members.items())))
        if self.optional:
            res['optional'] = self.optional
        return res

    def __repr__(self):
        opt = ', optional=%r' % self.optional if self.optional else ''
        return 'StructOf(%s%s)' % (', '.join(
            ['%s=%s' % (n, repr(st)) for n, st in list(self.members.items())]), opt)

    def __call__(self, value):
        """return the validated value or raise"""
        try:
            missing = set(self.members) - set(value) - set(self.optional)
            if missing:
                raise BadValueError('missing values for keys %r' % list(missing))
            # validate elements and return as dict
            return ImmutableDict((str(k), self.members[k](v))
                                 for k, v in list(value.items()))
        except Exception as exc:
            raise BadValueError('Can not validate %s: %s' % (repr(value), str(exc))) from None

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        self(value)  # check validity
        return dict((str(k), self.members[k].export_value(v))
                    for k, v in list(value.items()))

    def import_value(self, value):
        """returns a python object from serialisation"""
        return self({str(k): self.members[k].import_value(v) for k, v in value.items()})

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError('trailing garbage: %r' % rem)
        return self(dict(value))

    def format_value(self, value, unit=None):
        return '{%s}' % (', '.join(['%s=%s' % (k, self.members[k].format_value(v)) for k, v in sorted(value.items())]))

    def compatible(self, other):
        try:
            mandatory = set(other.members) - set(other.optional)
            for k, m in self.members.items():
                m.compatible(other.members[k])
                mandatory.discard(k)
            if mandatory:
                raise BadValueError('incompatible datatypes')
        except (AttributeError, TypeError, KeyError):
            raise BadValueError('incompatible datatypes') from None


class CommandType(DataType):
    """command

    a pseudo datatype for commands with arguments and return values
    """
    IS_COMMAND = True

    def __init__(self, argument=None, result=None):
        super().__init__()
        if argument is not None:
            if not isinstance(argument, DataType):
                raise BadValueError('CommandType: Argument type must be a DataType!')
        if result is not None:
            if not isinstance(result, DataType):
                raise BadValueError('CommandType: Result type must be a DataType!')
        self.argument = argument
        self.result = result

    def export_datatype(self):
        a, r = self.argument, self.result
        props = {'type': 'command'}
        if a is not None:
            props['argument'] = a.export_datatype()
        if r is not None:
            props['result'] = r.export_datatype()
        return props

    def __repr__(self):
        if self.result is None:
            return 'CommandType(%s)' % (repr(self.argument) if self.argument else '')
        return 'CommandType(%s, %s)' % (repr(self.argument), repr(self.result))

    def __call__(self, value):
        """return the validated argument value or raise"""
        return self.argument(value)

    def export_value(self, value):
        raise ProgrammingError('values of type command can not be transported!')

    def import_value(self, value):
        raise ProgrammingError('values of type command can not be transported!')

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError('trailing garbage: %r' % rem)
        return self(value)

    def format_value(self, value, unit=None):
        # actually I have no idea what to do here!
        raise NotImplementedError

    def compatible(self, other):
        try:
            if self.argument != other.argument:  # not both are None
                self.argument.compatible(other.argument)
            if self.result != other.result:  # not both are None
                other.result.compatible(self.result)
        except AttributeError:
            raise BadValueError('incompatible datatypes') from None


# internally used datatypes (i.e. only for programming the SEC-node)

class DataTypeType(DataType):
    def __call__(self, value):
        """check if given value (a python obj) is a valid datatype

        returns the value or raises an appropriate exception"""
        if isinstance(value, DataType):
            return value
        try:
            return get_datatype(value)
        except Exception as e:
            raise ProgrammingError(e) from None

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

    def setProperty(self, key, value):
        """silently ignored

        as ValueType is used for the datatype default, this makes code
        shorter for cases, where the datatype may not yet be defined
        """


class NoneOr(DataType):
    """validates a None or smth. else"""
    default = None

    def __init__(self, other):
        super().__init__()
        self.other = other

    def __call__(self, value):
        return None if value is None else self.other(value)

    def export_value(self, value):
        if value is None:
            return None
        return self.other.export_value(value)


class OrType(DataType):
    def __init__(self, *types):
        super().__init__()
        self.types = types
        self.default = self.types[0].default

    def __call__(self, value):
        for t in self.types:
            try:
                return t(value)
            except Exception:
                pass
        raise BadValueError("Invalid Value, must conform to one of %s" % (', '.join((str(t) for t in self.types))))


Int8   = IntRange(-(1 << 7),  (1 << 7) - 1)
Int16  = IntRange(-(1 << 15), (1 << 15) - 1)
Int32  = IntRange(-(1 << 31), (1 << 31) - 1)
Int64  = IntRange(-(1 << 63), (1 << 63) - 1)
UInt8  = IntRange(0, (1 << 8) - 1)
UInt16 = IntRange(0, (1 << 16) - 1)
UInt32 = IntRange(0, (1 << 32) - 1)
UInt64 = IntRange(0, (1 << 64) - 1)


# Goodie: Convenience Datatypes for Programming
class LimitsType(TupleOf):
    def __init__(self, members):
        super().__init__(members, members)

    def __call__(self, value):
        limits = TupleOf.__call__(self, value)
        if limits[1] < limits[0]:
            raise BadValueError('Maximum Value %s must be greater than minimum value %s!' % (limits[1], limits[0]))
        return limits


class StatusType(TupleOf):
    # shorten initialisation and allow access to status enumMembers from status values
    def __init__(self, enum):
        super().__init__(EnumType(enum), StringType())
        self._enum = enum

    def __getattr__(self, key):
        return getattr(self._enum, key)


def floatargs(kwds):
    return {k: v for k, v in kwds.items() if k in
            {'unit', 'fmtstr', 'absolute_resolution', 'relative_resolution'}}


# argumentnames to lambda from spec!
# **kwds at the end are for must-ignore policy
DATATYPES = dict(
    bool    = lambda **kwds:
        BoolType(),
    int     = lambda min, max, **kwds:
        IntRange(minval=min, maxval=max),
    scaled  = lambda scale, min, max, **kwds:
        ScaledInteger(scale=scale, minval=min*scale, maxval=max*scale, **floatargs(kwds)),
    double  = lambda min=None, max=None, **kwds:
        FloatRange(minval=min, maxval=max, **floatargs(kwds)),
    blob    = lambda maxbytes, minbytes=0, **kwds:
        BLOBType(minbytes=minbytes, maxbytes=maxbytes),
    string  = lambda minchars=0, maxchars=None, isUTF8=False, **kwds:
        StringType(minchars=minchars, maxchars=maxchars, isUTF8=isUTF8),
    array   = lambda maxlen, members, minlen=0, pname='', **kwds:
        ArrayOf(get_datatype(members, pname), minlen=minlen, maxlen=maxlen),
    tuple   = lambda members, pname='', **kwds:
        TupleOf(*tuple((get_datatype(t, pname) for t in members))),
    enum    = lambda members, pname='', **kwds:
        EnumType(pname, members=members),
    struct  = lambda members, optional=None, pname='', **kwds:
        StructOf(optional, **dict((n, get_datatype(t, pname)) for n, t in list(members.items()))),
    command = lambda argument=None, result=None, pname='', **kwds:
        CommandType(get_datatype(argument, pname), get_datatype(result)),
    limit   = lambda members, pname='', **kwds:
        LimitsType(get_datatype(members, pname)),
)


# important for getting the right datatype from formerly jsonified descr.
def get_datatype(json, pname=''):
    """returns a DataType object from description

    inverse of <DataType>.export_datatype()

    :param json: the datainfo object as returned from json.loads
    :param pname: if given, used to name EnumTypes from the parameter name
    :return: the datatype (instance of DataType)
    """
    if json is None:
        return json
    if isinstance(json, list) and len(json) == 2:
        base, kwargs = json  # still allow old syntax
    else:
        try:
            kwargs = json.copy()
            base = kwargs.pop('type')
        except (TypeError, KeyError, AttributeError):
            raise BadValueError('a data descriptor must be a dict containing a "type" key, not %r' % json) from None

    try:
        return DATATYPES[base](pname=pname, **kwargs)
    except Exception as e:
        raise BadValueError('invalid data descriptor: %r (%s)' % (json, str(e))) from None
