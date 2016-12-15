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

from secop.protocol.encoding import ENCODERS
from secop.protocol.framing import FRAMERS
from secop.protocol.messages import HelpMessage


class TCPRequestHandler(SocketServer.BaseRequestHandler):

    def setup(self):
        self.log = self.server.log
        self._queue = collections.deque(maxlen=100)
        self.framing = self.server.framingCLS()
        self.encoding = self.server.encodingCLS()

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
#        mysocket.setblocking(False)
        # start serving
        while True:
            # send replys fist, then listen for requests, timing out after 0.1s
            while self._queue:
                # put message into encoder to get frame(s)
                # put frame(s) into framer to get bytestring
                # send bytestring
                outmsg = self._queue.popleft()
                outframes = self.encoding.encode(outmsg)
                outdata = self.framing.encode(outframes)
                mysocket.sendall(outdata)

            # XXX: improve: use polling/select here?
            try:
                data = mysocket.recv(MAX_MESSAGE_SIZE)
            except (socket.timeout, socket.error) as e:
                continue
            # XXX: should use select instead of busy polling
            if not data:
                continue
            # put data into (de-) framer,
            # put frames into (de-) coder and if a message appear,
            # call dispatcher.handle_request(self, message)
            # dispatcher will queue the reply before returning
            frames = self.framing.decode(data)
            if frames is not None:
                if not frames:  # empty list
                    self.queue_reply(HelpMessage(MSGTYPE=reply))
                for frame in frames:
                    reply = None
                    msg = self.encoding.decode(frame)
                    if msg:
                        serverobj.dispatcher.handle_request(self, msg)

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
        except Exception:
            pass
        finally:
            self.request.close()


class TCPServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, logger, interfaceopts, dispatcher):
        self.dispatcher = dispatcher
        self.log = logger
        bindto = interfaceopts.pop('bindto', 'localhost')
        portnum = int(interfaceopts.pop('bindport', DEF_PORT))
        if ':' in bindto:
            bindto, _port = bindto.rsplit(':')
            portnum = int(_port)
        # tcp is a byte stream, so we need Framers (to get frames)
        # and encoders (to en/decode messages from frames)
        self.framingCLS = FRAMERS[interfaceopts.pop('framing', 'none')]
        self.encodingCLS = ENCODERS[interfaceopts.pop('encoding', 'pickle')]
        self.log.debug("TCPServer binding to %s:%d" % (bindto, portnum))
        self.log.debug("TCPServer using framing=%s" % self.framingCLS.__name__)
        self.log.debug("TCPServer using encoding=%s" %
                       self.encodingCLS.__name__)
        SocketServer.ThreadingTCPServer.__init__(self, (bindto, portnum),
                                                 TCPRequestHandler,
                                                 bind_and_activate=True)
        self.log.info("TCPServer initiated")
