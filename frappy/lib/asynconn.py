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
synchronous IO (see frappy.io)
"""

import ast
import select
import socket
import time
import re

from frappy.errors import CommunicationFailedError, ConfigError
from frappy.lib import closeSocket, parse_host_port, SECoP_DEFAULT_PORT

try:
    from serial import Serial
except ImportError:
    Serial = None


class ConnectionClosed(ConnectionError):
    pass


class AsynConn:
    timeout = 1  # inter byte timeout
    scheme = None
    SCHEME_MAP = {}
    connection = None  # is not None, if connected
    HOSTNAMEPAT = re.compile(r'[a-z0-9_.-]+$', re.IGNORECASE)  # roughly checking if it is a valid hostname

    def __new__(cls, uri, end_of_line=b'\n', default_settings=None):
        scheme = uri.split('://')[0]
        iocls = cls.SCHEME_MAP.get(scheme, None)
        if not iocls:
            # try tcp, if scheme not given
            try:
                parse_host_port(uri, 1)  # check hostname only
            except ValueError:
                if 'COM' in uri:
                    raise ValueError("the correct uri for a COM port is: "
                                     "'serial://COM<i>[?<option>=<value>[&<option>=value ...]]'") from None
                if '/dev' in uri:
                    raise ValueError("the correct uri for a serial port is: "
                                     "'serial:///dev/<tty>[?<option>=<value>[&<option>=value ...]]'") from None
                raise ValueError(f'invalid hostname {uri!r}') from None
            iocls = cls.SCHEME_MAP['tcp']
        return object.__new__(iocls)

    def __init__(self, uri, end_of_line=b'\n', default_settings=None):
        self.end_of_line = end_of_line
        self.default_settings = default_settings or {}
        self._rxbuffer = b''

    def __del__(self):
        self.disconnect()

    @classmethod
    def __init_subclass__(cls):
        """register subclass to scheme, if available"""
        if cls.scheme:
            cls.SCHEME_MAP[cls.scheme] = cls

    def shutdown(self):
        """prepare connection for disconnect, can be empty"""

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
                    raise TimeoutError(f'timeout in readline ({timeout:g} sec)')
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
                    raise TimeoutError(f'timeout in readbytes ({timeout:g} sec)')
                return None
            self._rxbuffer += data
        line = self._rxbuffer[:nbytes]
        self._rxbuffer = self._rxbuffer[nbytes:]
        return line

    def writeline(self, line):
        self.send(line + self.end_of_line)


class AsynTcp(AsynConn):
    """a tcp/ip connection

    uri syntax::

       tcp://<host address>:<port number>
    """
    scheme = 'tcp'

    def __init__(self, uri, *args, **kwargs):
        super().__init__(uri, *args, **kwargs)
        self.uri = uri
        if uri.startswith('tcp://'):
            uri = uri[6:]
        try:

            host, port = parse_host_port(uri, self.default_settings.get('port', SECoP_DEFAULT_PORT))
            self.connection = socket.create_connection((host, port), timeout=self.timeout)
        except (ConnectionRefusedError, socket.gaierror, socket.timeout) as e:
            # indicate that retrying might make sense
            raise CommunicationFailedError(f'can not connect to {host}:{port}, {e}') from None

    def shutdown(self):
        if self.connection:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # in case socket is already disconnected

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
            data = self.connection.recv(1024*1024)
            if data:
                return data
        except (socket.timeout, TimeoutError):
            # timeout while waiting
            return b''
        except ConnectionResetError:
            pass  # treat equally as a gracefully disconnected peer
        # note that when no data is sent on a connection, an interruption might
        # not be detected within a reasonable time. sending a heartbeat should
        # help in this case.
        raise ConnectionClosed()  # marks end of connection


class AsynSerial(AsynConn):
    """a serial connection using pyserial

    uri syntax::

      serial://<serial device>?[<option>=<value>[&<option>=<value> ...]]

      options (defaults, other examples):

      baudrate=9600  # 4800, 115200
      bytesize=8     # 5,6,7
      parity=none    # even, odd, mark, space
      stopbits=1     # 1.5, 2
      xonxoff=False  # True

      and others (see documentation of serial.Serial)
    """
    scheme = 'serial'
    PARITY_NAMES = {name[0]: name for name in ['NONE', 'ODD', 'EVEN', 'MARK', 'SPACE']}
    ARG_SEP = re.compile('[+&]')  # allow + or & as options separator in uri
    SETTINGS = set(Serial(None).get_settings()) if Serial else None  # keys of valid Serial settings

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
        options = {k: v for k, v in self.default_settings.items() if k in self.SETTINGS}
        if len(uri) > 1:
            for kv in self.ARG_SEP.split(uri[1]):
                try:
                    key, value = kv.split('=')
                except TypeError:
                    raise ConfigError(f'{kv!r} must be <key>=<value>') from None
                if key == 'parity':
                    options[key] = value
                else:
                    options[key] = ast.literal_eval(value.title())  # title(): turn false/true into False/True
        parity = options.get('parity')
        if parity:
            name = parity.upper()
            fullname = self.PARITY_NAMES[name[0]]
            if not fullname.startswith(name):
                raise ConfigError(f'illegal parity: {parity}')
            options['parity'] = name[0]
        if 'timeout' not in options:
            options['timeout'] = self.timeout
        try:
            self.connection = Serial(dev, **options)
        except ValueError as e:
            raise ConfigError(e) from None
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
