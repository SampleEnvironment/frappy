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

"""asynchonous connections

generic class for byte oriented communication
includes implementation for TCP connections
"""

import socket
import time

from secop.lib import parseHostPort, tcpSocket, closeSocket


class ConnectionClosed(ConnectionError):
    pass


class AsynConn:
    timeout = 1  # inter byte timeout
    SCHEME_MAP = {}
    connection = None  # is not None, if connected
    defaultport = None

    def __new__(cls, uri):
        scheme = uri.split('://')[0]
        iocls = cls.SCHEME_MAP.get(scheme, None)
        if not iocls:
            # try tcp, if scheme not given
            try:
                host_port = parseHostPort(uri, cls.defaultport)
            except (ValueError, TypeError, AssertionError):
                raise ValueError('invalid uri: %s' % uri)
            iocls = cls.SCHEME_MAP['tcp']
            uri = 'tcp://%s:%d' % host_port
        return object.__new__(iocls)

    def __init__(self, *args):
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

    def readline(self, timeout=None):
        """read one line

        return either a complete line or None in case of timeout
        the timeout argument may increase, but not decrease the default timeout
        """
        if timeout:
            end = time.time() + timeout
        while b'\n' not in self._rxbuffer:
            data = self.recv()
            if not data:
                if timeout:
                    if time.time() < end:
                        continue
                    raise TimeoutError('timeout in readline')
                return None
            self._rxbuffer += data
        line, self._rxbuffer = self._rxbuffer.split(b'\n', 1)
        return line

    def writeline(self, line):
        self.send(line + b'\n')


class AsynTcp(AsynConn):
    def __init__(self, uri):
        super().__init__()
        self.uri = uri
        if uri.startswith('tcp://'):
            # should be the case always
            uri = uri[6:]
        self.connection = tcpSocket(uri, self.defaultport, self.timeout)

    def disconnect(self):
        if self.connection:
            closeSocket(self.connection)
        self.connection = None

    def send(self, data):
        """send data (bytes!)"""
        self.connection.sendall(data)

    def recv(self):
        """return bytes received within 1 sec"""
        try:
            data = self.connection.recv(8192)
            if data:
                return data
        except socket.timeout:
            # timeout while waiting
            return b''
        raise ConnectionClosed()  # marks end of connection

AsynTcp.register_scheme('tcp')
