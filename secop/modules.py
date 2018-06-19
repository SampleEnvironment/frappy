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
"""Define Baseclasses for real Modules implemented in the server"""

from __future__ import print_function

# XXX: connect with 'protocol'-Modules.
# Idea: every Module defined herein is also a 'protocol'-Module,
# all others MUST derive from those, the 'interface'-class is still derived
# from these base classes (how to do this?)

import time

try:
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


from secop.lib import formatExtendedStack, mkthread, unset_value
from secop.lib.enum import Enum
from secop.errors import ConfigError, ProgrammingError
from secop.datatypes import DataType, EnumType, TupleOf, StringType, FloatRange, get_datatype


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

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def copy(self):
        # return a copy of ourselfs
        return Parameter(**self.__dict__)

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
    def __init__(self, **kwds):
        super(Override, self).__init__()
        self.kwds = kwds
        self.kwds['ctr'] = self.ctr

    def apply(self, paramobj):
        if isinstance(paramobj, Parameter):
            for k, v in self.kwds.items():
                if hasattr(paramobj, k):
                    setattr(paramobj, k, v)
                    return paramobj
                else:
                    raise ProgrammingError(
                        "Can not apply Override(%s=%r) to %r: non-existing property!" %
                        (k, v, paramobj))
        else:
            raise ProgrammingError(
                "Overrides can only be applied to Parameter's, %r is none!" %
                paramobj)


