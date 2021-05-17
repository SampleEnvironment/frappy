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

from secop.datatypes import BoolType, CommandType, DataType, \
    DataTypeType, EnumType, IntRange, NoneOr, OrType, \
    StringType, StructOf, TextType, TupleOf, ValueType
from secop.errors import BadValueError, ProgrammingError
from secop.properties import HasProperties, Property

UNSET = object()  # an argument not given, not even None


class Accessible(HasProperties):
    """base class for Parameter and Command"""

    kwds = None  # is a dict if it might be used as Override

    def __init__(self, **kwds):
        super().__init__()
        self.init(kwds)

    def init(self, kwds):
        # do not use self.propertyValues.update here, as no invalid values should be
        # assigned to properties, even not before checkProperties
        for k, v in kwds.items():
            self.setProperty(k, v)

    def inherit(self, cls, owner):
        for base in owner.__bases__:
            if hasattr(base, self.name):
                aobj = getattr(base, 'accessibles', {}).get(self.name)
                if aobj:
                    if not isinstance(aobj, cls):
                        raise ProgrammingError('%s %s.%s can not inherit from a %s' %
                                               (cls.__name__, owner.__name__, self.name, aobj.__class__.__name__))
                    # inherit from aobj
                    for pname, value in aobj.propertyValues.items():
                        if pname not in self.propertyValues:
                            self.propertyValues[pname] = value
                break

    def as_dict(self):
        return self.propertyValues

    def override(self, value=UNSET, **kwds):
        """return a copy, overridden by a bare attribute

        and/or some properties"""
        raise NotImplementedError

    def copy(self):
        """return a (deep) copy of ourselfs"""
        raise NotImplementedError

    def for_export(self):
        """prepare for serialisation"""
        raise NotImplementedError

    def __repr__(self):
        props = []
        for k, prop in sorted(self.propertyDict.items()):
            v = self.propertyValues.get(k, prop.default)
            if v != prop.default:
                props.append('%s=%r' % (k, v))
        return '%s(%s)' % (self.__class__.__name__, ', '.join(props))


