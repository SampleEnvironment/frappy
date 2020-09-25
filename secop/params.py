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
"""Define classes for Parameters/Commands and Overriding them"""


from collections import OrderedDict

from secop.datatypes import CommandType, DataType, StringType, BoolType, EnumType, DataTypeType, ValueType, OrType, \
    NoneOr, TextType, IntRange
from secop.errors import ProgrammingError, BadValueError
from secop.properties import HasProperties, Property


class CountedObj:
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
        # do not use self.properties.update here, as no invalid values should be
        # assigned to properties, even not before checkProperties
        for k,v in kwds.items():
            self.setProperty(k, v)

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ',\n\t'.join(
            ['%s=%r' % (k, self.properties.get(k, v.default)) for k, v in sorted(self.__class__.properties.items())]))

    def copy(self):
        # return a copy of ourselfs
        props = dict(self.properties, ctr=self.ctr)
        # deep copy, as datatype might be altered from config
        props['datatype'] = props['datatype'].copy()
        return type(self)(**props)

    def for_export(self):
        """prepare for serialisation"""
        return self.exportProperties()


class Parameter(Accessible):
    """storage for Parameter settings + value + qualifiers

    if readonly is False, the value can be changed (by code, or remote)
    if no default is given, the parameter MUST be specified in the configfile
    during startup, value is initialized with the default value or
    from the config file if specified there

    poll can be:
    - None: will be converted to True/False if handler is/is not None
    - False or 0 (never poll this parameter)
    - True or > 0  (poll this parameter)
    - the exact meaning depends on the used poller
      meaning for secop.poller.Poller:
        - 1 or True (AUTO), converted to SLOW (readonly=False), DYNAMIC('status' and 'value') or REGULAR(else)
        - 2 (SLOW), polled with lower priority and a multiple of pollperiod
        - 3 (REGULAR), polled with pollperiod
        - 4 (DYNAMIC), polled with pollperiod, if not BUSY, else with a fraction of pollperiod
      meaning for the basicPoller:
        - True or 1 (poll this every pollinterval)
        - positive int  (poll every N(th) pollinterval)
        - negative int  (normally poll every N(th) pollinterval, if module is busy, poll every pollinterval)
        note: Drivable (and derived classes) poll with 10 fold frequency if module is busy....
    """

    properties = {
        'description': Property('Description of the Parameter', TextType(),
                                 extname='description', mandatory=True),
        'datatype':    Property('Datatype of the Parameter', DataTypeType(),
                                 extname='datainfo', mandatory=True),
        'readonly':    Property('Is the Parameter readonly? (vs. changeable via SECoP)', BoolType(),
                                 extname='readonly', mandatory=True),
        'group':       Property('Optional parameter group this parameter belongs to', StringType(),
                                 extname='group', default=''),
        'visibility':  Property('Optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
                                 extname='visibility', default=1),
        'constant':    Property('Optional constant value for constant parameters', ValueType(),
                                 extname='constant', default=None, mandatory=False),
        'default':     Property('Default (startup) value of this parameter if it can not be read from the hardware.',
                                 ValueType(), export=False, default=None, mandatory=False),
        'export':      Property('Is this parameter accessible via SECoP? (vs. internal parameter)',
                                 OrType(BoolType(), StringType()), export=False, default=True),
        'poll':        Property('Polling indicator', NoneOr(IntRange()), export=False, default=None),
        'needscfg':    Property('needs value in config', NoneOr(BoolType()), export=False, default=None),
        'optional':    Property('[Internal] is this parameter optional?', BoolType(), export=False,
                                 settable=False, default=False),
        'handler':     Property('[internal] overload the standard read and write functions',
                                 ValueType(), export=False, default=None, mandatory=False, settable=False),
        'initwrite':   Property('[internal] write this parameter on initialization'
                                ' (default None: write if given in config)',
                                 NoneOr(BoolType()), export=False, default=None, mandatory=False, settable=False),
    }

    def __init__(self, description, datatype, ctr=None, unit=None, **kwds):

        if ctr is not None:
            self.ctr = ctr

        if not isinstance(datatype, DataType):
            if issubclass(datatype, DataType):
                # goodie: make an instance from a class (forgotten ()???)
                datatype = datatype()
            else:
                raise ProgrammingError(
                    'datatype MUST be derived from class DataType!')

        kwds['description'] = description
        kwds['datatype'] = datatype
        kwds['readonly'] = kwds.get('readonly', True) # for frappy optional, for SECoP mandatory
        if unit is not None: # for legacy code only
            datatype.setProperty('unit', unit)
        super(Parameter, self).__init__(**kwds)

        if self.initwrite and self.readonly:
            raise ProgrammingError('can not have both readonly and initwrite!')

        if self.constant is not None:
            self.properties['readonly'] = True
            # The value of the `constant` property should be the
            # serialised version of the constant, or unset
            constant = self.datatype(kwds['constant'])
            self.properties['constant'] = self.datatype.export_value(constant)

        # internal caching: value and timestamp of last change...
        self.value = self.default
        self.timestamp = 0
        self.readerror = None # if not None, indicates that last read was not successful

    def export_value(self):
        return self.datatype.export_value(self.value)

    def getProperties(self):
        """get also properties of datatype"""
        superProp = super().getProperties().copy()
        superProp.update(self.datatype.getProperties())
        return superProp

    def setProperty(self, key, value):
        """set also properties of datatype"""
        if key in self.__class__.properties:
            super().setProperty(key, value)
        else:
            self.datatype.setProperty(key, value)

    def checkProperties(self):
        super().checkProperties()
        self.datatype.checkProperties()

    def for_export(self):
        """prepare for serialisation

        readonly is mandatory for serialisation, but not for declaration in classes
        """
        r = super().for_export()
        if 'readonly' not in r:
            r['readonly'] = self.__class__.properties['readonly'].default
        return r


