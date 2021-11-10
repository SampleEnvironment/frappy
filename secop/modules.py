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
"""Define base classes for real Modules implemented in the server"""


import sys
import time
from collections import OrderedDict

from secop.datatypes import ArrayOf, BoolType, EnumType, FloatRange, \
    IntRange, StatusType, StringType, TextType, TupleOf
from secop.errors import BadValueError, ConfigError, \
    ProgrammingError, SECoPError, SilentError, secop_error
from secop.lib import formatException, mkthread
from secop.lib.enum import Enum
from secop.params import Accessible, Command, Parameter
from secop.poller import BasicPoller, Poller
from secop.properties import HasProperties, Property

Done = object()  #: a special return value for a read/write function indicating that the setter is triggered already


class HasAccessibles(HasProperties):
    """base class of Module

    joining the class's properties, parameters and commands dicts with
    those of base classes.
    wrap read_*/write_* methods
    (so the dispatcher will get notified of changed values)
    """
    @classmethod
    def __init_subclass__(cls):  # pylint: disable=too-many-branches
        super().__init_subclass__()
        # merge accessibles from all sub-classes, treat overrides
        # for now, allow to use also the old syntax (parameters/commands dict)
        accessibles = OrderedDict()  # dict of accessibles
        merged_properties = {}  # dict of dict of merged properties
        new_names = []  # list of names of new accessibles
        override_values = {}  # bare values overriding a parameter and methods overriding a command

        for base in reversed(cls.__mro__):
            for key, value in base.__dict__.items():
                if isinstance(value, Accessible):
                    value.updateProperties(merged_properties.setdefault(key, {}))
                    if base == cls and key not in accessibles:
                        new_names.append(key)
                    accessibles[key] = value
                    override_values.pop(key, None)
                elif key in accessibles:
                    override_values[key] = value
        for aname, aobj in list(accessibles.items()):
            if aname in override_values:
                aobj = aobj.copy()
                value = override_values[aname]
                if value is None:
                    accessibles.pop(aname)
                    continue
                aobj.merge(merged_properties[aname])
                aobj.override(value)
                # replace the bare value by the created accessible
                setattr(cls, aname, aobj)
            else:
                aobj.merge(merged_properties[aname])
            accessibles[aname] = aobj
        # rebuild order: (1) inherited items, (2) items from paramOrder, (3) new accessibles
        # move (2) to the end
        for aname in list(cls.__dict__.get('paramOrder', ())):
            if aname in accessibles:
                accessibles.move_to_end(aname)
                # ignore unknown names
        # move (3) to the end
        for aname in new_names:
            accessibles.move_to_end(aname)
        # note: for python < 3.6 the order of inherited items is not ensured between
        # declarations within the same class
        cls.accessibles = accessibles

        # Correct naming of EnumTypes
        # moved to Parameter.__set_name__

        # check validity of Parameter entries
        for pname, pobj in accessibles.items():
            # XXX: create getters for the units of params ??

            # wrap of reading/writing funcs
            if isinstance(pobj, Command):
                # nothing to do for now
                continue
            rfunc = getattr(cls, 'read_' + pname, None)
            rfunc_handler = pobj.handler.get_read_func(cls, pname) if pobj.handler else None
            wrapped = hasattr(rfunc, '__wrapped__')
            if rfunc_handler:
                if 'read_' + pname in cls.__dict__:
                    if pname in cls.__dict__:
                        raise ProgrammingError("parameter '%s' can not have a handler "
                                               "and read_%s" % (pname, pname))
                    # read_<pname> overwrites inherited handler
                else:
                    rfunc = rfunc_handler
                wrapped = False

            # create wrapper except when read function is already wrapped
            if not wrapped:

                def wrapped_rfunc(self, pname=pname, rfunc=rfunc):
                    if rfunc:
                        self.log.debug("calling %r" % rfunc)
                        try:
                            value = rfunc(self)
                            self.log.debug("rfunc(%s) returned %r" % (pname, value))
                            if value is Done:  # the setter is already triggered
                                return getattr(self, pname)
                        except Exception as e:
                            self.log.debug("rfunc(%s) failed %r" % (pname, e))
                            self.announceUpdate(pname, None, e)
                            raise
                    else:
                        # return cached value
                        self.log.debug("rfunc(%s): return cached value" % pname)
                        value = self.accessibles[pname].value
                    setattr(self, pname, value)  # important! trigger the setter
                    return value

                if rfunc:
                    wrapped_rfunc.__doc__ = rfunc.__doc__
                setattr(cls, 'read_' + pname, wrapped_rfunc)
                wrapped_rfunc.__wrapped__ = True

            if not pobj.readonly:
                wfunc = getattr(cls, 'write_' + pname, None)
                wrapped = hasattr(wfunc, '__wrapped__')
                if (wfunc is None or wrapped) and pobj.handler:
                    # ignore the handler, if a write function is present
                    wfunc = pobj.handler.get_write_func(pname)
                    wrapped = False

                # create wrapper except when write function is already wrapped
                if not wrapped:

                    def wrapped_wfunc(self, value, pname=pname, wfunc=wfunc):
                        self.log.debug("check validity of %s = %r" % (pname, value))
                        pobj = self.accessibles[pname]
                        value = pobj.datatype(value)
                        if wfunc:
                            self.log.debug('calling %s %r(%r)' % (wfunc.__name__, wfunc, value))
                            returned_value = wfunc(self, value)
                            if returned_value is Done:  # the setter is already triggered
                                return getattr(self, pname)
                            if returned_value is not None:  # goodie: accept missing return value
                                value = returned_value
                        setattr(self, pname, value)
                        return value

                    if wfunc:
                        wrapped_wfunc.__doc__ = wfunc.__doc__
                    setattr(cls, 'write_' + pname, wrapped_wfunc)
                    wrapped_wfunc.__wrapped__ = True

        # check information about Command's
        for attrname in cls.__dict__:
            if attrname.startswith('do_'):
                raise ProgrammingError('%r: old style command %r not supported anymore'
                                       % (cls.__name__, attrname))

        res = {}
        # collect info about properties
        for pn, pv in cls.propertyDict.items():
            if pv.settable:
                res[pn] = pv
        # collect info about parameters and their properties
        for param, pobj in cls.accessibles.items():
            res[param] = {}
            for pn, pv in pobj.getProperties().items():
                if pv.settable:
                    res[param][pn] = pv
        cls.configurables = res


