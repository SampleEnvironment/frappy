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

"""Define Client side proxies"""

import json
import socket
import serial
import threading
import Queue

from secop import loggers
from secop.validators import validator_from_str
from secop.lib import mkthread
from secop.lib.parsing import parse_time, format_time
from secop.protocol.encoding import ENCODERS
from secop.protocol.framing import FRAMERS
from secop.protocol.messages import *


class TCPConnection(object):
    # disguise a TCP connection as serial one

    def __init__(self, host, port):
        self._host = host
        self._port = int(port)
        self._thread = None
        self.connect()

    def connect(self):
        self._readbuffer = Queue.Queue(100)
        io = socket.create_connection((self._host, self._port))
        io.setblocking(False)
        io.settimeout(0.3)
        self._io = io
        if self._thread and self._thread.is_alive():
            return
        self._thread = mkthread(self._run)

    def _run(self):
        try:
            data = u''
            while True:
                try:
                    newdata = self._io.recv(1024)
                except socket.timeout:
                    newdata = u''
                    pass
                except Exception as err:
                    print err, "reconnecting"
                    self.connect()
                    data = u''
                    continue
                data += newdata
                while '\n' in data:
                    line, data = data.split('\n', 1)
                    try:
                        self._readbuffer.put(
                            line.strip('\r'), block=True, timeout=1)
                    except Queue.Full:
                        self.log.debug(
                            'rcv queue full! dropping line: %r' % line)
        finally:
            self._thread = None

    def readline(self, block=False):
        """blocks until a full line was read and returns it"""
        i = 10
        while i:
            try:
                return self._readbuffer.get(block=True, timeout=1)
            except Queue.Empty:
                continue
            if not block:
                i -= 1

    def readable(self):
        return not self._readbuffer.empty()

    def write(self, data):
        self._io.sendall(data)

    def writeline(self, line):
        self.write(line + '\n')

    def writelines(self, *lines):
        for line in lines:
            self.writeline(line)


class Value(object):
    t = None
    u = None
    e = None
    fmtstr = '%s'

    def __init__(self, value, qualifiers={}):
        self.value = value
        if 't' in qualifiers:
            self.t = parse_time(qualifiers.pop('t'))
        self.__dict__.update(qualifiers)

    def __repr__(self):
        r = []
        if self.t is not None:
            r.append("timestamp=%r" % format_time(self.t))
        if self.u is not None:
            r.append('unit=%r' % self.u)
        if self.e is not None:
            r.append(('error=%s' % self.fmtstr) % self.e)
        if r:
            return (self.fmtstr + '(%s)') % (self.value, ', '.join(r))
        return self.fmtstr % self.value


