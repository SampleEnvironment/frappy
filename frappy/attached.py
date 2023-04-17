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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

from frappy.errors import ConfigError
from frappy.modulebase import Module
from frappy.datatypes import StringType, ValueType
from frappy.properties import Property


class Attached(Property):
    """a special property, defining an attached module

    assign a module name to this property in the cfg file,
    and the server will create an attribute with this module

    When mandatory is set to False, and there is no value or an empty string
    given in the config file, the value of the attribute will be None.
    """
    def __init__(self, basecls=Module, description='attached module', mandatory=True):
        self.basecls = basecls
        super().__init__(description, StringType(), mandatory=mandatory)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        modobj = obj.attachedModules.get(self.name)
        if not modobj:
            modulename = super().__get__(obj, owner)
            if not modulename:
                return None  # happens when mandatory=False and modulename is not given
            modobj = obj.secNode.get_module(modulename)
            if not modobj:
                raise ConfigError(f'attached module {self.name}={modulename!r} '
                                  f'does not exist')
            if not isinstance(modobj, self.basecls):
                raise ConfigError(f'attached module {self.name}={modobj.name!r} '
                                  f'must inherit from {self.basecls.__qualname__!r}')
            obj.attachedModules[self.name] = modobj
        return modobj

    def copy(self):
        return Attached(self.basecls, self.description, self.mandatory)


class DictWithFlag(dict):
    flag = False


class AttachDictType(ValueType):
    """a custom datatype for a dict <key> of names or modules"""
    def __init__(self):
        super().__init__(DictWithFlag)

    def copy(self):
        return AttachDictType()

    def export_value(self, value):
        """export either names or the name attribute

        to treat bare names and modules the same
        """
        return {k: getattr(v, 'name', v) for k, v in value.items()}


class AttachedDict(Property):
    def __init__(self, description='attached modules', elements=None, optional=None, basecls=None,
                 **kwds):
        """a mapping of attached modules

        :param elements: None or a dict <key> of <basecls> for mandatory elements
        :param optional: None or a dict <key> of <basecls> for optional elements
        :param basecls: None or a base class for arbitrary keys
            if not given, only keys given in parameters 'elements' and 'optional' are allowed
        :param description: the property description

        <key> might also be a number or any other immutable
        """
        self.elements = elements or {}
        self.basecls = basecls
        self.baseclasses = {**self.elements, **(optional or {})}
        super().__init__(description, AttachDictType(), default={}, **kwds)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        attach_dict = super().__get__(obj, owner) or DictWithFlag({})
        if attach_dict.flag:
            return attach_dict

        for key, modulename in attach_dict.items():
            basecls = self.baseclasses.get(key, self.basecls)
            if basecls is None:
                raise ConfigError(f'unknown key {key!r} for attached modules {self.name}')
            modobj = obj.secNode.get_module(modulename)
            if modobj is None:
                raise ConfigError(f'attached modules {self.name}: '
                                  f'{key}={modulename!r} does not exist')
            if not isinstance(modobj, basecls):
                raise ConfigError(f'attached modules {self.name}: '
                                  f'module {key}={modulename!r} must inherit '
                                  f'from {basecls.__qualname__!r}')
            obj.attachedModules[self.name, key] = attach_dict[key] = modobj
        missing_keys = set(self.elements) - set(attach_dict)
        if missing_keys:
            raise ConfigError(f'attached modules {self.name}: '
                              f"missing {', '.join(missing_keys)} ")
        attach_dict.flag = True
        return attach_dict

    def copy(self):
        return AttachedDict(self.elements, self.baseclasses, self.basecls, self.description)
