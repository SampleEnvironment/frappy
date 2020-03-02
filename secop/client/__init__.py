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
"""general SECoP client"""

import time
import queue
import json
from threading import Event, RLock
from collections import defaultdict

from secop.lib import mkthread, formatExtendedTraceback, formatExtendedStack
from secop.lib.asynconn import AsynConn, ConnectionClosed
from secop.datatypes import get_datatype, EnumType
from secop.protocol.interface import encode_msg_frame, decode_msg
from secop.protocol.messages import REQUEST2REPLY, ERRORPREFIX, EVENTREPLY, WRITEREQUEST, WRITEREPLY, \
    READREQUEST, READREPLY, IDENTREQUEST, IDENTPREFIX, ENABLEEVENTSREQUEST, COMMANDREQUEST, DESCRIPTIONREQUEST
import secop.errors
import secop.params

# replies to be handled for cache
UPDATE_MESSAGES = {EVENTREPLY, READREPLY, WRITEREPLY, ERRORPREFIX + READREQUEST, ERRORPREFIX + EVENTREPLY}


class UNREGISTER:
    """a magic value, used a returned value in a callback

    to indicate it has to be unregistered
    used to implement one shot callbacks
    """


class Logger:
    """dummy logger, in case not provided from caller"""

    @staticmethod
    def info(fmt, *args, **kwds):
        print(str(fmt) % args)

    @staticmethod
    def noop(fmt, *args, **kwds):
        pass

    debug = noop
    error = warning = critical = info


class CallbackObject:
    """abstract definition for a target object for callbacks

    this is mainly for documentation, but it might be extended
    and used as a mixin for objects registered as a callback
    """
    def updateEvent(self, module, parameter, value, timestamp, readerror):
        """called whenever a value is changed

        or when new callbacks are registered
        """

    def unhandledMessage(self, action, ident, data):
        """called on an unhandled message"""

    def nodeStateChange(self, online, state):
        """called when the state of the connection changes

        'online' is True when connected or reconnecting, False when disconnected or connecting
        'state' is the connection state as a string
        """

    def descriptiveDataChange(self, module, description):
        """called when the description has changed

        this callback is called on the node with module=None
        and on every changed module with module==<module name>
        """


class ProxyClient:
    """common functionality for proxy clients"""

    CALLBACK_NAMES = ('updateEvent', 'descriptiveDataChange', 'nodeStateChange', 'unhandledMessage')
    online = False  # connected or reconnecting since a short time
    validate_data = False
    state = 'disconnected'  # further possible values: 'connecting', 'reconnecting', 'connected'

    def __init__(self):
        self.callbacks = {cbname: defaultdict(list) for cbname in self.CALLBACK_NAMES}
        # caches (module, parameter) = value, timestamp, readerror (internal names!)
        self.cache = {}

    def register_callback(self, key, *args, **kwds):
        """register callback functions

        - key might be either:
            1) None: general callback (all callbacks)
            2) <module name>: callbacks related to a module (not called for 'unhandledMessage')
            3) (<module name>, <parameter name>): callback for specified parameter (only called for 'updateEvent')
        - all the following arguments are callback functions. The callback name may be
          given by the keyword, or, for non-keyworded arguments it is taken from the
          __name__ attribute of the function
        """
        for cbfunc in args:
            kwds[cbfunc.__name__] = cbfunc
        for cbname in self.CALLBACK_NAMES:
            cbfunc = kwds.pop(cbname, None)
            if not cbfunc:
                continue
            cbdict = self.callbacks[cbname]
            cbdict[key].append(cbfunc)

            # immediately call for some callback types
            if cbname == 'updateEvent':
                if key is None:
                    for (mname, pname), data in self.cache.items():
                        cbfunc(mname, pname, *data)
                else:
                    data = self.cache.get(key, None)
                    if data:
                        cbfunc(*key, *data)  # case single parameter
                    else:  # case key = module
                        for (mname, pname), data in self.cache.items():
                            if mname == key:
                                cbfunc(mname, pname, *data)
            elif cbname == 'nodeStateChange':
                cbfunc(self.online, self.state)
        if kwds:
            raise TypeError('unknown callback: %s' % (', '.join(kwds)))

    def callback(self, key, cbname, *args):
        """perform callbacks

        key=None:
        key=<module name>: callbacks for specified module
        key=(<module name>, <parameter name): callbacks for specified parameter
        """
        cblist = self.callbacks[cbname].get(key, [])
        self.callbacks[cbname][key] = [cb for cb in cblist if cb(*args) is not UNREGISTER]
        return bool(cblist)

    def updateValue(self, module, param, value, timestamp, readerror):
        if readerror:
            assert isinstance(readerror, Exception)
        if self.validate_data:
            try:
                # try to validate, reason: make enum_members from integers
                datatype = self.modules[module]['parameters'][param]['datatype']
                value = datatype(value)
            except (KeyError, ValueError):
                pass
        self.cache[(module, param)] = (value, timestamp, readerror)
        self.callback(None, 'updateEvent', module, param, value, timestamp, readerror)
        self.callback(module, 'updateEvent', module, param, value, timestamp, readerror)
        self.callback((module, param), 'updateEvent', module, param, value, timestamp, readerror)


