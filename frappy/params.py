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

from frappy.datatypes import ArrayOf, BoolType, CommandType, DataType, \
    DataTypeType, EnumType, FloatRange, NoneOr, OrType, StringType, StructOf, \
    TextType, TupleOf, ValueType, visibility_validator
from frappy.errors import BadValueError, ProgrammingError, WrongTypeError
from frappy.lib import generalConfig
from frappy.properties import HasProperties, Property

generalConfig.set_default('tolerate_poll_property', False)
generalConfig.set_default('omit_unchanged_within', 0.1)


class Accessible(HasProperties):
    """base class for Parameter and Command

    Inheritance mechanism:

    param.propertyValues contains the properties, which will be used when the
      owner class will be instantiated

    param.ownProperties contains the properties to be used for inheritance
    """

    ownProperties = None
    optional = False

    def init(self, kwds):
        # do not use self.propertyValues.update here, as no invalid values should be
        # assigned to properties, even not before checkProperties
        for k, v in kwds.items():
            self.setProperty(k, v)

    def as_dict(self):
        return self.propertyValues

    def create_from_value(self, properties, value):
        """return a clone with given value and inherited properties"""
        raise NotImplementedError

    def clone(self, properties, **kwds):
        """return a clone of ourselfs with inherited properties"""
        raise NotImplementedError

    def copy(self):
        """return a (deep) copy of ourselfs"""
        return self.clone(self.propertyValues)

    def updateProperties(self, merged_properties):
        """update merged_properties with our own properties"""
        raise NotImplementedError

    def merge(self, merged_properties):
        """merge with inherited properties

        :param merged_properties: dict of properties to be updated
        note: merged_properties may be modified
        """
        raise NotImplementedError

    def finish(self, modobj=None):
        """ensure consistency"""
        raise NotImplementedError

    def for_export(self):
        """prepare for serialisation"""
        raise NotImplementedError

    def hasDatatype(self):
        return 'datatype' in self.propertyValues

    def __repr__(self):
        props = []
        for k, v in sorted(self.propertyValues.items()):
            props.append(f'{k}={v!r}')
        if self.optional:
            props.append('optional=True')
        return f"{self.__class__.__name__}({', '.join(props)})"

    def fixExport(self):
        if self.export is True:
            predefined_cls = PREDEFINED_ACCESSIBLES.get(self.name)
            if predefined_cls is None:
                self.export = '_' + self.name
            elif isinstance(self, predefined_cls):
                self.export = self.name
            else:
                raise ProgrammingError(f'can not use {self.name!r} as name of a {type(self).__name__}')


