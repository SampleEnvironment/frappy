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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

"""provides tcp interface to the SECoP Server"""

import os
import socket
import collections
import SocketServer

DEF_PORT = 10767
MAX_MESSAGE_SIZE = 1024


class TCPRequestHandler(SocketServer.BaseRequestHandler):
    def setup(self):
        self.log = self.server.log
        self._queue = collections.deque(maxlen=100)

    def handle(self):
        """handle a new tcp-connection"""
        # copy state info
        mysocket = self.request
        clientaddr = self.client_address
        serverobj = self.server
        self.log.debug("handling new connection from %s" % repr(clientaddr))
        # notify dispatcher of us
        serverobj.dispatcher.add_connection(self)

        mysocket.settimeout(.3)
        mysocket.setblocking(False)
        # start serving
        while True:
            # send replys fist, then listen for requests, timing out after 0.1s
            while self._queue:
                mysocket.sendall(self._queue.popleft())
            # XXX: improve: use polling/select here?
            try:
                data = mysocket.recv(MAX_MESSAGE_SIZE)
            except (socket.timeout, socket.error) as e:
                continue
            # XXX: should use select instead of busy polling
            if not data:
                continue
            # dispatcher will queue the reply before returning
            serverobj.dispatcher.handle_request(self, data)

    def queue_async_reply(self, data):
        """called by dispatcher for async data units"""
        self._queue.append(data)

    def queue_reply(self, data):
        """called by dispatcher to queue (sync) replies"""
        # sync replies go first!
        self._queue.appendleft(data)

    def finish(self):
        """called when handle() terminates, i.e. the socket closed"""
        # notify dispatcher
        self.server.dispatcher.remove_connection(self)
        # close socket
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        finally:
            self.request.close()


class TCPServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, logger, serveropts, dispatcher):
        self.dispatcher = dispatcher
        self.log = logger
        bindto = serveropts.pop('bindto', 'localhost')
        portnum = int(serveropts.pop('bindport', DEF_PORT))
        if ':' in bindto:
            bindto, _port = bindto.rsplit(':')
            portnum = int(_port)
        self.log.debug("TCPServer binding to %s:%d" % (bindto, portnum))
        SocketServer.ThreadingTCPServer.__init__(self, (bindto, portnum),
                                                 TCPRequestHandler,
                                                 bind_and_activate=True)
        self.log.info("TCPServer initiated")
