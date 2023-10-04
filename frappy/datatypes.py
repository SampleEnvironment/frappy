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

from frappy.errors import ConfigError, ProgrammingError, \
    ProtocolError, RangeError, WrongTypeError
from frappy.lib import clamp, generalConfig
from frappy.lib.enum import Enum
from frappy.parse import Parser
from frappy.properties import HasProperties, Property

generalConfig.set_default('lazy_number_validation', False)

# *DEFAULT* limits for IntRange/ScaledIntegers transport serialisation
DEFAULT_MIN_INT = -16777216
DEFAULT_MAX_INT = 16777216
UNLIMITED = 1 << 64  # internal limit for integers, is probably high enough for any datatype size

Parser = Parser()


def shortrepr(value):
    """shortened repr for error messages

    avoid lengthy error message in case a value is too complex
    """
    r = repr(value)
    if len(r) > 40:
        return r[:40] + '...'
    return r


# base class for all DataTypes
class DataType(HasProperties):
    """base class for all data types"""
    IS_COMMAND = False
    unit = ''
    default = None
    client = False  # used on the client side

    def __call__(self, value):
        """convert given value to our datatype and validate

        :param value: the value to be converted
        :return: the converted type

        check if given value (a python obj) is valid for this datatype,
        """
        raise NotImplementedError

    def validate(self, value, previous=None):
        """convert value to datatype and check for limits

        :param value: the value to be converted
        :param previous: previous value (used for optional struct members)
        """
        # default: no limits to check
        return self(value)

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

    def set_main_unit(self, unit):
        """replace $ in unit by argument"""


class Stub(DataType):
    """incomplete datatype, to be replaced with a proper one later during module load

    this workaround because datatypes need properties with datatypes defined later
    """
    def __init__(self, datatype_name, *args, **kwds):
        super().__init__()
        self.name = datatype_name
        self.args = args
        self.kwds = kwds

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
                        prop.datatype = globals()[stub.name](*stub.args, **stub.kwds)


class HasUnit:
    unit = Property('physical unit', Stub('StringType', isUTF8=True), extname='unit', default='')

    def set_main_unit(self, unit):
        if '$' in self.unit:
            self.setProperty('unit', self.unit.replace('$', unit))


# SECoP types:

class FloatRange(HasUnit, DataType):
    """(restricted) float type

    :param min: (property **min**)
    :param max: (property **max**)
    :param kwds: any of the properties below
    """
    min = Property('low limit', Stub('FloatRange'), extname='min', default=-sys.float_info.max)
    max = Property('high limit', Stub('FloatRange'), extname='max', default=sys.float_info.max)
    fmtstr = Property('format string', Stub('StringType'), extname='fmtstr', default='%g')
    absolute_resolution = Property('absolute resolution', Stub('FloatRange', 0),
                                   extname='absolute_resolution', default=0.0)
    relative_resolution = Property('relative resolution', Stub('FloatRange', 0),
                                   extname='relative_resolution', default=1.2e-7)

    def __init__(self, min=None, max=None, **kwds):  # pylint: disable=redefined-builtin
        super().__init__()
        self.set_properties(min=min if min is not None else -sys.float_info.max,
                            max=max if max is not None else sys.float_info.max,
                            **kwds)

    def checkProperties(self):
        self.default = 0 if self.min <= 0 <= self.max else self.min
        super().checkProperties()
        if '%' not in self.fmtstr:
            raise ConfigError('Invalid fmtstr!')

    def export_datatype(self):
        return self.get_info(type='double')

    def __call__(self, value):
        """accepts floats, integers and booleans, but not strings"""
        try:
            value += 0.0  # do not accept strings here
        except Exception:
            try:
                if not generalConfig.lazy_number_validation:
                    raise
                value = float(value)
            except Exception:
                raise WrongTypeError(f'can not convert {shortrepr(value)} to a float') from None

        # map +/-infty to +/-max possible number
        return clamp(-sys.float_info.max, value, sys.float_info.max)

    def validate(self, value, previous=None):
        # convert
        value = self(value)
        # check the limits
        prec = max(abs(value * self.relative_resolution), self.absolute_resolution)
        if self.min - prec <= value <= self.max + prec:
            # silently clamp when outside by not more than prec
            return clamp(self.min, value, self.max)
        info = self.exportProperties()
        raise RangeError(f"{value:.14g} must be between {info.get('min', float('-inf')):g} and {info.get('max', float('inf')):g}")

    def __repr__(self):
        hints = self.get_info()
        if 'min' in hints:
            hints['min'] = hints.pop('min')
        if 'max' in hints:
            hints['max'] = hints.pop('max')
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

    def compatible(self, other):
        if not isinstance(other, (FloatRange, ScaledInteger)):
            raise WrongTypeError('incompatible datatypes')
        other.validate(self.min)
        other.validate(self.max)


