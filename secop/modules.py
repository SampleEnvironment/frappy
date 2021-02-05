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
from secop.errors import ConfigError, ProgrammingError, SECoPError, BadValueError,\
    SilentError, InternalError, secop_error
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
    """basic module

    all SECoP modules derive from this.

    :param name: the modules name
    :param logger: a logger instance
    :param cfgdict: the dict from this modules section in the config file
    :param srv: the server instance

    Notes:

    - the programmer normally should not need to reimplement :meth:`__init__`
    - within modules, parameters should only be addressed as ``self.<pname>``, i.e. ``self.value``, ``self.target`` etc...

      - these are accessing the cached version.
      - they can also be written to, generating an async update

    - if you want to 'update from the hardware', call ``self.read_<pname>()`` instead

      - the return value of this method will be used as the new cached value and
        be an async update sent automatically.

    - if you want to 'update the hardware' call ``self.write_<pname>(<new value>)``.

      - The return value of this method will also update the cache.

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

    pollerClass = Poller  #: default poller used

    def __init__(self, name, logger, cfgdict, srv):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = srv.dispatcher
        self.log = logger
        self.name = name
        self.valueCallbacks = {}
        self.errorCallbacks = {}

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
            self.valueCallbacks[pname] = []
            self.errorCallbacks[pname] = []

            if pname in cfgdict:
                if not pobj.readonly and pobj.initwrite is not False:
                    # parameters given in cfgdict have to call write_<pname>
                    # TODO: not sure about readonly (why not a parameter which can only be written from config?)
                    try:
                        pobj.value = pobj.datatype(cfgdict[pname])
                    except BadValueError as e:
                        raise ConfigError('%s.%s: %s' % (name, pname, e))
                    self.writeDict[pname] = pobj.value
            else:
                if pobj.default is None:
                    if pobj.needscfg:
                        raise ConfigError('Parameter %s.%s has no default '
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
                    if pobj.initwrite and not pobj.readonly:
                        # we will need to call write_<pname>
                        # if this is not desired, the default must not be given
                        # TODO: not sure about readonly (why not a parameter which can only be written from config?)
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

    def announceUpdate(self, pname, value=None, err=None, timestamp=None):
        """announce a changed value or readerror"""
        pobj = self.parameters[pname]
        if value is not None:
            pobj.value = value  # store the value even in case of error
        if err:
            if not isinstance(err, SECoPError):
                err = InternalError(err)
            if str(err) == str(pobj.readerror):
                return  # do call updates for repeated errors
        else:
            try:
                pobj.value = pobj.datatype(value)
            except Exception as e:
                err = secop_error(e)
        pobj.timestamp = timestamp or time.time()
        pobj.readerror = err
        if pobj.export:
            self.DISPATCHER.announce_update(self.name, pname, pobj)
        if err:
            callbacks = self.errorCallbacks
            arg = err
        else:
            callbacks = self.valueCallbacks
            arg = value
        cblist = callbacks[pname]
        for cb in cblist:
            try:
                cb(arg)
            except Exception as e:
                # print(formatExtendedTraceback())
                pass

    def registerCallbacks(self, modobj, autoupdate=()):
        for pname in self.parameters:
            errfunc = getattr(modobj, 'error_update_' + pname, None)
            if errfunc:
                def errcb(err, p=pname, efunc=errfunc):
                    try:
                        efunc(err)
                    except Exception as e:
                        modobj.announceUpdate(p, err=e)
                self.errorCallbacks[pname].append(errcb)
            else:
                def errcb(err, p=pname):
                    modobj.announceUpdate(p, err=err)
                if pname in autoupdate:
                    self.errorCallbacks[pname].append(errcb)

            updfunc = getattr(modobj, 'update_' + pname, None)
            if updfunc:
                def cb(value, ufunc=updfunc, efunc=errcb):
                    try:
                        ufunc(value)
                    except Exception as e:
                        efunc(e)
                self.valueCallbacks[pname].append(cb)
            elif pname in autoupdate:
                def cb(value, p=pname):
                    modobj.announceUpdate(p, value)
                self.valueCallbacks[pname].append(cb)


    def isBusy(self, status=None):
        """helper function for treating substates of BUSY correctly"""
        # defined even for non drivable (used for dynamic polling)
        return False

    def earlyInit(self):
        # may be overriden in derived classes to init stuff
        self.log.debug('empty %s.earlyInit()' % self.__class__.__name__)

    def initModule(self):
        self.log.debug('empty %s.initModule()' % self.__class__.__name__)

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

    def writeInitParams(self, started_callback=None):
        """write values for parameters with configured values

        this must be called at the beginning of the poller thread
        with proper error handling
        """
        for pname in list(self.writeDict):
            if pname in self.writeDict:  # this might not be true with handlers
                try:
                    self.log.debug('initialize parameter %s', pname)
                    getattr(self, 'write_' + pname)(self.writeDict.pop(pname))
                except SilentError:
                    pass
                except SECoPError as e:
                    self.log.error(str(e))
                except Exception:
                    self.log.error(formatException())
        if started_callback:
            started_callback()

    def startModule(self, started_callback):
        """runs after init of all modules

        started_callback to be called when the thread spawned by startModule
        has finished its initial work
        might return a timeout value, if different from default
        """
        mkthread(self.writeInitParams, started_callback)


class Readable(Module):
    """basic readable Module"""
    # pylint: disable=invalid-name
    Status = Enum('Status',
                  IDLE = 100,
                  WARN = 200,
                  UNSTABLE = 270,
                  ERROR = 400,
                  DISABLED = 0,
                  UNKNOWN = 401,
                 )  #: status codes
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
            super().startModule(started_callback)

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
        self.writeInitParams()
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
    """basic writable module"""
    parameters = {
        'target': Parameter('target value of the Module',
                            default=0, readonly=False, datatype=FloatRange(),
                           ),
    }


class Drivable(Writable):
    """basic drivable module"""

    Status = Enum(Readable.Status, BUSY=300)  #: status codes

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
        """check for busy, treating substates correctly

        returns True when busy (also when finalizing)
        """
        return 300 <= (status or self.status)[0] < 400

    def isDriving(self, status=None):
        """check for driving, treating status substates correctly

        returns True when busy, but not finalizing
        """
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
    """basic abstract communication module"""

    commands = {
        "communicate": Command("provides the simplest mean to communication",
                            argument=StringType(),
                            result=StringType()
                           ),
    }

    def do_communicate(self, command):
        """communicate command

        :param command: the command to be sent
        :return: the reply
        """
        raise NotImplementedError()


class Attached(Property):
    """a special property, defining an attached modle

    assign a module name to this property in the cfg file,
    and the server will create an attribute with this module

    :param attrname: the name of the to be created attribute. if not given
      the attribute name is the property name prepended by an underscore.
    """
    # we can not put this to properties.py, as it needs datatypes
    def __init__(self, attrname=None):
        self.attrname = attrname
        super().__init__('attached module', StringType())

    def __repr__(self):
        return 'Attached(%s)' % (repr(self.attrname) if self.attrname else '')