class Parameter(Accessible):
    """defines a parameter

    :param description: description
    :param datatype: the datatype
    :param inherit: whether properties not given should be inherited
    :param kwds: optional properties
    """
    # storage for Parameter settings + value + qualifiers

    description = Property(
        'mandatory description of the parameter', TextType(),
        extname='description', mandatory=True)
    datatype = Property(
        'datatype of the Parameter (SECoP datainfo)', DataTypeType(),
        extname='datainfo', mandatory=True)
    readonly = Property(
        'not changeable via SECoP (default True)', BoolType(),
        extname='readonly', default=True, export='always')
    group = Property(
        'optional parameter group this parameter belongs to', StringType(),
        extname='group', default='')
    visibility = Property(
        'optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
        extname='visibility', default=1)
    constant = Property(
        'optional constant value for constant parameters', ValueType(),
        extname='constant', default=None)
    default = Property(
        '''[internal] default (startup) value of this parameter

        if it can not be read from the hardware''', ValueType(),
        export=False, default=None)
    export = Property(
        '''[internal] export settings

          * False: not accessible via SECoP.
          * True: exported, name automatic.
          * a string: exported with custom name''', OrType(BoolType(), StringType()),
        export=False, default=True)
    poll = Property(
        '''[internal] polling indicator

           may be:

             * None (omitted): will be converted to True/False if handler is/is not None
             * False or 0 (never poll this parameter)
             * True or 1 (AUTO), converted to SLOW (readonly=False)
               DYNAMIC (*status* and *value*) or REGULAR (else)
             * 2 (SLOW), polled with lower priority and a multiple of pollinterval
             * 3 (REGULAR), polled with pollperiod
             * 4 (DYNAMIC), if BUSY, with a fraction of pollinterval,
               else polled with pollperiod
           ''', NoneOr(IntRange()),
        export=False, default=None)
    needscfg = Property(
        '[internal] needs value in config', NoneOr(BoolType()),
        export=False, default=None)
    optional = Property(
        '[internal] is this parameter optional?', BoolType(),
        export=False, settable=False, default=False)
    handler = Property(
        '[internal] overload the standard read and write functions', ValueType(),
        export=False, default=None, settable=False)
    initwrite = Property(
        '''[internal] write this parameter on initialization

        default None: write if given in config''', NoneOr(BoolType()),
        export=False, default=None, settable=False)

    # used on the instance copy only
    value = None
    timestamp = 0
    readerror = None

    def __init__(self, description=None, datatype=None, inherit=True, *, unit=None, constant=None, **kwds):
        super().__init__(**kwds)
        if datatype is not None:
            if not isinstance(datatype, DataType):
                if isinstance(datatype, type) and issubclass(datatype, DataType):
                    # goodie: make an instance from a class (forgotten ()???)
                    datatype = datatype()
                else:
                    raise ProgrammingError(
                        'datatype MUST be derived from class DataType!')
            self.datatype = datatype
            if 'default' in kwds:
                self.default = datatype(kwds['default'])

        if description is not None:
            self.description = inspect.cleandoc(description)

        # save for __set_name__
        self._inherit = inherit
        self._unit = unit  # for legacy code only
        self._constant = constant

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.parameters[self.name].value

    def __set__(self, obj, value):
        obj.announceUpdate(self.name, value)

    def __set_name__(self, owner, name):
        self.name = name

        if self._inherit:
            self.inherit(Parameter, owner)

        # check for completeness
        missing_properties = [pname for pname in ('description', 'datatype') if pname not in self.propertyValues]
        if missing_properties:
            raise ProgrammingError('Parameter %s.%s needs a %s' %
                                   (owner.__name__, name, ' and a '.join(missing_properties)))
        if self._unit is not None:
            self.datatype.setProperty('unit', self._unit)

        if self._constant is not None:
            constant = self.datatype(self._constant)
            # The value of the `constant` property should be the
            # serialised version of the constant, or unset
            self.constant = self.datatype.export_value(constant)
            self.readonly = True

        if 'default' in self.propertyValues:
            # fixes in case datatype has changed
            try:
                self.datatype(self.default)
            except BadValueError:
                # clear default, if it does not match datatype
                self.propertyValues.pop('default')

        if self.export is True:
            predefined_cls = PREDEFINED_ACCESSIBLES.get(name, None)
            if predefined_cls is Parameter:
                self.export = name
            elif predefined_cls is None:
                self.export = '_' + name
            else:
                raise ProgrammingError('can not use %r as name of a Parameter' % name)

    def copy(self):
        # deep copy, as datatype might be altered from config
        res = Parameter()
        res.name = self.name
        res.init(self.propertyValues)
        res.datatype = res.datatype.copy()
        return res

    def override(self, value=UNSET, **kwds):
        res = self.copy()
        res.init(kwds)
        if value is not UNSET:
            res.value = res.datatype(value)
        return res

    def export_value(self):
        return self.datatype.export_value(self.value)

    def for_export(self):
        return dict(self.exportProperties(), readonly=self.readonly)

    def getProperties(self):
        """get also properties of datatype"""
        super_prop = super().getProperties().copy()
        super_prop.update(self.datatype.getProperties())
        return super_prop

    def setProperty(self, key, value):
        """set also properties of datatype"""
        if key in self.propertyDict:
            super().setProperty(key, value)
        else:
            self.datatype.setProperty(key, value)

    def checkProperties(self):
        super().checkProperties()
        self.datatype.checkProperties()