class IntRange(DataType):
    """restricted int type

    :param min: (property **min**)
    :param max: (property **max**)
    """
    min = Property('minimum value', Stub('IntRange', -UNLIMITED, UNLIMITED), extname='min', mandatory=True)
    max = Property('maximum value', Stub('IntRange', -UNLIMITED, UNLIMITED), extname='max', mandatory=True)
    # a unit on an int is now allowed in SECoP, but do we need them in Frappy?
    # unit = Property('physical unit', StringType(), extname='unit', default='')

    def __init__(self, min=None, max=None):  # pylint: disable=redefined-builtin
        super().__init__()
        self.set_properties(min=DEFAULT_MIN_INT if min is None else min,
                            max=DEFAULT_MAX_INT if max is None else max)

    def checkProperties(self):
        self.default = 0 if self.min <= 0 <= self.max else self.min
        super().checkProperties()

    def export_datatype(self):
        return self.get_info(type='int')

    def __call__(self, value):
        """accepts integers, booleans and whole-number floats, but not strings"""
        try:
            fvalue = value + 0.0  # do not accept strings here
            value = int(value)
        except Exception:
            try:
                if not generalConfig.lazy_number_validation:
                    raise
                fvalue = float(value)
                value = int(value)
            except Exception:
                raise WrongTypeError(f'can not convert {shortrepr(value)} to an int') from None
        if round(fvalue) != fvalue:
            raise WrongTypeError(f'{value} should be an int')
        return value

    def validate(self, value, previous=None):
        # convert
        value = self(value)
        # check the limits
        if self.min <= value <= self.max:
            return value
        raise RangeError(f'{value!r} must be between {self.min} and {self.max}')

    def __repr__(self):
        args = (self.min, self.max)
        if args[1] == DEFAULT_MAX_INT:
            args = args[:1]
            if args[0] == DEFAULT_MIN_INT:
                args = ()
        return f'IntRange{repr(args)}'

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
        return f'{value}'

    def compatible(self, other):
        if isinstance(other, (IntRange, FloatRange, ScaledInteger)):
            other.validate(self.min)
            other.validate(self.max)
            return
        if isinstance(other, (EnumType, BoolType)):
            # the following loop will not cycle more than the number of Enum elements
            for i in range(self.min, self.max + 1):
                other(i)
        raise WrongTypeError('incompatible datatypes')


