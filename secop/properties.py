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
import sys

from secop.errors import BadValueError, ConfigError, ProgrammingError


class HasDescriptorMeta(type):
    def __new__(cls, name, bases, attrs):
        newtype = type.__new__(cls, name, bases, attrs)
        if sys.version_info < (3, 6):
            # support older python versions
            for key, attr in attrs.items():
                if hasattr(attr, '__set_name__'):
                    attr.__set_name__(newtype, key)
            newtype.__init_subclass__()
        return newtype


class HasDescriptors(metaclass=HasDescriptorMeta):
    @classmethod
    def __init_subclass__(cls):
        # when migrating old style declarations, sometimes the trailing comma is not removed
        bad = [k for k, v in cls.__dict__.items()
               if isinstance(v, tuple) and len(v) == 1 and hasattr(v[0], '__set_name__')]
        if bad:
            raise ProgrammingError('misplaced trailing comma after %s.%s' % (cls.__name__, '/'.join(bad)))

    @classmethod
    def filterDescriptors(cls, filter_type):
        res = {}
        for name in dir(cls):
            desc = getattr(cls, name, None)
            if isinstance(desc, filter_type):
                res[name] = desc
        return res


UNSET = object()  # an unset value, not even None


# storage for 'properties of a property'
class Property:
    """base class holding info about a property

    :param description: mandatory
    :param datatype: the datatype to be accepted. not only to the SECoP datatypes are allowed!
         also for example ``ValueType()`` (any type!), ``NoneOr(...)``, etc.
    :param default: a default value. SECoP properties are normally not sent to the ECS,
         when they match the default
    :param extname: external name
    :param export: sent to the ECS when True. defaults to True, when ``extname`` is given.
         special value 'always': export also when matching the default
    :param mandatory: defaults to True, when ``default`` is not given. indicates that it must have a value
       assigned from the cfg file (or, in case of a module property, it may be assigned as a class attribute)
    :param settable: settable from the cfg file
    """

    # note: this is intended to be used on base classes.
    #       the VALUES of the properties are on the instances!
    def __init__(self, description, datatype, default=UNSET, extname='', export=False, mandatory=None,
                 settable=True, value=UNSET, name=''):
        if not callable(datatype):
            raise ValueError('datatype MUST be a valid DataType or a basic_validator')
        self.description = inspect.cleandoc(description)
        self.default = datatype.default if default is UNSET else datatype(default)
        self.datatype = datatype
        self.extname = extname
        self.export = export or bool(extname)
        if mandatory is None:
            mandatory = default is UNSET
        self.mandatory = mandatory
        self.settable = settable or mandatory  # settable means settable from the cfg file
        self.value = UNSET if value is UNSET else datatype(value)
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.propertyValues.get(self.name, self.default)

    def __set__(self, instance, value):
        instance.propertyValues[self.name] = self.datatype(value)

    def __set_name__(self, owner, name):
        self.name = name
        if self.export and not self.extname:
            self.extname = '_' + name

    def __repr__(self):
        extras = ['default=%s' % repr(self.default)]
        if self.export:
            extras.append('extname=%r' % self.extname)
            extras.append('export=%r' % self.export)
        if self.mandatory:
            extras.append('mandatory=True')
        if not self.settable:
            extras.append('settable=False')
        if self.value is not UNSET:
            extras.append('value=%s' % repr(self.value))
        if not self.name:
            extras.append('name=%r' % self.name)
        return 'Property(%r, %s, %s)' % (self.description, self.datatype, ', '.join(extras))


class HasProperties(HasDescriptors):
    propertyValues = None

    def __init__(self):
        super().__init__()
        # store property values in the instance, keep descriptors on the class
        self.propertyValues = {}
        # pre-init
        for pn, po in self.propertyDict.items():
            if po.value is not UNSET:
                self.setProperty(pn, po.value)

    @classmethod
    def __init_subclass__(cls):
        super().__init_subclass__()
        # raise an error when an attribute is a tuple with one single descriptor as element
        # when migrating old style declarations, sometimes the trailing comma is not removed
        bad = [k for k, v in cls.__dict__.items()
               if isinstance(v, tuple) and len(v) == 1 and hasattr(v[0], '__set_name__')]
        if bad:
            raise ProgrammingError('misplaced trailing comma after %s.%s' % (cls.__name__, '/'.join(bad)))
        properties = {}
        for base in cls.__bases__:
            properties.update(getattr(base, 'propertyDict', {}))
        properties.update(cls.filterDescriptors(Property))
        cls.propertyDict = properties
        # treat overriding properties with bare values
        for pn, po in properties.items():
            value = getattr(cls, pn, po)
            if not isinstance(value, Property):  # attribute is a bare value
                po = Property(**po.__dict__)
                try:
                    po.value = po.datatype(value)
                except BadValueError:
                    for base in cls.__bases__:
                        if pn in getattr(base, 'propertyDict', {}):
                            if callable(value):
                                raise ProgrammingError('method %s.%s collides with property of %s' %
                                                       (cls.__name__, pn, base.__name__)) from None
                            raise ProgrammingError('can not set property %s.%s to %r' %
                                                   (cls.__name__, pn, value)) from None
                cls.propertyDict[pn] = po

    def checkProperties(self):
        """validates properties and checks for min... <= max..."""
        for pn, po in self.propertyDict.items():
            if po.mandatory:
                try:
                    self.propertyValues[pn] = po.datatype(self.propertyValues[pn])
                except (KeyError, BadValueError):
                    name = getattr(self, 'name', self.__class__.__name__)
                    raise ConfigError('%s.%s needs a value of type %r!' % (name, pn, po.datatype)) from None
        for pn, po in self.propertyDict.items():
            if pn.startswith('min'):
                maxname = 'max' + pn[3:]
                minval = self.propertyValues.get(pn, po.default)
                maxval = self.propertyValues.get(maxname, minval)
                if minval > maxval:
                    raise ConfigError('%s=%r must be <= %s=%r for %r' % (pn, minval, maxname, maxval, self))

    def getProperties(self):
        return self.propertyDict

    def exportProperties(self):
        # export properties which have
        # export=True and
        # mandatory=True or non_default=True
        res = {}
        for pn, po in self.propertyDict.items():
            val = self.propertyValues.get(pn, po.default)
            if po.export and (po.export == 'always' or val != po.default):
                try:
                    val = po.datatype.export_value(val)
                except AttributeError:
                    pass  # for properties, accept simple datatypes without export_value
                res[po.extname] = val
        return res

    def setProperty(self, key, value):
        # this is overwritten by Param.setProperty and DataType.setProperty
        # in oder to extend setting to inner properties
        # otherwise direct setting of self.<key> = value is preferred
        self.propertyValues[key] = self.propertyDict[key].datatype(value)
