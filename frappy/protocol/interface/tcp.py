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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""TCP interface to the SECoP Server"""

import errno
import os
import socket
import socketserver
import time

from frappy.datatypes import BoolType, StringType
from frappy.lib import SECoP_DEFAULT_PORT
from frappy.properties import Property
from frappy.protocol.interface import decode_msg, encode_msg_frame, get_msg
from frappy.protocol.interface.handler import ConnectionClose, \
    RequestHandler, DecodeError
from frappy.protocol.messages import HELPREQUEST


MESSAGE_READ_SIZE = 1024


def format_address(addr):
    if len(addr) == 2:
        return '%s:%d' % addr
    address, port = addr[0:2]
    if address.startswith('::ffff'):
        return '%s:%d' % (address[7:], port)
    return '[%s]:%d' % (address, port)


class TCPRequestHandler(RequestHandler):
    def setup(self):
        super().setup()
        self.request.settimeout(1)
        self.data = b''

    def finish(self):
        """called when handle() terminates, i.e. the socket closed"""
        super().finish()
        # close socket
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        finally:
            self.request.close()

    def ingest(self, newdata):
        self.data += newdata

    def next_message(self):
        try:
            message, self.data = get_msg(self.data)
            if message is None:
                return None
            if message.strip() == b'':
                return (HELPREQUEST, None, None)
            return decode_msg(message)
        except Exception as e:
            raise DecodeError('exception in receive', raw_msg=message) from e

    def receive(self):
        try:
            data = self.request.recv(MESSAGE_READ_SIZE)
            if not data:
                raise ConnectionClose('socket was closed')
            return data
        except socket.timeout:
            return None
        except socket.error as e:
            self.log.exception(e)
            raise ConnectionClose() from e

    def send_reply(self, data):
        """send reply

        stops recv loop on error (including timeout when output buffer full for more than 1 sec)
        """
        if not data:
            self.log.error('should not reply empty data!')
            return
        outdata = encode_msg_frame(*data)
        with self.send_lock:
            if self.running:
                try:
                    self.request.sendall(outdata)
                except (BrokenPipeError, IOError) as e:
                    self.log.debug('send_reply got an %r, connection closed?',
                                   e)
                    self.running = False
                except Exception as e:
                    self.log.error('ERROR in send_reply %r', e)
                    self.running = False

    def format(self):
        return f'from {format_address(self.client_address)}'


class DualStackTCPServer(socketserver.ThreadingTCPServer):
    """Subclassed to provide IPv6 capabilities as socketserver only uses IPv4"""
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True, enable_ipv6=False):
        super().__init__(
                    server_address, RequestHandlerClass, bind_and_activate=False)

        # override default socket
        if enable_ipv6:
            self.address_family = socket.AF_INET6
            self.socket = socket.socket(self.address_family,
                                        self.socket_type)
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except:
                self.server_close()
                raise


class TCPServer(DualStackTCPServer):
    daemon_threads = True
    # on windows, 'reuse_address' means that several servers might listen on
    # the same port, on the other hand, a port is not blocked after closing
    allow_reuse_address = os.name != 'nt'  # False on Windows systems

    # for cfg-editor
    configurables = {
        'uri': Property('hostname or ip address for binding', StringType(),
                        default=f'tcp://{SECoP_DEFAULT_PORT}', export=False),
        'detailed_errors': Property('Flag to enable detailed Errorreporting.', BoolType(),
                                    default=False, export=False),
    }

    def __init__(self, name, logger, options, srv):
        self.dispatcher = srv.dispatcher
        self.name = name
        self.log = logger
        port = int(options.pop('uri').split('://', 1)[-1])
        enable_ipv6 = options.pop('ipv6', False)
        self.detailed_errors = options.pop('detailed_errors', False)

        self.log.info("TCPServer %s binding to port %d", name, port)
        for ntry in range(5):
            try:
                DualStackTCPServer.__init__(
                    self, ('', port), TCPRequestHandler,
                    bind_and_activate=True, enable_ipv6=enable_ipv6
                )
                break
            except OSError as e:
                if e.args[0] == errno.EADDRINUSE:  # address already in use
                    # this may happen despite of allow_reuse_address
                    time.sleep(0.3 * (1 << ntry))  # max accumulated sleep time: 0.3 * 31 = 9.3 sec
                else:
                    self.log.error('could not initialize TCP Server: %r', e)
                    raise
        if ntry:
            self.log.warning('tried again %d times after "Address already in use"', ntry)
        self.log.info("TCPServer initiated")
