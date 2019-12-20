#!/usr/bin/env python
#  -*- coding: utf-8 -*-
# *****************************************************************************
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
#   Markus Zolliker <markus.zolliker@psi.ch>
# *****************************************************************************
"""Line oriented stream communication

implements TCP/IP and is be used as a base for SerialIO
"""

import time
import socket
import threading
import re
from secop.modules import Module, Communicator, Parameter, Command, Property, Attached
from secop.datatypes import StringType, FloatRange, ArrayOf, BoolType, TupleOf
from secop.errors import CommunicationFailedError, CommunicationSilentError
from secop.poller import REGULAR
from secop.metaclass import Done



class StringIO(Communicator):
    """line oriented communicator

    implementation for TCP/IP streams.
    other types have to override the following methods:
    createConnection, readWithTimeout, writeBytes, closeConnection

    self healing is assured by polling the parameter 'is_connected'
    """
    properties = {
        'uri':
            Property('hostname:portnumber', datatype=StringType()),
        'end_of_line':
            Property('end_of_line character', datatype=StringType(),
                default='\n', settable=True),
        'encoding':
            Property('used encoding', datatype=StringType(),
                default='ascii', settable=True),
        'identification':
            Property('a list of tuples with commands and expected responses as regexp',
                datatype=ArrayOf(TupleOf(StringType(),StringType())), default=[], export=False),
    }
    parameters = {
        'timeout':
            Parameter('timeout', datatype=FloatRange(0), default=2),
        'wait_before':
            Parameter('wait time before sending', datatype=FloatRange(), default=0),
        'is_connected':
            Parameter('connection state', datatype=BoolType(), readonly=False, poll=REGULAR),
        'pollinterval':
            Parameter('reconnect interval', datatype=FloatRange(0), readonly=False, default=10),
    }
    commands = {
        'multicomm':
            Command('execute multiple commands in one go',
                argument=ArrayOf(StringType()), result= ArrayOf(StringType()))
    }

    _reconnectCallbacks = None

    def earlyInit(self):
        self._stream = None
        self._lock = threading.RLock()
        self._end_of_line = self.end_of_line.encode(self.encoding)
        self._connect_error = None
        self._last_error = None

    def createConnection(self):
        """create connection

        in case of success, self.is_connected MUST be set to True by implementors
        """
        uri = self.uri
        if uri.startswith('tcp://'):
            uri = uri[6:]
        try:
            host, port = uri.split(':')
            self._stream = socket.create_connection((host, int(port)), 10)
            self.is_connected = True
        except (ConnectionRefusedError, socket.gaierror) as e:
            raise CommunicationFailedError(str(e))
        except Exception as e:
            # this is really bad, do not try again
            self._connect_error = e
            raise

    def readWithTimeout(self, timeout):
        """read with timeout

        Read bytes available now, or wait at most the specified timeout until some bytes
        are available. Throw an error, if disconnected.
        If no bytes are available, return b''

        to be overwritten for other stream types
        """
        if timeout is None or timeout < 0:
            raise ValueError('illegal timeout %r' % timeout)
        if not self.is_connected:
            raise CommunicationSilentError(self._last_error or 'not connected')
        self._stream.settimeout(timeout)
        try:
            reply = self._stream.recv(4096)
            if reply:
                return reply
        except (BlockingIOError, socket.timeout):
            return b''
        except Exception as e:
            self.closeConnection()
            raise CommunicationFailedError('disconnected because of %s' % e)
        # other end disconnected
        self.closeConnection()
        raise CommunicationFailedError('other end disconnected')

    def writeBytes(self, data):
        """write bytes

        to be overwritten for other stream types
        """
        self._stream.sendall(data)

    def closeConnection(self):
        """close connection

        self.is_connected MUST be set to False by implementors
        """
        if not self._stream:
            return
        self.log.debug('disconnect %s' % self.uri)
        try:
            self._stream.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        try:
            self._stream.close()
        except socket.error:
            pass
        self._stream = None
        self.is_connected = False

    def read_is_connected(self):
        """try to reconnect, when not connected

        self.is_connected is changed only by self.connectStart or self.closeConnection
        """
        if self.is_connected:
            return Done # no need for intermediate updates
        try:
            self.connectStart()
            if self._last_error:
                self.log.info('connected')
                self._last_error = 'connected'
                self.callCallbacks()
                return Done
        except Exception as e:
            if str(e) == self._last_error:
                raise CommunicationSilentError(str(e))
            self._last_error = str(e)
            self.log.error(self._last_error)
            raise
        return Done

    def write_is_connected(self, value):
        """value = True: connect if not yet done
        value = False: disconnect (will be reconnected automatically)
        """
        if not value:
            self.closeConnection()
            return False
        return self.read_is_connected()

    def connectStart(self):
        if not self.is_connected:
            self.createConnection()
            for command, regexp in self.identification:
                reply = self.do_communicate(command)
                if not re.match(regexp, reply):
                    self.closeConnection()
                    raise CommunicationFailedError('bad response: %s does not match %s' %
                        (reply, regexp))

    def registerReconnectCallback(self, name, func):
        """register reconnect callback

        if the callback fails or returns False, it is cleared
        """
        if self._reconnectCallbacks is None:
            self._reconnectCallbacks = {name: func}
        else:
            self._reconnectCallbacks[name] = func

    def callCallbacks(self):
        for key, cb in list(self._reconnectCallbacks.items()):
            try:
                removeme = not cb()
            except Exception as e:
                self.log.error('callback: %s' % e)
                removeme = True
            if removeme:
                self._reconnectCallbacks.pop(key)

    def do_communicate(self, command):
        '''send a command and receive a reply

        using end_of_line, encoding and self._lock
        for commands without reply, join it with a query command,
        wait_before is respected for end_of_lines within a command.
        '''
        if not self.is_connected:
            self.read_is_connected() # try to reconnect
        try:
            with self._lock:
                # read garbage and wait before send
                if self.wait_before:
                    cmds = command.split(self.end_of_line)
                else:
                    cmds = [command]
                garbage = None
                for cmd in cmds:
                    if self.wait_before:
                        time.sleep(self.wait_before)
                    if garbage is None: # read garbage only once
                        garbage = b''
                        data = self.readWithTimeout(0)
                        while data:
                            garbage += data
                            data = self.readWithTimeout(0)
                        if garbage:
                            self.log.debug('garbage: %s', garbage.decode(self.encoding))
                    self.writeBytes((cmd + self.end_of_line).encode(self.encoding))
                timeout = self.timeout
                buffer = b''
                data = True
                while data:
                    data = self.readWithTimeout(timeout)
                    buffer += data
                    if self._end_of_line in buffer:
                        break
                else:
                    raise CommunicationFailedError('timeout')
                reply = buffer.split(self._end_of_line, 1)[0].decode(self.encoding)
                self.log.debug('recv: %s', reply)
                return reply
        except Exception as e:
            if str(e) == self._last_error:
                raise CommunicationSilentError(str(e))
            self._last_error = str(e)
            self.log.error(self._last_error)
            raise

    def do_multicomm(self, commands):
        replies = []
        with self._lock:
            for cmd in commands:
                replies.append(self.do_communicate(cmd))
        return replies


class HasIodev(Module):
    """Mixin for modules using a communicator"""
    properties = {
        'iodev': Attached(),
        'uri': Property('uri for auto creation of iodev', StringType(), default=''),
    }

    def __init__(self, name, logger, opts, srv):
        super().__init__(name, logger, opts, srv)
        if self.uri:
            opts = {'uri': self.uri, 'description': 'communication device for %s' % name,
                    'export': False}
            ioname = name + '_iodev'
            iodev = self.iodevClass(ioname, self.log.getChild(ioname), opts, srv)
            srv.modules[ioname] = iodev
            self.setProperty('iodev', ioname)

    def initModule(self):
        try:
            self._iodev.read_is_connected()
        except (CommunicationFailedError, AttributeError):
            pass
        super().initModule()

    def sendRecv(self, command):
        return self._iodev.do_communicate(command)
