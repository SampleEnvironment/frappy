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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
"""Defines the base Module class"""


import time
import threading
from collections import OrderedDict

from frappy.datatypes import ArrayOf, BoolType, FloatRange, IntRange, NoneOr, \
    StringType, TextType, TupleOf, ValueType, visibility_validator

from frappy.errors import BadValueError, CommunicationFailedError, ConfigError, \
    ProgrammingError, SECoPError, secop_error, RangeError
from frappy.lib import formatException, mkthread, UniqueObject
from frappy.params import Accessible, Command, Parameter, Limit, PREDEFINED_ACCESSIBLES
from frappy.properties import HasProperties, Property
from frappy.logging import RemoteLogHandler

# TODO: resolve cirular import
# from .interfaces import SECoP_BASE_CLASSES
# WORKAROUND:
SECoP_BASE_CLASSES = ['Readable', 'Writable', 'Drivable', 'Communicator']
PREDEF_ORDER = list(PREDEFINED_ACCESSIBLES)

Done = UniqueObject('Done')
"""a special return value for a read_<param>/write_<param> method

indicating that the setter is triggered already"""

wrapperClasses = {}


class HasAccessibles(HasProperties):
    """base class of Module

    joining the class's properties, parameters and commands dicts with
    those of base classes.
    wrap read_*/write_* methods
    (so the dispatcher will get notified of changed values)
    """
    isWrapped = False

    @classmethod
    def __init_subclass__(cls):  # pylint: disable=too-many-branches
        super().__init_subclass__()
        if cls.isWrapped:
            return
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
                    if base == cls and key not in accessibles and key not in PREDEFINED_ACCESSIBLES:
                        new_names.append(key)
                    accessibles[key] = value
                    override_values.pop(key, None)
                elif key in accessibles:
                    override_values[key] = value
        # remark: merged_properties contain already the properties of accessibles of cls
        for aname, aobj in list(accessibles.items()):
            if aname in override_values:
                value = override_values[aname]
                if value is None:
                    accessibles.pop(aname)
                    continue
                aobj = aobj.create_from_value(merged_properties[aname], value)
                # replace the bare value by the created accessible
                setattr(cls, aname, aobj)
            else:
                aobj.merge(merged_properties[aname])
            accessibles[aname] = aobj

        # rebuild order:
        # (1) predefined accessibles, in a predefined order, (2) inherited custom items, (3) new custom items
        # move (1) to the beginning
        for key in reversed(PREDEF_ORDER):
            if key in accessibles:
                accessibles.move_to_end(key, last=False)
        # move (3) to the end
        for aname in new_names:
            accessibles.move_to_end(aname)
        cls.accessibles = accessibles

        cls.wrappedAttributes = {'isWrapped': True}
        # create wrappers for access methods
        wrapped_name = '_' + cls.__name__
        for pname, pobj in accessibles.items():
            # wrap of reading/writing funcs
            if not isinstance(pobj, Parameter) or pobj.optional:
                # nothing to do for Commands and optional parameters
                continue

            rname = 'read_' + pname
            rfunc = getattr(cls, rname, None)
            # create wrapper
            if rfunc:

                def new_rfunc(self, pname=pname, rfunc=rfunc):
                    with self.accessLock:
                        try:
                            value = rfunc(self)
                            self.log.debug("read_%s returned %r", pname, value)
                            if value is Done:  # TODO: to be removed when all code using Done is updated
                                return getattr(self, pname)
                            pobj = self.accessibles[pname]
                            value = pobj.datatype(value)
                        except Exception as e:
                            self.log.debug("read_%s failed with %r", pname, e)
                            if isinstance(e, SECoPError):
                                e.raising_methods.append(f'{self.name}.read_{pname}')
                            self.announceUpdate(pname, err=e)
                            raise
                        self.announceUpdate(pname, value, validate=False)
                        return value

                new_rfunc.poll = getattr(rfunc, 'poll', True)
            else:

                def new_rfunc(self, pname=pname):
                    return getattr(self, pname)

                new_rfunc.poll = False

            new_rfunc.__name__ = rname
            new_rfunc.__qualname__ = wrapped_name + '.' + rname
            new_rfunc.__module__ = cls.__module__
            cls.wrappedAttributes[rname] = new_rfunc

            cname = 'check_' + pname
            for postfix in ('_limits', '_min', '_max'):
                limname = pname + postfix
                if limname in accessibles:
                    # find the base class, where the parameter <limname> is defined first.
                    # we have to check all bases, as they may not be treated yet when
                    # not inheriting from HasAccessibles
                    base = next(b for b in reversed(cls.__mro__) if limname in b.__dict__)
                    if cname not in base.__dict__:
                        # there is no check method yet at this class
                        # add check function to the class where the limit was defined
                        setattr(base, cname, lambda self, value, pname=pname: self.checkLimits(value, pname))

            cfuncs = tuple(filter(None, (b.__dict__.get(cname) for b in cls.__mro__)))
            wname = 'write_' + pname
            wfunc = getattr(cls, wname, None)
            if wfunc or not pobj.readonly:
                # allow write method even when parameter is readonly, but internally writable

                def new_wfunc(self, value, pname=pname, wfunc=wfunc, check_funcs=cfuncs):
                    with self.accessLock:
                        self.log.debug('validate %r to datatype of %r', value, pname)
                        validate = self.parameters[pname].datatype.validate
                        try:
                            new_value = validate(value)
                            for c in check_funcs:
                                if c(self, value):
                                    break
                            if wfunc:
                                new_value = wfunc(self, new_value)
                                self.log.debug('write_%s(%r) returned %r', pname, value, new_value)
                                if new_value is Done:  # TODO: to be removed when all code using Done is updated
                                    return getattr(self, pname)
                                new_value = value if new_value is None else validate(new_value)
                        except SECoPError as e:
                            e.raising_methods.append(f'{self.name}.write_{pname}')
                            raise
                        self.announceUpdate(pname, new_value, validate=False)
                        return new_value

                new_wfunc.__name__ = wname
                new_wfunc.__qualname__ = wrapped_name + '.' + wname
                new_wfunc.__module__ = cls.__module__
                cls.wrappedAttributes[wname] = new_wfunc

        # check for programming errors
        for attrname, func in cls.__dict__.items():
            prefix, _, pname = attrname.partition('_')
            if not pname:
                continue
            if prefix == 'do':
                raise ProgrammingError(f'{cls.__name__!r}: old style command {attrname!r} not supported anymore')
            if (prefix in ('read', 'write') and attrname not in cls.wrappedAttributes
                    and not hasattr(func, 'poll')):  # may be a handler, which always has a poll attribute
                raise ProgrammingError(f'{cls.__name__}.{attrname} defined, but {pname!r} is no parameter')

        try:
            # update Status type
            cls.Status = cls.status.datatype.members[0]._enum
        except AttributeError:
            pass
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

    def __new__(cls, *args, **kwds):
        wrapper_class = wrapperClasses.get(cls)
        if wrapper_class is None:
            wrapper_class = type('_' + cls.__name__, (cls,), cls.wrappedAttributes)
            wrapperClasses[cls] = wrapper_class
        return super().__new__(wrapper_class)


