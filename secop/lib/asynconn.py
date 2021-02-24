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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

"""asynchronous connections

generic class for byte oriented communication
includes implementation for TCP and Serial connections
support for asynchronous communication, but may be used also for
synchronous IO (see secop.stringio.StringIO)
"""

import ast
import select
import socket
import time

from secop.errors import CommunicationFailedError, ConfigError
from secop.lib import closeSocket, parseHostPort, tcpSocket

try:
    from serial import Serial
except ImportError:
    Serial = None


class ConnectionClosed(ConnectionError):
    pass


class AsynConn:
    timeout = 1  # inter byte timeout
    SCHEME_MAP = {}
    connection = None  # is not None, if connected
    defaultport = None

    def __new__(cls, uri, end_of_line=b'\n'):
        scheme = uri.split('://')[0]
        iocls = cls.SCHEME_MAP.get(scheme, None)
        if not iocls:
            # try tcp, if scheme not given
            try:
                host_port = parseHostPort(uri, cls.defaultport)
            except (ValueError, TypeError, AssertionError):
                if 'COM' in uri:
                    raise ValueError("the correct uri for a COM port is: "
                                     "'serial://COM<i>[?<option>=<value>[+<option>=value ...]]'")
                if '/dev' in uri:
                    raise ValueError("the correct uri for a serial port is: "
                                     "'serial:///dev/<tty>[?<option>=<value>[+<option>=value ...]]'")
                raise ValueError('invalid uri: %s' % uri)
            iocls = cls.SCHEME_MAP['tcp']
            uri = 'tcp://%s:%d' % host_port
        return object.__new__(iocls)

    def __init__(self, uri, end_of_line=b'\n'):
        self.end_of_line = end_of_line
        self._rxbuffer = b''

    def __del__(self):
        self.disconnect()

    @classmethod
    def register_scheme(cls, scheme):
        cls.SCHEME_MAP[scheme] = cls

    def disconnect(self):
        raise NotImplementedError

    def send(self, data):
        """send data (bytes!)

        tries to send all data"""
        raise NotImplementedError

    def recv(self):
        """return bytes received within timeout

        in contrast to socket.recv:
        - returns b'' on timeout
        - raises ConnectionClosed if the other end has disconnected
        """
        raise NotImplementedError

    def flush_recv(self):
        """flush all available bytes (return them)"""
        raise NotImplementedError

    def readline(self, timeout=None):
        """read one line

        return either a complete line or None if no data available within 1 sec (self.timeout)
        if a non-zero timeout is given, a timeout error is raised instead of returning None
        the timeout effectively used will not be lower than self.timeout (1 sec)
        """
        if timeout:
            end = time.time() + timeout
        while True:
            splitted = self._rxbuffer.split(self.end_of_line, 1)
            if len(splitted) == 2:
                line, self._rxbuffer = splitted
                return line
            data = self.recv()
            if not data:
                if timeout:
                    if time.time() < end:
                        continue
                    raise TimeoutError('timeout in readline (%g sec)' % timeout)
                return None
            self._rxbuffer += data

    def readbytes(self, nbytes, timeout=None):
        """read a fixed number of bytes

        return either <nbytes> bytes or None if not enough data available within 1 sec (self.timeout)
        if a non-zero timeout is given, a timeout error is raised instead of returning None
        the timeout effectively used will not be lower than self.timeout (1 sec)
        """
        if timeout:
            end = time.time() + timeout
        while len(self._rxbuffer) < nbytes:
            data = self.recv()
            if not data:
                if timeout:
                    if time.time() < end:
                        continue
                    raise TimeoutError('timeout in readbytes (%g sec)' % timeout)
                return None
            self._rxbuffer += data
        line = self._rxbuffer[:nbytes]
        self._rxbuffer = self._rxbuffer[nbytes:]
        return line

    def writeline(self, line):
        self.send(line + self.end_of_line)


