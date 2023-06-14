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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""provides tcp interface to the SECoP Server"""

import errno
import os
import socket
import socketserver
import sys
import threading
import time

from frappy.datatypes import BoolType, StringType
from frappy.errors import SECoPError
from frappy.lib import formatException, formatExtendedStack, \
    formatExtendedTraceback
from frappy.properties import Property
from frappy.protocol.interface import decode_msg, encode_msg_frame, get_msg
from frappy.protocol.messages import ERRORPREFIX, HELPREPLY, HELPREQUEST, \
    HelpMessage

DEF_PORT = 10767
MESSAGE_READ_SIZE = 1024
HELP = HELPREQUEST.encode()


class TCPRequestHandler(socketserver.BaseRequestHandler):

    def setup(self):
        self.log = self.server.log
        self.running = True
        self.send_lock = threading.Lock()

    def handle(self):
        """handle a new tcp-connection"""
        # copy state info
        mysocket = self.request
        clientaddr = self.client_address
        serverobj = self.server

        self.log.info("handling new connection from %s",  format_address(clientaddr))
        data = b''

        # notify dispatcher of us
        serverobj.dispatcher.add_connection(self)

        # copy relevant settings from Interface
        detailed_errors = serverobj.detailed_errors

        mysocket.settimeout(1)
        # start serving
        while self.running:
            try:
                newdata = mysocket.recv(MESSAGE_READ_SIZE)
                if not newdata:
                    # no timeout error, but no new data -> connection closed
                    return
                data = data + newdata
            except socket.timeout:
                continue
            except socket.error as e:
                self.log.exception(e)
                return
            if not data:
                continue
            # put data into (de-) framer,
            # put frames into (de-) coder and if a message appear,
            # call dispatcher.handle_request(self, message)
            # dispatcher will queue the reply before returning
            while self.running:
                origin, data = get_msg(data)
                if origin is None:
                    break  # no more messages to process
                origin = origin.strip()
                if origin in (HELP, b''):  # empty string -> send help message
                    for idx, line in enumerate(HelpMessage.splitlines()):
                        # not sending HELPREPLY here, as there should be only one reply for every request
                        self.send_reply(('_', f'{idx + 1}', line))
                    # ident matches request
                    self.send_reply((HELPREPLY, None, None))
                    continue
                try:
                    msg = decode_msg(origin)
                except Exception as err:
                    # we have to decode 'origin' here
                    # use latin-1, as utf-8 or ascii may lead to encoding errors
                    msg = origin.decode('latin-1').split(' ', 3) + [None]  # make sure len(msg) > 1
                    result = (ERRORPREFIX + msg[0], msg[1], ['InternalError', str(err),
                                                             {'exception': formatException(),
                                                              'traceback': formatExtendedStack()}])
                    print('--------------------')
                    print(formatException())
                    print('--------------------')
                    print(formatExtendedTraceback(sys.exc_info()))
                    print('====================')
                else:
                    try:
                        result = serverobj.dispatcher.handle_request(self, msg)
                    except SECoPError as err:
                        result = (ERRORPREFIX + msg[0], msg[1], [err.name, str(err),
                                                                 {'exception': formatException(),
                                                                  'traceback': formatExtendedStack()}])
                    except Exception as err:
                        # create Error Obj instead
                        result = (ERRORPREFIX + msg[0], msg[1], ['InternalError', repr(err),
                                                                 {'exception': formatException(),
                                                                  'traceback': formatExtendedStack()}])
                        print('--------------------')
                        print(formatException())
                        print('--------------------')
                        print(formatExtendedTraceback(sys.exc_info()))
                        print('====================')

                if not result:
                    self.log.error('empty result upon msg %s', repr(msg))
                if result[0].startswith(ERRORPREFIX) and not detailed_errors:
                    # strip extra information
                    result[2][2].clear()
                self.send_reply(result)

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

    def finish(self):
        """called when handle() terminates, i.e. the socket closed"""
        self.log.info('closing connection from %s', format_address(self.client_address))
        # notify dispatcher
        self.server.dispatcher.remove_connection(self)
        # close socket
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        finally:
            self.request.close()

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
                        default=f'tcp://{DEF_PORT}', export=False),
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

    # py35 compatibility
    if not hasattr(socketserver.ThreadingTCPServer, '__exit__'):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.server_close()

def format_address(addr):
    if len(addr) == 2:
        return '%s:%d' % addr
    address, port = addr[0:2]
    if address.startswith('::ffff'):
        return '%s:%d' % (address[7:], port)
    return '[%s]:%d' % (address, port)