class Module(HasAccessibles):
    """basic module

    all SECoP modules derive from this.

    :param name: the modules name
    :param logger: a logger instance
    :param cfgdict: the dict from this modules section in the config file
    :param srv: the server instance

    Notes:

    - the programmer normally should not need to reimplement :meth:`__init__`
    - within modules, parameters should only be addressed as ``self.<pname>``,
      i.e. ``self.value``, ``self.target`` etc...

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
    export = Property('flag if this module is to be exported', BoolType(), default=True, export=False)
    group = Property('optional group the module belongs to', StringType(), default='', extname='group')
    description = Property('description of the module', TextType(), extname='description', mandatory=True)
    meaning = Property('optional meaning indicator', TupleOf(StringType(), IntRange(0, 50)),
                       default=('', 0), extname='meaning')
    visibility = Property('optional visibility hint', EnumType('visibility', user=1, advanced=2, expert=3),
                          default='user', extname='visibility')
    implementation = Property('internal name of the implementation class of the module', StringType(),
                              extname='implementation')
    interface_classes = Property('offical highest interface-class of the module', ArrayOf(StringType()),
                                 extname='interface_classes')

    # properties, parameters and commands are auto-merged upon subclassing
    parameters = {}
    commands = {}

    # reference to the dispatcher (used for sending async updates)
    DISPATCHER = None
    pollerClass = Poller  #: default poller used

    def __init__(self, name, logger, cfgdict, srv):
        # remember the dispatcher object (for the async callbacks)
        self.DISPATCHER = srv.dispatcher
        self.omit_unchanged_within = getattr(self.DISPATCHER, 'omit_unchanged_within', 0.1)
        self.log = logger
        self.name = name
        self.valueCallbacks = {}
        self.errorCallbacks = {}
        errors = []

        # handle module properties
        # 1) make local copies of properties
        super().__init__()

        # 2) check and apply properties specified in cfgdict as
        # '<propertyname> = <propertyvalue>'
        for key in self.propertyDict:
            value = cfgdict.pop(key, None)
            if value is None:
                # legacy cfg: specified as '.<propertyname> = <propertyvalue>'
                value = cfgdict.pop('.' + key, None)
            if value is not None:
                try:
                    self.setProperty(key, value)
                except BadValueError:
                    errors.append('%s: value %r does not match %r!' %
                                  (key, value, self.propertyDict[key].datatype))

        # 3) set automatic properties
        mycls = self.__class__
        myclassname = '%s.%s' % (mycls.__module__, mycls.__name__)
        self.implementation = myclassname
        # list of all 'secop' modules
        # self.interface_classes = [
        #    b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')]
        # list of only the 'highest' secop module class
        self.interface_classes = [
            b.__name__ for b in mycls.__mro__ if b.__module__.startswith('secop.modules')][0:1]

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
            if isinstance(aobj, Parameter):
                # fix default properties poll and needscfg
                if aobj.poll is None:
                    aobj.poll = bool(aobj.handler)
                if aobj.needscfg is None:
                    aobj.needscfg = not aobj.poll

            if not self.export:  # do not export parameters of a module not exported
                aobj.export = False
            if aobj.export:
                accessiblename2attr[aobj.export] = aname
            accessibles[aname] = aobj
        # do not re-use self.accessibles as this is the same for all instances
        self.accessibles = accessibles
        self.accessiblename2attr = accessiblename2attr
        # provide properties to 'filter' out the parameters/commands
        self.parameters = {k: v for k, v in accessibles.items() if isinstance(v, Parameter)}
        self.commands = {k: v for k, v in accessibles.items() if isinstance(v, Command)}

        # 2) check and apply parameter_properties
        #    specified as '<paramname>.<propertyname> = <propertyvalue>'
        for k, v in list(cfgdict.items()):  # keep list() as dict may change during iter
            if '.' in k[1:]:
                paramname, propname = k.split('.', 1)
                propvalue = cfgdict.pop(k)
                paramobj = self.accessibles.get(paramname, None)
                # paramobj might also be a command (not sure if this is needed)
                if paramobj:
                    # no longer needed, this conversion is done by DataTypeType.__call__:
                    # if propname == 'datatype':
                    #     propvalue = get_datatype(propvalue, k)
                    try:
                        paramobj.setProperty(propname, propvalue)
                    except KeyError:
                        errors.append("'%s.%s' does not exist" %
                                      (paramname, propname))
                    except BadValueError as e:
                        errors.append('%s.%s: %s' %
                                      (paramname, propname, str(e)))
                else:
                    errors.append('%r not found' % paramname)

        # 3) check config for problems:
        #    only accept remaining config items specified in parameters
        bad = [k for k in cfgdict if k not in self.parameters]
        if bad:
            errors.append(
                '%s does not exist (use one of %s)' %
                (', '.join(bad), ', '.join(list(self.parameters) +
                                                      list(self.propertyDict))))

        # 4) complain if a Parameter entry has no default value and
        #    is not specified in cfgdict and deal with parameters to be written.
        self.writeDict = {}  # values of parameters to be written
        for pname, pobj in self.parameters.items():
            self.valueCallbacks[pname] = []
            self.errorCallbacks[pname] = []

            if not pobj.hasDatatype():
                errors.append('%s needs a datatype' % pname)
                continue

            if pname in cfgdict:
                if not pobj.readonly and pobj.initwrite is not False:
                    # parameters given in cfgdict have to call write_<pname>
                    # TODO: not sure about readonly (why not a parameter which can only be written from config?)
                    try:
                        pobj.value = pobj.datatype(cfgdict[pname])
                        self.writeDict[pname] = pobj.value
                    except BadValueError as e:
                        errors.append('%s: %s' % (pname, e))
            else:
                if pobj.default is None:
                    if pobj.needscfg:
                        errors.append('%r has no default '
                                      'value and was not given in config!' % pname)
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
                        # this should not happen, as the default is already checked in Parameter
                        raise ProgrammingError('bad default for %s:%s: %s' % (name, pname, e)) from None
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
                if k in self.parameters or k in self.propertyDict:
                    setattr(self, k, v)
                    cfgdict.pop(k)
            except (ValueError, TypeError) as e:
                # self.log.exception(formatExtendedStack())
                errors.append('parameter %s: %s' % (k, e))

        # ensure consistency
        for aobj in self.accessibles.values():
            aobj.finish()

        # Modify units AFTER applying the cfgdict
        for pname, pobj in self.parameters.items():
            dt = pobj.datatype
            if '$' in dt.unit:
                dt.setProperty('unit', dt.unit.replace('$', self.parameters['value'].datatype.unit))

        # 6) check complete configuration of * properties
        if not errors:
            try:
                self.checkProperties()
            except ConfigError as e:
                errors.append(str(e))
            for pname, p in self.parameters.items():
                try:
                    p.checkProperties()
                except ConfigError as e:
                    errors.append('%s: %s' % (pname, e))
        if errors:
            raise ConfigError(errors)

    # helper cfg-editor
    def __iter__(self):
        return self.accessibles.__iter__()

    def __getitem__(self, item):
        return self.accessibles.__getitem__(item)

    def announceUpdate(self, pname, value=None, err=None, timestamp=None):
        """announce a changed value or readerror"""
        pobj = self.parameters[pname]
        timestamp = timestamp or time.time()
        changed = pobj.value != value
        try:
            # store the value even in case of error
            pobj.value = pobj.datatype(value)
        except Exception as e:
            if not err:  # do not overwrite given error
                err = e
        if err:
            err = secop_error(err)
            if str(err) == str(pobj.readerror):
                return  # do call updates for repeated errors
        elif not changed and timestamp < (pobj.timestamp or 0) + self.omit_unchanged_within:
            # no change within short time -> omit
            return
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
            except Exception:
                # print(formatExtendedTraceback())
                pass

    def registerCallbacks(self, modobj, autoupdate=()):
        """register callbacks to another module <modobj>

        - whenever a self.<param> changes:
          <modobj>.update_<param> is called with the new value as argument.
          If this method raises an exception, <modobj>.<param> gets into an error state.
          If the method does not exist and <param> is in autoupdate,
          <modobj>.<param> is updated to self.<param>
        - whenever <self>.<param> gets into an error state:
          <modobj>.error_update_<param> is called with the exception as argument.
          If this method raises an error, <modobj>.<param> gets into an error state.
          If this method does not exist, and <param> is in autoupdate,
          <modobj>.<param> gets into the same error state as self.<param>
        """
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
            getattr(self, 'read_' + pname)()
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
            value = self.writeDict.pop(pname, Done)
            # in the mean time, a poller or handler might already have done it
            if value is not Done:
                try:
                    self.log.debug('initialize parameter %s', pname)
                    getattr(self, 'write_' + pname)(value)
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
    """basic readable module"""
    # pylint: disable=invalid-name
    Status = Enum('Status',
                  IDLE=100,
                  WARN=200,
                  UNSTABLE=270,
                  ERROR=400,
                  DISABLED=0,
                  UNKNOWN=401,
                  )  #: status codes

    value = Parameter('current value of the module', FloatRange(), poll=True)
    status = Parameter('current status of the module', TupleOf(EnumType(Status), StringType()),
                       default=(Status.IDLE, ''), poll=True)
    pollinterval = Parameter('sleeptime between polls', FloatRange(0.1, 120),
                             default=5, readonly=False)

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

    target = Parameter('target value of the module',
                       default=0, readonly=False, datatype=FloatRange(unit='$'))


class Drivable(Writable):
    """basic drivable module"""

    Status = Enum(Readable.Status, BUSY=300)  #: status codes

    status = Parameter(datatype=StatusType(Status))  # override Readable.status

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

    @Command(None, result=None)
    def stop(self):
        """cease driving, go to IDLE state"""


class Communicator(Module):
    """basic abstract communication module"""

    @Command(StringType(), result=StringType())
    def communicate(self, command):
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
        # we can not make it mandatory, as the check in Module.__init__ will be before auto-assign in HasIodev
        super().__init__('attached module', StringType(), mandatory=False)

    def __repr__(self):
        return 'Attached(%s)' % (repr(self.attrname) if self.attrname else '')