class Command(Accessible):
    """decorator to turn a method into a command

    :param argument: the datatype of the argument or None
    :param result: the datatype of the result or None
    :param inherit: whether properties not given should be inherited
    :param kwds: optional properties
    """

    description = Property(
        'description of the Command', TextType(),
        extname='description', export=True, mandatory=True)
    group = Property(
        'optional command group of the command.', StringType(),
        extname='group', export=True, default='')
    visibility = Property(
        'optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
        extname='visibility', export=True, default=1)
    export = Property(
        '''[internal] export settings

          * False: not accessible via SECoP.
          * True: exported, name automatic.
          * a string: exported with custom name''', OrType(BoolType(), StringType()),
        export=False, default=True)
    optional = Property(
        '[internal] is the command optional to implement? (vs. mandatory)', BoolType(),
        export=False, default=False, settable=False)
    datatype = Property(
        "datatype of the command, auto generated from 'argument' and 'result'",
        DataTypeType(), extname='datainfo', export='always')
    argument = Property(
        'datatype of the argument to the command, or None', NoneOr(DataTypeType()),
        export=False, mandatory=True)
    result = Property(
        'datatype of the result from the command, or None', NoneOr(DataTypeType()),
        export=False, mandatory=True)

    func = None

    def __init__(self, argument=False, *, result=None, inherit=True, **kwds):
        super().__init__(**kwds)
        if result or kwds or isinstance(argument, DataType) or not callable(argument):
            # normal case
            if argument is False and result:
                argument = None
            if argument is not False:
                if isinstance(argument, (tuple, list)):
                    # goodie: treat as TupleOf
                    argument = TupleOf(*argument)
                self.argument = argument
                self.result = result
        else:
            # goodie: allow @Command instead of @Command()
            self.func = argument  # this is the wrapped method!
            if argument.__doc__:
                self.description = inspect.cleandoc(argument.__doc__)
            self.name = self.func.__name__
        self._inherit = inherit  # save for __set_name__

    def __set_name__(self, owner, name):
        self.name = name
        if self.func is None:
            raise ProgrammingError('Command %s.%s must be used as a method decorator' %
                                   (owner.__name__, name))
        if self._inherit:
            self.inherit(Command, owner)

        self.datatype = CommandType(self.argument, self.result)
        if self.export is True:
            predefined_cls = PREDEFINED_ACCESSIBLES.get(name, None)
            if predefined_cls is Command:
                self.export = name
            elif predefined_cls is None:
                self.export = '_' + name
            else:
                raise ProgrammingError('can not use %r as name of a Command' % name)

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        if not self.func:
            raise ProgrammingError('Command %s not properly configured' % self.name)
        return self.func.__get__(obj, owner)

    def __call__(self, func):
        if 'description' not in self.propertyValues and func.__doc__:
            self.description = inspect.cleandoc(func.__doc__)
        self.func = func
        return self

    def copy(self):
        res = Command()
        res.name = self.name
        res.func = self.func
        res.init(self.propertyValues)
        if res.argument:
            res.argument = res.argument.copy()
        if res.result:
            res.result = res.result.copy()
        res.datatype = CommandType(res.argument, res.result)
        return res

    def override(self, value=UNSET, **kwds):
        res = self.copy()
        res.init(kwds)
        if value is not UNSET:
            res.func = value
        return res

    def do(self, module_obj, argument):
        """perform function call

        :param module_obj: the module on which the command is to be executed
        :param argument: the argument from the do command
        :returns: the return value converted to the result type

        - when the argument type is TupleOf, the function is called with multiple arguments
        - when the argument type is StructOf, the function is called with keyworded arguments
        - the validity of the argument/s is/are checked
        """
        func = self.__get__(module_obj)
        if self.argument:
            # validate
            argument = self.argument(argument)
            if isinstance(self.argument, TupleOf):
                res = func(*argument)
            elif isinstance(self.argument, StructOf):
                res = func(**argument)
            else:
                res = func(argument)
        else:
            if argument is not None:
                raise BadValueError('%s.%s takes no arguments' % (module_obj.__class__.__name__, self.name))
            res = func()
        if self.result:
            return self.result(res)
        return None  # silently ignore the result from the method

    def for_export(self):
        return self.exportProperties()

    def __repr__(self):
        result = super().__repr__()
        return result[:-1] + ', %r)' % self.func if self.func else result


# list of predefined accessibles with their type
PREDEFINED_ACCESSIBLES = dict(
    value=Parameter,
    status=Parameter,
    target=Parameter,
    pollinterval=Parameter,
    ramp=Parameter,
    user_ramp=Parameter,
    setpoint=Parameter,
    time_to_target=Parameter,
    unit=Parameter,  # reserved name
    loglevel=Parameter,  # reserved name
    mode=Parameter,  # reserved name
    stop=Command,
    reset=Command,
    go=Command,
    abort=Command,
    shutdown=Command,
    communicate=Command,
)