class UnusedClass:
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
                value.properties['export'] = key
            else:
                value.properties['export'] = '_' + key
            self.exported[value.export] = key
        super(Parameters, self).__setitem__(key, value)

    def __getitem__(self, item):
        return super(Parameters, self).__getitem__(self.exported.get(item, item))


class ParamValue:
    __slots__ = ['value', 'timestamp']
    def __init__(self, value, timestamp=0):
        self.value = value
        self.timestamp = timestamp


class Commands(Parameters):
    """class storage for Commands"""


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
            self.kwds['description'] = description
        # for now, do not use the Override ctr
        # self.kwds['ctr'] = self.ctr

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.kwds.items())]))

    def apply(self, obj):
        if isinstance(obj, Accessible):
            props = obj.properties.copy()
            props['datatype'] = props['datatype'].copy()
            if isinstance(obj, Parameter):
                if 'constant' in self.kwds:
                    constant = obj.datatype(self.kwds.pop('constant'))
                    self.kwds['constant'] = obj.datatype.export_value(constant)
                    self.kwds['readonly'] = True
                if 'datatype' in self.kwds and 'default' not in self.kwds:
                    try:
                        self.kwds['datatype'](obj.default)
                    except BadValueError:
                        # clear default, if it does not match datatype
                        props['default'] = None
            props.update(self.kwds)

            if self.reorder:
                #props['ctr'] = self.ctr
                return type(obj)(ctr=self.ctr, **props)
            return type(obj)(**props)
        raise ProgrammingError(
            "Overrides can only be applied to Accessibles, %r is none!" %
            obj)


class Command(Accessible):
    """storage for Commands settings (description + call signature...)
    """
    properties = {
        'description': Property('Description of the Command', TextType(),
                                 extname='description', export=True, mandatory=True),
        'group':       Property('Optional command group of the command.', StringType(),
                                 extname='group', export=True, default=''),
        'visibility':  Property('Optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
                                 extname='visibility', export=True, default=1),
        'export':      Property('[internal] Flag: is the command accessible via SECoP? (vs. pure internal use)',
                                 OrType(BoolType(), StringType()), export=False, default=True),
        'optional':    Property('[internal] is the command optional to implement? (vs. mandatory)',
                                 BoolType(), export=False, default=False, settable=False),
        'datatype': Property('[internal] datatype of the command, auto generated from \'argument\' and \'result\'',
                              DataTypeType(), extname='datainfo', mandatory=True),
        'argument': Property('Datatype of the argument to the command, or None.',
                              NoneOr(DataTypeType()), export=False, mandatory=True),
        'result': Property('Datatype of the result from the command, or None.',
                              NoneOr(DataTypeType()), export=False, mandatory=True),
    }

    def __init__(self, description, ctr=None, **kwds):
        kwds['description'] = description
        kwds['datatype'] = CommandType(kwds.get('argument', None), kwds.get('result', None))
        super(Command, self).__init__(**kwds)
        if ctr is not None:
            self.ctr = ctr

    @property
    def argument(self):
        return self.datatype.argument

    @property
    def result(self):
        return self.datatype.result


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
    communicate = Command,
)