class Command(CountedObj):
    """storage for Commands settings (description + call signature...)
    """
    def __init__(self, description, arguments=None, result=None, optional=False):
        super(Command, self).__init__()
        # descriptive text for humans
        self.description = description
        # list of datatypes for arguments
        self.arguments = arguments or []
        # datatype for result
        self.resulttype = result
        # whether implementation is optional
        self.optional = optional

    def __repr__(self):
        return '%s_%d(%s)' % (self.__class__.__name__, self.ctr, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def for_export(self):
        # used for serialisation only
        return dict(
            description=self.description,
            arguments=[arg.export_datatype() for arg in self.arguments],
            resulttype=self.resulttype.export_datatype() if self.resulttype else None,
        )


# Meta class
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

        # Check naming of EnumType
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


@add_metaclass(ModuleMeta)
class Module(object):
    """Basic Module

    ALL secop Modules derive from this

    note: within Modules, parameters should only be addressed as self.<pname>
    i.e. self.value, self.target etc...
    these are accessing the cached version.
    they can also be written to (which auto-calls self.write_<pname> and
    generate an async update)

    if you want to 'update from the hardware', call self.read_<pname>() instead
    the return value of this method will be used as the new cached value and
    be an async update sent automatically.
    """
    # static properties, definitions in derived classes should overwrite earlier ones.
    # note: properties don't change after startup and are usually filled
    #       with data from a cfg file...
    # note: so far all properties are STRINGS
    # note: only the properties defined here are allowed to be set in the cfg file
    properties = {
        'group': None,  # some Modules may be grouped together
        'description': "Short description of this Module class and its functionality.",

        'meaning': None,  # XXX: ???
        'priority': None,  # XXX: ???
        'visibility': None,  # XXX: ????
        # what else?
    }
    # properties, parameter and commands are auto-merged upon subclassing
    parameters = {}
    commands = {}

    # reference to the dispatcher (used for sending async updates)
    DISPATCHER = None

    def __init__(self, logger, cfgdict, modname, dispatcher):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = dispatcher
        self.log = logger
        self.name = modname
        # make local copies of parameter objects
        # they need to be individual per instance since we use them also
        # to cache the current value + qualifiers...
        params = {}
        for k, v in list(self.parameters.items()):
            entry = v.copy()
            if '$' in entry.unit:
                entry.unit = entry.unit.replace('$', self.parameters['value'].unit)
            params[k] = entry
        # do not re-use self.parameters as this is the same for all instances
        self.parameters = params

        # make local copies of properties
        props = {}
        for k, v in list(self.properties.items()):
            props[k] = v
        self.properties = props

        # check and apply properties specified in cfgdict
        # moduleproperties are to be specified as
        # '.<propertyname>=<propertyvalue>'
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if k[0] == '.':
                if k[1:] in self.properties:
                    self.properties[k[1:]] = cfgdict.pop(k)
                else:
                    raise ConfigError('Module %r has no property %r' %
                                      (self.name, k[1:]))
        # remove unset (default) module properties
        for k, v in list(self.properties.items()):  # keep list() as dict may change during iter
            if v is None:
                del self.properties[k]

        # MAGIC: derive automatic properties
        mycls = self.__class__
        myclassname = '%s.%s' % (mycls.__module__, mycls.__name__)
        self.properties['_implementation'] = myclassname
        self.properties['interface_class'] = [
            b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')]

        # check and apply parameter_properties
        # specified as '<paramname>.<propertyname> = <propertyvalue>'
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if '.' in k[1:]:
                paramname, propname = k.split('.', 1)
                if paramname in self.parameters:
                    paramobj = self.parameters[paramname]
                    if propname == 'datatype':
                        paramobj.datatype = get_datatype(cfgdict.pop(k))
                    elif hasattr(paramobj, propname):
                        setattr(paramobj, propname, cfgdict.pop(k))

        # check config for problems
        # only accept remaining config items specified in parameters
        for k, v in cfgdict.items():
            if k not in self.parameters:
                raise ConfigError(
                    'Module %s:config Parameter %r '
                    'not unterstood! (use one of %s)' %
                    (self.name, k, ', '.join(self.parameters)))

        # complain if a Parameter entry has no default value and
        # is not specified in cfgdict
        for k, v in self.parameters.items():
            if k not in cfgdict:
                if v.default is unset_value and k != 'value':
                    # unset_value is the one single value you can not specify....
                    raise ConfigError('Module %s: Parameter %r has no default '
                                      'value and was not given in config!' %
                                      (self.name, k))
                # assume default value was given
                cfgdict[k] = v.default

            # replace CLASS level Parameter objects with INSTANCE level ones
            # self.parameters[k] = self.parameters[k].copy() # already done above...

        # now 'apply' config:
        # pass values through the datatypes and store as attributes
        for k, v in cfgdict.items():
            if k == 'value':
                continue
            # apply datatype, complain if type does not fit
            datatype = self.parameters[k].datatype
            try:
                v = datatype.validate(v)
            except (ValueError, TypeError):
                self.log.exception(formatExtendedStack())
                raise
#                    raise ConfigError('Module %s: config parameter %r:\n%r' %
#                                      (self.name, k, e))
            # note: this will call write_* methods which will
            # write to the hardware, if possible!
            setattr(self, k, v)

    def init(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('empty init()')
        mkthread(self.late_init)

    def late_init(self):
        # this runs async somewhen after init
        self.log.debug('late init()')


class Readable(Module):
    """Basic readable Module

    providing the readonly parameter 'value' and 'status'

    Also allow configurable polling per 'pollinterval' parameter.
    """
    # pylint: disable=invalid-name
    Status = Enum('Status',
                  IDLE = 100,
                  WARN = 200,
                  UNSTABLE = 250,
                  ERROR = 400,
                  UNKNOWN = 900,
                 )
    parameters = {
        'value':        Parameter('current value of the Module', readonly=True,
                                  default=0., datatype=FloatRange(),
                                  unit='', poll=True,
                                 ),
        'pollinterval': Parameter('sleeptime between polls', default=5,
                                  readonly=False,
                                  datatype=FloatRange(0.1, 120),
                                 ),
        'status':       Parameter('current status of the Module',
                                  default=(Status.IDLE, ''),
                                  datatype=TupleOf(EnumType(Status), StringType()),
                                  readonly=True, poll=True,
                                 ),
    }

    def init(self):
        Module.init(self)
        self._pollthread = mkthread(self.__pollThread)

    def __pollThread(self):
        try:
            self.__pollThread_inner()
        except Exception as e:
            self.log.exception(e)
            print(formatExtendedStack())

    def __pollThread_inner(self):
        """super simple and super stupid per-module polling thread"""
        i = 0
        while True:
            fastpoll = self.poll(i)
            i += 1
            try:
                time.sleep(self.pollinterval * (0.1 if fastpoll else 1))
            except TypeError:
                time.sleep(min(self.pollinterval)
                           if fastpoll else max(self.pollinterval))

    def poll(self, nr=0):
        # Just poll all parameters regularly where polling is enabled
        for pname, pobj in self.parameters.items():
            if not pobj.poll:
                continue
            if nr % abs(int(pobj.poll)) == 0:
                # poll every 'pobj.poll' iteration
                rfunc = getattr(self, 'read_' + pname, None)
                if rfunc:
                    try:
                        rfunc()
                    except Exception:  # really all!
                        pass


class Writable(Readable):
    """Basic Writable Module

    providing a settable 'target' parameter to those of a Readable
    """
    parameters = {
        'target': Parameter('target value of the Module',
                            default=0., readonly=False, datatype=FloatRange(),
                           ),
    }


class Drivable(Writable):
    """Basic Drivable Module

    provides a stop command to interrupt actions.
    Also status gets extended with a BUSY state indicating a running action.
    """

    Status = Enum(Readable.Status, BUSY=300)

    commands = {
        'stop': Command(
            'cease driving, go to IDLE state',
            arguments=[],
            result=None
        ),
    }

    overrides = {
        'status' : Override(datatype=TupleOf(EnumType(Status), StringType())),
    }

    # improved polling: may poll faster if module is BUSY
    def poll(self, nr=0):
        # poll status first
        stat = self.read_status(0)
        fastpoll = stat[0] == self.Status.BUSY
        for pname, pobj in self.parameters.items():
            if not pobj.poll:
                continue
            if pname == 'status':
                # status was already polled above
                continue
            if ((int(pobj.poll) < 0) and fastpoll) or (
                    nr % abs(int(pobj.poll))) == 0:
                # poll always if pobj.poll is negative and fastpoll (i.e. Module is busy)
                # otherwise poll every 'pobj.poll' iteration
                rfunc = getattr(self, 'read_' + pname, None)
                if rfunc:
                    try:
                        rfunc()
                    except Exception:  # really all!
                        pass
        return fastpoll

    def do_stop(self):
        """default implementation of the stop command

        by default does nothing."""


class Communicator(Module):
    """Basic communication Module

    providing no parameters, but a 'communicate' command.
    """

    commands = {
        "communicate": Command("provides the simplest mean to communication",
                            arguments=[StringType()],
                            result=StringType()
                           ),
    }