class Client(object):
    equipment_id = 'unknown'
    secop_id = 'unknown'
    describing_data = {}
    stopflag = False

    def __init__(self, opts, autoconnect=True):
        self.log = loggers.log.getChild('client', True)
        self._cache = dict()
        if 'device' in opts:
            # serial port
            devport = opts.pop('device')
            baudrate = int(opts.pop('baudrate', 115200))
            self.contactPoint = "serial://%s:%s" % (devport, baudrate)
            self.connection = serial.Serial(devport, baudrate=baudrate,
                                            timeout=1)
        else:
            host = opts.pop('connectto', 'localhost')
            port = int(opts.pop('port', 10767))
            self.contactPoint = "tcp://%s:%d" % (host, port)
            self.connection = TCPConnection(host, port)
        # maps an expected reply to an list containing a single Event()
        # upon rcv of that reply, the event is set and the listitem 0 is
        # appended with the reply-tuple
        self.expected_replies = {}

        # maps spec to a set of callback functions (or single_shot callbacks)
        self.callbacks = dict()
        self.single_shots = dict()

        # mapping the modulename to a dict mapping the parameter names to their values
        # note: the module value is stored as the value of the parameter value
        # of the module

        self._syncLock = threading.RLock()
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()

        if autoconnect:
            self.startup()

    def _run(self):
        while not self.stopflag:
            try:
                self._inner_run()
            except Exception as err:
                self.log.exception(err)
                raise

    def _inner_run(self):
        data = ''
        self.connection.writeline('*IDN?')

        while not self.stopflag:
            line = self.connection.readline()
            self.log.debug('got answer %r' % line)
            if line.startswith(('SECoP', 'SINE2020&ISSE,SECoP')):
                self.log.info('connected to: ' + line.strip())
                self.secop_id = line
                continue
            msgtype, spec, data = self._decode_message(line)
            if msgtype in ('update', 'changed'):
                # handle async stuff
                self._handle_event(spec, data)
            if msgtype != 'update':
                # handle sync stuff
                if msgtype in self.expected_replies:
                    entry = self.expected_replies[msgtype]
                    entry.extend([msgtype, spec, data])
                    # wake up calling process
                    entry[0].set()
                elif msgtype == "error":
                    # XXX: hack!
                    if len(self.expected_replies) == 1:
                        entry = self.expected_replies.values()[0]
                        entry.extend([msgtype, spec, data])
                        # wake up calling process
                        entry[0].set()
                    else: # try to find the right request....
                        print data[0] # should be the origin request
                    # XXX: make an assignment of ERROR to an expected reply.
                    self.log.error('TODO: handle ERROR replies!')
                else:
                    self.log.error('ignoring unexpected reply %r' % line)

    def _encode_message(self, requesttype, spec='', data=Ellipsis):
        """encodes the given message to a string
        """
        req = [str(requesttype)]
        if spec:
            req.append(str(spec))
        if data is not Ellipsis:
            req.append(json.dumps(data))
        req = ' '.join(req)
        return req

    def _decode_message(self, msg):
        """return a decoded message tripel"""
        msg = msg.strip()
        if ' ' not in msg:
            return msg, None, None
        msgtype, spec = msg.split(' ', 1)
        data = None
        if ' ' in spec:
            spec, json_data = spec.split(' ', 1)
            try:
                data = json.loads(json_data)
            except ValueError:
                # keep as string
                data = json_data
        return msgtype, spec, data

    def _handle_event(self, spec, data):
        """handles event"""
        self.log.debug('handle_event %r %r' % (spec, data))
        if ':' not in spec:
            self.log.warning("deprecated specifier %r" % spec)
            spec = '%s:value' % spec
        modname, pname = spec.split(':', 1)
        self._cache.setdefault(modname, {})[pname] = Value(*data)
        if spec in self.callbacks:
            for func in self.callbacks[spec]:
                try:
                    mkthread(func, modname, pname, data)
                except Exception as err:
                    self.log.exception('Exception in Callback!', err)
        run = set()
        if spec in self.single_shots:
            for func in self.single_shots[spec]:
                try:
                    mkthread(func, data)
                except Exception as err:
                    self.log.exception(
                        'Exception in Single-shot Callback!', err)
                run.add(func)
            self.single_shots[spec].difference_update(run)

    def _getDescribingModuleData(self, module):
        return self.describingModulesData[module]

    def _getDescribingParameterData(self, module, parameter):
        return self._getDescribingModuleData(module)['parameters'][parameter]

    def _issueDescribe(self):
        _, self.equipment_id, self.describing_data = self.communicate(
            'describe')

        for module, moduleData in self.describing_data['modules'].items():
            for parameter, parameterData in moduleData['parameters'].items():
                validator = validator_from_str(parameterData['validator'])
                self.describing_data['modules'][module]['parameters'] \
                    [parameter]['validator'] = validator

    def register_callback(self, module, parameter, cb):
        self.log.debug(
            'registering callback %r for %s:%s' %
            (cb, module, parameter))
        self.callbacks.setdefault('%s:%s' % (module, parameter), set()).add(cb)

    def unregister_callback(self, module, parameter, cb):
        self.log.debug(
            'unregistering callback %r for %s:%s' %
            (cb, module, parameter))
        self.callbacks.setdefault('%s:%s' %
                                  (module, parameter), set()).discard(cb)

    def communicate(self, msgtype, spec='', data=Ellipsis):
        # maps each (sync) request to the corresponding reply
        # XXX: should go to the encoder! and be imported here (or make a
        # translating method)
        REPLYMAP = {
            "describe": "describing",
            "do": "done",
            "change": "changed",
            "activate": "active",
            "deactivate": "inactive",
            "*IDN?": "SECoP,",
            "ping": "pong",
        }
        if self.stopflag:
            raise RuntimeError('alreading stopping!')
        if msgtype == 'read':
            # send a poll request and then check incoming events
            if ':' not in spec:
                spec = spec + ':value'
            event = threading.Event()
            result = ['update', spec]
            self.single_shots.setdefault(spec, set()).add(
                lambda d: (result.append(d), event.set()))
            self.connection.writeline(
                self._encode_message(
                    msgtype, spec, data))
            if event.wait(10):
                return tuple(result)
            raise RuntimeError("timeout upon waiting for reply!")

        rply = REPLYMAP[msgtype]
        if rply in self.expected_replies:
            raise RuntimeError(
                "can not have more than one requests of the same type at the same time!")
        event = threading.Event()
        self.expected_replies[rply] = [event]
        self.log.debug('prepared reception of %r msg' % rply)
        self.connection.writeline(self._encode_message(msgtype, spec, data))
        self.log.debug('sent %r msg' % msgtype)
        if event.wait(10):  # wait 10s for reply
            self.log.debug('checking reply')
            result = self.expected_replies[rply][1:4]
            del self.expected_replies[rply]
