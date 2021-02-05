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


import inspect
from collections import OrderedDict

from secop.errors import ProgrammingError, ConfigError, BadValueError


def flatten_dict(dictname, itemcls, attrs, remove=True):
    properties = {}
    # allow to declare properties directly as class attribute
    # all these attributes are removed
    for k, v in attrs.items():
        if isinstance(v, tuple) and v and isinstance(v[0], itemcls):
            # this might happen when migrating from old to new style
            raise ProgrammingError('declared %r with trailing comma' % k)
        if isinstance(v, itemcls):
            properties[k] = v
    if remove:
        for k in properties:
            attrs.pop(k)
    properties.update(attrs.get(dictname, {}))
    attrs[dictname] = properties


# storage for 'properties of a property'
class Property:
    """base class holding info about a property

    :param description: mandatory
    :param datatype: the datatype to be accepted. not only to the SECoP datatypes are allowed!
         also for example ``ValueType()`` (any type!), ``NoneOr(...)``, etc.
    :param default: a default value. SECoP properties are normally not sent to the ECS,
         when they match the default
    :param extname: external name
    :param export: sent to the ECS when True. defaults to True, when ``extname`` is given
    :param mandatory: defaults to True, when ``default`` is not given. indicates that it must have a value
       assigned from the cfg file (or, in case of a module property, it may be assigned as a class attribute)
    :param settable: settable from the cfg file
    """

    # note: this is intended to be used on base classes.
    #       the VALUES of the properties are on the instances!
    def __init__(self, description, datatype, default=None, extname='', export=False, mandatory=None, settable=True):
        if not callable(datatype):
            raise ValueError('datatype MUST be a valid DataType or a basic_validator')
        self.description = inspect.cleandoc(description)
        self.default = datatype.default if default is None else datatype(default)
        self.datatype = datatype
        self.extname = extname
        self.export = export or bool(extname)
        if mandatory is None:
            mandatory = default is None
        self.mandatory = mandatory
        self.settable = settable or mandatory  # settable means settable from the cfg file

    def __repr__(self):
        return 'Property(%r, %s, default=%r, extname=%r, export=%r, mandatory=%r, settable=%r)' % (
            self.description, self.datatype, self.default, self.extname, self.export,
            self.mandatory, self.settable)


class Properties(OrderedDict):
    """a collection of `Property` objects

    checks values upon assignment.
    You can either assign a Property object, or a value
    (which must pass the validator of the already existing Property)
    """
    def __setitem__(self, key, value):
        if not isinstance(value, Property):
            raise ProgrammingError('setting property %r on classes is not supported!' % key)
        # make sure, extname is valid if export is True
        if not value.extname and value.export:
            value.extname = '_%s' % key  # generate custom key
        elif value.extname and not value.export:
            value.export = True
        OrderedDict.__setitem__(self, key, value)

    def __delitem__(self, key):
        raise ProgrammingError('deleting Properties is not supported!')


class PropertyMeta(type):
    """Metaclass for HasProperties

    joining the class's properties with those of base classes.
    """

    def __new__(cls, name, bases, attrs):
        newtype = type.__new__(cls, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype

        flatten_dict('properties', Property, attrs)
        newtype = cls.__join_properties__(newtype, name, bases, attrs)

        attrs['__constructed__'] = True
        return newtype

    @classmethod
    def __join_properties__(cls, newtype, name, bases, attrs):
        # merge properties from all sub-classes
        properties = Properties()
        for base in reversed(bases):
            properties.update(getattr(base, "properties", {}))
        # update with properties from new class
        properties.update(attrs.get('properties', {}))
        newtype.properties = properties

        # generate getters
        for k, po in properties.items():

            def getter(self, pname=k):
                val = self.__class__.properties[pname].default
                return self.properties.get(pname, val)

            if k in attrs and not isinstance(attrs[k], (property, Property)):
                if callable(attrs[k]):
                    raise ProgrammingError('%r: property %r collides with method'
                                        % (newtype, k))
                # store the attribute value for putting on the instance later
                try:
                    # for inheritance reasons, it seems best to store it as a renamed attribute
                    setattr(newtype, '_initProp_' + k, po.datatype(attrs[k]))
                except BadValueError:
                    raise ProgrammingError('%r: property %r can not be set to %r'
                                            % (newtype, k, attrs[k]))
            setattr(newtype, k, property(getter))
        return newtype


class HasProperties(metaclass=PropertyMeta):
    properties = {}

    def __init__(self):
        super(HasProperties, self).__init__()
        self.initProperties()

    def initProperties(self):
        # store property values in the instance, keep descriptors on the class
        self.properties = {}
        # pre-init with properties default value (if any)
        for pn, po in self.__class__.properties.items():
            value = getattr(self, '_initProp_' + pn, self)
            if value is not self:  # property value was given as attribute
                self.properties[pn] = value
            elif not po.mandatory:
                self.properties[pn] = po.default

    def checkProperties(self):
        """validates properties and checks for min... <= max..."""
        for pn, po in self.__class__.properties.items():
            if po.export and po.mandatory:
                if pn not in self.properties:
                    name = getattr(self, 'name', self.__class__.__name__)
                    raise ConfigError('Property %r of %s needs a value of type %r!' % (pn, name, po.datatype))
                # apply validator (which may complain further)
                self.properties[pn] = po.datatype(self.properties[pn])
        for pn, po in self.__class__.properties.items():
            if pn.startswith('min'):
                maxname = 'max' + pn[3:]
                minval = self.properties[pn]
                maxval = self.properties.get(maxname, minval)
                if minval > maxval:
                    raise ConfigError('%s=%r must be <= %s=%r for %r' % (pn, minval, maxname, maxval, self))


    def getProperties(self):
        return self.__class__.properties

    def exportProperties(self):
        # export properties which have
        # export=True and
        # mandatory=True or non_default=True
        res = {}
        for pn, po in self.__class__.properties.items():
            val = self.properties.get(pn, None)
            if po.export and (po.mandatory or val != po.default):
                try:
                    val = po.datatype.export_value(val)
                except AttributeError:
                    pass # for properties, accept simple datatypes without export_value
                res[po.extname] = val
        return res

    def setProperty(self, key, value):
        self.properties[key] = self.__class__.properties[key].datatype(value)