class AsynTcp(AsynConn):
    def __init__(self, uri, *args, **kwargs):
        super().__init__(uri, *args, **kwargs)
        self.uri = uri
        if uri.startswith('tcp://'):
            # should be the case always
            uri = uri[6:]
        try:
            self.connection = tcpSocket(uri, self.defaultport, self.timeout)
        except (ConnectionRefusedError, socket.gaierror) as e:
            # indicate that retrying might make sense
            raise CommunicationFailedError(str(e))

    def disconnect(self):
        if self.connection:
            closeSocket(self.connection)
        self.connection = None

    def send(self, data):
        """send data (bytes!)"""
        # remark: will raise socket.timeout when output buffer is full and blocked for 1 sec
        self.connection.sendall(data)

    def flush_recv(self):
        """flush recv buffer"""
        data = [self._rxbuffer]
        while select.select([self.connection], [], [], 0)[0]:
            data.append(self.recv())
        self._rxbuffer = b''
        return b''.join(data)

    def recv(self):
        """return bytes in the recv buffer

        or bytes received within 1 sec
        """
        try:
            data = self.connection.recv(8192)
            if data:
                return data
        except (socket.timeout, TimeoutError):
            # timeout while waiting
            return b''
        # note that when no data is sent on a connection, an interruption might
        # not be detected within a reasonable time. sending a heartbeat should
        # help in this case.
        raise ConnectionClosed()  # marks end of connection


AsynTcp.register_scheme('tcp')


class AsynSerial(AsynConn):
    """a serial connection using pyserial

    uri syntax:
    serial://<path>?[<option>=<value>[+<option>=<value> ...]]

    options (defaults, other examples):

    baudrate=9600  # 4800, 115200
    bytesize=8     # 5,6,7
    parity=none    # even, odd, mark, space
    stopbits=1     # 1.5, 2
    xonxoff=False  # True

    and others (see documentation of serial.Serial)
    """
    PARITY_NAMES = {name[0]: name for name in ['NONE', 'ODD', 'EVEN', 'MASK', 'SPACE']}

    def __init__(self, uri, *args, **kwargs):
        if Serial is None:
            raise ConfigError('pyserial is not installed')
        super().__init__(uri, *args, **kwargs)
        self.uri = uri
        if uri.startswith('serial://'):
            # should be the case always
            uri = uri[9:]
        uri = uri.split('?', 1)
        dev = uri[0]
        try:
            options = dict((kv.split('=') for kv in uri[1].split('+')))
        except IndexError:  # no uri[1], no options
            options = {}
        except ValueError:
            raise ConfigError('illegal serial options')
        parity = options.pop('parity', None)  # only parity is to be treated as text
        for k, v in options.items():
            try:
                options[k] = ast.literal_eval(v.title())  # title(): turn false/true into False/True
            except ValueError:
                pass
        if parity is not None:
            name = parity.upper()
            fullname = self.PARITY_NAMES[name[0]]
            if not fullname.startswith(name):
                raise ConfigError('illegal parity: %s' % parity)
            options['parity'] = name[0]
        if 'timeout' not in options:
            options['timeout'] = self.timeout
        try:
            self.connection = Serial(dev, **options)
        except ValueError as e:
            raise ConfigError(e)
        # TODO: turn exceptions into ConnectionFailedError, where a retry makes sense

    def disconnect(self):
        if self.connection:
            self.connection.close()
        self.connection = None

    def send(self, data):
        """send data (bytes!)"""
        self.connection.write(data)

    def flush_recv(self):
        result = self._rxbuffer + self.connection.read(self.connection.in_waiting)
        self._rxbuffer = b''
        return result

    def recv(self):
        """return bytes received within 1 sec"""
        if not self.connection:  # disconnect() might have been called in between
            raise ConnectionClosed()
        n = self.connection.in_waiting
        if n:
            return self.connection.read(n)
        data = self.connection.read(1)
        return data + self.connection.read(self.connection.in_waiting)


AsynSerial.register_scheme('serial')
