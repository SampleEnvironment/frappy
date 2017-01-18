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
"""Define Baseclasses for real devices implemented in the server"""

# XXX: connect with 'protocol'-Devices.
# Idea: every Device defined herein is also a 'protocol'-device,
# all others MUST derive from those, the 'interface'-class is still derived
# from these base classes (how to do this?)

import time
import types
import inspect
import threading

from secop.lib.parsing import format_time
from secop.errors import ConfigError, ProgrammingError
from secop.protocol import status
from secop.validators import enum, vector, floatrange, validator_to_str

EVENT_ONLY_ON_CHANGED_VALUES = False

# storage for PARAMeter settings:
# if readonly is False, the value can be changed (by code, or remote)
# if no default is given, the parameter MUST be specified in the configfile
# during startup, value is initialized with the default value or
# from the config file if specified there


class PARAM(object):
    def __init__(self,
                 description,
                 validator=float,
                 default=Ellipsis,
                 unit=None,
                 readonly=True,
                 export=True,
                 group=''):
        if isinstance(description, PARAM):
            # make a copy of a PARAM object
            self.__dict__.update(description.__dict__)
            return
        self.description = description
        self.validator = validator
        self.default = default
        self.unit = unit
        self.readonly = readonly
        self.export = export
        self.group = group
        # internal caching: value and timestamp of last change...
        self.value = default
        self.timestamp = 0

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def as_dict(self, static_only=False):
        # used for serialisation only
        res = dict(
                   description=self.description,
                   readonly=self.readonly,
                   validator=validator_to_str(self.validator),
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


# storage for CMDs settings (description + call signature...)
class CMD(object):
    def __init__(self, description, arguments, result):
        # descriptive text for humans
        self.description = description
        # list of validators for arguments
        self.arguments = arguments
        # validator for result
        self.resulttype = result

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, ', '.join(
            ['%s=%r' % (k, v) for k, v in sorted(self.__dict__.items())]))

    def as_dict(self):
        # used for serialisation only
        return dict(
            description=self.description,
            arguments=repr(self.arguments),
            resulttype=repr(self.resulttype), )

# Meta class
# warning: MAGIC!