class Parameter(Accessible):
    """defines a parameter

    :param description: description
    :param datatype: the datatype
    :param inherit: whether properties not given should be inherited
    :param kwds: optional properties

    Usage of 'value' and 'default':

    - if a value is given for a parameter in the config file,  and if the write_<paramname>
      method is given, it is called on startup with this value as argument

    - if a value should be written to the HW on startup, even when not given in the config
      add the value argument to the Parameter definition

    - for parameters which are not polling the HW, either a default should be given
      as a Parameter argument, or, when needscfg is set to True, a configured value is required

    - when default instead of value is given in the cfg file, it is assigne to the parameter
      but not written to the HW

    Please note that in addition to the listed parameter properties, datatype properties
    like ``min``, ``max`` or ``unit`` may be given as keyworded argument.
    """
    # storage for Parameter settings + value + qualifiers

    description = Property(
        'mandatory description of the parameter', TextType(),
        extname='description', mandatory=True, export='always')
    datatype = Property(
        'datatype of the Parameter (SECoP datainfo)', DataTypeType(),
        extname='datainfo', mandatory=True, export='always', default=ValueType())
    readonly = Property(
        'not changeable via SECoP (default True)', BoolType(),
        extname='readonly', default=True, export='always')
    group = Property(
        'optional parameter group this parameter belongs to', StringType(),
        extname='group', default='')
    visibility = Property(
        'optional visibility hint', ValueType(visibility_validator),
        extname='visibility', default='www')
    constant = Property(
        'optional constant value for constant parameters', ValueType(),
        extname='constant', default=None)
    default = Property(
        '''[internal] default (startup) value of this parameter

        if it can not be read from the hardware''', ValueType(),
        export=False, default=None)
    value = Property(
        '''[internal] configured value of this parameter

        if given, write to the hardware''', ValueType(),
        export=False, default=None)
    export = Property(
        '''[internal] export settings

          * False: not accessible via SECoP.
          * True: exported, name automatic.
          * a string: exported with custom name''', OrType(BoolType(), StringType()),
        export=False, default=True)
    needscfg = Property(
        '[internal] needs value in config', NoneOr(BoolType()),
        export=False, default=False)
    update_unchanged = Property(
        '''[internal] updates of unchanged values

        - one of the values 'always', 'never', 'default'
          or the minimum time between updates of equal values [sec]''',
        OrType(FloatRange(0), EnumType(always=0, never=999999999, default=-1)),
        export=False, default=-1)
    influences = Property(
        'optional hint about affected parameters', ArrayOf(StringType()),
        extname='influences', export=True, mandatory=False, default=[])

    # used on the instance copy only
    # value = None
    timestamp = 0
    readerror = None
    omit_unchanged_within = 0

    def __init__(self, description=None, datatype=None, inherit=True, optional=False, **kwds):
        super().__init__()
        self.optional = optional
        if 'poll' in kwds and generalConfig.tolerate_poll_property:
            kwds.pop('poll')
        if datatype is None:
            # collect datatype properties. these are not applied, as we have no datatype
            self.ownProperties = {k: kwds.pop(k) for k in list(kwds) if k not in self.propertyDict}
        else:
            self.ownProperties = {}
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
            if 'value' in kwds:
                self.value = datatype(kwds['value'])

        if description is not None:
            kwds['description'] = inspect.cleandoc(description)

        self.init(kwds)

        if inherit:
            self.ownProperties.update(self.propertyValues)
        else:
            self.ownProperties = {k: getattr(self, k) for k in self.propertyDict}

    def __get__(self, instance, owner):
        if instance is None:
            return self
        try:
            return instance.parameters[self.name].value
        except KeyError:
            raise ProgrammingError(f'optional parameter {self.name} it is not implemented') from None

    def __set__(self, obj, value):
        try:
            obj.announceUpdate(self.name, value)
        except KeyError:
            raise ProgrammingError(f'optional parameter {self.name} it is not implemented') from None

    def __set_name__(self, owner, name):
        self.name = name
        if isinstance(self.datatype, EnumType):
            self.datatype.set_name(name)
        self.fixExport()

    def clone(self, properties, **kwds):
        """return a clone of ourselfs with inherited properties"""
        res = type(self)(**kwds)
        res.name = self.name
        res.init(properties)
        res.init(res.ownProperties)
        if 'datatype' in self.propertyValues:
            res.datatype = res.datatype.copy()
        res.finish()
        return res

    def updateProperties(self, merged_properties):
        """update merged_properties with our own properties"""
        datatype = self.ownProperties.get('datatype')
        if datatype is not None:
            # clear datatype properties, as they are overriden by datatype
            for key in list(merged_properties):
                if key not in self.propertyDict:
                    merged_properties.pop(key)
        merged_properties.update(self.ownProperties)

    def create_from_value(self, properties, value):
        """return a clone with given value and inherited properties

        called when a Parameter is overridden with a bare value
        """
        try:
            value = self.datatype(value)
        except Exception as e:
            raise ProgrammingError(f'{self.name} must be assigned to a Parameter '
                                   f'or a value compatible with {type(self.datatype).__name__}') from e
        return self.clone(properties, value=value)

    def merge(self, merged_properties):
        """merge with inherited properties

        :param merged_properties: dict of properties to be updated
        note: merged_properties may be modified
        """
        datatype = merged_properties.pop('datatype', None)
        if datatype is not None:
            self.datatype = datatype.copy()
        self.init(merged_properties)
        self.finish()

    def finish(self, modobj=None):
        """ensure consistency

        :param modobj: final call, called from Module.__init__
        """
        self.fixExport()
        if self.constant is not None:
            constant = self.datatype(self.constant)
            # The value of the `constant` property should be the
            # serialised version of the constant, or unset
            self.constant = self.datatype.export_value(constant)
            self.readonly = True
        for propname in 'default', 'value':
            if propname in self.propertyValues:
                value = self.propertyValues.pop(propname)
                # fixes in case datatype has changed
                try:
                    self.propertyValues[propname] = self.datatype(value)
                except BadValueError:
                    # clear, if it does not match datatype
                    pass
        if modobj:
            if self.update_unchanged == -1:
                t = modobj.omit_unchanged_within
                self.omit_unchanged_within = generalConfig.omit_unchanged_within if t is None else t
            else:
                self.omit_unchanged_within = float(self.update_unchanged)

    def export_value(self):
        return self.datatype.export_value(self.value)

    def for_export(self):
        return dict(self.exportProperties(), readonly=self.readonly)

    def getProperties(self):
        """get also properties of datatype"""
        super_prop = super().getProperties().copy()
        if self.datatype:
            super_prop.update(self.datatype.getProperties())
        return super_prop

    def setProperty(self, key, value):
        """set also properties of datatype"""
        try:
            if key in self.propertyDict:
                super().setProperty(key, value)
            else:
                try:
                    self.datatype.setProperty(key, value)
                except KeyError:
                    raise ProgrammingError(f'cannot set {key} on parameter with datatype {type(self.datatype).__name__}') from None
        except BadValueError as e:
            raise ProgrammingError(f'property {key}: {str(e)}') from None

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
        extname='description', export='always', mandatory=True)
    group = Property(
        'optional command group of the command.', StringType(),
        extname='group', export=True, default='')
    visibility = Property(
        'optional visibility hint', ValueType(visibility_validator),
        extname='visibility', export=True, default='www')
    export = Property(
        '''[internal] export settings

          * False: not accessible via SECoP.
          * True: exported, name automatic.
          * a string: exported with custom name''', OrType(BoolType(), StringType()),
        export=False, default=True)
    datatype = Property(
        "datatype of the command, auto generated from 'argument' and 'result'",
        DataTypeType(), extname='datainfo', export='always')
    argument = Property(
        'datatype of the argument to the command, or None', NoneOr(DataTypeType()),
        export=False, mandatory=True)
    result = Property(
        'datatype of the result from the command, or None', NoneOr(DataTypeType()),
        export=False, mandatory=True)
    influences = Property(
        'optional hint about affected parameters', ArrayOf(StringType()),
        extname='influences', export=True, mandatory=False, default=[])

    func = None

    def __init__(self, argument=False, *, result=None, inherit=True, optional=False, **kwds):
        super().__init__()
        self.optional = optional
        if 'datatype' in kwds:
            # self.init will complain about invalid keywords except 'datatype', as this is a property
            raise ProgrammingError("Command() got an invalid keyword 'datatype'")
        self.init(kwds)
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
            if argument.__doc__ is not None:
                self.description = inspect.cleandoc(argument.__doc__)
            self.name = self.func.__name__  # this is probably not needed
        self._inherit = inherit  # save for __set_name__
        self.ownProperties = self.propertyValues.copy()

    def __set_name__(self, owner, name):
        self.name = name
        if self.func is None and not self.optional:
            raise ProgrammingError(f'Command {owner.__name__}.{name} must be optional or used as a method decorator')

        self.fixExport()
        self.datatype = CommandType(self.argument, self.result)
        if not self._inherit:
            for key, pobj in self.properties.items():
                if key not in self.propertyValues:
                    self.propertyValues[key] = pobj.default

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        if not self.func:
            raise ProgrammingError(f'Command {self.name} not properly configured') from None
        return self.func.__get__(obj, owner)

    def __call__(self, func):
        """called when used as decorator"""
        if isinstance(self.argument, StructOf):
            # automatically set optional struct members
            sig = inspect.signature(func)
            params = set(sig.parameters.keys())
            params.discard('self')
            members = set(self.argument.members)
            if params != members:
                raise ProgrammingError(f'Command {func.__name__}: Function'
                                       f' argument names do not match struct'
                                       f' members!: {params} != {members}')
            self.argument.optional = [p for p,v in sig.parameters.items()
                   if v.default is not inspect.Parameter.empty]
        if 'description' not in self.ownProperties and func.__doc__ is not None:
            self.description = inspect.cleandoc(func.__doc__)
            self.ownProperties['description'] = self.description
        self.func = func
        return self

    def clone(self, properties, **kwds):
        """return a clone of ourselfs with inherited properties"""
        res = type(self)(**kwds)
        res.name = self.name
        self.fixExport()
        res.func = self.func
        res.init(properties)
        res.init(res.ownProperties)
        if res.argument:
            res.argument = res.argument.copy()
        if res.result:
            res.result = res.result.copy()
        res.finish()
        return res

    def updateProperties(self, merged_properties):
        """update merged_properties with our own properties"""
        merged_properties.update(self.ownProperties)

    def create_from_value(self, properties, value):
        """return a clone with given value and inherited properties

        called when the @Command is missing on a method overriding a command
        """
        if not callable(value):
            raise ProgrammingError(f'{self.name} = {value!r} is overriding a Command')
        return self.clone(properties)(value)

    def merge(self, merged_properties):
        """merge with inherited properties

        :param merged_properties: dict of properties to be updated
        """
        self.init(merged_properties)
        self.finish()

    def finish(self, modobj=None):
        """ensure consistency"""
        self.datatype = CommandType(self.argument, self.result)

    def setProperty(self, key, value):
        """special treatment of datatype"""
        try:
            if key == 'datatype':
                command = DataTypeType()(value)
                super().setProperty('argument', command.argument)
                super().setProperty('result', command.result)
            super().setProperty(key, value)
        except ValueError as e:
            raise ProgrammingError(f'property {key}: {str(e)}') from None

    def do(self, module_obj, argument):
        """perform function call

        :param module_obj: the module on which the command is to be executed
        :param argument: the argument from the do command (transported value!)
        :returns: the return value converted to the result type

        - when the argument type is TupleOf, the function is called with multiple arguments
        - when the argument type is StructOf, the function is called with keyworded arguments
        - the validity of the argument/s is/are checked
        """
        # pylint: disable=unnecessary-dunder-call
        func = self.__get__(module_obj)
        if self.argument:
            if argument is None:
                raise WrongTypeError(
                    f'{module_obj.__class__.__name__}.{self.name} needs an'
                    f' argument of type {self.argument}!'
                )
            # convert transported value to internal value
            argument = self.argument.import_value(argument)
            # verify range
            self.argument.validate(argument)
            if isinstance(self.argument, TupleOf):
                res = func(*argument)
            elif isinstance(self.argument, StructOf):
                res = func(**argument)
            else:
                res = func(argument)
        else:
            if argument is not None:
                raise WrongTypeError(f'{module_obj.__class__.__name__}.{self.name} takes no arguments')
            res = func()
        if self.result:
            return self.result(res)
        return None  # silently ignore the result from the method

    def for_export(self):
        return self.exportProperties()

    def __repr__(self):
        result = super().__repr__()
        return result[:-1] + f', {self.func!r})' if self.func else result


