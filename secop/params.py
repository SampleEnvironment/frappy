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


import inspect
import itertools
from collections import OrderedDict

from secop.datatypes import CommandType, DataType, StringType, BoolType, EnumType, DataTypeType, ValueType, OrType, \
    NoneOr, TextType, IntRange, TupleOf
from secop.errors import ProgrammingError, BadValueError
from secop.properties import HasProperties, Property


object_counter = itertools.count(1)


class Accessible(HasProperties):
    """base class for Parameter and Command"""

    properties = {}
    kwds = None  # is a dict if it might be used as Override

    def __init__(self, ctr, **kwds):
        self.ctr = ctr or next(object_counter)
        super(Accessible, self).__init__()
        # do not use self.properties.update here, as no invalid values should be
        # assigned to properties, even not before checkProperties
        for k,v in kwds.items():
            self.setProperty(k, v)

    def __repr__(self):
        props = []
        for k, prop in sorted(self.__class__.properties.items()):
            v = self.properties.get(k, prop.default)
            if v != prop.default:
                props.append('%s=%r' % (k, v))
        return '%s(%s, ctr=%d)' % (self.__class__.__name__, ', '.join(props), self.ctr)

    def as_dict(self):
        return self.properties

    def override(self, from_object=None, **kwds):
        """return a copy of ourselfs, modified by <other>"""
        props = dict(self.properties, ctr=self.ctr)
        if from_object:
            props.update(from_object.kwds)
        props.update(kwds)
        props['datatype'] = props['datatype'].copy()
        return type(self)(inherit=False, internally_called=True, **props)

    def copy(self):
        """return a copy of ourselfs"""
        props = dict(self.properties, ctr=self.ctr)
        # deep copy, as datatype might be altered from config
        props['datatype'] = props['datatype'].copy()
        return type(self)(inherit=False, internally_called=True, **props)

    def for_export(self):
        """prepare for serialisation"""
        return self.exportProperties()


class Parameter(Accessible):
    """defines a parameter

    :param description: description
    :param datatype: the datatype
    :param inherit: whether properties not given should be inherited.
      defaults to True when datatype or description is missing, else to False
    :param reorder: when True, put this parameter after all inherited items in the accessible list
    :param kwds: optional properties
    :param ctr: (for internal use only)
    :param internally_used: (for internal use only)
    """
    # storage for Parameter settings + value + qualifiers

    properties = {
        'description': Property('mandatory description of the parameter', TextType(),
                                 extname='description', mandatory=True),
        'datatype':    Property('datatype of the Parameter (SECoP datainfo)', DataTypeType(),
                                 extname='datainfo', mandatory=True),
        'readonly':    Property('not changeable via SECoP (default True)', BoolType(),
                                 extname='readonly', default=True),
        'group':       Property('optional parameter group this parameter belongs to', StringType(),
                                 extname='group', default=''),
        'visibility':  Property('optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
                                 extname='visibility', default=1),
        'constant':    Property('optional constant value for constant parameters', ValueType(),
                                 extname='constant', default=None, mandatory=False),
        'default':     Property('[internal] default (startup) value of this parameter '
                                'if it can not be read from the hardware',
                                 ValueType(), export=False, default=None, mandatory=False),
        'export':      Property('''
                                [internal] export settings
        
                                  * False: not accessible via SECoP.
                                  * True: exported, name automatic.
                                  * a string: exported with custom name''',
                                 OrType(BoolType(), StringType()), export=False, default=True),
        'poll':        Property('''
                                [internal] polling indicator
                                
                                may be:
                                
                                  * None (omitted): will be converted to True/False if handler is/is not None
                                  * False or 0 (never poll this parameter)
                                  * True or 1 (AUTO), converted to SLOW (readonly=False)
                                    DYNAMIC (*status* and *value*) or REGULAR (else)
                                  * 2 (SLOW), polled with lower priority and a multiple of pollinterval
                                  * 3 (REGULAR), polled with pollperiod
                                  * 4 (DYNAMIC), if BUSY, with a fraction of pollinterval,
                                    else polled with pollperiod
                                ''',
                                NoneOr(IntRange()), export=False, default=None),
        'needscfg':    Property('[internal] needs value in config', NoneOr(BoolType()), export=False, default=None),
        'optional':    Property('[internal] is this parameter optional?', BoolType(), export=False,
                                 settable=False, default=False),
        'handler':     Property('[internal] overload the standard read and write functions',
                                 ValueType(), export=False, default=None, mandatory=False, settable=False),
        'initwrite':   Property('[internal] write this parameter on initialization'
                                ' (default None: write if given in config)',
                                 NoneOr(BoolType()), export=False, default=None, mandatory=False, settable=False),
    }

    def __init__(self, description=None, datatype=None, inherit=True, *,
                 reorder=False, ctr=None, internally_called=False, **kwds):
        if datatype is not None:
            if not isinstance(datatype, DataType):
                if isinstance(datatype, type) and issubclass(datatype, DataType):
                    # goodie: make an instance from a class (forgotten ()???)
                    datatype = datatype()
                else:
                    raise ProgrammingError(
                        'datatype MUST be derived from class DataType!')
            kwds['datatype'] = datatype

        if description is not None:
            if not internally_called:
                description = inspect.cleandoc(description)
            kwds['description'] = description

        unit = kwds.pop('unit', None)
        if unit is not None and datatype:   # for legacy code only
            datatype.setProperty('unit', unit)

        constant = kwds.get('constant')
        if constant is not None:
            constant = datatype(constant)
            # The value of the `constant` property should be the
            # serialised version of the constant, or unset
            kwds['constant'] = datatype.export_value(constant)
            kwds['readonly'] = True
        if internally_called:  # fixes in case datatype has changed
            default = kwds.get('default')
            if default is not None:
                try:
                    datatype(default)
                except BadValueError:
                    # clear default, if it does not match datatype
                    kwds['default'] = None
        super().__init__(ctr, **kwds)
        if inherit:
            if reorder:
                kwds['ctr'] = next(object_counter)
            if unit is not None:
                kwds['unit'] = unit
            self.kwds = kwds  # contains only the items which must be overwritten

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


