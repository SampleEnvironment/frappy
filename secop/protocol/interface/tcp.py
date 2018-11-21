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
#
# *****************************************************************************
"""provides tcp interface to the SECoP Server"""
from __future__ import print_function

import sys
import socket
import collections

try:
    import socketserver  # py3
except ImportError:
    import SocketServer as socketserver  # py2

from secop.lib import formatExtendedStack, formatException, formatExtendedTraceback
from secop.protocol.messages import HELPREQUEST, HELPREPLY, HelpMessage
from secop.errors import SECoPError
from secop.protocol.interface import encode_msg_frame, get_msg, decode_msg


DEF_PORT = 10767
MESSAGE_READ_SIZE = 1024


CR = b'\r'
SPACE = b' '




class TCPRequestHandler(socketserver.BaseRequestHandler):

    def setup(self):
        self.log = self.server.log
        # Queue of msgObjects to send
        self._queue = collections.deque(maxlen=100)
#        self.framing = self.server.framingCLS()
#        self.encoding = self.server.encodingCLS()

    def handle(self):
        """handle a new tcp-connection"""
        # copy state info
        mysocket = self.request
        clientaddr = self.client_address
        serverobj = self.server
        self.log.info("handling new connection from %s:%d" % clientaddr)
        data = b''

        # notify dispatcher of us
        serverobj.dispatcher.add_connection(self)

        mysocket.settimeout(.3)
        #        mysocket.setblocking(False)
        # start serving
        while True:
            # send replys first, then listen for requests, timing out after 0.1s
            while self._queue:
                # put message into encoder to get frame(s)
                # put frame(s) into framer to get bytestring
                # send bytestring
                outmsg = self._queue.popleft()
                if not outmsg:
                    outmsg = ('error','InternalError', ['<unknown origin>', 'trying to send none-data', {}])
                if len(outmsg) > 3:
                    outmsg = ('error', 'InternalError', ['<unknown origin>', 'bad message format', {'msg':outmsg}])
                outdata = encode_msg_frame(*outmsg)
                try:
                    mysocket.sendall(outdata)
                except Exception:
                    return

            # XXX: improve: use polling/select here?
            try:
                newdata = mysocket.recv(MESSAGE_READ_SIZE)
                if not newdata:
                    # no timeout error, but no new data -> connection closed
                    return
                data = data + newdata
            except socket.timeout as e:
                continue
            except socket.error as e:
                self.log.exception(e)
                return
            # XXX: should use select instead of busy polling
            if not data:
                continue
            # put data into (de-) framer,
            # put frames into (de-) coder and if a message appear,
            # call dispatcher.handle_request(self, message)
            # dispatcher will queue the reply before returning
            while True:
                origin, data = get_msg(data)
                if origin is None:
                    break  # no more messages to process
                origin = origin.strip()
                if origin and origin[0] == CR:
                    origin = origin[1:]
                if origin and origin[-1] == CR:
                    origin = origin[:-1]
                if origin in (HELPREQUEST, ''):  # empty string -> send help message
                    for idx, line in enumerate(HelpMessage.splitlines()):
                        self.queue_async_reply((HELPREPLY, '%d' % (idx+1), line))
                    continue
                msg = decode_msg(origin)
                result = None
                try:
                    result = serverobj.dispatcher.handle_request(self, msg)
                    if (msg[0] == 'read') and result:
                        # read should only trigger async_replies
                        self.queue_async_reply(('error', 'InternalError', [origin,
                                                'read should only trigger async data units']))
                except SECoPError as err:
                    result = ('error', err.name, [origin, str(err), {'exception': formatException(),
                                                          'traceback': formatExtendedStack()}])
                except Exception as err:
                    # create Error Obj instead
                    result = ('error', 'InternalError', [origin, str(err), {'exception': formatException(),
                                                          'traceback': formatExtendedStack()}])
                    print('--------------------')
                    print(formatException())
                    print('--------------------')
                    print(formatExtendedTraceback(sys.exc_info()))
                    print('====================')

                if not result:
                    self.log.error('empty result upon msg %s' % repr(msg))
                self.queue_async_reply(result)

    def queue_async_reply(self, data):
        """called by dispatcher for async data units"""
        if data:
            self._queue.append(data)
        else:
            self.log.error('should async_queue empty data!')

    def finish(self):
        """called when handle() terminates, i.e. the socket closed"""
        self.log.info('closing connection from %s:%d' % self.client_address)
        # notify dispatcher
        self.server.dispatcher.remove_connection(self)
        # close socket
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        finally:
            self.request.close()


class TCPServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, name, logger, options, srv):
        self.dispatcher =srv.dispatcher
        self.name = name
        self.log = logger
        bindto = options.pop('bindto', 'localhost')
        portnum = int(options.pop('bindport', DEF_PORT))
        if ':' in bindto:
            bindto, _port = bindto.rsplit(':')
            portnum = int(_port)

        self.log.info("TCPServer %s binding to %s:%d" % (name, bindto, portnum))
        socketserver.ThreadingTCPServer.__init__(
            self, (bindto, portnum), TCPRequestHandler, bind_and_activate=True)
        self.log.info("TCPServer initiated")