class Feature(HasAccessibles):
    """all things belonging to a small, predefined functionality influencing the working of a module

    a mixin with Feature as a direct base class is recognized as a SECoP feature
    and reported in the module property 'features'
    """


class PollInfo:
    def __init__(self, pollinterval, trigger_event):
        self.interval = pollinterval
        self.last_main = 0
        self.last_slow = 0
        self.pending_errors = set()
        self.polled_parameters = []
        self.fast_flag = False
        self.trigger_event = trigger_event

    def trigger(self, immediate=False):
        """trigger a recalculation of poll due times

        :param immediate: when True, doPoll should be called as soon as possible
        """
        if immediate:
            self.last_main = 0
        self.trigger_event.set()

    def update_interval(self, pollinterval):
        if not self.fast_flag:
            self.interval = pollinterval
            self.trigger()


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
    visibility = Property('optional visibility hint', ValueType(visibility_validator),
                          default='www', extname='visibility')
    implementation = Property('internal name of the implementation class of the module', StringType(),
                              extname='implementation')
    interface_classes = Property('offical highest interface-class of the module', ArrayOf(StringType()),
                                 extname='interface_classes')
    features = Property('list of features', ArrayOf(StringType()), extname='features')
    pollinterval = Property('poll interval for parameters handled by doPoll', FloatRange(0.1, 120), default=5)
    slowinterval = Property('poll interval for other parameters', FloatRange(0.1, 120), default=15)
    omit_unchanged_within = Property('default for minimum time between updates of unchanged values',
                                     NoneOr(FloatRange(0)), export=False, default=None)
    original_id = Property('original equipment_id\n\ngiven only if different from equipment_id of node',
                           NoneOr(StringType()), default=None, export=True)  # exported as custom property _original_id
    enablePoll = True

    pollInfo = None
    triggerPoll = None  # trigger event for polls. used on io modules and modules without io
    __poller = None  # the poller thread, if used

    def __init__(self, name, logger, cfgdict, srv):
        # remember the secnode for interacting with other modules and the
        # server
        self.secNode = srv.secnode
        self.log = logger
        self.name = name
        self.paramCallbacks = {}
        self.earlyInitDone = False
        self.initModuleDone = False
        self.startModuleDone = False
        self.remoteLogHandler = None
        self.accessLock = threading.RLock()  # for read_* / write_* methods
        self.updateLock = threading.RLock()  # for announceUpdate
        self.polledModules = []  # modules polled by thread started in self.startModules
        self.attachedModules = {}
        self.errors = []
        self._isinitialized = False
        self.updateCallback = srv.dispatcher.announce_update

        # handle module properties
        # 1) make local copies of properties
        super().__init__()

        # conversion from exported names to internal attribute names
        self.accessiblename2attr = {}
        self.writeDict = {}  # values of parameters to be written
        # properties, parameters and commands are auto-merged upon subclassing
        self.parameters = {}
        self.commands = {}

        # 2) check and apply properties specified in cfgdict as
        # '<propertyname> = <propertyvalue>'
        # pylint: disable=consider-using-dict-items
        for key in self.propertyDict:
            value = cfgdict.pop(key, None)
            if value is not None:
                try:
                    if isinstance(value, dict):
                        self.setProperty(key, value['value'])
                    else:
                        self.setProperty(key, value)
                except BadValueError:
                    self.errors.append(f'{key}: value {value!r} does not match {self.propertyDict[key].datatype!r}!')

        # 3) set automatic properties
        mycls, = self.__class__.__bases__  # skip the wrapper class
        myclassname = f'{mycls.__module__}.{mycls.__name__}'
        self.implementation = myclassname

        # list of only the 'highest' secop module class
        self.interface_classes = [
            b.__name__ for b in mycls.__mro__ if b.__name__ in SECoP_BASE_CLASSES][:1]

        # handle Features
        self.features = [b.__name__ for b in mycls.__mro__ if Feature in b.__bases__]

        # handle accessibles
        # 1) make local copies of parameter objects
        #    they need to be individual per instance since we use them also
        #    to cache the current value + qualifiers...
        # do not re-use self.accessibles as this is the same for all instances
        accessibles = self.accessibles
        self.accessibles = {}
        for aname, aobj in accessibles.items():
            if aobj.optional:
                continue
            # make a copy of the Parameter/Command object
            aobj = aobj.copy()
            acfg = cfgdict.pop(aname, None)
            self._add_accessible(aname, aobj, cfg=acfg)

        # 3) complain about names not found as accessible or property names
        if cfgdict:
            self.errors.append(
                f"{', '.join(cfgdict.keys())} does not exist (use one of"
                f" {', '.join(list(self.accessibles) + list(self.propertyDict))})")

        # 5) ensure consistency of all accessibles added here
        for aobj in self.accessibles.values():
            aobj.finish(self)

        # Modify units AFTER applying the cfgdict
        mainvalue = self.parameters.get('value')
        if mainvalue:
            mainunit = mainvalue.datatype.unit
            if mainunit:
                self.applyMainUnit(mainunit)

        # 6) check complete configuration of * properties
        if not self.errors:
            try:
                self.checkProperties()
            except ConfigError as e:
                self.errors.append(str(e))
            for aname, aobj in self.accessibles.items():
                try:
                    aobj.checkProperties()
                except (ConfigError, ProgrammingError) as e:
                    self.errors.append(f'{aname}: {e}')
        if self.errors:
            raise ConfigError(self.errors)

    # helper cfg-editor
    def __iter__(self):
        return self.accessibles.__iter__()

    def __getitem__(self, item):
        return self.accessibles.__getitem__(item)

    def applyMainUnit(self, mainunit):
        """replace $ in units of parameters by mainunit"""
        for pobj in self.parameters.values():
            pobj.datatype.set_main_unit(mainunit)

    def _add_accessible(self, name, accessible, cfg=None):
        if self.startModuleDone:
            raise ProgrammingError('Accessibles can only be added before startModule()!')
        if not self.export:  # do not export parameters of a module not exported
            accessible.export = False
        self.accessibles[name] = accessible
        if accessible.export:
            self.accessiblename2attr[accessible.export] = name
        if isinstance(accessible, Parameter):
            self.parameters[name] = accessible
        if isinstance(accessible, Command):
            self.commands[name] = accessible
        if cfg is not None:
            try:
                # apply datatype first
                datatype = cfg.pop('datatype', None)
                if datatype is not None:
                    accessible.setProperty('datatype', datatype)
                for propname, propvalue in cfg.items():
                    if propname in {'value', 'default', 'constant'}:
                        # these properties have ValueType(), but should be checked for datatype
                        accessible.datatype(cfg[propname])
                    accessible.setProperty(propname, propvalue)
            except KeyError:
                self.errors.append(f"'{name}' has no property '{propname}'")
            except BadValueError as e:
                self.errors.append(f'{name}.{propname}: {str(e)}')
        if isinstance(accessible, Parameter):
            self._handle_writes(name, accessible)

    def _handle_writes(self, pname, pobj):
        """ register value for writing, if given
        apply default when no value is given (in cfg or as Parameter argument)
        or complain, when cfg is needed
        """
        self.paramCallbacks[pname] = []
        if isinstance(pobj, Limit):
            basepname = pname.rpartition('_')[0]
            baseparam = self.parameters.get(basepname)
            if not baseparam:
                self.errors.append(f'limit {pname!r} is given, but not {basepname!r}')
                return
            if baseparam.datatype is None:
                return  # an error will be reported on baseparam
            pobj.set_datatype(baseparam.datatype)
        if not pobj.hasDatatype():
            self.errors.append(f'{pname} needs a datatype')
            return
        if pobj.value is None:
            if pobj.needscfg:
                self.errors.append(f'{pname!r} has no default value and was not given in config!')
            if pobj.default is None:
                # we do not want to call the setter for this parameter for now,
                # this should happen on the first read
                pobj.readerror = ConfigError(f'parameter {pname!r} not initialized')
                # above error will be triggered on activate after startup,
                # when not all hardware parameters are read because of startup timeout
                pobj.default = pobj.datatype.default
            pobj.value = pobj.default
        else:
            # value given explicitly, either by cfg or as Parameter argument
            pobj.given = True  # for PersistentMixin
            if hasattr(self, 'write_' + pname):
                self.writeDict[pname] = pobj.value
            if pobj.default is None:
                pobj.default = pobj.value
            # this checks again for datatype and sets the timestamp
            setattr(self, pname, pobj.value)

    def announceUpdate(self, pname, value=None, err=None, timestamp=None, validate=True):
        """announce a changed value or readerror

        :param pname: parameter name
        :param value: new value or None in case of error
        :param err: None or an exception
        :param timestamp: a timestamp or None for taking current time
        :param validate: True: convert to datatype, in case of error store in readerror
        :return:

        when err=None and validate=False, the value must already be converted to the datatype
        """

        with self.updateLock:
            pobj = self.parameters[pname]
            timestamp = timestamp or time.time()
            changed = False
            if not err:
                try:
                    if validate:
                        value = pobj.datatype(value)
                except Exception as e:
                    err = e
                else:
                    changed = pobj.value != value or pobj.readerror
                    # store the value even in case of error
                    pobj.value = value
            if err:
                if secop_error(err) == pobj.readerror:
                    err.report_error = False
                    return  # no updates for repeated errors
                err = secop_error(err)
                value_err = value, err
            else:
                if not changed and timestamp < (pobj.timestamp or 0) + pobj.omit_unchanged_within:
                    # no change within short time -> omit
                    return
                value_err = (value,)
            pobj.timestamp = timestamp or time.time()
            pobj.readerror = err
            for cbfunc, cbargs in self.paramCallbacks[pname]:
                try:
                    cbfunc(*cbargs, *value_err)
                except Exception:
                    pass
            if pobj.export:
                self.updateCallback(self, pobj)

    def addCallback(self, pname, callback_function, *args):
        self.paramCallbacks[pname].append((callback_function, args))

    def registerCallbacks(self, modobj, autoupdate=()):
        """register callbacks to another module <modobj>

        whenever a self.<param> changes or changes its error state:
        <modobj>.update_param(<value> [, <exc>]) is called,
        where <value> is the new value and <exc> is given only in case of error.
        if the method does not exist, and <param> is in autoupdate
        <modobj>.announceUpdate(<pname>, <value>, <exc>) is called
        with <exc> being None in case of no error.

        Remark: when <modobj>.update_<param> does not accept the <exc> argument,
        nothing happens (the callback is catched by try / except).
        Any exceptions raised by the callback function are silently ignored.
        """
        autoupdate = set(autoupdate)
        for pname in self.parameters:
            cbfunc = getattr(modobj, 'update_' + pname, None)
            if cbfunc:
                self.addCallback(pname, cbfunc)
            elif pname in autoupdate:
                self.addCallback(pname, modobj.announceUpdate, pname)

    def isBusy(self, status=None):
        """helper function for treating substates of BUSY correctly"""
        # defined even for non drivable (used for dynamic polling)
        return False

    def earlyInit(self):
        """initialise module with stuff to be done before all modules are created"""
        self.earlyInitDone = True

    def initModule(self):
        """initialise module with stuff to be done after all modules are created"""
        self.initModuleDone = True
        if self.enablePoll or self.writeDict:
            # enablePoll == False: we still need the poll thread for writing values from writeDict
            if hasattr(self, 'io'):
                self.io.polledModules.append(self)
                if not self.io.triggerPoll:
                    # when self.io.enablePoll is False, triggerPoll is not
                    # created for self.io in the else clause below
                    self.io.triggerPoll = threading.Event()
            else:
                self.triggerPoll = threading.Event()
                self.polledModules.append(self)

    def startModule(self, start_events):
        """runs after init of all modules

        when a thread is started, a trigger function may signal that it
        has finished its initial work
        start_events.get_trigger(<timeout>) creates such a trigger and
        registers it in the server for waiting
        <timeout> defaults to 30 seconds
        """
        # we do not need self.errors any longer. should we delete it?
        # del self.errors
        if self.polledModules:
            self.__poller = mkthread(self.__pollThread, self.polledModules, start_events.get_trigger())
        self.startModuleDone = True

    def initialReads(self):
        """initial reads to be done

        override to read initial values from HW, when it is not desired
        to poll them afterwards

        called from the poll thread, after writeInitParams but before
        all parameters are polled once
        """

    def stopPollThread(self):
        """trigger the poll thread to stop

        this is called on shutdown
        """
        if self.__poller:
            self.polledModules.clear()
            self.triggerPoll.set()

    def joinPollThread(self, timeout):
        """wait for poll thread to finish

        if the wait time exceeds <timeout> seconds, return and log a warning
        """
        if self.__poller:
            self.stopPollThread()
            self.__poller.join(timeout)
            if self.__poller.is_alive():
                self.log.warning('can not stop poller')

    def shutdownModule(self):
        """called when the server shuts down

        any cleanup-work should be performed here, like closing threads and
        saving data.
        """

    def doPoll(self):
        """polls important parameters like value and status

        all other parameters are polled automatically
        """

    def setFastPoll(self, flag, fast_interval=0.25):
        """change poll interval

        :param flag: enable/disable fast poll mode
        :param fast_interval: fast poll interval
        """
        if self.pollInfo:
            self.pollInfo.fast_flag = flag
            self.pollInfo.interval = fast_interval if flag else self.pollinterval
            self.pollInfo.trigger()

    def callPollFunc(self, rfunc, raise_com_failed=False):
        """call read method with proper error handling"""
        try:
            rfunc()
            if rfunc.__name__ in self.pollInfo.pending_errors:
                self.log.info('%s: o.k.', rfunc.__name__)
                self.pollInfo.pending_errors.discard(rfunc.__name__)
        except Exception as e:
            if getattr(e, 'report_error', True):
                name = rfunc.__name__
                self.pollInfo.pending_errors.add(name)  # trigger o.k. message after error is resolved
                if isinstance(e, SECoPError):
                    e.raising_methods.append(name)
                    if e.silent:
                        self.log.debug('%s', e.format(False))
                    else:
                        self.log.error('%s', e.format(False))
                    if raise_com_failed and isinstance(e, CommunicationFailedError):
                        raise
                else:
                    # not a SECoPError: this is proabably a programming error
                    # we want to log the traceback
                    self.log.error('%s', formatException())

    def __pollThread(self, modules, started_callback):
        """poll thread body

        :param modules: list of modules to be handled by this thread
        :param started_callback: to be called after all polls are done once

        before polling, parameters which need hardware initialisation are written
        """
        polled_modules = [m for m in modules if m.enablePoll]
        if hasattr(self, 'registerReconnectCallback'):
            # self is a communicator supporting reconnections
            def trigger_all(trg=self.triggerPoll, polled_modules=polled_modules):
                for m in polled_modules:
                    m.pollInfo.last_main = 0
                    m.pollInfo.last_slow = 0
                trg.set()
            self.registerReconnectCallback('trigger_polls', trigger_all)

        # collect all read functions
        for mobj in polled_modules:
            pinfo = mobj.pollInfo = PollInfo(mobj.pollinterval, self.triggerPoll)
            # trigger a poll interval change when self.pollinterval changes.
            if 'pollinterval' in mobj.paramCallbacks:
                mobj.addCallback('pollinterval', pinfo.update_interval)

            for pname, pobj in mobj.parameters.items():
                rfunc = getattr(mobj, 'read_' + pname)
                if rfunc.poll:
                    pinfo.polled_parameters.append((mobj, rfunc, pobj))
        try:
            for mobj in modules:
                # TODO when needed: here we might add a call to a method :meth:`beforeWriteInit`
                mobj.writeInitParams()
                mobj.initialReads()
            # call all read functions a first time
            for m in polled_modules:
                for mobj, rfunc, _ in m.pollInfo.polled_parameters:
                    mobj.callPollFunc(rfunc, raise_com_failed=True)
            # TODO when needed: here we might add calls to a method :meth:`afterInitPolls`
        except CommunicationFailedError as e:
            # when communication failed, probably all parameters and may be more modules are affected.
            # as this would take a lot of time (summed up timeouts), we do not continue
            # trying and let the server accept connections, further polls might success later
            if started_callback:
                self.log.error('communication failure on startup: %s', e)
                started_callback()
                started_callback = None
        if started_callback:
            started_callback()
        if not polled_modules:  # no polls needed - exit thread
            return
        to_poll = ()
        while modules:  # modules will be cleared on shutdown
            now = time.time()
            wait_time = 999
            for mobj in modules:
                pinfo = mobj.pollInfo
                if pinfo:
                    wait_time = min(pinfo.last_main + pinfo.interval - now, wait_time,
                                    pinfo.last_slow + mobj.slowinterval - now)
            if wait_time > 0 and not to_poll:
                # nothing to do
                self.triggerPoll.wait(wait_time)
                self.triggerPoll.clear()
                continue
            # call doPoll of all modules where due
            for mobj in modules:
                pinfo = mobj.pollInfo
                if pinfo and now > pinfo.last_main + pinfo.interval:
                    try:
                        pinfo.last_main = (now // pinfo.interval) * pinfo.interval
                    except ZeroDivisionError:
                        pinfo.last_main = now
                    mobj.callPollFunc(mobj.doPoll)
                now = time.time()
            # find ONE due slow poll and call it
            loop = True
            while loop:  # loops max. 2 times, when to_poll is at end
                for mobj, rfunc, pobj in to_poll:
                    if now > pobj.timestamp + mobj.slowinterval * 0.5:
                        mobj.callPollFunc(rfunc)
                        loop = False  # one poll done
                        break
                else:
                    to_poll = []
                    # collect due slow polls
                    for mobj in modules:
                        pinfo = mobj.pollInfo
                        if pinfo and now > pinfo.last_slow + mobj.slowinterval:
                            to_poll.extend(pinfo.polled_parameters)
                            pinfo.last_slow = (now // mobj.slowinterval) * mobj.slowinterval
                    if to_poll:
                        to_poll = iter(to_poll)
                    else:
                        loop = False  # no slow polls ready

    def writeInitParams(self):
        """write values for parameters with configured values

        - does proper error handling

        called at the beginning of the poller thread and for writing persistent values
        """
        for pname in list(self.writeDict):
            value = self.writeDict.pop(pname, Done)
            # in the mean time, a poller or handler might already have done it
            if value is not Done:
                wfunc = getattr(self, 'write_' + pname, None)
                if wfunc is None:
                    setattr(self, pname, value)
                else:
                    try:
                        self.log.debug('initialize parameter %s', pname)
                        wfunc(value)
                    except SECoPError as e:
                        if e.silent:
                            self.log.debug('%s: %s', pname, str(e))
                        else:
                            self.log.error('%s: %s', pname, str(e))
                    except Exception:
                        self.log.error(formatException())

    def setRemoteLogging(self, conn, level, send_log):
        if self.remoteLogHandler is None:
            # for non-mlzlog loggers: search parents for remoteloghandler
            log = self.log
            while log is not None:
                for handler in log.handlers:
                    if isinstance(handler, RemoteLogHandler):
                        handler.send_log = send_log
                        self.remoteLogHandler = handler
                        break
                if self.remoteLogHandler is None:
                    # if the log message does not propagate, we would not get it in
                    # the handler anyway, so we can stop searching and fail
                    log = log.parent if log.propagate else None
                else:
                    break
            else:
                raise ValueError('remote handler not found')
        self.remoteLogHandler.set_conn_level(self.name, conn, level)

    def checkLimits(self, value, pname='target'):
        """check for limits

        :param value: the value to be checked for <pname>_min <= value <= <pname>_max
        :param pname: parameter name, default is 'target'

        raises RangeError in case the value is not valid

        This method is called automatically and needs therefore rarely to be
        called by the programmer. It might be used in a check_<param> method,
        when no automatic super call is desired.
        """
        try:
            min_, max_ = getattr(self, pname + '_limits')
            if not min_ <= value <= max_:
                raise RangeError(f'{pname} outside {pname}_limits')
            return
        except AttributeError:
            pass
        min_ = getattr(self, pname + '_min', float('-inf'))
        max_ = getattr(self, pname + '_max', float('inf'))
        if min_ > max_:
            raise RangeError(f'invalid limits: {pname}_min > {pname}_max')
        if value < min_:
            raise RangeError(f'{pname} below {pname}_min')
        if value > max_:
            raise RangeError(f'{pname} above {pname}_max')