class SecopClient(ProxyClient):
    """a general SECoP client"""
    reconnect_timeout = 10
    _running = False
    _shutdown = False
    _rxthread = None
    _txthread = None
    _connthread = None
    disconnect_time = 0  # time of last disconnect
    secop_version = ''
    descriptive_data = {}
    modules = {}
    _last_error = None

    def __init__(self, uri, log=Logger):
        super().__init__()
        # maps expected replies to [request, Event, is_error, result] until a response came
        # there can only be one entry per thread calling 'request'
        self.active_requests = {}
        self.io = None
        self.txq = queue.Queue(30)   # queue for tx requests
        self.pending = queue.Queue(30)  # requests with colliding action + ident
        self.log = log
        self.uri = uri
        self.nodename = uri
        self._lock = RLock()

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass

    def connect(self, try_period=0):
        """establish connection

        if a <try_period> is given, repeat trying for the given time (sec)
        """
        with self._lock:
            if self.io:
                return
            if self.online:
                self._set_state(True, 'reconnecting')
            else:
                self._set_state(False, 'connecting')
            deadline = time.time() + try_period
            while not self._shutdown:
                try:
                    self.io = AsynConn(self.uri)  # timeout 1 sec
                    self.io.writeline(IDENTREQUEST.encode('utf-8'))
                    reply = self.io.readline(10)
                    if reply:
                        self.secop_version = reply.decode('utf-8')
                    else:
                        raise self.error_map('HardwareError')('no answer to %s' % IDENTREQUEST)
                    if not self.secop_version.startswith(IDENTPREFIX):
                        raise self.error_map('HardwareError')('bad answer to %s: %r' %
                                                              (IDENTREQUEST, self.secop_version))
                    # now its safe to do secop stuff
                    self._running = True
                    self._rxthread = mkthread(self.__rxthread)
                    self._txthread = mkthread(self.__txthread)
                    self.log.debug('connected to %s', self.uri)
                    # pylint: disable=unsubscriptable-object
                    self._init_descriptive_data(self.request(DESCRIPTIONREQUEST)[2])
                    self.nodename = self.properties.get('equipment_id', self.uri)
                    if self.activate:
                        self.request(ENABLEEVENTSREQUEST)
                    self._set_state(True, 'connected')
                    break
                except Exception:
                    # print(formatExtendedTraceback())
                    if time.time() > deadline:
                        # stay online for now, if activated
                        self._set_state(self.online and self.activate)
                        raise
                    time.sleep(1)
            if not self._shutdown:
                self.log.info('%s ready', self.nodename)

    def __txthread(self):
        while self._running:
            entry = self.txq.get()
            if entry is None:
                break
            request = entry[0]
            reply_action = REQUEST2REPLY.get(request[0], None)
            if reply_action:
                key = (reply_action, request[1])  # action and identifier
            else:  # allow experimental unknown requests, but only one at a time
                key = None
            if key in self.active_requests:
                # store to requeue after the next reply was received
                self.pending.put(entry)
            else:
                self.active_requests[key] = entry
                line = encode_msg_frame(*request)
                self.log.debug('TX: %r', line)
                self.io.send(line)
        self._txthread = None
        self.disconnect(False)

    def __rxthread(self):
        while self._running:
            try:
                reply = self.io.readline()
                if reply is None:
                    continue
            except ConnectionClosed:
                break
            action, ident, data = decode_msg(reply)
            if ident == '.':
                ident = None
            if action in UPDATE_MESSAGES:
                module_param = self.internal.get(ident, None)
                if module_param is None and ':' not in ident:
                    # allow missing ':value'/':target'
                    if action == WRITEREPLY:
                        module_param = self.internal.get(ident + ':target', None)
                    else:
                        module_param = self.internal.get(ident + ':value', None)
                if module_param is not None:
                    if action.startswith(ERRORPREFIX):
                        timestamp = data[2].get('t', None)
                        readerror = secop.errors.make_secop_error(*data[0:2])
                        value = None
                    else:
                        timestamp = data[1].get('t', None)
                        value = data[0]
                        readerror = None
                    module, param = module_param
                    self.updateValue(module, param, value, timestamp, readerror)
                    if action in (EVENTREPLY, ERRORPREFIX + EVENTREPLY):
                        continue
            try:
                key = action, ident
                entry = self.active_requests.pop(key)
            except KeyError:
                if action.startswith(ERRORPREFIX):
                    try:
                        key = REQUEST2REPLY[action[len(ERRORPREFIX):]], ident
                    except KeyError:
                        key = None
                    entry = self.active_requests.pop(key, None)
                else:
                    # this may be a response to the last unknown request
                    key = None
                    entry = self.active_requests.pop(key, None)
            if entry is None:
                self._unhandled_message(action, ident, data)
                continue
            entry[2] = action, ident, data
            entry[1].set()  # trigger event
            while not self.pending.empty():
                # let the TX thread sort out which entry to treat
                # this may have bad performance, but happens rarely
                self.txq.put(self.pending.get())

        self._rxthread = None
        self.disconnect(False)
        if self.activate:
            self.log.info('try to reconnect to %s', self.uri)
            self._connthread = mkthread(self._reconnect)
        else:
            self.log.warning('%s disconnected', self.uri)
            self._set_state(False, 'disconnected')

    def spawn_connect(self, connected_callback=None):
        """try to connect in background

        and trigger event when done and event is not None
        """
        self.disconnect_time = time.time()
        self._connthread = mkthread(self._reconnect, connected_callback)

    def _reconnect(self, connected_callback=None):
        while not self._shutdown:
            try:
                self.connect()
                if connected_callback:
                    connected_callback()
                break
            except Exception as e:
                txt = str(e).split('\n', 1)[0]
                if txt != self._last_error:
                    self._last_error = txt
                    self.log.error(str(e))
                if time.time() > self.disconnect_time + self.reconnect_timeout:
                    if self.online:  # was recently connected
                        self.disconnect_time = 0
                        self.log.warning('can not reconnect to %s (%r)' % (self.nodename, e))
                        self.log.info('continue trying to reconnect')
                        # self.log.warning(formatExtendedTraceback())
                        self._set_state(False)
                    time.sleep(self.reconnect_timeout)
                else:
                    time.sleep(1)
        self._connthread = None

    def disconnect(self, shutdown=True):
        self._running = False
        if shutdown:
            self._shutdown = True
            self._set_state(False, 'shutdown')
            if self._connthread:  # wait for connection thread stopped
                self._connthread.join()
                self._connthread = None
        self.disconnect_time = time.time()
        if self._txthread:
            self.txq.put(None)  # shutdown marker
            self._txthread.join()
            self._txthread = None
        if self._rxthread:
            self._rxthread.join()
            self._rxthread = None
        if self.io:
            self.io.disconnect()
        self.io = None
        # abort pending requests early
        try:  # avoid race condition
            while self.active_requests:
                _, (_, event, _) = self.active_requests.popitem()
                event.set()
        except KeyError:
            pass
        try:
            while True:
                _, event, _ = self.pending.get(block=False)
                event.set()
        except queue.Empty:
            pass

    def _init_descriptive_data(self, data):
        """rebuild descriptive data"""
        changed_modules = None
        if json.dumps(data, sort_keys=True) != json.dumps(self.descriptive_data, sort_keys=True):
            if self.descriptive_data:
                changed_modules = set()
                modules = data.get('modules', {})
                for modname, moddesc in self.descriptive_data['modules'].items():
                    if json.dumps(moddesc, sort_keys=True) != json.dumps(modules.get(modname), sort_keys=True):
                        changed_modules.add(modname)
        self.descriptive_data = data
        modules = data['modules']
        self.modules = {}
        self.properties = {k: v for k, v in data.items() if k != 'modules'}
        self.identifier = {}  # map (module, parameter) -> identifier
        self.internal = {}  # map identifier -> (module, parameter)
        for modname, moddescr in modules.items():
            #  separate accessibles into command and parameters
            parameters = {}
            commands = {}
            accessibles = moddescr['accessibles']
            for aname, aentry in accessibles.items():
                iname = self.internalize_name(aname)
                datatype = get_datatype(aentry['datainfo'], iname)
                aentry = dict(aentry, datatype=datatype)
                ident = '%s:%s' % (modname, aname)
                self.identifier[modname, iname] = ident
                self.internal[ident] = modname, iname
                if datatype.IS_COMMAND:
                    commands[iname] = aentry
                else:
                    parameters[iname] = aentry
            properties = {k: v for k, v in moddescr.items() if k != 'accessibles'}
            self.modules[modname] = dict(accessibles=accessibles, parameters=parameters,
                                         commands=commands, properties=properties)
        if changed_modules is not None:
            done = self.callback(None, 'descriptiveDataChange', None, self)
            for mname in changed_modules:
                if not self.callback(mname, 'descriptiveDataChange', mname, self):
                    self.log.warning('descriptive data changed on module %r', mname)
                    done = True
            if not done:
                self.log.warning('descriptive data of %r changed', self.nodename)

    def _unhandled_message(self, action, ident, data):
        if not self.callback(None, 'unhandledMessage', action, ident, data):
            self.log.warning('unhandled message: %s %s %r' % (action, ident, data))

    def _set_state(self, online, state=None):
        # treat reconnecting as online!
        state = state or self.state
        self.callback(None, 'nodeStateChange', online, state)
        for mname in self.modules:
            self.callback(mname, 'nodeStateChange', online, state)
        # set online attribute after callbacks -> callback may check for old state
        self.online = online
        self.state = state

    def queue_request(self, action, ident=None, data=None):
        """make a request"""
        request = action, ident, data
        self.connect()  # make sure we are connected
        # the last item is for the reply
        entry = [request, Event(), None]
        self.txq.put(entry)
        return entry

    def get_reply(self, entry):
        """wait for reply and return it"""
        if not entry[1].wait(10):  # event
            raise TimeoutError('no response within 10s')
        if not entry[2]:  # reply
            raise ConnectionError('connection closed before reply')
        action, _, data = entry[2]  # pylint: disable=unpacking-non-sequence
        if action.startswith(ERRORPREFIX):
            errcls = self.error_map(data[0])
            raise errcls(data[1])
        return entry[2]  # reply

    def request(self, action, ident=None, data=None):
        """make a request

        and wait for reply
        """
        entry = self.queue_request(action, ident, data)
        return self.get_reply(entry)

    def readParameter(self, module, parameter):
        """forced read over connection"""
        try:
            self.request(READREQUEST, self.identifier[module, parameter])
        except secop.errors.SECoPError:
            # error reply message is already stored as readerror in cache
            pass
        return self.cache.get((module, parameter), None)

    def getParameter(self, module, parameter, trycache=False):
        if trycache:
            cached = self.cache.get((module, parameter), None)
            if cached:
                return cached
        if self.online:
            self.readParameter(module, parameter)
        return self.cache[module, parameter]

    def setParameter(self, module, parameter, value):
        self.connect()  # make sure we are connected
        datatype = self.modules[module]['parameters'][parameter]['datatype']
        value = datatype.export_value(datatype.from_string(value))
        self.request(WRITEREQUEST, self.identifier[module, parameter], value)
        return self.cache[module, parameter]

    def execCommand(self, module, command, argument=None):
        self.connect()  # make sure we are connected
        datatype = self.modules[module]['commands'][command]['datatype'].argument
        if datatype:
            argument = datatype.export_value(datatype.from_string(argument))
        else:
            if argument is not None:
                raise secop.errors.BadValueError('command has no argument')
        # pylint: disable=unsubscriptable-object
        data, qualifiers = self.request(COMMANDREQUEST, self.identifier[module, command], argument)[2]
        datatype = self.modules[module]['commands'][command]['datatype'].result
        if datatype:
            data = datatype.import_value(data)
        return data, qualifiers

    # the following attributes may be/are intended to be overwritten by a subclass

    ERROR_MAP = secop.errors.EXCEPTIONS
    DEFAULT_EXCEPTION = secop.errors.SECoPError
    PREDEFINED_NAMES = set(secop.params.PREDEFINED_ACCESSIBLES)
    activate = True

    def error_map(self, exc):
        """how to convert SECoP and unknown exceptions"""
        return self.ERROR_MAP.get(exc, self.DEFAULT_EXCEPTION)

    def internalize_name(self, name):
        """how to create internal names"""
        if name.startswith('_') and name[1:] not in self.PREDEFINED_NAMES:
            return name[1:]
        return name
