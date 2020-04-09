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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""Define Baseclasses for real Modules implemented in the server"""


import sys
import time
from collections import OrderedDict

from secop.datatypes import EnumType, FloatRange, BoolType, IntRange, \
    StringType, TupleOf, get_datatype, ArrayOf, TextType, StatusType
from secop.errors import ConfigError, ProgrammingError, SECoPError, BadValueError, SilentError
from secop.lib import formatException, formatExtendedStack, mkthread
from secop.lib.enum import Enum
from secop.metaclass import ModuleMeta
from secop.params import PREDEFINED_ACCESSIBLES, Command, Override, Parameter, Parameters, Commands
from secop.properties import HasProperties, Property
from secop.poller import Poller, BasicPoller


# XXX: connect with 'protocol'-Modules.
# Idea: every Module defined herein is also a 'protocol'-Module,
# all others MUST derive from those, the 'interface'-class is still derived
# from these base classes (how to do this?)


class Module(HasProperties, metaclass=ModuleMeta):
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
    # note: only the properties predefined here are allowed to be set in the cfg file
    # note: the names map to a [datatype, value] list, value comes from the cfg file,
    #       datatype is fixed!
    properties = {
        'export':          Property('Flag if this Module is to be exported', BoolType(), default=True, export=False),
        'group':           Property('Optional group the Module belongs to', StringType(), default='', extname='group'),
        'description':     Property('Description of the module', TextType(), extname='description', mandatory=True),
        'meaning':         Property('Optional Meaning indicator', TupleOf(StringType(),IntRange(0,50)),
                                    default=('',0), extname='meaning'),
        'visibility':      Property('Optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
                                    default='user', extname='visibility'),
        'implementation':  Property('Internal name of the implementation class of the module', StringType(),
                                    extname='implementation'),
        'interface_classes': Property('Offical highest Interface-class of the module', ArrayOf(StringType()),
                                    extname='interface_classes'),
        # what else?
    }

    # properties, parameters and commands are auto-merged upon subclassing
    parameters = {}
    commands = {}

    # reference to the dispatcher (used for sending async updates)
    DISPATCHER = None

    pollerClass = Poller

    def __init__(self, name, logger, cfgdict, srv):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = srv.dispatcher
        self.log = logger
        self.name = name

        # handle module properties
        # 1) make local copies of properties
        super(Module, self).__init__()

        # 2) check and apply properties specified in cfgdict
        #    specified as '.<propertyname> = <propertyvalue>'
        #    (this is for legacy config files only)
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if k[0] == '.':
                if k[1:] in self.__class__.properties:
                    self.setProperty(k[1:], cfgdict.pop(k))
                else:
                    raise ConfigError('Module %r has no property %r' %
                                      (self.name, k[1:]))

        # 3) check and apply properties specified in cfgdict as
        #    '<propertyname> = <propertyvalue>' (without '.' prefix)
        for k in self.__class__.properties:
            if k in cfgdict:
                self.setProperty(k, cfgdict.pop(k))

        # 4) set automatic properties
        mycls = self.__class__
        myclassname = '%s.%s' % (mycls.__module__, mycls.__name__)
        self.properties['implementation'] = myclassname
        # list of all 'secop' modules
        self.properties['interface_classes'] = [
            b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')]
        # list of only the 'highest' secop module class
        self.properties['interface_classes'] = [[
            b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')][0]]

        # handle Features
        # XXX: todo

        # handle accessibles
        # 1) make local copies of parameter objects
        #    they need to be individual per instance since we use them also
        #    to cache the current value + qualifiers...
        accessibles = OrderedDict()
        # conversion from exported names to internal attribute names
        accessiblename2attr = {}
        for aname, aobj in self.accessibles.items():
            # make a copy of the Parameter/Command object
            aobj = aobj.copy()
            if isinstance(aobj, Parameter):
                # fix default properties poll and needscfg
                if aobj.poll is None:
                    aobj.properties['poll'] = bool(aobj.handler)
                if aobj.needscfg is None:
                    aobj.properties['needscfg'] = not aobj.poll

            if not self.export:  # do not export parameters of a module not exported
                aobj.properties['export'] = False
            if aobj.export:
                if aobj.export is True:
                    predefined_obj = PREDEFINED_ACCESSIBLES.get(aname, None)
                    if predefined_obj:
                        if isinstance(aobj, predefined_obj):
                            aobj.setProperty('export', aname)
                        else:
                            raise ProgrammingError("can not use '%s' as name of a %s" %
                                  (aname, aobj.__class__.__name__))
                    else: # create custom parameter
                        aobj.setProperty('export', '_' + aname)
                accessiblename2attr[aobj.export] = aname
            accessibles[aname] = aobj
        # do not re-use self.accessibles as this is the same for all instances
        self.accessibles = accessibles
        self.accessiblename2attr = accessiblename2attr
        # provide properties to 'filter' out the parameters/commands
        self.parameters = Parameters((k,v) for k,v in accessibles.items() if isinstance(v, Parameter))
        self.commands = Commands((k,v) for k,v in accessibles.items() if isinstance(v, Command))

        # 2) check and apply parameter_properties
        #    specified as '<paramname>.<propertyname> = <propertyvalue>'
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if '.' in k[1:]:
                paramname, propname = k.split('.', 1)
                paramobj = self.accessibles.get(paramname, None)
                # paramobj might also be a command (not sure if this is needed)
                if paramobj:
                    if propname == 'datatype':
                        paramobj.setProperty('datatype', get_datatype(cfgdict.pop(k), k))
                    elif propname in paramobj.getProperties():
                        paramobj.setProperty(propname, cfgdict.pop(k))
                    else:
                        raise ConfigError('Module %s: Parameter %r has no property %r!' %
                                          (self.name, paramname, propname))

        # 3) check config for problems:
        #    only accept remaining config items specified in parameters
        for k, v in cfgdict.items():
            if k not in self.parameters:
                raise ConfigError(
                    'Module %s:config Parameter %r '
                    'not understood! (use one of %s)' %
                    (self.name, k, ', '.join(list(self.parameters) +
                                             list(self.__class__.properties))))

        # 4) complain if a Parameter entry has no default value and
        #    is not specified in cfgdict and deal with parameters to be written.
        self.writeDict = {}  # values of parameters to be written
        for pname, pobj in self.parameters.items():
            if pname in cfgdict:
                if not pobj.readonly and pobj.initwrite is not False:
                    # parameters given in cfgdict have to call write_<pname>
                    try:
                        pobj.value = pobj.datatype(cfgdict[pname])
                    except BadValueError as e:
                        raise ConfigError('%s.%s: %s' % (name, pname, e))
                    self.writeDict[pname] = pobj.value
            else:
                if pobj.default is None:
                    if pobj.needscfg:
                        raise ConfigError('Module %s: Parameter %r has no default '
                                          'value and was not given in config!' %
                                          (self.name, pname))
                    # we do not want to call the setter for this parameter for now,
                    # this should happen on the first read
                    pobj.readerror = ConfigError('not initialized')
                    # above error will be triggered on activate after startup,
                    # when not all hardware parameters are read because of startup timeout
                    pobj.value = pobj.datatype(pobj.datatype.default)
                else:
                    try:
                        value = pobj.datatype(pobj.default)
                    except BadValueError as e:
                        raise ProgrammingError('bad default for %s.%s: %s'
                                               % (name, pname, e))
                    if pobj.initwrite:
                        # we will need to call write_<pname>
                        # if this is not desired, the default must not be given
                        pobj.value = value
                        self.writeDict[pname] = value
                    else:
                        cfgdict[pname] = value

        # 5) 'apply' config:
        #    pass values through the datatypes and store as attributes
        for k, v in list(cfgdict.items()):
            try:
                # this checks also for the proper datatype
                # note: this will NOT call write_* methods!
                setattr(self, k, v)
            except (ValueError, TypeError):
                self.log.exception(formatExtendedStack())
                raise
                # raise ConfigError('Module %s: config parameter %r:\n%r' %
                #                   (self.name, k, e))
            cfgdict.pop(k)

        # Modify units AFTER applying the cfgdict
        for k, v in self.parameters.items():
            dt = v.datatype
            if '$' in dt.unit:
                dt.setProperty('unit', dt.unit.replace('$', self.parameters['value'].datatype.unit))

        # 6) check complete configuration of * properties
        self.checkProperties()
        for p in self.parameters.values():
            p.checkProperties()

    # helper cfg-editor
    def __iter__(self):
        return self.accessibles.__iter__()

    def __getitem__(self, item):
        return self.accessibles.__getitem__(item)

    def setError(self, pname, exception):
        """sets a parameter to a read error state

        the error will be cleared when the parameter is set
        """
        pobj = self.parameters[pname]
        if pobj.export:
            self.DISPATCHER.announce_update_error(self, pname, pobj, exception)

    def isBusy(self, status=None):
        """helper function for treating substates of BUSY correctly"""
        # defined even for non drivable (used for dynamic polling)
        return False

    def earlyInit(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('empty %s.earlyInit()' % self.__class__.__name__)

    def initModule(self):
        self.log.debug('empty %s.initModule()' % self.__class__.__name__)

    def startModule(self, started_callback):
        """runs after init of all modules

        started_callback to be called when thread spawned by late_init
        or, if not implemented, immediately
        might return a timeout value, if different from default
        """
        self.log.debug('empty %s.startModule()' % self.__class__.__name__)
        started_callback()

    def pollOneParam(self, pname):
        """poll parameter <pname> with proper error handling"""
        try:
            return getattr(self, 'read_' + pname)()
        except SilentError:
            pass
        except SECoPError as e:
            self.log.error(str(e))
        except Exception:
            self.log.error(formatException())

    def writeOrPoll(self, pname):
        """write configured value for a parameter, if any, else poll

        with proper error handling
        """
        try:
            if pname in self.writeDict:
                self.log.debug('write parameter %s', pname)
                getattr(self, 'write_' + pname)(self.writeDict.pop(pname))
            else:
                getattr(self, 'read_' + pname)()
        except SilentError:
            pass
        except SECoPError as e:
            self.log.error(str(e))
        except Exception:
            self.log.error(formatException())


class Readable(Module):
    """Basic readable Module

    providing the readonly parameter 'value' and 'status'

    Also allow configurable polling per 'pollinterval' parameter.
    """
    # pylint: disable=invalid-name
    Status = Enum('Status',
                  IDLE = 100,
                  WARN = 200,
                  UNSTABLE = 270,
                  ERROR = 400,
                  DISABLED = 0,
                  UNKNOWN = 401,
                 )
    parameters = {
        'value':        Parameter('current value of the Module', readonly=True,
                                  datatype=FloatRange(),
                                  poll=True,
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

    def startModule(self, started_callback):
        """start basic polling thread"""
        if self.pollerClass and issubclass(self.pollerClass, BasicPoller):
            # use basic poller for legacy code
            mkthread(self.__pollThread, started_callback)
        else:
            started_callback()

    def __pollThread(self, started_callback):
        while True:
            try:
                self.__pollThread_inner(started_callback)
            except Exception as e:
                self.log.exception(e)
                self.status = (self.Status.ERROR, 'polling thread could not start')
                started_callback()
                print(formatException(0, sys.exc_info(), verbose=True))
                time.sleep(10)

    def __pollThread_inner(self, started_callback):
        """super simple and super stupid per-module polling thread"""
        for pname in list(self.writeDict):
            self.writeOrPoll(pname)
        i = 0
        fastpoll = self.pollParams(i)
        started_callback()
        while True:
            i += 1
            try:
                time.sleep(self.pollinterval * (0.1 if fastpoll else 1))
            except TypeError:
                time.sleep(min(self.pollinterval)
                           if fastpoll else max(self.pollinterval))
            fastpoll = self.pollParams(i)

    def pollParams(self, nr=0):
        # Just poll all parameters regularly where polling is enabled
        for pname, pobj in self.parameters.items():
            if not pobj.poll:
                continue
            if nr % abs(int(pobj.poll)) == 0:
                # pollParams every 'pobj.pollParams' iteration
                self.pollOneParam(pname)
        return False


class Writable(Readable):
    """Basic Writable Module

    providing a settable 'target' parameter to those of a Readable
    """
    parameters = {
        'target': Parameter('target value of the Module',
                            default=0, readonly=False, datatype=FloatRange(),
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
        'status': Override(datatype=StatusType(Status)),
    }

    def isBusy(self, status=None):
        """helper function for treating substates of BUSY correctly"""
        return 300 <= (status or self.status)[0] < 400

    def isDriving(self, status=None):
        """helper function (finalize is busy, not driving)"""
        return 300 <= (status or self.status)[0] < 390

    # improved polling: may poll faster if module is BUSY
    def pollParams(self, nr=0):
        # poll status first
        self.read_status()
        fastpoll = self.isBusy()
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
                self.pollOneParam(pname)
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


class Attached(Property):
    # we can not put this to properties.py, as it needs datatypes
    def __init__(self, attrname=None):
        self.attrname = attrname
        super().__init__('attached module', StringType())

    def __repr__(self):
        return 'Attached(%s)' % (repr(self.attrname) if self.attrname else '')