#            if result[0] == "ERROR":
#                raise RuntimeError('Got %s! %r' % (str(result[1]), repr(result[2])))
            return result
        del self.expected_replies[rply]
        raise RuntimeError("timeout upon waiting for reply to %r!" % msgtype)

    def quit(self):
        # after calling this the client is dysfunctional!
        self.communicate('deactivate')
        self.stopflag = True
        if self._thread and self._thread.is_alive():
            self.thread.join(self._thread)

    def handle_async(self, msg):
        self.log.info("Got async update %r" % msg)
        device = msg.device
        param = msg.param
        value = msg.value
        self._cache.getdefault(device, {})[param] = value
        # XXX: further notification-callbacks needed ???

    def startup(self, async=False):
        self._issueDescribe()
        # always fill our cache
        self.communicate('activate')
        # deactivate updates if not wanted
        if not async:
            self.communicate('deactivate')

    def queryCache(self, module, parameter=None):
        result = self._cache.get(module, {})

        if parameter is not None:
            result = result[parameter]

        return result

    def setParameter(self, module, parameter, value):
        validator = self._getDescribingParameterData(module,
                                                     parameter)['validator']

        value = validator(value)
        self.communicate('change', '%s:%s' % (module, parameter), value)

    @property
    def describingData(self):
        return self.describing_data

    @property
    def describingModulesData(self):
        return self.describingData['modules']

    @property
    def equipmentId(self):
        return self.equipment_id

    @property
    def protocolVersion(self):
        return self.secop_id

    @property
    def modules(self):
        return self.describing_data['modules'].keys()

    def getParameters(self, module):
        return self.describing_data['modules'][module]['parameters'].keys()

    def getModuleBaseClass(self, module):
        return self.describing_data['modules'][module]['baseclass']

    def getCommands(self, module):
        return self.describing_data['modules'][module]['commands'].keys()

    def getProperties(self, module, parameter):
        return self.describing_data['modules'][
            module]['parameters'][parameter].items()

    def syncCommunicate(self, *msg):
        return self.communicate(*msg)
