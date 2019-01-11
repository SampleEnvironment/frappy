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
"""Define Metaclass for Modules/Features"""

from __future__ import division, print_function

import time
from collections import OrderedDict

from secop.datatypes import EnumType
from secop.errors import ProgrammingError
from secop.params import Command, Override, Parameter

try:
    # pylint: disable=unused-import
    from six import add_metaclass # for py2/3 compat
except ImportError:
    # copied from six v1.10.0
    def add_metaclass(metaclass):
        """Class decorator for creating a class with a metaclass."""
        def wrapper(cls):
            orig_vars = cls.__dict__.copy()
            slots = orig_vars.get('__slots__')
            if slots is not None:
                if isinstance(slots, str):
                    slots = [slots]
                for slots_var in slots:
                    orig_vars.pop(slots_var)
            orig_vars.pop('__dict__', None)
            orig_vars.pop('__weakref__', None)
            return metaclass(cls.__name__, cls.__bases__, orig_vars)
        return wrapper



EVENT_ONLY_ON_CHANGED_VALUES = True


# warning: MAGIC!

class ModuleMeta(type):
    """Metaclass

    joining the class's properties, parameters and commands dicts with
    those of base classes.
    also creates getters/setter for parameter access
    and wraps read_*/write_* methods
    (so the dispatcher will get notfied of changed values)
    """
    def __new__(mcs, name, bases, attrs):
        commands = attrs.pop('commands', {})
        parameters = attrs.pop('parameters', {})
        overrides = attrs.pop('overrides', {})

        newtype = type.__new__(mcs, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype

        # merge properties from all sub-classes
        newentry = {}
        for base in reversed(bases):
            newentry.update(getattr(base, "properties", {}))
        newentry.update(attrs.get("properties", {}))
        newtype.properties = newentry

        # merge accessibles from all sub-classes, treat overrides
        # for now, allow to use also the old syntax (parameters/commands dict)
        accessibles_list = []
        for base in reversed(bases):
            if hasattr(base, "accessibles"):
                accessibles_list.append(base.accessibles)
        for accessibles in [attrs.get('accessibles', {}), parameters, commands, overrides]:
            accessibles_list.append(accessibles)
        accessibles = {} # unordered dict of accessibles, will be sorted later
        for accessibles_dict in accessibles_list:
            for key, obj in accessibles_dict.items():
                if isinstance(obj, Override):
                    try:
                        obj = obj.apply(accessibles[key])
                        accessibles[key] = obj
                    except KeyError:
                        raise ProgrammingError("module %s: %s does not exist"
                                       % (name, key))
                else:
                    if key in accessibles:
                        # for now, accept redefinitions:
                        print("WARNING: module %s: %s should not be redefined"
                              % (name, key))
                        # raise ProgrammingError("module %s: %s must not be redefined"
                        #               % (name, key))
                    if isinstance(obj, Parameter):
                        accessibles[key] = obj
                    elif isinstance(obj, Command):
                        # XXX: convert to param with datatype=CommandType???
                        accessibles[key] = obj
                    else:
                        raise ProgrammingError('%r: accessibles entry %r should be a '
                                               'Parameter or Command object!' % (name, key))

        # Correct naming of EnumTypes
        for k, v in accessibles.items():
            if isinstance(v.datatype, EnumType) and not v.datatype._enum.name:
                v.datatype._enum.name = k

        # newtype.accessibles will be used in 2 places only:
        # 1) for inheritance (see above)
        # 2) for the describing message
        newtype.accessibles = OrderedDict(sorted(accessibles.items(), key=lambda item: item[1].ctr))

        # check validity of Parameter entries
        for pname, pobj in newtype.accessibles.items():
            # XXX: create getters for the units of params ??

            # wrap of reading/writing funcs
            if isinstance(pobj, Command):
                # skip commands for now
                continue
            rfunc = attrs.get('read_' + pname, None)
            for base in bases:
                if rfunc is not None:
                    break
                rfunc = getattr(base, 'read_' + pname, None)

            def wrapped_rfunc(self, maxage=0, pname=pname, rfunc=rfunc):
                if rfunc:
                    self.log.debug("rfunc(%s): call %r" % (pname, rfunc))
                    value = rfunc(self, maxage)
                else:
                    # return cached value
                    self.log.debug("rfunc(%s): return cached value" % pname)
                    value = self.accessibles[pname].value
                setattr(self, pname, value)  # important! trigger the setter
                return value

            if rfunc:
                wrapped_rfunc.__doc__ = rfunc.__doc__
            if getattr(rfunc, '__wrapped__', False) is False:
                setattr(newtype, 'read_' + pname, wrapped_rfunc)
            wrapped_rfunc.__wrapped__ = True

            if not pobj.readonly:
                wfunc = attrs.get('write_' + pname, None)
                for base in bases:
                    if wfunc is not None:
                        break
                    wfunc = getattr(base, 'write_' + pname, None)

                def wrapped_wfunc(self, value, pname=pname, wfunc=wfunc):
                    self.log.debug("wfunc(%s): set %r" % (pname, value))
                    pobj = self.accessibles[pname]
                    value = pobj.datatype.validate(value)
                    if wfunc:
                        self.log.debug('calling %r(%r)' % (wfunc, value))
                        returned_value = wfunc(self, value)
                        if returned_value is not None:
                            value = returned_value
                    # XXX: use setattr or direct manipulation
                    # of self.accessibles[pname]?
                    setattr(self, pname, value)
                    return value

                if wfunc:
                    wrapped_wfunc.__doc__ = wfunc.__doc__
                if getattr(wfunc, '__wrapped__', False) is False:
                    setattr(newtype, 'write_' + pname, wrapped_wfunc)
                wrapped_wfunc.__wrapped__ = True

            def getter(self, pname=pname):
                return self.accessibles[pname].value

            def setter(self, value, pname=pname):
                pobj = self.accessibles[pname]
                value = pobj.datatype.validate(value)
                pobj.timestamp = time.time()
                if (not EVENT_ONLY_ON_CHANGED_VALUES) or (value != pobj.value):
                    pobj.value = value
                    # also send notification
                    if self.accessibles[pname].export:
                        self.log.debug('%s is now %r' % (pname, value))
                        self.DISPATCHER.announce_update(self, pname, pobj)

            setattr(newtype, pname, property(getter, setter))

        # check information about Command's
        for attrname in attrs:
            if attrname.startswith('do_'):
                if attrname[3:] not in newtype.accessibles:
                    raise ProgrammingError('%r: command %r has to be specified '
                                           'explicitly!' % (name, attrname[3:]))
        attrs['__constructed__'] = True
        return newtype
