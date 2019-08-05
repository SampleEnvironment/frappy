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
"""Define classes for Parameters/Commands and Overriding them"""

from __future__ import division, print_function

from collections import OrderedDict

from secop.datatypes import CommandType, DataType, StringType, BoolType, EnumType, DataTypeType, ValueType, OrType, \
    NoneOr, TextType
from secop.errors import ProgrammingError
from secop.properties import HasProperties, Property

try:
    unicode
except NameError:
    # pylint: disable=redefined-builtin
    unicode = str  # py3 compat

class CountedObj(object):
    ctr = [0]
    def __init__(self):
        cl = self.__class__.ctr
        cl[0] += 1
        self.ctr = cl[0]


class Accessible(HasProperties, CountedObj):
    '''base class for Parameter and Command'''

    properties = {}

    def __init__(self, **kwds):
        super(Accessible, self).__init__()
        self.properties.update(kwds)

    def __repr__(self):
        return u'%s_%d(%s)' % (self.__class__.__name__, self.ctr, ',\n\t'.join(
            [u'%s=%r' % (k, self.properties.get(k, v.default)) for k, v in sorted(self.__class__.properties.items())]))

    def copy(self):
        # return a copy of ourselfs
        props = dict(self.properties, ctr=self.ctr)
        return type(self)(**props)

    def for_export(self):
        # used for serialisation only
        # some specials:
        # - datatype needs a special serialisation
        # - readonly is mandatory for serialisation, but not for declaration in classes
        r =  self.exportProperties()
        if isinstance(self, Parameter):
            if 'readonly' not in r:
                r['readonly'] = self.__class__.properties['readonly'].default
        return r


class Parameter(Accessible):
    """storage for Parameter settings + value + qualifiers

    if readonly is False, the value can be changed (by code, or remote)
    if no default is given, the parameter MUST be specified in the configfile
    during startup, value is initialized with the default value or
    from the config file if specified there

    poll can be:
    - False  (never poll this parameter)
    - True   (poll this every pollinterval)
    - positive int  (poll every N(th) pollinterval)
    - negative int  (normally poll every N(th) pollinterval, if module is busy, poll every pollinterval)

    note: Drivable (and derived classes) poll with 10 fold frequency if module is busy....
    """

    properties = {
        u'description': Property('Description of the Parameter', TextType(),
                                 extname=u'description', mandatory=True),
        u'datatype':    Property('Datatype of the Parameter', DataTypeType(),
                                 extname=u'datatype', mandatory=True),
        u'unit':        Property('[legacy] unit of the parameter. This should now be on the datatype!', StringType(),
                                 extname=u'unit', default=''),  # goodie, should be on the datatype!
        u'readonly':    Property('Is the Parameter readonly? (vs. changeable via SECoP)', BoolType(),
                                 extname=u'readonly', default=True),
        u'group':       Property('Optional parameter group this parameter belongs to', StringType(),
                                 extname=u'group', default=''),
        u'visibility':  Property('Optional visibility hint', EnumType(u'visibility', user=1, advanced=2, expert=3),
                                 extname=u'visibility', default=1),
        u'constant':    Property('Optional constant value for constant parameters', ValueType(),
                                 extname=u'constant', default=None),
        u'default':     Property('Default (startup) value of this parameter if it can not be read from the hardware.',
                                 ValueType(), export=False, default=None, mandatory=False),
        u'export':      Property('Is this parameter accessible via SECoP? (vs. internal parameter)',
                                 OrType(BoolType(), StringType()), export=False, default=True),
        u'poll':        Property('Polling indicator', ValueType(), export=False, default=True),  # check default value!
        u'optional':    Property('[Internal] is this parameter optional?', BoolType(), export=False, default=False),
    }

    value = None
    timestamp = None
    def __init__(self, description, datatype, ctr=None, **kwds):

        if ctr is not None:
            self.ctr = ctr

        if not isinstance(datatype, DataType):
            if issubclass(datatype, DataType):
                # goodie: make an instance from a class (forgotten ()???)
                datatype = datatype()
            else:
                raise ValueError(
                    u'datatype MUST be derived from class DataType!')

        kwds[u'description'] = description
        kwds[u'datatype'] = datatype
        super(Parameter, self).__init__(**kwds)

        # note: auto-converts True/False to 1/0 which yield the expected
        # behaviour...
        self.properties[u'poll'] = int(self.poll)

        if self.constant is not None:
            self.properties[u'readonly'] = True
            # The value of the `constant` property should be the
            # serialised version of the constant, or unset
            constant = self.datatype(kwds[u'constant'])
            self.properties[u'constant'] = self.datatype.export_value(constant)

        # helper: unit should be set on the datatype, not on the parameter!
        if self.unit:
            self.datatype.unit = self.unit
            self.properties[u'unit'] = ''

        # internal caching: value and timestamp of last change...
        self.value = self.default
        self.timestamp = 0

    def export_value(self):
        return self.datatype.export_value(self.value)

    # helpers...
    def _get_unit_(self):
        return self.datatype.unit

    def _set_unit_(self, unit):
        print(u'DeprecationWarning: setting unit on the parameter is going to be removed')
        self.datatype.unit = unit

    unit = property(_get_unit_, _set_unit_)
    del _get_unit_
    del _set_unit_


