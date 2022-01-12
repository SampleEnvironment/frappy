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
"""stream oriented input / output

May be used for TCP/IP as well for serial IO or
other future extensions of AsynConn
"""

import re
import time
import threading

from secop.lib.asynconn import AsynConn, ConnectionClosed
from secop.datatypes import ArrayOf, BLOBType, BoolType, FloatRange, IntRange, \
    StringType, TupleOf, ValueType
from secop.errors import CommunicationFailedError, CommunicationSilentError, \
    ConfigError, ProgrammingError
from secop.modules import Attached, Command, \
    Communicator, Done, Module, Parameter, Property
from secop.lib import generalConfig


generalConfig.defaults['legacy_hasiodev'] = False
HEX_CODE = re.compile(r'[0-9a-fA-F][0-9a-fA-F]$')


class HasIO(Module):
    """Mixin for modules using a communicator"""
    io = Attached()
    uri = Property('uri for automatic creation of the attached communication module',
                   StringType(), default='')

    ioDict = {}
    ioClass = None

    def __init__(self, name, logger, opts, srv):
        io = opts.get('io')
        super().__init__(name, logger, opts, srv)
        if self.uri:
            opts = {'uri': self.uri, 'description': 'communication device for %s' % name,
                    'export': False}
            ioname = self.ioDict.get(self.uri)
            if not ioname:
                ioname = io or name + '_io'
                io = self.ioClass(ioname, srv.log.getChild(ioname), opts, srv)  # pylint: disable=not-callable
                io.callingModule = []
                srv.modules[ioname] = io
                self.ioDict[self.uri] = ioname
            self.io = ioname
        elif not io:
            raise ConfigError("Module %s needs a value for either 'uri' or 'io'" % name)

    def initModule(self):
        try:
            self.io.read_is_connected()
        except (CommunicationFailedError, AttributeError):
            # AttributeError: read_is_connected is not required for an io object
            pass
        super().initModule()

    def communicate(self, *args):
        return self.io.communicate(*args)

    def multicomm(self, *args):
        return self.io.multicomm(*args)


class HasIodev(HasIO):
    # TODO: remove this legacy mixin
    iodevClass = None

    @property
    def _iodev(self):
        return self.io

    def __init__(self, name, logger, opts, srv):
        self.ioClass = self.iodevClass
        super().__init__(name, logger, opts, srv)
        if generalConfig.legacy_hasiodev:
            self.log.warn('using the HasIodev mixin is deprecated - use HasIO instead')
        else:
            self.log.error('legacy HasIodev no longer supported')
            self.log.error('you may suppress this error message by running the server with --relaxed')
            raise ProgrammingError('legacy HasIodev no longer supported')
        self.sendRecv = self.communicate


class IOBase(Communicator):
    """base of StringIO and BytesIO"""
    uri = Property('hostname:portnumber', datatype=StringType())
    timeout = Parameter('timeout', datatype=FloatRange(0), default=2)
    wait_before = Parameter('wait time before sending', datatype=FloatRange(), default=0)
    is_connected = Parameter('connection state', datatype=BoolType(), readonly=False, default=False)
    pollinterval = Parameter('reconnect interval', datatype=FloatRange(0), readonly=False, default=10)

    _reconnectCallbacks = None
    _conn = None
    _last_error = None
    _lock = None

    def earlyInit(self):
        super().earlyInit()
        self._lock = threading.RLock()

    def connectStart(self):
        raise NotImplementedError

    def closeConnection(self):
        """close connection

        self.is_connected MUST be set to False by implementors
        """
        self._conn.disconnect()
        self._conn = None
        self.is_connected = False

    def doPoll(self):
        self.read_is_connected()

    def read_is_connected(self):
        """try to reconnect, when not connected

        self.is_connected is changed only by self.connectStart or self.closeConnection
        """
        if self.is_connected:
            return Done  # no need for intermediate updates
        try:
            self.connectStart()
            if self._last_error:
                self.log.info('connected')
                self._last_error = 'connected'
                self.callCallbacks()
                return Done
        except Exception as e:
            if str(e) == self._last_error:
                raise CommunicationSilentError(str(e)) from e
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

    def communicate(self, command):
        return NotImplementedError


class StringIO(IOBase):
    """line oriented communicator

    self healing is assured by polling the parameter 'is_connected'
    """
    end_of_line = Property('end_of_line character', datatype=ValueType(),
                           default='\n', settable=True)
    encoding = Property('used encoding', datatype=StringType(),
                        default='ascii', settable=True)
    identification = Property('''
                              identification

                              a list of tuples with commands and expected responses as regexp,
                              to be sent on connect''',
                              datatype=ArrayOf(TupleOf(StringType(), StringType())), default=[], export=False)

    def _convert_eol(self, value):
        if isinstance(value, str):
            return value.encode(self.encoding)
        if isinstance(value, int):
            return bytes([value])
        if isinstance(value, bytes):
            return value
        raise ValueError('invalid end_of_line: %s' % repr(value))

    def earlyInit(self):
        super().earlyInit()
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

    def connectStart(self):
        if not self.is_connected:
            uri = self.uri
            self._conn = AsynConn(uri, self._eol_read)
            self.is_connected = True
            for command, regexp in self.identification:
                reply = self.communicate(command)
                if not re.match(regexp, reply):
                    self.closeConnection()
                    raise CommunicationFailedError('bad response: %s does not match %s' %
                                                   (reply, regexp))

    @Command(StringType(), result=StringType())
    def communicate(self, command):
        """send a command and receive a reply

        using end_of_line, encoding and self._lock
        for commands without reply, the command must be joined with a query command,
        wait_before is respected for end_of_lines within a command.
        """
        command = command.encode(self.encoding)
        if not self.is_connected:
            self.read_is_connected()  # try to reconnect
            if not self._conn:
                self.log.debug('can not connect to %r' % self.uri)
                raise CommunicationSilentError('can not connect to %r' % self.uri)
        try:
            with self._lock:
                # read garbage and wait before send
                if self.wait_before and self._eol_write:
                    cmds = command.split(self._eol_write)
                else:
                    cmds = [command]
                garbage = None
                try:
                    for cmd in cmds:
                        if self.wait_before:
                            time.sleep(self.wait_before)
                        if garbage is None:  # read garbage only once
                            garbage = self._conn.flush_recv()
                            if garbage:
                                self.comLog('garbage: %r', garbage)
                        self._conn.send(cmd + self._eol_write)
                        self.comLog('> %s', cmd.decode(self.encoding))
                    reply = self._conn.readline(self.timeout)
                except ConnectionClosed as e:
                    self.closeConnection()
                    raise CommunicationFailedError('disconnected') from None
                reply = reply.decode(self.encoding)
                self.comLog('< %s', reply)
                return reply
        except Exception as e:
            if str(e) == self._last_error:
                raise CommunicationSilentError(str(e)) from None
            self._last_error = str(e)
            self.log.error(self._last_error)
            raise

    @Command(ArrayOf(StringType()), result=ArrayOf(StringType()))
    def multicomm(self, commands):
        """communicate multiple request/replies in one row"""
        replies = []
        with self._lock:
            for cmd in commands:
                replies.append(self.communicate(cmd))
        return replies


