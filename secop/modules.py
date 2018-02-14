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

# XXX: connect with 'protocol'-Modules.
# Idea: every Module defined herein is also a 'protocol'-Module,
# all others MUST derive from those, the 'interface'-class is still derived
# from these base classes (how to do this?)

import time
import types
import inspect

from secop.lib import formatExtendedStack, mkthread
from secop.lib.parsing import format_time
from secop.errors import ConfigError, ProgrammingError
from secop.protocol import status
from secop.datatypes import DataType, EnumType, TupleOf, StringType, FloatRange, get_datatype


EVENT_ONLY_ON_CHANGED_VALUES = False

# storage for Parameter settings:
# if readonly is False, the value can be changed (by code, or remote)
# if no default is given, the parameter MUST be specified in the configfile
# during startup, value is initialized with the default value or
# from the config file if specified there


class Param(object):

    def __init__(self,
                 description,
                 datatype=None,
                 default=Ellipsis,
                 unit=None,
                 readonly=True,
                 export=True,
                 group='',
                 poll=False):
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

        # note: auto-converts True/False to 1/0 which yield the expected
        # behaviour...
        self.poll = int(poll)
        # internal caching: value and timestamp of last change...
        self.value = default
        self.timestamp = 0

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def copy(self):
        # return a copy of ourselfs
        return Param(description=self.description,
                     datatype=self.datatype,
                     default=self.default,
                     unit=self.unit,
                     readonly=self.readonly,
                     export=self.export,
                     group=self.group,
                     poll=self.poll,
                     )

    def as_dict(self, static_only=False):
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
        if not static_only:
            res['value'] = self.value
            if self.timestamp:
                res['timestamp'] = format_time(self.timestamp)
        return res

    def export_value(self):
        return self.datatype.export_value(self.value)


class Override(object):

    def __init__(self, **kwds):
        self.kwds = kwds

    def apply(self, paramobj):
        if isinstance(paramobj, Param):
            for k, v in self.kwds.iteritems():
                if hasattr(paramobj, k):
                    setattr(paramobj, k, v)
                    return paramobj
                else:
                    raise ProgrammingError(
                        "Can not apply Override(%s=%r) to %r: non-existing property!" %
                        (k, v, paramobj))
        else:
            raise ProgrammingError(
                "Overrides can only be applied to Param's, %r is none!" %
                paramobj)


# storage for Commands settings (description + call signature...)
class Command(object):

    def __init__(self, description, arguments=None, result=None):
        # descriptive text for humans
        self.description = description
        # list of datatypes for arguments
        self.arguments = arguments or []
        # datatype for result
        self.resulttype = result

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def as_dict(self):
        # used for serialisation only
        return dict(
            description=self.description,
            arguments=[arg.export_datatype() for arg in self.arguments],
            resulttype=self.resulttype.export_datatype() if self.resulttype else None,
        )


# Meta class
# warning: MAGIC!