class Commands(Parameters):
    """class storage for Commands"""


class Override:
    """Stores the overrides to be applied to a Parameter

    note: overrides are applied by the metaclass during class creating
    reorder=True: use position of Override instead of inherited for the order
    """
    def __init__(self, description="", datatype=None, *, reorder=False, **kwds):
        self.kwds = kwds
        # allow to override description and datatype without keyword
        if description:
            self.kwds['description'] = description
        if datatype is not None:
            self.kwds['datatype'] = datatype
        if reorder:  # result from apply must use new ctr from Override
            self.kwds['ctr'] = next(object_counter)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.kwds.items())]))

    def apply(self, obj):
        return obj.override(self)


class Command(Accessible):
    # to be merged with usercommand
    properties = {
        'description': Property('description of the Command', TextType(),
                                 extname='description', export=True, mandatory=True),
        'group':       Property('optional command group of the command.', StringType(),
                                 extname='group', export=True, default=''),
        'visibility':  Property('optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
                                 extname='visibility', export=True, default=1),
        'export':      Property('''
                                [internal] export settings
        
                                  * False: not accessible via SECoP.
                                  * True: exported, name automatic.
                                  * a string: exported with custom name''',
                                 OrType(BoolType(), StringType()), export=False, default=True),
        'optional':    Property('[internal] is the command optional to implement? (vs. mandatory)',
                                 BoolType(), export=False, default=False, settable=False),
        'datatype': Property('[internal] datatype of the command, auto generated from \'argument\' and \'result\'',
                              DataTypeType(), extname='datainfo', mandatory=True),
        'argument': Property('datatype of the argument to the command, or None',
                              NoneOr(DataTypeType()), export=False, mandatory=True),
        'result': Property('datatype of the result from the command, or None',
                              NoneOr(DataTypeType()), export=False, mandatory=True),
    }

    def __init__(self, description=None, *, reorder=False, inherit=True,
                 internally_called=False, ctr=None, **kwds):
        if internally_called:
            inherit = False
        # make sure either all or no datatype info is in kwds
        if 'argument' in kwds or 'result' in kwds:
            datatype = CommandType(kwds.get('argument'), kwds.get('result'))
        else:
            datatype = kwds.get('datatype')
        datainfo = {}
        datainfo['datatype'] = datatype or CommandType()
        datainfo['argument'] = datainfo['datatype'].argument
        datainfo['result'] = datainfo['datatype'].result
        if datatype:
            kwds.update(datainfo)
        if description is not None:
            kwds['description'] = description
        if datatype:
            datainfo = {}
        super(Command, self).__init__(ctr, **datainfo, **kwds)
        if inherit:
            if reorder:
                kwds['ctr'] = next(object_counter)
            self.kwds = kwds

    @property
    def argument(self):
        return self.datatype.argument

    @property
    def result(self):
        return self.datatype.result


class usercommand(Command):
    """decorator to turn a method into a command

    :param argument: the datatype of the argument or None
    :param result: the datatype of the result or None
    :param inherit: whether properties not given should be inherited.
      defaults to True when datatype or description is missing, else to False
    :param reorder: when True, put this command after all inherited items in the accessible list
    :param kwds: optional properties

    {all properties}
    """

    func = None

    def __init__(self, argument=False, result=None, inherit=True, **kwds):
        if result or kwds or isinstance(argument, DataType) or not callable(argument):
            # normal case
            self.func = None
            if argument is False and result:
                argument = None
            if argument is not False:
                if isinstance(argument, (tuple, list)):
                    # goodie: allow declaring multiple arguments as a tuple
                    # TODO: check that calling works properly
                    argument = TupleOf(*argument)
                kwds['argument'] = argument
                kwds['result'] = result
            self.kwds = kwds
        else:
            # goodie: allow @usercommand instead of @usercommand()
            self.func = argument  # this is the wrapped method!
            if argument.__doc__ is not None:
                kwds['description'] = argument.__doc__
            self.name = self.func.__name__
        super().__init__(kwds.pop('description', ''), inherit=inherit, **kwds)

    def override(self, from_object=None, **kwds):
        result = super().override(from_object, **kwds)
        func = kwds.pop('func', from_object.func if from_object else None)
        if func:
            result(func)  # pylint: disable=not-callable
        return result

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        if not self.func:
            raise ProgrammingError('usercommand %s not properly configured' % self.name)
        return self.func.__get__(obj, owner)

    def __call__(self, fun):
        description = self.kwds.get('description') or fun.__doc__
        self.properties['description'] = self.kwds['description'] = description
        self.name = fun.__name__
        self.func = fun
        return self


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