class DeviceMeta(type):
    def __new__(mcs, name, bases, attrs):
        newtype = type.__new__(mcs, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype

        # merge PROPERTIES, PARAM and CMDS from all sub-classes
        for entry in ['PROPERTIES', 'PARAMS', 'CMDS']:
            newentry = {}
            for base in reversed(bases):
                if hasattr(base, entry):
                    newentry.update(getattr(base, entry))
            newentry.update(attrs.get(entry, {}))
            setattr(newtype, entry, newentry)

        # check validity of PARAM entries
        for pname, pobj in newtype.PARAMS.items():
            # XXX: allow dicts for overriding certain aspects only.
            if not isinstance(pobj, PARAM):
                raise ProgrammingError('%r: device PARAM %r should be a '
                                       'PARAM object!' % (name, pname))
            # XXX: create getters for the units of params ??
            # wrap of reading/writing funcs
            rfunc = attrs.get('read_' + pname, None)

            def wrapped_rfunc(self, maxage=0, pname=pname, rfunc=rfunc):
                if rfunc:
                    value = rfunc(self, maxage)
                    setattr(self, pname, value)
                    return value
                else:
                    # return cached value
                    return self.PARAMS[pname].value

            if rfunc:
                wrapped_rfunc.__doc__ = rfunc.__doc__
            setattr(newtype, 'read_' + pname, wrapped_rfunc)

            if not pobj.readonly:
                wfunc = attrs.get('write_' + pname, None)

                def wrapped_wfunc(self, value, pname=pname, wfunc=wfunc):
                    self.log.debug("wfunc: set %s to %r" % (pname, value))
                    pobj = self.PARAMS[pname]
                    value = pobj.validator(value) if pobj.validator else value
                    if wfunc:
                        value = wfunc(self, value) or value
                    # XXX: use setattr or direct manipulation
                    # of self.PARAMS[pname]?
                    setattr(self, pname, value)
                    return value

                if wfunc:
                    wrapped_wfunc.__doc__ = wfunc.__doc__
                setattr(newtype, 'write_' + pname, wrapped_wfunc)

            def getter(self, pname=pname):
                return self.PARAMS[pname].value

            def setter(self, value, pname=pname):
                pobj = self.PARAMS[pname]
                value = pobj.validator(value) if pobj.validator else value
                pobj.timestamp = time.time()
                if not EVENT_ONLY_ON_CHANGED_VALUES or (value != pobj.value):
                    pobj.value = value
                    # also send notification
                    self.log.debug('%s is now %r' % (pname, value))
                    self.DISPATCHER.announce_update(self, pname, pobj)

            setattr(newtype, pname, property(getter, setter))

        # also collect/update information about CMD's
        setattr(newtype, 'CMDS', getattr(newtype, 'CMDS', {}))
        for name in attrs:
            if name.startswith('do_'):
                if name[3:] in newtype.CMDS:
                    continue
                value = getattr(newtype, name)
                if isinstance(value, types.MethodType):
                    argspec = inspect.getargspec(value)
                    if argspec[0] and argspec[0][0] == 'self':
                        del argspec[0][0]
                        newtype.CMDS[name[3:]] = CMD(
                            getattr(value, '__doc__'), argspec.args,
                            None)  # XXX: how to find resulttype?
        attrs['__constructed__'] = True
        return newtype


# Basic device class
#
# within devices, parameters should only be addressed as self.<pname>
# i.e. self.value, self.target etc...
# these are accesses to the cached version.
# they can also be written to
# (which auto-calls self.write_<pname> and generate an async update)
# if you want to 'update from the hardware', call self.read_<pname>
# the return value of this method will be used as the new cached value and
# be returned.
class Device(object):
    """Basic Device, doesn't do much"""
    __metaclass__ = DeviceMeta
    # static PROPERTIES, definitions in derived classes should overwrite earlier ones.
    # how to configure some stuff which makes sense to take from configfile???
    PROPERTIES = {
        'group' : None,  # some Modules may be grouped together
        'meaning' : None,  # XXX: ???
        'priority' : None,  # XXX: ???
        'visibility' : None,  # XXX: ????
        # what else?
    }
    # PARAMS and CMDS are auto-merged upon subclassing
    PARAMS = {}
    CMDS = {}
    DISPATCHER = None

    def __init__(self, logger, cfgdict, devname, dispatcher):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = dispatcher
        self.log = logger
        self.name = devname
        # make local copies of PARAMS
        params = {}
        for k, v in self.PARAMS.items()[:]:
            #params[k] = PARAM(v)
            # PARAM: type(v) -> PARAM
            # type(v)(v) -> PARAM(v)
            # EPICS_PARAM: type(v) -> EPICS_PARAM
            # type(v)(v) -> EPICS_PARAM(v)
            param_type = type(v)
            params[k] = param_type(v)

        self.PARAMS = params

        # check and apply properties specified in cfgdict
        # moduleproperties are to be specified as '.<propertyname>=<propertyvalue>'
        for k, v in cfgdict.items():
            if k[0] == '.':
                if k[1:] in self.PROPERTIES:
                    self.PROPERTIES[k[1:]] = v
                    del cfgdict[k]
        # derive automatic properties
        mycls = self.__class__
        myclassname = '%s.%s' % (mycls.__module__, mycls.__name__)
        self.PROPERTIES['implementation'] = myclassname
        self.PROPERTIES['interfaces'] = [b.__name__ for b in mycls.__mro__
                                                    if b.__module__.startswith('secop.devices.core')]
        self.PROPERTIES['interface'] = self.PROPERTIES['interfaces'][0]

        # remove unset (default) module properties
        for k,v in self.PROPERTIES.items():
            if v == None:
                del self.PROPERTIES[k]

        # check and apply parameter_properties
        # specified as '<paramname>.<propertyname> = <propertyvalue>'
        for k,v in cfgdict.items()[:]:
            if '.' in k[1:]:
                paramname, propname = k.split('.', 1)
                if paramname in self.PARAMS:
                    paramobj = self.PARAMS[paramname]
                    if hasattr(paramobj, propname):
                        setattr(paramobj, propname, v)
                        del cfgdict[k]

        # check config for problems
        # only accept config items specified in PARAMS
        for k, v in cfgdict.items():
            if k not in self.PARAMS:
                raise ConfigError('Device %s:config Parameter %r '
                                  'not unterstood!' % (self.name, k))
        # complain if a PARAM entry has no default value and
        # is not specified in cfgdict
        for k, v in self.PARAMS.items():
            if k not in cfgdict:
                if v.default is Ellipsis and k != 'value':
                    # Ellipsis is the one single value you can not specify....
                    raise ConfigError('Device %s: Parameter %r has no default '
                                      'value and was not given in config!' %
                                      (self.name, k))
                # assume default value was given
                cfgdict[k] = v.default

            # replace CLASS level PARAM objects with INSTANCE level ones
            #self.PARAMS[k] = PARAM(self.PARAMS[k])
            param_type = type(self.PARAMS[k])
            self.PARAMS[k] = param_type(self.PARAMS[k])

        # now 'apply' config:
        # pass values through the validators and store as attributes
        for k, v in cfgdict.items():
            # apply validator, complain if type does not fit
            validator = self.PARAMS[k].validator
            if validator is not None:
                # only check if validator given
                try:
                    v = validator(v)
                except (ValueError, TypeError) as e:
                    raise ConfigError('Device %s: config parameter %r:\n%r' %
                                      (self.name, k, e))
            setattr(self, k, v)
        self._requestLock = threading.RLock()

    def init(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('init()')

    def _pollThread(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('init()')


class Readable(Device):
    """Basic readable device

    providing the readonly parameter 'value' and 'status'
    """
    PARAMS = {
        'value': PARAM('current value of the device', readonly=True, default=0.),
        'pollinterval': PARAM('sleeptime between polls', default=5,
                              readonly=False, validator=floatrange(0.1, 120), ),
        'status': PARAM('current status of the device', default=(status.OK, ''),
            validator=vector(
                enum(**{
                    'IDLE': status.OK,
                    'BUSY': status.BUSY,
                    'WARN': status.WARN,
                    'UNSTABLE': status.UNSTABLE,
                    'ERROR': status.ERROR,
                    'UNKNOWN': status.UNKNOWN
                }), str),
            readonly=True),
    }

    def init(self):
        Device.init(self)
        self._pollthread = threading.Thread(target=self._pollThread)
        self._pollthread.daemon = True
        self._pollthread.start()

    def _pollThread(self):
        """super simple and super stupid per-module polling thread"""
        while True:
            time.sleep(self.pollinterval)
            for pname in self.PARAMS:
                if pname != 'pollinterval':
                    rfunc = getattr(self, 'read_%s' % pname, None)
                    if rfunc:
                        rfunc()


class Driveable(Readable):
    """Basic Driveable device

    providing a settable 'target' parameter to those of a Readable
    """
    PARAMS = {
        'target': PARAM('target value of the device', default=0., readonly=False,
                       ),
    }
    # XXX: CMDS ???? auto deriving working well enough?

    def do_start(self):
        """normally does nothing,

        but there may be modules which _start_ the action here
        """

    def do_stop(self):
        """Testing command implementation

        wait a second"""
        time.sleep(1)  # for testing !

    def do_pause(self):
        """if implemented should pause the module
        use start to continue movement
        """