class ModuleMeta(type):

    def __new__(mcs, name, bases, attrs):
        newtype = type.__new__(mcs, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype

        # merge properties, Param and commands from all sub-classes
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
            for n, o in overrides.iteritems():
                newparams[n] = o.apply(newparams[n].copy())
        for n, o in attrs.get('overrides', {}).iteritems():
            newparams[n] = o.apply(newparams[n].copy())

        # check validity of Param entries
        for pname, pobj in newtype.parameters.items():
            # XXX: allow dicts for overriding certain aspects only.
            if not isinstance(pobj, Param):
                raise ProgrammingError('%r: Params entry %r should be a '
                                       'Param object!' % (name, pname))

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
                if not EVENT_ONLY_ON_CHANGED_VALUES or (value != pobj.value):
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
                if attrname[3:] in newtype.commands:
                    continue
                value = getattr(newtype, attrname)
                if isinstance(value, types.MethodType):
                    argspec = inspect.getargspec(value)
                    if argspec[0] and argspec[0][0] == 'self':
                        del argspec[0][0]
                        newtype.commands[attrname[3:]] = Command(
                            getattr(value, '__doc__'), argspec.args,
                            None)  # XXX: how to find resulttype?
        attrs['__constructed__'] = True
        return newtype


# Basic module class
#
# within Modules, parameters should only be addressed as self.<pname>
# i.e. self.value, self.target etc...
# these are accesses to the cached version.
# they can also be written to
# (which auto-calls self.write_<pname> and generate an async update)
# if you want to 'update from the hardware', call self.read_<pname>
# the return value of this method will be used as the new cached value and
# be returned.
class Module(object):
    """Basic Module, doesn't do much"""
    __metaclass__ = ModuleMeta
    # static properties, definitions in derived classes should overwrite earlier ones.
    # how to configure some stuff which makes sense to take from configfile???
    properties = {
        'group': None,  # some Modules may be grouped together
        'meaning': None,  # XXX: ???
        'priority': None,  # XXX: ???
        'visibility': None,  # XXX: ????
        'description': "The manufacturer forgot to set a meaningful description. please nag him!",
        # what else?
    }
    # parameter and commands are auto-merged upon subclassing
#    parameters = {
#        'description': Param('short description of this module and its function', datatype=StringType(), default='no specified'),
#    }
    commands = {}
    DISPATCHER = None

    def __init__(self, logger, cfgdict, devname, dispatcher):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = dispatcher
        self.log = logger
        self.name = devname
        # make local copies of parameter
        params = {}
        for k, v in self.parameters.items()[:]:
            params[k] = v.copy()

        self.parameters = params
        # make local copies of properties
        props = {}
        for k, v in self.properties.items()[:]:
            props[k] = v

        self.properties = props

        # check and apply properties specified in cfgdict
        # moduleproperties are to be specified as
        # '.<propertyname>=<propertyvalue>'
        for k, v in cfgdict.items():
            if k[0] == '.':
                if k[1:] in self.properties:
                    self.properties[k[1:]] = v
                    del cfgdict[k]

        # derive automatic properties
        mycls = self.__class__
        myclassname = '%s.%s' % (mycls.__module__, mycls.__name__)
        self.properties['_implementation'] = myclassname
        self.properties['interface_class'] = [
            b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')]
        #self.properties['interface'] = self.properties['interfaces'][0]

        # remove unset (default) module properties
        for k, v in self.properties.items():
            if v is None:
                del self.properties[k]

        # check and apply parameter_properties
        # specified as '<paramname>.<propertyname> = <propertyvalue>'
        for k, v in cfgdict.items()[:]:
            if '.' in k[1:]:
                paramname, propname = k.split('.', 1)
                if paramname in self.parameters:
                    paramobj = self.parameters[paramname]
                    if propname == 'datatype':
                        paramobj.datatype = get_datatype(cfgdict.pop(k))
                    elif hasattr(paramobj, propname):
                        setattr(paramobj, propname, v)
                        del cfgdict[k]

        # check config for problems
        # only accept config items specified in parameters
        for k, v in cfgdict.items():
            if k not in self.parameters:
                raise ConfigError(
                    'Module %s:config Parameter %r '
                    'not unterstood! (use on of %r)' %
                    (self.name, k, self.parameters.keys()))

        # complain if a Param entry has no default value and
        # is not specified in cfgdict
        for k, v in self.parameters.items():
            if k not in cfgdict:
                if v.default is Ellipsis and k != 'value':
                    # Ellipsis is the one single value you can not specify....
                    raise ConfigError('Module %s: Parameter %r has no default '
                                      'value and was not given in config!' %
                                      (self.name, k))
                # assume default value was given
                cfgdict[k] = v.default

            # replace CLASS level Param objects with INSTANCE level ones
            self.parameters[k] = self.parameters[k].copy()

        # now 'apply' config:
        # pass values through the datatypes and store as attributes
        for k, v in cfgdict.items():
            if k == 'value':
                continue
            # apply datatype, complain if type does not fit
            datatype = self.parameters[k].datatype
            if datatype is not None:
                # only check if datatype given
                try:
                    v = datatype.validate(v)
                except (ValueError, TypeError):
                    self.log.exception(formatExtendedStack())
                    raise
#                    raise ConfigError('Module %s: config parameter %r:\n%r' %
#                                      (self.name, k, e))
            setattr(self, k, v)

    def init(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('empty init()')
        mkthread(self.late_init)

    def late_init(self):
        self.log.debug('late init()')


class Readable(Module):
    """Basic readable Module

    providing the readonly parameter 'value' and 'status'
    """
    parameters = {
        'value': Param('current value of the Module', readonly=True, default=0.,
                       datatype=FloatRange(), unit='', poll=True),
        'pollinterval': Param('sleeptime between polls', default=5,
                              readonly=False, datatype=FloatRange(0.1, 120), ),
        'status': Param('current status of the Module', default=(status.OK, ''),
                        datatype=TupleOf(
            EnumType(**{
                'IDLE': status.OK,
                'BUSY': status.BUSY,
                'WARN': status.WARN,
                'UNSTABLE': status.UNSTABLE,
                'ERROR': status.ERROR,
                'UNKNOWN': status.UNKNOWN
            }), StringType()),
            readonly=True, poll=True),
    }

    def init(self):
        Module.init(self)
        self._pollthread = mkthread(self.__pollThread)

    def __pollThread(self):
        """super simple and super stupid per-module polling thread"""
        i = 0
        fastpoll = True  # first update should be quick
        while True:
            i = 1
            try:
                time.sleep(self.pollinterval * (0.1 if fastpoll else 1))
            except TypeError:
                time.sleep(min(self.pollinterval)
                           if fastpoll else max(self.pollinterval))
            fastpoll = self.poll(i)

    def poll(self, nr):
        # poll status first
        fastpoll = False
        if 'status' in self.parameters:
            stat = self.read_status(0)
#            self.log.info('polling read_status -> %r' % (stat,))
            fastpoll = stat[0] == status.BUSY
#        if fastpoll:
#            self.log.info('fastpoll!')
        for pname, pobj in self.parameters.iteritems():
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
                        # self.log.info('polling read_%s -> %r' % (pname, rfunc()))
                        rfunc()
                    except Exception:  # really all!
                        pass
        return fastpoll


class Writable(Readable):
    """Basic Writable Module

    providing a settable 'target' parameter to those of a Readable
    """
    parameters = {
        'target': Param(
            'target value of the Module',
            default=0.,
            readonly=False,
            datatype=FloatRange(),
        ),
    }
    # XXX: commands ???? auto deriving working well enough?


class Drivable(Writable):
    """Basic Drivable Module

    provides a stop command to interrupt actions.
    Also status gets extended with a BUSY state indicating a running action.
    """

    def do_stop(self):
        """default implementation of the stop command

        by default does nothing."""


class Communicator(Module):
    """Basic communication Module

    providing no parameters, but a 'communicate' command.
    """

    commands = {
        "communicate" : Command("provides the simplest mean to communication",
                            arguments=[StringType()],
                            result=StringType()
                           ),
    }
