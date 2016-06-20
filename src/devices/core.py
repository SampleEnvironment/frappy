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

import types
import inspect

from errors import ConfigError, ProgrammingError
from protocol import status

# storage for CONFIGurable settings (from configfile)
class CONFIG(object):
    def __init__(self, description, validator=None, default=None, unit=None):
        self.description = description
        self.validator = validator
        self.default = default
        self.unit = unit


# storage for PARAMeter settings (changeable during runtime)
class PARAM(object):
    def __init__(self, description, validator=None, default=None, unit=None, readonly=False):
        self.description = description
        self.validator = validator
        self.default = default
        self.unit = unit
        self.readonly = readonly
        # internal caching...
        self.currentvalue = default


# storage for CMDs settings (names + call signature...)
class CMD(object):
    def __init__(self, description, *args):
        self.description = description
        self.arguments = args

# Meta class
# warning: MAGIC!
class DeviceMeta(type):
    def __new__(mcs, name, bases, attrs):
        newtype = type.__new__(mcs, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype
        # merge CONFIG, PARAM, CMDS from all sub-classes
        for entry in ['CONFIG', 'PARAMS', 'CMDS']:
            newentry = {}
            for base in reversed(bases):
                if hasattr(base, entry):
                    newentry.update(getattr(base, entry))
            newentry.update(attrs.get(entry, {}))
            setattr(newtype, entry, newentry)
        # check validity of entries
        for cname, info in newtype.CONFIG.items():
            if not isinstance(info, CONFIG):
                raise ProgrammingError("%r: device CONFIG %r should be a CONFIG object!" %
                                       (name, cname))
            #XXX: greate getters for the config value
        for pname, info in newtype.PARAMS.items():
            if not isinstance(info, PARAM):
                raise ProgrammingError("%r: device PARAM %r should be a PARAM object!" %
                                       (name, pname))
            #XXX: greate getters and setters, setters should send async updates
        # also collect/update information about CMD's
        setattr(newtype, 'CMDS', getattr(newtype, 'CMDS', {}))
        for name in attrs:
            if name.startswith('do'):
                value = getattr(newtype, name)
                if isinstance(value, types.MethodType):
                    argspec = inspect.getargspec(value)
                    if argspec[0] and argspec[0][0] == 'self':
                        del argspec[0][0]
                        newtype.CMDS[name] = CMD(value.get('__doc__', name), *argspec)
        attrs['__constructed__'] = True
        return newtype

# Basic device class
class Device(object):
    """Basic Device, doesn't do much"""
    __metaclass__ = DeviceMeta
    # CONFIG, PARAMS and CMDS are auto-merged upon subclassing
    CONFIG = {}
    PARAMS = {}
    CMDS = {}
    SERVER = None
    def __init__(self, devname, serverobj, logger, cfgdict):
        # remember the server object (for the async callbacks)
        self.SERVER = serverobj
        self.log = logger
        self.name = devname
        # check config for problems
        # only accept config items specified in CONFIG
        for k, v in cfgdict.items():
            if k not in self.CONFIG:
                raise ConfigError('Device %s:config Parameter %r not unterstood!' % (self.name, k))
        # complain if a CONFIG entry has no default value and is not specified in cfgdict
        for k, v in self.CONFIG.items():
            if k not in cfgdict:
                if 'default' not in v:
                    raise ConfigError('Config Parameter %r was not given and not default value exists!' % k)
                cfgdict[k] = v['default'] # assume default value was given.
        # now 'apply' config, passing values through the validators and store as attributes
        for k, v in cfgdict.items():
            # apply validator, complain if type does not fit
            validator = self.CONFIG[k].validator
            if validator is not None:
                # only check if validator given
                try:
                    v = validator(v)
                except ValueError as e:
                    raise ConfigError("Device %s: config paramter %r:\n%r" % (self.name, k, e))
            # XXX: with or without prefix?
            setattr(self, 'config_' + k, v)
        # set default parameter values as inital values
        for k, v in self.PARAMS.items():
            # apply validator, complain if type does not fit
            validator = v.validator
            value = v.default
            if validator is not None:
                # only check if validator given
                value = validator(value)
            setattr(self, k, v)

    def init(self):
        # may be overriden in other classes
        pass


class Readable(Device):
    """Basic readable device, providing the RO parameter 'value' and 'status'"""
    PARAMS = {
        'value' : PARAM('current value of the device', readonly=True),
        'status' : PARAM('current status of the device',
                         readonly=True),
    }
    def read_value(self, maxage=0):
        raise NotImplementedError

    def read_status(self):
        return status.OK


class Driveable(Readable):
    """Basic Driveable device, providing a RW target parameter to those of a Readable"""
    PARAMS = {
        'target' : PARAM('target value of the device'),
    }
    def write_target(self, value):
        raise NotImplementedError

