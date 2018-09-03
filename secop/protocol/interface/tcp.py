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

import socket
import collections

try:
    import socketserver  # py3
except ImportError:
    import SocketServer as socketserver  # py2

from secop.lib import formatExtendedStack, formatException
from secop.protocol.messages import HELPREPLY, Message, HelpMessage
from secop.errors import SECoPError


DEF_PORT = 10767
MAX_MESSAGE_SIZE = 1024

EOL = b'\n'
CR = b'\r'
SPACE = b' '


def encode_msg_frame(action, specifier=None, data=None):
    """ encode a msg_tripel into an msg_frame, ready to be sent

    action (and optional specifier) are unicode strings,
    data may be an json-yfied python object"""
    action = action.encode('utf-8')
    if specifier is None:
        # implicit: data is None
        return b''.join((action, EOL))
    specifier = specifier.encode('utf-8')
    if data:
        data = data.encode('utf-8')
        return b''.join((action, SPACE, specifier, SPACE, data, EOL))
    return b''.join((action, SPACE, specifier, EOL))


def get_msg(_bytes):
    """try to deframe the next msg in (binary) input
    always return a tupel (msg, remaining_input)
    msg may also be None
    """
    if EOL not in _bytes:
        return None, _bytes
    return _bytes.split(EOL, 1)


def decode_msg(msg):
    """decode the (binary) msg into a (unicode) msg_tripel"""
    # check for leading/trailing CR and remove it
    if msg and msg[0] == CR:
        msg = msg[1:]
    if msg and msg[-1] == CR:
        msg = msg[:-1]

    res = msg.split(b' ', 2)
    action = res[0].decode('utf-8')
    if len(res) == 1:
        return action, None, None
    specifier = res[1].decode('utf-8')
    if len(res) == 2:
        return action, specifier, None
    data = res[2].decode('utf-8')
    return action, specifier, data


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
                #outmsg.mkreply()
                outdata = encode_msg_frame(*outmsg.serialize())
#                outframes = self.encoding.encode(outmsg)
#                outdata = self.framing.encode(outframes)
                try:
                    mysocket.sendall(outdata)
                except Exception:
                    return

            # XXX: improve: use polling/select here?
            try:
                newdata = mysocket.recv(MAX_MESSAGE_SIZE)
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
                if not origin:  # empty string -> send help message
                    for idx, line in enumerate(HelpMessage.splitlines()):
                        msg = Message(HELPREPLY, specifier='%d' % idx)
                        msg.data = line
                        self.queue_async_reply(msg)
                    continue
                msg = decode_msg(origin)
                # construct msgObj from msg
                try:
                    msgObj = Message(*msg)
                    msgObj.origin = origin.decode('latin-1')
                    msgObj = serverobj.dispatcher.handle_request(self, msgObj)
                except SECoPError as err:
                    msgObj.set_error(err.name, str(err), {'exception': formatException(),
                                                          'traceback': formatExtendedStack()})
                except Exception as err:
                    # create Error Obj instead
                    msgObj.set_error(u'Internal', str(err), {'exception': formatException(),
                                                          'traceback':formatExtendedStack()})
                    print('--------------------')
                    print(formatException())
                    print('--------------------')
                    print(formatExtendedStack())
                    print('====================')

                if msgObj:
                    self.queue_reply(msgObj)

    def queue_async_reply(self, data):
        """called by dispatcher for async data units"""
        if data:
            self._queue.append(data)
        else:
            self.log.error('should async_queue empty data!')

    def queue_reply(self, data):
        """called by dispatcher to queue (sync) replies"""
        # sync replies go first!
        if data:
            self._queue.appendleft(data)
        else:
            self.log.error('should queue empty data!')

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

    def __init__(self, logger, interfaceopts, dispatcher):
        self.dispatcher = dispatcher
        self.log = logger
        bindto = interfaceopts.pop('bindto', 'localhost')
        portnum = int(interfaceopts.pop('bindport', DEF_PORT))
        if ':' in bindto:
            bindto, _port = bindto.rsplit(':')
            portnum = int(_port)

        self.log.info("TCPServer binding to %s:%d" % (bindto, portnum))
        socketserver.ThreadingTCPServer.__init__(
            self, (bindto, portnum), TCPRequestHandler, bind_and_activate=True)
        self.log.info("TCPServer initiated")
