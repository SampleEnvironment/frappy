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

from __future__ import division, print_function

import sys
import time

from secop.datatypes import (EnumType, FloatRange, StringType, TupleOf,
                             get_datatype)
from secop.errors import ConfigError, ProgrammingError
from secop.lib import (formatException, formatExtendedStack, mkthread,
                       unset_value)
from secop.lib.enum import Enum
from secop.metaclass import ModuleMeta, add_metaclass
from secop.params import Command, Override, Parameter, PREDEFINED_ACCESSIBLES

# XXX: connect with 'protocol'-Modules.
# Idea: every Module defined herein is also a 'protocol'-Module,
# all others MUST derive from those, the 'interface'-class is still derived
# from these base classes (how to do this?)


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
        'export': True, # should be exported remotely?
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

    def __init__(self, name, logger, cfgdict, srv):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = srv.dispatcher
        self.log = logger
        self.name = name

        # handle module properties
        # 1) make local copies of properties
        # XXX: self.properties = self.properties.copy() ???
        props = {}
        for k, v in list(self.properties.items()):
            props[k] = v
        self.properties = props

        # 2) check and apply properties specified in cfgdict
        #    specified as '.<propertyname> = <propertyvalue>'
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if k[0] == '.':
                if k[1:] in self.properties:
                    self.properties[k[1:]] = cfgdict.pop(k)
                elif k[1] == '_':
                    self.properties[k[1:]] = cfgdict.pop(k)
                else:
                    raise ConfigError('Module %r has no property %r' %
                                      (self.name, k[1:]))
        # 3) remove unset (default) module properties
        for k, v in list(self.properties.items()):  # keep list() as dict may change during iter
            if v is None:
                del self.properties[k]

        # 4) set automatic properties
        mycls = self.__class__
        myclassname = '%s.%s' % (mycls.__module__, mycls.__name__)
        self.properties['_implementation'] = myclassname
        self.properties['interface_class'] = [[
            b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')][0]]

        # handle Features
        # XXX: todo

        # handle accessibles
        # 1) make local copies of parameter objects
        #    they need to be individual per instance since we use them also
        #    to cache the current value + qualifiers...
        accessibles = {}
        # conversion from exported names to internal attribute names
        accessiblename2attr = {}
        for aname, aobj in self.accessibles.items():
            # make a copy of the Parameter/Command object
            aobj = aobj.copy()
            if aobj.export:
                if aobj.export is True:
                    predefined_obj = PREDEFINED_ACCESSIBLES.get(aname, None)
                    if predefined_obj:
                        if isinstance(aobj, predefined_obj):
                            aobj.export = aname
                        else:
                            raise ProgrammingError("can not use '%s' as name of a %s" %
                                  (aname, aobj.__class__.__name__))
                    else: # create custom parameter
                        aobj.export = '_' + aname
                accessiblename2attr[aobj.export] = aname
            accessibles[aname] = aobj
        # do not re-use self.accessibles as this is the same for all instances
        self.accessibles = accessibles
        self.accessiblename2attr = accessiblename2attr

        # 2) check and apply parameter_properties
        #    specified as '<paramname>.<propertyname> = <propertyvalue>'
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if '.' in k[1:]:
                paramname, propname = k.split('.', 1)
                paramobj = self.accessibles.get(paramname, None)
                if paramobj:
                    if propname == 'datatype':
                        paramobj.datatype = get_datatype(cfgdict.pop(k))
                    elif hasattr(paramobj, propname):
                        setattr(paramobj, propname, cfgdict.pop(k))
                    else:
                        raise ConfigError('Module %s: Parameter %r has no property %r!' %
                                          (self.name, paramname, propname))

        # 3) check config for problems:
        #    only accept remaining config items specified in parameters
        for k, v in cfgdict.items():
            if k not in self.accessibles:
                raise ConfigError(
                    'Module %s:config Parameter %r '
                    'not unterstood! (use one of %s)' %
                    (self.name, k, ', '.join(n for n,o in self.accessibles if isinstance(o, Parameter))))

        # 4) complain if a Parameter entry has no default value and
        #    is not specified in cfgdict
        for k, v in self.accessibles.items():
            if not isinstance(v, Parameter):
                continue
            if k not in cfgdict:
                if v.default is unset_value and k != 'value':
                    # unset_value is the one single value you can not specify....
                    raise ConfigError('Module %s: Parameter %r has no default '
                                      'value and was not given in config!' %
                                      (self.name, k))
                # assume default value was given
                cfgdict[k] = v.default

        # 5) 'apply' config:
        #    pass values through the datatypes and store as attributes
        for k, v in cfgdict.items():
            # apply datatype, complain if type does not fit
            datatype = self.accessibles[k].datatype
            try:
                v = datatype.validate(v)
                self.accessibles[k].default = v
            except (ValueError, TypeError):
                self.log.exception(formatExtendedStack())
                raise
#                    raise ConfigError('Module %s: config parameter %r:\n%r' %
#                                      (self.name, k, e))
            # note: this will call write_* methods which will
            # write to the hardware, if possible!
            if k != u'value':
                setattr(self, k, v)
            cfgdict.pop(k)

        # Adopt units AFTER applying the cfgdict
        for k, v in self.accessibles.items():
            if not isinstance(v, Parameter):
                continue
            if '$' in v.unit:
                v.unit = v.unit.replace('$', self.accessibles['value'].unit)


    def early_init(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('empty early_init()')

    def init_module(self):
        self.log.debug('empty init_module()')

    def start_module(self, started_callback):
        '''runs after init of all modules

        started_callback to be called when thread spawned by late_init
        or, if not implmemented, immediately
        '''

        self.log.debug('empty start_module()')
        started_callback(self)


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
                  DISABLED = 500,
                  UNKNOWN = 0,
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

    def start_module(self, started_callback):
        '''start polling thread'''
        mkthread(self.__pollThread, started_callback)

    def __pollThread(self, started_callback):
        while True:
            try:
                self.__pollThread_inner(started_callback)
            except Exception as e:
                self.log.exception(e)
                self.status = (self.Status.ERROR, 'polling thread could not start')
                started_callback(self)
                print(formatException(0, sys.exc_info(), verbose=True))
                time.sleep(10)

    def __pollThread_inner(self, started_callback):
        """super simple and super stupid per-module polling thread"""
        i = 0
        fastpoll = self.poll(i)
        started_callback(self)
        while True:
            i += 1
            try:
                time.sleep(self.pollinterval * (0.1 if fastpoll else 1))
            except TypeError:
                time.sleep(min(self.pollinterval)
                           if fastpoll else max(self.pollinterval))
            fastpoll = self.poll(i)

    def poll(self, nr=0):
        # Just poll all parameters regularly where polling is enabled
        for pname, pobj in self.accessibles.items():
            if not isinstance(pobj, Parameter):
                continue
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
            argument=None,
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
        for pname, pobj in self.accessibles.items():
            if not isinstance(pobj, Parameter):
                continue
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
                            argument=StringType(),
                            result=StringType()
                           ),
    }