class UnusedClass(object):
    # do not derive anything from this!
    pass

class Parameters(OrderedDict):
    """class storage for Parameters"""
    def __init__(self, *args, **kwds):
        self.exported = {}  # only for lookups!
        super(Parameters, self).__init__(*args, **kwds)

    def __setitem__(self, key, value):
        if value.export:
            if isinstance(value, PREDEFINED_ACCESSIBLES.get(key, UnusedClass)):
                value.properties[u'export'] = key
            else:
                value.properties[u'export'] = '_' + key
            self.exported[value.export] = key
        super(Parameters, self).__setitem__(key, value)

    def __getitem__(self, item):
        return super(Parameters, self).__getitem__(self.exported.get(item, item))


class ParamValue(object):
    __slots__ = ['value', 'timestamp']
    def __init__(self, value, timestamp=0):
        self.value = value
        self.timestamp = timestamp


class Commands(Parameters):
    """class storage for Commands"""
    pass


class Override(CountedObj):
    """Stores the overrides to be applied to a Parameter

    note: overrides are applied by the metaclass during class creating
    reorder= True: use position of Override instead of inherited for the order
    """
    def __init__(self, description="", reorder=False, **kwds):
        super(Override, self).__init__()
        self.kwds = kwds
        self.reorder = reorder
        # allow to override description without keyword
        if description:
            self.kwds[u'description'] = description
        # for now, do not use the Override ctr
        # self.kwds['ctr'] = self.ctr

    def __repr__(self):
        return u'%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            [u'%s=%r' % (k, v) for k, v in sorted(self.kwds.items())]))

    def apply(self, obj):
        if isinstance(obj, Accessible):
            props = obj.properties.copy()
            if isinstance(obj, Parameter):
                if u'constant' in self.kwds:
                    constant = obj.datatype(self.kwds.pop(u'constant'))
                    self.kwds[u'constant'] = obj.datatype.export_value(constant)
                    self.kwds[u'readonly'] = True
            props.update(self.kwds)

            if self.reorder:
                #props['ctr'] = self.ctr
                return type(obj)(ctr=self.ctr, **props)
            return type(obj)(**props)
        else:
            raise ProgrammingError(
                u"Overrides can only be applied to Accessibles, %r is none!" %
                obj)


class Command(Accessible):
    """storage for Commands settings (description + call signature...)
    """
    # datatype is not listed (handled separately)
    properties = {
        u'description': Property('Description of the Command', TextType(),
                                 extname=u'description', export=True, mandatory=True),
        u'group':       Property('Optional command group of the command.', StringType(),
                                 extname=u'group', export=True, default=''),
        u'visibility':  Property('Optional visibility hint', EnumType(u'visibility', user=1, advanced=2, expert=3),
                                 extname=u'visibility', export=True, default=1),
        u'export':      Property('[internal] Flag: is the command accessible via SECoP? (vs. pure internal use)',
                                 OrType(BoolType(), StringType()), export=False, default=True),
        u'optional':    Property('[internal] is The comamnd optional to implement? (vs. mandatory',
                                 BoolType(), export=False, default=False, settable=False),
        u'datatype': Property('[internal] datatype of the command, auto generated from \'argument\' and \'result\'',
                              DataTypeType(), extname=u'datatype', mandatory=True),
        u'argument': Property('Datatype of the argument to the command, or None.',
                              NoneOr(DataTypeType()), export=False, mandatory=True),
        u'result': Property('Datatype of the result from the command, or None.',
                              NoneOr(DataTypeType()), export=False, mandatory=True),
    }

    def __init__(self, description, ctr=None, **kwds):
        kwds[u'description'] = description
        kwds[u'datatype'] = CommandType(kwds.get('argument', None), kwds.get('result', None))
        super(Command, self).__init__(**kwds)
        if ctr is not None:
            self.ctr = ctr

    @property
    def argument(self):
        return self.datatype.argument

    @property
    def result(self):
        return self.datatype.result

    def for_export(self):
        # used for serialisation only
        # some specials:
        # - datatype needs a special serialisation
        # - readonly is mandatory for serialisation, but not for declaration in classes
        r =  self.exportProperties()
#        if isinstance(self, Parameter):
#            if u'readonly' not in r:
#                r[u'readonly'] = self.__class__.properties[u'readonly'].default
#        if u'datatype' in r:
#            _d = r[u'datatype']
#            print(formatExtendedStack())  # for debug
        return r


# list of predefined accessibles with their type
PREDEFINED_ACCESSIBLES = dict(
    value = Parameter,
    status = Parameter,
    target = Parameter,
    pollinterval = Parameter,
    ramp = Parameter,
    user_ramp = Parameter,
    setpoint = Parameter,
    time_to_target = Parameter,
    unit = Parameter, # reserved name
    loglevel = Parameter, # reserved name
    mode = Parameter, # reserved name
    stop = Command,
    reset = Command,
    go = Command,
    abort = Command,
    shutdown = Command,
)
