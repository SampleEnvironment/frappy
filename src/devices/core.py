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

import types
import inspect

from errors import ConfigError, ProgrammingError
from protocol import status


# storage for PARAMeter settings:
# if readonly is False, the value can be changed (by code, or remte)
# if no default is given, the parameter MUST be specified in the configfile
# during startup, currentvalue is initialized with the default value or
# from the config file
class PARAM(object):
    def __init__(self, description, validator=None, default=Ellipsis,
                 unit=None, readonly=False, export=True):
        self.description = description
        self.validator = validator
        self.default = default
        self.unit = unit
        self.readonly = readonly
        self.export = export
        # internal caching...
        self.currentvalue = default


# storage for CMDs settings (description + call signature...)
class CMD(object):
    def __init__(self, description, arguments, result):
        # descriptive text for humans
        self.description = description
        # list of validators for arguments
        self.argumenttype = arguments
        # validator for results
        self.resulttype = result


# Meta class
# warning: MAGIC!
class DeviceMeta(type):
    def __new__(mcs, name, bases, attrs):
        newtype = type.__new__(mcs, name, bases, attrs)
        if '__constructed__' in attrs:
            return newtype

        # merge PARAM and CMDS from all sub-classes
        for entry in ['PARAMS', 'CMDS']:
            newentry = {}
            for base in reversed(bases):
                if hasattr(base, entry):
                    newentry.update(getattr(base, entry))
            newentry.update(attrs.get(entry, {}))
            setattr(newtype, entry, newentry)

        # check validity of PARAM entries
        for pname, info in newtype.PARAMS.items():
            if not isinstance(info, PARAM):
                raise ProgrammingError('%r: device PARAM %r should be a '
                                       'PARAM object!' % (name, pname))
            #XXX: greate getters and setters, setters should send async updates

            def getter():
                return self.PARAMS[pname].currentvalue

            def setter(value):
                p = self.PARAMS[pname]
                p.currentvalue = p.validator(value) if p.validator else value
                # also send notification
                self.DISPATCHER.announce_update(self, pname, value)

            attrs[pname] = property(getter, setter)

        # also collect/update information about CMD's
        setattr(newtype, 'CMDS', getattr(newtype, 'CMDS', {}))
        for name in attrs:
            if name.startswith('do'):
                value = getattr(newtype, name)
                if isinstance(value, types.MethodType):
                    argspec = inspect.getargspec(value)
                    if argspec[0] and argspec[0][0] == 'self':
                        del argspec[0][0]
                        newtype.CMDS[name] = CMD(value.get('__doc__', name),
                                                 *argspec)
        attrs['__constructed__'] = True
        return newtype


# Basic device class
class Device(object):
    """Basic Device, doesn't do much"""
    __metaclass__ = DeviceMeta
    # PARAMS and CMDS are auto-merged upon subclassing
    PARAMS = {}
    CMDS = {}
    DISPATCHER = None

    def __init__(self, logger, cfgdict, devname, dispatcher):
        # remember the server object (for the async callbacks)
        self.DISPATCHER = dispatcher
        self.log = logger
        self.name = devname
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
                if v.default is Ellipsis:
                    # Ellipsis is the one single value you can not specify....
                    raise ConfigError('Device %s: Parameter %r has no default '
                                      'value and was not given in config!'
                                      % (self.name, k))
                # assume default value was given
                cfgdict[k] = v.default
        # now 'apply' config:
        # pass values through the validators and store as attributes
        for k, v in cfgdict.items():
            # apply validator, complain if type does not fit
            validator = self.PARAMS[k].validator
            if validator is not None:
                # only check if validator given
                try:
                    v = validator(v)
                except ValueError as e:
                    raise ConfigError('Device %s: config parameter %r:\n%r'
                                      % (self.name, k, e))
            # XXX: with or without prefix?
            setattr(self, k, v)

    def init(self):
        # may be overriden in other classes
        pass


class Readable(Device):
    """Basic readable device

    providing the readonly parameter 'value' and 'status'
    """
    PARAMS = {
        'value': PARAM('current value of the device', readonly=True, default=0.),
        'status': PARAM('current status of the device', default=status.OK,
                        readonly=True),
    }

    def read_value(self, maxage=0):
        raise NotImplementedError

    def read_status(self):
        return status.OK


class Driveable(Readable):
    """Basic Driveable device

    providing a settable 'target' parameter to those of a Readable
    """
    PARAMS = {
        'target': PARAM('target value of the device', default=0.),
    }

    def write_target(self, value):
        raise NotImplementedError