class ScaledInteger(HasUnit, DataType):
    """scaled integer (= fixed resolution float) type

    :param min: (property **min**)
    :param max: (property **max**)
    :param kwds: any of the properties below

    note: limits are for the scaled float value
          the scale is only used for calculating to/from transport serialisation
    """
    scale = Property('scale factor', FloatRange(sys.float_info.min), extname='scale', mandatory=True)
    min = Property('low limit', FloatRange(), extname='min', mandatory=True)
    max = Property('high limit', FloatRange(), extname='max', mandatory=True)
    fmtstr = Property('format string', Stub('StringType'), extname='fmtstr', default='%g')
    absolute_resolution = Property('absolute resolution', FloatRange(0),
                                   extname='absolute_resolution', default=0.0)
    relative_resolution = Property('relative resolution', FloatRange(0),
                                   extname='relative_resolution', default=1.2e-7)

    # pylint: disable=redefined-builtin
    def __init__(self, scale, min=None, max=None, absolute_resolution=None, **kwds):
        super().__init__()
        try:
            scale = float(scale)
        except (ValueError, TypeError) as e:
            raise ProgrammingError(e) from None
        if absolute_resolution is None:
            absolute_resolution = scale
        self.set_properties(
            scale=scale,
            min=DEFAULT_MIN_INT * scale if min is None else float(min),
            max=DEFAULT_MAX_INT * scale if max is None else float(max),
            absolute_resolution=absolute_resolution,
            **kwds)

    def checkProperties(self):
        self.default = 0 if self.min <= 0 <= self.max else self.min
        super().checkProperties()

        # check values
        if '%' not in self.fmtstr:
            raise ConfigError('Invalid fmtstr!')
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
                             min=int(round(self.min / self.scale)),
                             max=int(round(self.max / self.scale)))

    def __call__(self, value):
        """accepts floats, integers and booleans, but not strings"""
        try:
            value += 0.0  # do not accept strings here
        except Exception:
            try:
                if not generalConfig.lazy_number_validation:
                    raise
                value = float(value)
            except Exception:
                raise WrongTypeError(f'can not convert {shortrepr(value)} to float') from None
        intval = int(round(value / self.scale))
        return float(intval * self.scale)   # return 'actual' value (which is more discrete than a float)

    def validate(self, value, previous=None):
        # convert
        result = self(value)
        if self.min - self.scale < value < self.max + self.scale:
            # silently clamp when outside by not more than self.scale
            return clamp(self(self.min), result, self(self.max))
        raise RangeError(f'{value:.14g} must be between between {self.min:g} and {self.max:g}')

    def __repr__(self):
        hints = self.get_info(scale=float(f'{self.scale:g}'),
                              min=int(round(self.min / self.scale)),
                              max=int(round(self.max / self.scale)))
        return 'ScaledInteger(%s)' % (', '.join('%s=%r' % kv for kv in hints.items()))

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return int(round(value / self.scale))

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
            raise WrongTypeError('incompatible datatypes')
        other.validate(self.min)
        other.validate(self.max)


