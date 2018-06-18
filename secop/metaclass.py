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

from __future__ import print_function

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

import time

from secop.errors import ProgrammingError
from secop.datatypes import EnumType
from secop.params import Parameter

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
        newtype = type.__new__(mcs, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype

        # merge properties, Parameter and commands from all sub-classes
        for entry in ['properties', 'parameters', 'commands']:
            newentry = {}
            for base in reversed(bases):
                if hasattr(base, entry):
                    newentry.update(getattr(base, entry))
            newentry.update(attrs.get(entry, {}))
            setattr(newtype, entry, newentry)

        # apply Overrides from all sub-classes
        newparams = getattr(newtype, 'parameters')
        for base in reversed(bases):
            overrides = getattr(base, 'overrides', {})
            for n, o in overrides.items():
                newparams[n] = o.apply(newparams[n].copy())
        for n, o in attrs.get('overrides', {}).items():
            newparams[n] = o.apply(newparams[n].copy())

        # Correct naming of EnumTypes
        for k, v in newparams.items():
            if isinstance(v.datatype, EnumType) and not v.datatype._enum.name:
                v.datatype._enum.name = k

        # check validity of Parameter entries
        for pname, pobj in newtype.parameters.items():
            # XXX: allow dicts for overriding certain aspects only.
            if not isinstance(pobj, Parameter):
                raise ProgrammingError('%r: Parameters entry %r should be a '
                                       'Parameter object!' % (name, pname))

            # XXX: create getters for the units of params ??

            # wrap of reading/writing funcs
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
                    value = self.parameters[pname].value
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
                    pobj = self.parameters[pname]
                    value = pobj.datatype.validate(value)
                    if wfunc:
                        self.log.debug('calling %r(%r)' % (wfunc, value))
                        value = wfunc(self, value) or value
                    # XXX: use setattr or direct manipulation
                    # of self.parameters[pname]?
                    setattr(self, pname, value)
                    return value

                if wfunc:
                    wrapped_wfunc.__doc__ = wfunc.__doc__
                if getattr(wfunc, '__wrapped__', False) is False:
                    setattr(newtype, 'write_' + pname, wrapped_wfunc)
                wrapped_wfunc.__wrapped__ = True

            def getter(self, pname=pname):
                return self.parameters[pname].value

            def setter(self, value, pname=pname):
                pobj = self.parameters[pname]
                value = pobj.datatype.validate(value)
                pobj.timestamp = time.time()
                if (not EVENT_ONLY_ON_CHANGED_VALUES) or (value != pobj.value):
                    pobj.value = value
                    # also send notification
                    if self.parameters[pname].export:
                        self.log.debug('%s is now %r' % (pname, value))
                        self.DISPATCHER.announce_update(self, pname, pobj)

            setattr(newtype, pname, property(getter, setter))

        # also collect/update information about Command's
        setattr(newtype, 'commands', getattr(newtype, 'commands', {}))
        for attrname in attrs:
            if attrname.startswith('do_'):
                if attrname[3:] not in newtype.commands:
                    raise ProgrammingError('%r: command %r has to be specified '
                                           'explicitly!' % (name, attrname[3:]))
        attrs['__constructed__'] = True
        return newtype
