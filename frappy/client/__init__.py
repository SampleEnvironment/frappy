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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
"""general SECoP client"""

import re
import json
import queue
import time
from collections import defaultdict
from threading import Event, RLock, current_thread

import frappy.errors
import frappy.params
from frappy.datatypes import get_datatype
from frappy.lib import mkthread, formatExtendedStack
from frappy.lib.asynconn import AsynConn, ConnectionClosed
from frappy.protocol.interface import decode_msg, encode_msg_frame
from frappy.protocol.messages import COMMANDREQUEST, \
    DESCRIPTIONREQUEST, ENABLEEVENTSREQUEST, ERRORPREFIX, \
    EVENTREPLY, HEARTBEATREQUEST, IDENTPREFIX, IDENTREQUEST, \
    READREPLY, READREQUEST, REQUEST2REPLY, WRITEREPLY, WRITEREQUEST

# replies to be handled for cache
UPDATE_MESSAGES = {EVENTREPLY, READREPLY, WRITEREPLY, ERRORPREFIX + READREQUEST, ERRORPREFIX + EVENTREPLY}

VERSIONFMT= re.compile(r'^[^,]*?ISSE[^,]*,SECoP,')


class UnregisterCallback(Exception):
    """raise in a callback to indicate it has to be unregistered

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
    error = exception = warning = critical = info


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


class CacheItem(tuple):
    """cache entry

    includes formatting information
    inheriting from tuple: compatible with old previous version of cache
    """
    def __new__(cls, value, timestamp=None, readerror=None, datatype=None):
        if readerror:
            assert isinstance(readerror, Exception)
        else:
            try:
                value = datatype.import_value(value)
            except (KeyError, ValueError, AttributeError):
                readerror = ValueError(f'can not import {value!r} as {datatype!r}')
                value = None
        obj = tuple.__new__(cls, (value, timestamp, readerror))
        try:
            obj.format_value = datatype.format_value
        except AttributeError:
            obj.format_value = lambda value, unit=None: str(value)
        return obj

    @property
    def value(self):
        return self[0]

    @property
    def timestamp(self):
        return self[1]

    @property
    def readerror(self):
        return self[2]

    def __str__(self):
        """format value without unit"""
        if self[2]:  # readerror
            return repr(self[2])
        return self.format_value(self[0], unit='')  # skip unit

    def formatted(self):
        """format value with using unit"""
        if self[2]:  # readerror
            return repr(self[2])
        return self.format_value(self[0])

    def __repr__(self):
        args = (self.value,)
        if self.timestamp:
            args += (self.timestamp,)
        if self.readerror:
            args += (self.readerror,)
        return f'CacheItem{repr(args)}'


class ProxyClient:
    """common functionality for proxy clients"""

    CALLBACK_NAMES = {'updateEvent', 'updateItem', 'descriptiveDataChange',
                      'nodeStateChange', 'unhandledMessage'}
    online = False  # connected or reconnecting since a short time
    state = 'disconnected'  # further possible values: 'connecting', 'reconnecting', 'connected'
    log = None

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
        for cbname, cbfunc in kwds.items():
            if cbname not in self.CALLBACK_NAMES:
                raise TypeError(f"unknown callback: {', '.join(kwds)}")

            # immediately call for some callback types
            if cbname in ('updateItem', 'updateEvent'):
                if key is None:  # case generic callback
                    cbargs = [(m, p, d) for (m, p), d in self.cache.items()]
                else:
                    data = self.cache.get(key, None)
                    if data:  # case single parameter
                        cbargs = [key + (data,)]
                    else:  # case key = module
                        cbargs = [(m, p, d) for (m, p), d in self.cache.items() if m == key]

                if cbname == 'updateEvent':
                    # expand entry argument to (value, timestamp, readerror)
                    cbargs = [a[0:2] + a[2] for a in cbargs]

            elif cbname == 'nodeStateChange':
                cbargs = [(self.online, self.state)]
            else:
                cbargs = []

            do_append = True
            for args in cbargs:
                try:
                    cbfunc(*args)
                except UnregisterCallback:
                    do_append = False
                except Exception as e:
                    if self.log:
                        self.log.error('error %r calling %s%r', e, cbfunc.__name__, args)
            if do_append:
                self.callbacks[cbname][key].append(cbfunc)

    def unregister_callback(self, key, *args, **kwds):
        """unregister a callback

        for the arguments see register_callback
        """
        for cbfunc in args:
            kwds[cbfunc.__name__] = cbfunc
        for cbname, func in kwds.items():
            cblist = self.callbacks[cbname][key]
            if func in cblist:
                cblist.remove(func)
            if not cblist:
                self.callbacks[cbname].pop(key)

    def callback(self, key, cbname, *args):
        """perform callbacks

        key=None:
        key=<module name>: callbacks for specified module
        key=(<module name>, <parameter name): callbacks for specified parameter
        """
        cblist = self.callbacks[cbname].get(key, [])
        for cbfunc in list(cblist):
            try:
                cbfunc(*args)
            except UnregisterCallback:
                cblist.remove(cbfunc)
            except Exception as e:
                # the programmer should catch all errors in callbacks
                # if not, the log will be flooded with errors
                if self.log:
                    self.log.exception('error %r calling %s%r', e, cbfunc.__name__, args)
        return bool(cblist)

    def updateValue(self, module, param, value, timestamp, readerror):
        self.callback(None, 'updateEvent', module, param, value, timestamp, readerror)
        self.callback(module, 'updateEvent', module, param, value, timestamp, readerror)
        self.callback((module, param), 'updateEvent', module, param,value, timestamp, readerror)


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
                        raise self.error_map('HardwareError')(f'no answer to {IDENTREQUEST}')

                    if not VERSIONFMT.match(self.secop_version):
                        raise self.error_map('HardwareError')(f'bad answer to {IDENTREQUEST}: {self.secop_version!r}')
                    # inform that the other party still uses a legacy identifier
                    # see e.g. Frappy Bug #4659 (https://forge.frm2.tum.de/redmine/issues/4659)
                    if not self.secop_version.startswith(IDENTPREFIX):
                        self.log.warning('SEC-Node replied with legacy identify reply: %s',
                                         self.secop_version)

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
        noactivity = 0
        try:
            while self._running:
                # may raise ConnectionClosed
                reply = self.io.readline()
                if reply is None:
                    noactivity += 1
                    if noactivity % 5 == 0:
                        # send ping to check if the connection is still alive
                        self.queue_request(HEARTBEATREQUEST, str(noactivity))
                    continue
                self.log.debug('RX: %r', reply)
                noactivity = 0
                action, ident, data = decode_msg(reply)
                if ident == '.':
                    ident = None
                if action in UPDATE_MESSAGES:
                    module_param = self.internal.get(ident, None)
                    if module_param is None and ':' not in (ident or ''):
                        # allow missing ':value'/':target'
                        if action == WRITEREPLY:
                            module_param = self.internal.get(f'{ident}:target', None)
                        else:
                            module_param = self.internal.get(f'{ident}:value', None)
                    if module_param is not None:
                        if action.startswith(ERRORPREFIX):
                            timestamp = data[2].get('t', None)
                            readerror = frappy.errors.make_secop_error(*data[0:2])
                            value = None
                        else:
                            timestamp = data[1].get('t', None)
                            value = data[0]
                            readerror = None
                        module, param = module_param
                        timestamp = min(time.time(), timestamp)  # no timestamps in the future!
                        try:
                            self.updateValue(module, param, value, timestamp, readerror)
                        except KeyError:
                            pass  # ignore updates of unknown parameters
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
        except ConnectionClosed:
            pass
        except Exception as e:
            self.log.error('rxthread ended with %r', e)
        self._rxthread = None
        self.disconnect(False)
        if self._shutdown:
            return
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
                    if 'join' in str(e):
                        raise
                    self.log.error(str(e))
                if time.time() > self.disconnect_time + self.reconnect_timeout:
                    if self.online:  # was recently connected
                        self.disconnect_time = 0
                        self.log.warning('can not reconnect to %s (%r)', self.nodename, e)
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
            if self._connthread:
                if self._connthread == current_thread():
                    return
                # wait for connection thread stopped
                self._connthread.join()
                self._connthread = None
        self.disconnect_time = time.time()
        try:  # make sure txq does not block
            while not self.txq.empty():
                self.txq.get(False)
        except Exception:
            pass
        if self.io:
            self.io.shutdown()
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
                ident = f'{modname}:{aname}'
                self.identifier[modname, iname] = ident
                self.internal[ident] = modname, iname
                if datatype.IS_COMMAND:
                    commands[iname] = aentry
                else:
                    parameters[iname] = aentry
            properties = {k: v for k, v in moddescr.items() if k != 'accessibles'}
            self.modules[modname] = {'accessibles': accessibles, 'parameters': parameters,
                                     'commands': commands, 'properties': properties}
        if changed_modules is not None:
            done = done_main = self.callback(None, 'descriptiveDataChange', None, self)
            for mname in changed_modules:
                if not self.callback(mname, 'descriptiveDataChange', mname, self):
                    if not done_main:
                        self.log.warning('descriptive data changed on module %r', mname)
                    done = True
            if not done:
                self.log.warning('descriptive data of %r changed', self.nodename)

    def _unhandled_message(self, action, ident, data):
        if not self.callback(None, 'unhandledMessage', action, ident, data):
            self.log.warning('unhandled message: %s %s %r', action, ident, data)

    def _set_state(self, online, state=None):
        # remark: reconnecting is treated as online
        self.online = online
        self.state = state or self.state
        self.callback(None, 'nodeStateChange', self.online, self.state)
        for mname in self.modules:
            self.callback(mname, 'nodeStateChange', self.online, self.state)

    def queue_request(self, action, ident=None, data=None):
        """make a request"""
        request = action, ident, data
        self.connect()  # make sure we are connected
        # the last item is for the reply
        entry = [request, Event(), None]
        self.txq.put(entry, timeout=3)
        return entry

    def get_reply(self, entry):
        """wait for reply and return it"""
        if not entry[1].wait(10):  # event
            raise TimeoutError('no response within 10s')
        if not entry[2]:  # reply
            raise ConnectionError('connection closed before reply')
        action, _, data = entry[2]  # pylint: disable=unpacking-non-sequence
        if action.startswith(ERRORPREFIX):
            raise frappy.errors.make_secop_error(*data[0:2])
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
        except frappy.errors.SECoPError:
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
        value = datatype.export_value(value)
        self.request(WRITEREQUEST, self.identifier[module, parameter], value)
        return self.cache[module, parameter]

    def execCommand(self, module, command, argument=None):
        self.connect()  # make sure we are connected
        datatype = self.modules[module]['commands'][command]['datatype'].argument
        if datatype:
            argument = datatype.export_value(argument)
        else:
            if argument is not None:
                raise frappy.errors.WrongTypeError('command has no argument')
        # pylint: disable=unsubscriptable-object
        data, qualifiers = self.request(COMMANDREQUEST, self.identifier[module, command], argument)[2]
        datatype = self.modules[module]['commands'][command]['datatype'].result
        if datatype:
            data = datatype.import_value(data)
        return data, qualifiers

    def updateValue(self, module, param, value, timestamp, readerror):
        entry = CacheItem(value, timestamp, readerror,
                          self.modules[module]['parameters'][param]['datatype'])
        self.cache[(module, param)] = entry
        self.callback(None, 'updateItem', module, param, entry)
        self.callback(module, 'updateItem', module, param, entry)
        self.callback((module, param), 'updateItem', module, param, entry)
        # TODO: change clients to use updateItem instead of updateEvent
        super().updateValue(module, param, value, timestamp, readerror)

    # the following attributes may be/are intended to be overwritten by a subclass

    PREDEFINED_NAMES = set(frappy.params.PREDEFINED_ACCESSIBLES)
    activate = True

    def internalize_name(self, name):
        """how to create internal names"""
        if name.startswith('_') and name[1:] not in self.PREDEFINED_NAMES:
            return name[1:]
        return name