class EnumType(DataType):
    """enumeration

    :param enum_or_name: the name of the Enum or an Enum to inherit from
    :param members: members dict or None when using kwds only
    :param kwds: (additional) members
    """
    def __init__(self, enum_or_name='', members=None, **kwds):
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
        """accepts integers and strings, converts to EnumMember (may be used like an int)"""
        try:
            return self._enum[value]
        except (KeyError, TypeError):  # TypeError will be raised when value is not hashable
            if isinstance(value, (int, str)):
                raise RangeError(f'{shortrepr(value)} is not a member of enum {self._enum!r}') from None
            raise WrongTypeError(f'{shortrepr(value)} must be either int or str for an enum value') from None

    def from_string(self, text):
        return self(text)

    def format_value(self, value, unit=None):
        return f'{self._enum[value].name}<{self._enum[value].value}>'

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
        return f'BLOBType({self.minbytes}, {self.maxbytes})'

    def __call__(self, value):
        """accepts bytes only"""
        if not isinstance(value, bytes):
            raise WrongTypeError(f'{shortrepr(value)} must be of type bytes')
        size = len(value)
        if size < self.minbytes:
            raise RangeError(
                f'{value!r} must be at least {self.minbytes} bytes long!')
        if size > self.maxbytes:
            raise RangeError(
                f'{value!r} must be at most {self.maxbytes} bytes long!')
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
                raise RangeError('incompatible datatypes')
        except AttributeError:
            raise WrongTypeError('incompatible datatypes') from None


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
        """accepts strings only"""
        if not isinstance(value, str):
            raise WrongTypeError(f'{shortrepr(value)} has the wrong type!')
        if not self.isUTF8:
            try:
                value.encode('ascii')
            except UnicodeEncodeError:
                raise RangeError(f'{shortrepr(value)} contains non-ascii character!') from None
        size = len(value)
        if size < self.minchars:
            raise RangeError(
                f'{shortrepr(value)} must be at least {self.minchars} chars long!')
        if size > self.maxchars:
            raise RangeError(
                f'{shortrepr(value)} must be at most {self.maxchars} chars long!')
        if '\0' in value:
            raise RangeError(
                'Strings are not allowed to embed a \\0! Use a Blob instead!')
        return value

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        return f'{value}'

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
                raise RangeError('incompatible datatypes')
        except AttributeError:
            raise WrongTypeError('incompatible datatypes') from None


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
        return f'TextType({self.maxchars})'

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
        """accepts 0, False, 1, True"""
        # TODO: probably remove conversion from string (not needed anymore with python cfg)
        if value in [0, '0', 'False', 'false', 'no', 'off', False]:
            return False
        if value in [1, '1', 'True', 'true', 'yes', 'on', True]:
            return True
        raise WrongTypeError(f'{shortrepr(value)} is not a boolean value!')

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
            raise ProgrammingError(
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
        return {'type': 'array', 'minlen': self.minlen, 'maxlen': self.maxlen,
                'members': self.members.export_datatype()}

    def __repr__(self):
        return f'ArrayOf({repr(self.members)}, {self.minlen}, {self.maxlen})'

    def check_type(self, value):
        try:
            # check number of elements
            if self.minlen is not None and len(value) < self.minlen:
                raise RangeError(
                    f'array too small, needs at least {self.minlen} elements!')
            if self.maxlen is not None and len(value) > self.maxlen:
                raise RangeError(
                    f'array too big, holds at most {self.maxlen} elements!')
        except TypeError:
            raise WrongTypeError(f'{type(value).__name__} can not be converted to ArrayOf DataType!') from None

    def __call__(self, value):
        """accepts any sequence, converts to tuple (immutable!)"""
        self.check_type(value)
        try:
            return tuple(self.members(v) for v in value)
        except Exception as e:
            errcls = RangeError if isinstance(e, RangeError) else WrongTypeError
            raise errcls('can not convert some array elements') from e

    def validate(self, value, previous=None):
        self.check_type(value)
        try:
            if previous:
                return tuple(self.members.validate(v, p) for v, p in zip(value, previous))
            return tuple(self.members.validate(v) for v in value)
        except Exception as e:
            errcls = RangeError if isinstance(e, RangeError) else WrongTypeError
            raise errcls('some array elements are invalid') from e

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        self.check_type(value)
        return [self.members.export_value(elem) for elem in value]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return tuple(self.members.import_value(elem) for elem in value)

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(f'trailing garbage: {rem!r}')
        return self(value)

    def format_value(self, value, unit=None):
        innerunit = ''
        if unit is None:
            members = self.members
            while isinstance(members, ArrayOf):
                members = members.members
            if members.unit:
                unit = members.unit
            else:
                innerunit = None
        res = f"[{', '.join([self.members.format_value(elem, innerunit) for elem in value])}]"
        if unit:
            return ' '.join([res, unit])
        return res

    def compatible(self, other):
        try:
            if self.minlen < other.minlen or self.maxlen > other.maxlen:
                raise RangeError('incompatible datatypes')
            self.members.compatible(other.members)
        except AttributeError:
            raise WrongTypeError('incompatible datatypes') from None

    def set_main_unit(self, unit):
        self.members.set_main_unit(unit)


class TupleOf(DataType):
    """data structure with fields of inhomogeneous type

    types are given as positional arguments
    """
    def __init__(self, *members):
        super().__init__()
        if not members:
            raise ProgrammingError('Empty tuples are not allowed!')
        for subtype in members:
            if not isinstance(subtype, DataType):
                raise ProgrammingError(
                    'TupleOf only works with DataType objs as arguments!')
        self.members = members
        self.default = tuple(el.default for el in members)

    def copy(self):
        """DataType.copy does not work when members contain enums"""
        return TupleOf(*(m.copy() for m in self.members))

    def export_datatype(self):
        return {'type': 'tuple', 'members': [subtype.export_datatype() for subtype in self.members]}

    def __repr__(self):
        return f"TupleOf({', '.join([repr(st) for st in self.members])})"

    def check_type(self, value):
        try:
            if len(value) == len(self.members):
                return
        except TypeError:
            raise WrongTypeError(f'{type(value).__name__} can not be converted to TupleOf DataType!') from None
        raise WrongTypeError(f'tuple needs {len(self.members)} elements')

    def __call__(self, value):
        """accepts any sequence, converts to tuple"""
        self.check_type(value)
        try:
            return tuple(sub(elem) for sub, elem in zip(self.members, value))
        except Exception as e:
            errcls = RangeError if isinstance(e, RangeError) else WrongTypeError
            raise errcls('can not convert some tuple elements') from e

    def validate(self, value, previous=None):
        self.check_type(value)
        try:
            if previous is None:
                return tuple(sub.validate(elem) for sub, elem in zip(self.members, value))
            return tuple(sub.validate(v, p) for sub, v, p in zip(self.members, value, previous))
        except Exception as e:
            errcls = RangeError if isinstance(e, RangeError) else WrongTypeError
            raise errcls('some tuple elements are invalid') from e

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        self.check_type(value)
        return [sub.export_value(elem) for sub, elem in zip(self.members, value)]

    def import_value(self, value):
        """returns a python object from serialisation"""
        return tuple(sub.import_value(elem) for sub, elem in zip(self.members, value))

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(f'trailing garbage: {rem!r}')
        return self(value)

    def format_value(self, value, unit=None):
        return f"({', '.join([sub.format_value(elem) for sub, elem in zip(self.members, value)])})"

    def compatible(self, other):
        if not isinstance(other, TupleOf):
            raise WrongTypeError('incompatible datatypes')
        if len(self.members) != len(other.members):
            raise WrongTypeError('incompatible datatypes')
        for a, b in zip(self.members, other.members):
            a.compatible(b)

    def set_main_unit(self, unit):
        for member in self.members:
            member.set_main_unit(unit)


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
            raise ProgrammingError('Empty structs are not allowed!')
        self.optional = list(members if optional is None else optional)
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
        res = {'type': 'struct', 'members': dict((n, s.export_datatype())
                                                 for n, s in list(self.members.items()))}
        if set(self.optional) != set(self.members):
            res['optional'] = self.optional
        return res

    def __repr__(self):
        opt = f', optional={self.optional!r}' if set(self.optional) == set(self.members) else ''
        return 'StructOf(%s%s)' % (', '.join(
            ['%s=%s' % (n, repr(st)) for n, st in list(self.members.items())]), opt)

    def __call__(self, value):
        """accepts any mapping, returns an immutable dict"""
        self.check_type(value)
        try:
            result = {}
            for key, val in value.items():
                if val is not None:  # goodie: allow None instead of missing key
                    result[key] = self.members[key](val)
            return ImmutableDict(result)
        except Exception as e:
            errcls = RangeError if isinstance(e, RangeError) else WrongTypeError
            raise errcls('can not convert struct element %s' % key) from e

    def validate(self, value, previous=None):
        self.check_type(value, True)
        try:
            result = dict(previous or {})
            for key, val in value.items():
                if val is not None:  # goodie: allow None instead of missing key
                    result[key] = self.members[key].validate(val)
            return ImmutableDict(result)
        except Exception as e:
            errcls = RangeError if isinstance(e, RangeError) else WrongTypeError
            raise errcls('struct element %s is invalid' % key) from e

    def check_type(self, value, allow_optional=False):
        try:
            superfluous = set(dict(value)) - set(self.members)
        except TypeError:
            raise WrongTypeError(f'{type(value).__name__} can not be converted a StructOf') from None
        if superfluous - set(self.optional):
            raise WrongTypeError(f"struct contains superfluous members: {', '.join(superfluous)}")
        missing = set(self.members) - set(value)
        if self.client or allow_optional:  # on the client side, allow optional elements always
            missing -= set(self.optional)
        if missing:
            raise WrongTypeError(f"missing struct elements: {', '.join(missing)}")

    def export_value(self, value):
        """returns a python object fit for serialisation"""
        self.check_type(value)
        return dict((str(k), self.members[k].export_value(v))
                    for k, v in list(value.items()))

    def import_value(self, value):
        """returns a python object from serialisation"""
        self.check_type(value, True)
        return {str(k): self.members[k].import_value(v)
                for k, v in value.items()}

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(f'trailing garbage: {rem!r}')
        return self(dict(value))

    def format_value(self, value, unit=None):
        return '{%s}' % (', '.join(['%s=%s' % (k, self.members[k].format_value(v)) for k, v in value.items()]))

    def compatible(self, other):
        try:
            mandatory = set(other.members) - set(other.optional)
            for k, m in self.members.items():
                m.compatible(other.members[k])
                mandatory.discard(k)
            if mandatory:
                raise WrongTypeError('incompatible datatypes')
        except (AttributeError, TypeError, KeyError):
            raise WrongTypeError('incompatible datatypes') from None

    def set_main_unit(self, unit):
        for member in self.members.values():
            member.set_main_unit(unit)


class CommandType(DataType):
    """command

    a pseudo datatype for commands with arguments and return values
    """
    IS_COMMAND = True

    def __init__(self, argument=None, result=None):
        super().__init__()
        if argument is not None:
            if not isinstance(argument, DataType):
                raise ProgrammingError('CommandType: Argument type must be a DataType!')
        if result is not None:
            if not isinstance(result, DataType):
                raise ProgrammingError('CommandType: Result type must be a DataType!')
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
            return f"CommandType({repr(self.argument) if self.argument else ''})"
        return f'CommandType({repr(self.argument)}, {repr(self.result)})'

    def __call__(self, value):
        raise ProgrammingError('commands can not be converted to a value')

    def export_value(self, value):
        raise ProgrammingError('values of type command can not be transported!')

    def import_value(self, value):
        raise ProgrammingError('values of type command can not be transported!')

    def from_string(self, text):
        value, rem = Parser.parse(text)
        if rem:
            raise ProtocolError(f'trailing garbage: {rem!r}')
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
            raise WrongTypeError('incompatible datatypes') from None


# internally used datatypes (i.e. only for programming the SEC-node)

class DataTypeType(DataType):
    def __call__(self, value):
        """accepts a datatype"""
        if isinstance(value, DataType):
            return value
        #TODO: not needed anymore?
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
    """Can take any python value.

    The optional (callable) validator can be used to restrict values to a
    certain type.
    For example using ``ValueType(dict)`` would ensure only values that can be
    turned into a dictionary can be used in this instance, as the conversion
    ``dict(value)`` is called for validation.

    Notes:
    The validator must either accept a value by returning it or the converted value,
    or raise an error.
    """
    def __init__(self, validator=None):
        super().__init__()
        self.validator = validator

    def __call__(self, value):
        """accepts any type -> default is no conversion"""
        if self.validator:
            try:
                return self.validator(value)
            except Exception as e:
                raise ConfigError(f'Validator {self.validator} raised {e!r} for value {value}') from e
        return value

    def copy(self):
        return ValueType(self.validator)

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
        """accepts None and other type"""
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
        """accepts any of the given types, takes the first valid"""
        for t in self.types:
            try:
                return t.validate(value)  # use always strict validation
            except Exception:
                pass
        raise WrongTypeError(f"Invalid Value, must conform to one of {', '.join(str(t) for t in self.types)}")


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
        """accepts an ordered tuple of numeric member types"""
        limits = TupleOf.validate(self, value)
        if limits[1] < limits[0]:
            raise RangeError(f'Maximum Value {limits[1]} must be greater than minimum value {limits[0]}!')
        return limits


class StatusType(TupleOf):
    """convenience type for status

    :param first: an Enum or Module to inherit from, or the first member name
    :param args: member names (codes will be taken from class attributes below)
    :param kwds: additional members not matching the standard
    """
    DISABLED = 0
    IDLE = 100
    STANDBY = 130
    PREPARED = 150
    WARN = 200
    WARN_STANDBY = 230
    WARN_PREPARED = 250
    UNSTABLE = 270  # not in SECoP standard (yet)
    BUSY = 300
    DISABLING = 310
    INITIALIZING = 320
    PREPARING = 340
    STARTING = 360
    RAMPING = 370
    STABILIZING = 380
    FINALIZING = 390
    ERROR = 400
    ERROR_STANDBY = 430
    ERROR_PREPARED = 450
    UNKNOWN = 401  # not in SECoP standard (yet)

    def __init__(self, first, *args, **kwds):
        if first:
            if isinstance(first, str):
                args = (first,) + args
                first = 'Status'  # enum name
            else:
                if not isinstance(first, Enum):
                    # assume first is a Module with a status parameter
                    try:
                        first = first.status.datatype.members[0]._enum
                    except AttributeError:
                        raise ProgrammingError('first argument must be either str, Enum or a module') from None
        else:
            first = 'Status'  # enum name
        bad = {n for n in args if n not in StatusType.__dict__ or n.startswith('_')}  # avoid built-in attributes
        if bad:
            raise ProgrammingError(f'positional arguments {bad!r} must be standard status code names')
        self.enum = Enum(Enum(first, **{n: StatusType.__dict__[n] for n in args}), **kwds)
        super().__init__(EnumType(self.enum), StringType())

    def __getattr__(self, key):
        return self.enum[key]


def floatargs(kwds):
    return {k: v for k, v in kwds.items() if k in
            {'unit', 'fmtstr', 'absolute_resolution', 'relative_resolution'}}


# argumentnames to lambda from spec!
# **kwds at the end are for must-ignore policy
DATATYPES = {
    'bool': lambda **kwds:
        BoolType(),
    'int': lambda min, max, **kwds:
        IntRange(min=min, max=max),
    'scaled': lambda scale, min, max, **kwds:
        ScaledInteger(scale=scale, min=min*scale, max=max*scale, **floatargs(kwds)),
    'double': lambda min=None, max=None, **kwds:
        FloatRange(min=min, max=max, **floatargs(kwds)),
    'blob': lambda maxbytes, minbytes=0, **kwds:
        BLOBType(minbytes=minbytes, maxbytes=maxbytes),
    'string': lambda minchars=0, maxchars=None, isUTF8=False, **kwds:
        StringType(minchars=minchars, maxchars=maxchars, isUTF8=isUTF8),
    'array': lambda maxlen, members, minlen=0, pname='', **kwds:
        ArrayOf(get_datatype(members, pname), minlen=minlen, maxlen=maxlen),
    'tuple': lambda members, pname='', **kwds:
        TupleOf(*tuple((get_datatype(t, pname) for t in members))),
    'enum': lambda members, pname='', **kwds:
        EnumType(pname, members=members),
    'struct': lambda members, optional=None, pname='', **kwds:
        StructOf(optional, **dict((n, get_datatype(t, pname)) for n, t in list(members.items()))),
    'command': lambda argument=None, result=None, pname='', **kwds:
        CommandType(get_datatype(argument, pname), get_datatype(result)),
    'limit': lambda members, pname='', **kwds:
        LimitsType(get_datatype(members, pname)),
}


# used on the client side for getting the right datatype from formerly jsonified descr.
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
            raise WrongTypeError(f'a data descriptor must be a dict containing a "type" key, not {json!r}') from None

    try:
        datatype = DATATYPES[base](pname=pname, **kwargs)
        datatype.client = True
        return datatype
    except Exception as e:
        raise WrongTypeError(f'invalid data descriptor: {json!r} ({str(e)})') from None