class Limit(Parameter):
    """a special limit parameter"""
    POSTFIXES = {'min', 'max', 'limits'}  # allowed postfixes

    def __set_name__(self, owner, name):
        super().__set_name__(owner, name)
        head, _, postfix = name.rpartition('_')
        if postfix not in self.POSTFIXES:
            raise ProgrammingError(f'Limit name must end with one of {self.POSTFIXES}')
        if 'readonly' not in self.propertyValues:
            self.readonly = False
        if not self.description:
            self.description = f'limit for {head}'
        if self.export.startswith('_') and PREDEFINED_ACCESSIBLES.get(head):
            self.export = self.export[1:]

    def set_datatype(self, datatype):
        if self.hasDatatype():
            return  # the programmer is responsible that a given datatype is correct
        postfix = self.name.rpartition('_')[-1]
        if postfix == 'limits':
            self.datatype = TupleOf(datatype, datatype)
            self.default = (datatype.min, datatype.max)
        else:  # min, max
            self.datatype = datatype
            self.default = getattr(datatype, postfix)


# list of predefined accessibles with their type
# the order of this list affects the parameter order
PREDEFINED_ACCESSIBLES = {
    'value': Parameter,
    'status': Parameter,
    'target': Parameter,
    'pollinterval': Parameter,
    'ramp': Parameter,
    'use_ramp': Parameter,
    'setpoint': Parameter,
    'time_to_target': Parameter,
    'controlled_by': Parameter,
    'control_active': Parameter,
    'unit': Parameter,  # reserved name
    'loglevel': Parameter,  # reserved name
    'mode': Parameter,  # reserved name
    'ctrlpars': Parameter,  # spec to be confirmed
    'stop': Command,
    'reset': Command,
    'go': Command,
    'abort': Command,
    'shutdown': Command,
    'communicate': Command,
}
