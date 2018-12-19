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

from secop.datatypes import CommandType, DataType
from secop.errors import ProgrammingError
from secop.lib import unset_value

EVENT_ONLY_ON_CHANGED_VALUES = False


class CountedObj(object):
    ctr = [0]
    def __init__(self):
        cl = self.__class__.ctr
        cl[0] += 1
        self.ctr = cl[0]


class Accessible(CountedObj):
    '''abstract base class for Parameter and Command'''

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def copy(self):
        # return a copy of ourselfs
        props = self.__dict__.copy()
        props.pop('ctr')
        return type(self)(**props)

    def exported_properties(self):
        res = dict(datatype=self.datatype.export_datatype())
        for key, value in self.__dict__.items():
            if key in self.valid_properties:
                res[self.valid_properties[key]] = value
        return res

    @classmethod
    def add_property(cls, *args, **kwds):
        '''add custom properties

        args: custom properties, exported with leading underscore
        kwds: special cases, where exported name differs from internal

        intention: to be called in secop_<facility>/__init__.py for
        facility specific properties
        '''
        for name in args:
            kwds[name] = '_' + name
        for name, external in kwds.items():
            if name in cls.valid_properties and name != cls.valid_properties[name]:
                raise ProgrammingError('can not overrride property name %s' % name)
            cls.valid_properties[name] = external


class Parameter(Accessible):
    """storage for Parameter settings + value + qualifiers

    if readonly is False, the value can be changed (by code, or remote)
    if no default is given, the parameter MUST be specified in the configfile
    during startup, value is initialized with the default value or
    from the config file if specified there

    poll can be:
    - False  (never poll this parameter)
    - True   (poll this ever pollinterval)
    - positive int  (poll every N(th) pollinterval)
    - negative int  (normally poll every N(th) pollinterval, if module is busy, poll every pollinterval)

    note: Drivable (and derived classes) poll with 10 fold frequency if module is busy....
    """

    # unit and datatype are not listed (handled separately)
    valid_properties = dict()
    for prop in ('description', 'readonly', 'group', 'visibility', 'fmtstr', 'precision'):
        valid_properties[prop] = prop

    def __init__(self,
                 description,
                 datatype=None,
                 default=unset_value,
                 unit='',
                 readonly=True,
                 export=True,
                 poll=False,
                 value=None, # swallow
                 timestamp=None, # swallow
                 optional=False,
                 ctr=None,
                 **kwds):
        super(Parameter, self).__init__()
        if not isinstance(datatype, DataType):
            if issubclass(datatype, DataType):
                # goodie: make an instance from a class (forgotten ()???)
                datatype = datatype()
            else:
                raise ValueError(
                    'datatype MUST be derived from class DataType!')
        self.description = description
        self.datatype = datatype
        self.default = default
        self.unit = unit
        self.readonly = readonly
        self.export = export
        self.optional = optional

        # note: auto-converts True/False to 1/0 which yield the expected
        # behaviour...
        self.poll = int(poll)
        for key in kwds:
            if key not in self.valid_properties:
                raise ProgrammingError('%s is not a valid parameter property' % key)
        self.__dict__.update(kwds)
        # internal caching: value and timestamp of last change...
        self.value = default
        self.timestamp = 0
        if ctr is not None:
            self.ctr = ctr

    def for_export(self):
        # used for serialisation only
        res = self.exported_properties()
        if self.unit:
            res['unit'] = self.unit
        return res

    def export_value(self):
        return self.datatype.export_value(self.value)


class Override(CountedObj):
    """Stores the overrides to be applied to a Parameter

    note: overrides are applied by the metaclass during class creating
    """
    def __init__(self, description="", **kwds):
        super(Override, self).__init__()
        self.kwds = kwds
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
            props = obj.__dict__.copy()
            for key in self.kwds:
                if key not in props and key not in type(obj).valid_properties:
                    raise ProgrammingError( "%s is not a valid %s property" %
                                           (key, type(obj).__name__))
            props.update(self.kwds)
            props['ctr'] = self.ctr
            return type(obj)(**props)
        else:
            raise ProgrammingError(
                "Overrides can only be applied to Accessibles, %r is none!" %
                obj)


class Command(Accessible):
    """storage for Commands settings (description + call signature...)
    """
    # datatype is not listed (handled separately)
    valid_properties = dict()
    for prop in ('description', 'group', 'visibility'):
        valid_properties[prop] = prop

    def __init__(self,
                 description,
                 argument=None,
                 result=None,
                 export=True,
                 optional=False,
                 datatype=None, # swallow datatype argument on copy
                 ctr=None,
                 **kwds):
        super(Command, self).__init__()
        # descriptive text for humans
        self.description = description
        # datatypes for argument/result
        self.argument = argument
        self.result = result
        self.datatype = CommandType(argument, result)
        # whether implementation is optional
        self.optional = optional
        self.export = export
        for key in kwds:
            if key not in self.valid_properties:
                raise ProgrammingError('%s is not a valid command property' % key)
        self.__dict__.update(kwds)
        if ctr is not None:
            self.ctr = ctr

    def for_export(self):
        # used for serialisation only
        return self.exported_properties()

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
