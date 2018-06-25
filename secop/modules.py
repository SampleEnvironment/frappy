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

from secop.lib import formatExtendedStack, mkthread, unset_value
from secop.lib.enum import Enum
from secop.errors import ConfigError
from secop.datatypes import EnumType, TupleOf, StringType, FloatRange, get_datatype
from secop.metaclass import add_metaclass, ModuleMeta
from secop.params import Command, Parameter, Override


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

    def postinit(self):
        self.log.debug('empty postinit()')

    def late_init(self, started_callback):
        '''runs after postinit of all modules

        started_callback to be called when thread spawned by late_init
        or, if not implmemented, immediately
        '''

        self.log.debug('empty late init()')
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

    def late_init(self, started_callback):
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
                print(formatExtendedStack())

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
