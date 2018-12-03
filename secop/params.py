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

class Parameter(CountedObj):
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
    def __init__(self,
                 description,
                 datatype=None,
                 default=unset_value,
                 unit='',
                 readonly=True,
                 export=True,
                 group='',
                 poll=False,
                 value=unset_value,
                 timestamp=0,
                 optional=False,
                 ctr=None):
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
        self.group = group
        self.optional = optional

        # note: auto-converts True/False to 1/0 which yield the expected
        # behaviour...
        self.poll = int(poll)
        # internal caching: value and timestamp of last change...
        self.value = default
        self.timestamp = 0
        if ctr is not None:
            self.ctr = ctr

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def copy(self):
        # return a copy of ourselfs
        params = self.__dict__.copy()
        params.pop('ctr')
        return Parameter(**params)

    def for_export(self):
        # used for serialisation only
        res = dict(
            description=self.description,
            readonly=self.readonly,
            datatype=self.datatype.export_datatype(),
        )
        if self.unit:
            res['unit'] = self.unit
        if self.group:
            res['group'] = self.group
        return res

    def export_value(self):
        return self.datatype.export_value(self.value)


class Override(CountedObj):
    """Stores the overrides to ba applied to a Parameter

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

    def apply(self, paramobj):
        if isinstance(paramobj, Parameter):
            props = paramobj.__dict__.copy()
            for k, v in self.kwds.items():
                if k in props:
                    props[k] = v
                else:
                    raise ProgrammingError(
                        "Can not apply Override(%s=%r) to %r: non-existing property!" %
                        (k, v, props))
            props['ctr'] = self.ctr
            return Parameter(**props)
        else:
            raise ProgrammingError(
                "Overrides can only be applied to Parameter's, %r is none!" %
                paramobj)


class Command(CountedObj):
    """storage for Commands settings (description + call signature...)
    """
    def __init__(self, description, argument=None, result=None, export=True, optional=False, datatype=None, ctr=None):
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
        if ctr is not None:
            self.ctr = ctr

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def for_export(self):
        # used for serialisation only

        return dict(
            description=self.description,
            datatype = self.datatype.export_datatype(),
        )

    def copy(self):
        # return a copy of ourselfs
        params = self.__dict__.copy()
        params.pop('ctr')
        return Command(**params)
