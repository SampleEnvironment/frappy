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
import threading
import re
from secop.lib.asynconn import AsynConn, ConnectionClosed
from secop.modules import Module, Communicator, Parameter, Command, Property, Attached
from secop.datatypes import StringType, FloatRange, ArrayOf, BoolType, TupleOf, ValueType
from secop.errors import CommunicationFailedError, CommunicationSilentError
from secop.poller import REGULAR
from secop.metaclass import Done


class StringIO(Communicator):
    """line oriented communicator

    self healing is assured by polling the parameter 'is_connected'
    """
    properties = {
        'uri':
            Property('hostname:portnumber', datatype=StringType()),
        'end_of_line':
            Property('end_of_line character', datatype=ValueType(),
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
        self._conn = None
        self._lock = threading.RLock()
        eol = self.end_of_line
        if isinstance(eol, (tuple, list)):
            if len(eol) not in (1, 2):
                raise ValueError('invalid end_of_line: %s' % eol)
        else:
            eol = [eol]
        # eol for read and write might be distinct
        self._eol_read = self._convert_eol(eol[0])
        if not self._eol_read:
            raise ValueError('end_of_line for read must not be empty')
        self._eol_write = self._convert_eol(eol[-1])
        self._last_error = None

    def _convert_eol(self, value):
        if isinstance(value, str):
            return value.encode(self.encoding)
        if isinstance(value, int):
            return bytes([value])
        if isinstance(value, bytes):
            return value
        raise ValueError('invalid end_of_line: %s' % repr(value))

    def connectStart(self):
        if not self.is_connected:
            uri = self.uri
            self._conn = AsynConn(uri, self._eol_read)
            self.is_connected = True
            for command, regexp in self.identification:
                reply = self.do_communicate(command)
                if not re.match(regexp, reply):
                    self.closeConnection()
                    raise CommunicationFailedError('bad response: %s does not match %s' %
                                                   (reply, regexp))
    def closeConnection(self):
        """close connection

        self.is_connected MUST be set to False by implementors
        """
        self._conn.disconnect()
        self._conn = None
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
        """send a command and receive a reply

        using end_of_line, encoding and self._lock
        for commands without reply, the command must be joined with a query command,
        wait_before is respected for end_of_lines within a command.
        """
        if not self.is_connected:
            self.read_is_connected()  # try to reconnect
        try:
            with self._lock:
                # read garbage and wait before send
                if self.wait_before and self._eol_write:
                    cmds = command.encode(self.encoding).split(self._eol_write)
                else:
                    cmds = [command.encode(self.encoding)]
                garbage = None
                try:
                    for cmd in cmds:
                        if self.wait_before:
                            time.sleep(self.wait_before)
                        if garbage is None:  # read garbage only once
                            garbage = self._conn.flush_recv()
                            if garbage:
                                self.log.debug('garbage: %r', garbage)
                        self._conn.send(cmd + self._eol_write)
                    reply = self._conn.readline(self.timeout)
                except ConnectionClosed:
                    self.closeConnection()
                    raise CommunicationFailedError('disconnected')
                reply = reply.decode(self.encoding)
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
    """Mixin for modules using a communicator

    not only StringIO !
    """
    properties = {
        'iodev': Attached(),
        'uri': Property('uri for auto creation of iodev', StringType(), default=''),
    }

    iodevDict = {}

    def __init__(self, name, logger, opts, srv):
        iodev = opts.get('iodev')
        super().__init__(name, logger, opts, srv)
        if self.uri:
            opts = {'uri': self.uri, 'description': 'communication device for %s' % name,
                    'export': False}
            ioname = self.iodevDict.get(self.uri)
            if not ioname:
                ioname = iodev or name + '_iodev'
                iodev = self.iodevClass(ioname, srv.log.getChild(ioname), opts, srv)
                srv.modules[ioname] = iodev
                self.iodevDict[self.uri] = ioname
            self.setProperty('iodev', ioname)

    def initModule(self):
        try:
            self._iodev.read_is_connected()
        except (CommunicationFailedError, AttributeError):
            # AttributeError: for missing _iodev?
            pass
        super().initModule()

    def sendRecv(self, command):
        return self._iodev.do_communicate(command)