def make_regexp(string):
    """create a bytes regexp pattern from a string describing a bytes pattern

    :param string: a string containing white space separated items containing either
        - a two digit hexadecimal number (byte value)
        - a character from first unicode page, to be replaced by its code
        - ?? indicating any byte

    :return: a tuple of length and compiled re pattern
        Example: make_regexp('00 ff A ??') == (4, re.compile(b'\x00\xffA.'))
    """
    relist = [b'.' if c == '??' else
              re.escape(bytes([int(c, 16) if HEX_CODE.match(c) else ord(c)]))
              for c in string.split()]
    return len(relist), re.compile(b''.join(relist) + b'$')


def make_bytes(string):
    """create bytes from a string describing bytes

    :param string: a string containing white space separated items containing either
        - a two digit hexadecimal number (byte value)
        - a character from first unicode page, to be replaced by its code

    :return: the bytes
        Example: make_bytes('02 A 20 B 03') == b'\x02A B\x03'
    """
    return bytes([int(c, 16) if HEX_CODE.match(c) else ord(c) for c in string.split()])


def hexify(bytes_):
    return ' '.join('%02x' % r for r in bytes_)


class BytesIO(IOBase):
    identification = Property(
        """identification

        a list of tuples with requests and expected responses, to be sent on connect.
        requests and responses are whitespace separated items
        an item is either:
        - a two digit hexadecimal number (byte value)
        - a character
        - ?? indicating ignored bytes in responses
        """, datatype=ArrayOf(TupleOf(StringType(), StringType())), default=[], export=False)

    def connectStart(self):
        if not self.is_connected:
            uri = self.uri
            self._conn = AsynConn(uri, b'')
            self.is_connected = True
            for request, expected in self.identification:
                replylen, replypat = make_regexp(expected)
                reply = self.communicate(make_bytes(request), replylen)
                if not replypat.match(reply):
                    self.closeConnection()
                    raise CommunicationFailedError('bad response: %r does not match %r' % (reply, expected))

    @Command((BLOBType(), IntRange(0)), result=BLOBType())
    def communicate(self, request, replylen):  # pylint: disable=arguments-differ
        """send a request and receive (at least) <replylen> bytes as reply"""
        if not self.is_connected:
            self.read_is_connected()  # try to reconnect
            if not self._conn:
                raise CommunicationSilentError('can not connect to %r' % self.uri)
        try:
            with self._lock:
                # read garbage and wait before send
                try:
                    if self.wait_before:
                        time.sleep(self.wait_before)
                    garbage = self._conn.flush_recv()
                    if garbage:
                        self.comLog('garbage: %r', garbage)
                    self._conn.send(request)
                    self.comLog('> %s', hexify(request))
                    reply = self._conn.readbytes(replylen, self.timeout)
                except ConnectionClosed as e:
                    self.closeConnection()
                    raise CommunicationFailedError('disconnected') from None
                self.comLog('< %s', hexify(reply))
                return self.getFullReply(request, reply)
        except Exception as e:
            if str(e) == self._last_error:
                raise CommunicationSilentError(str(e)) from None
            self._last_error = str(e)
            self.log.error(self._last_error)
            raise

    @Command((ArrayOf(TupleOf(BLOBType(), IntRange(0)))), result=ArrayOf(BLOBType()))
    def multicomm(self, requests):
        """communicate multiple request/replies in one row"""
        replies = []
        with self._lock:
            for request in requests:
                replies.append(self.communicate(*request))
        return replies

    def readBytes(self, nbytes):
        """read bytes

        :param nbytes: the number of expected bytes
        :return: the returned bytes
        """
        return self._conn.readbytes(nbytes, self.timeout)

    def getFullReply(self, request, replyheader):
        """to be overwritten in case the reply length is variable

        :param request: the request
        :param replyheader: the already received bytes
        :return: the full reply (replyheader + additional bytes)

        When the reply length is variable, :meth:`communicate` should be called
        with the `replylen` argument set to the minimum expected length of the reply.
        Typically this method determines then the length of additional bytes from
        the already received bytes (replyheader) and/or the request and calls
        :meth:`readBytes` to get the remaining bytes.

        Remark: this mechanism avoids the need to call readBytes after communicate
        separately, which would not honour the lock properly.
        """
        return replyheader
