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
"""The common parts of the SECNodes outside interfaces"""

import sys
import threading

from frappy.errors import SECoPError
from frappy.lib import formatException, formatExtendedStack, \
    formatExtendedTraceback
from frappy.protocol.messages import ERRORPREFIX, HELPREPLY, HELPREQUEST, \
    HelpMessage


class DecodeError(Exception):
    def __init__(self, message, raw_msg):
        super().__init__(message)
        self._raw_msg = raw_msg

    @property
    def raw_msg(self):
        return self._raw_msg


class ConnectionClose(Exception):
    """Indicates that receive quit due to an error."""


class RequestHandler:
    """Base class for the request handlers.

    This is an extended copy of the BaseRequestHandler from socketserver.

    To make a new interface, implement these methods:
        ingest, next_message, decode_message, receive, send_reply and format
    and extend (override) setup() and finish() if needed.

    For an example, have a look at TCPRequestHandler.
    """

    # Methods from BaseRequestHandler
    def __init__(self, request, client_address, server):
        self.request = request
        self.client_address = client_address
        self.server = server

        self.setup()
        try:
            self.handle()
        finally:
            self.finish()

    def setup(self):
        self.log = self.server.log
        self.log.info("new connection %s",  self.format())
        # notify dispatcher of us
        self.server.dispatcher.add_connection(self)
        self.send_lock = threading.Lock()
        self.running = True
        # overwrite this with an appropriate buffer if needed
        self.data = None

    def handle(self):
        """handle a new connection"""
        # copy state info
        serverobj = self.server
        # copy relevant settings from Interface
        detailed_errors = serverobj.detailed_errors

        # start serving
        while self.running:
            try:
                newdata = self.receive()
                if newdata is None:
                    # no new data during read, continue
                    continue
                self.ingest(newdata)
            except ConnectionClose:
                # either normal close or error in receive
                return
            # put data into (de-) framer,
            # de-frame data with next_message() and decode it
            # call dispatcher.handle_request(self, message)
            # dispatcher will queue the reply before returning
            while self.running:
                try:
                    msg = self.next_message()
                    if msg is None:
                        break  # no more messages to process
                except DecodeError as err:
                    # we have to decode 'origin' here
                    # use latin-1, as utf-8 or ascii may lead to encoding errors
                    msg = err.raw_msg.decode('latin-1').split(' ', 3) + [
                        None
                    ]  # make sure len(msg) > 1
                    result = (
                        ERRORPREFIX + msg[0],
                        msg[1],
                        [
                            'InternalError', str(err),
                            {
                                'exception': formatException(),
                                'traceback': formatExtendedStack()
                            }
                        ]
                    )
                    print('--------------------')
                    print(formatException())
                    print('--------------------')
                    print(formatExtendedTraceback(sys.exc_info()))
                    print('====================')
                else:
                    try:
                        if msg[0] == HELPREQUEST:
                            self.handle_help()
                            result = (HELPREPLY, None, None)
                        else:
                            result = serverobj.dispatcher.handle_request(self,
                                                                         msg)
                    except SECoPError as err:
                        result = (
                            ERRORPREFIX + msg[0],
                            msg[1],
                            [
                                err.name,
                                str(err),
                                {
                                    'exception': formatException(),
                                    'traceback': formatExtendedStack()
                                }
                            ]
                        )
                    except Exception as err:
                        # create Error Obj instead
                        result = (
                            ERRORPREFIX + msg[0],
                            msg[1],
                            [
                                'InternalError',
                                repr(err),
                                {
                                    'exception': formatException(),
                                    'traceback': formatExtendedStack()
                                }
                            ]
                        )
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

    def handle_help(self):
        for idx, line in enumerate(HelpMessage.splitlines()):
            # not sending HELPREPLY here, as there should be only one reply for
            # every request
            self.send_reply(('_', f'{idx + 1}', line))

    def finish(self):
        """called when handle() terminates, i.e. the socket closed"""
        self.log.info('closing connection %s', self.format())
        # notify dispatcher
        self.server.dispatcher.remove_connection(self)

    # Methods for implementing in derived classes:
    def ingest(self, newdata):
        """Put the new data into the buffer."""
        raise NotImplementedError

    def next_message(self):
        """Get the next decoded message from the buffer.

        Has to return a triple of (MESSAGE, specifier, data) or None, in case
        there are no further messages in the receive queue.

        If there is an Error during decoding, this method has to raise a
        DecodeError.
        """
        raise NotImplementedError

    def receive(self):
        """Receive data from the link.

        Should return the received data or None if there was nothing new. Has
        to raise a ConnectionClose on shutdown of the connection or on errors
        that are not recoverable.
        """
        raise NotImplementedError

    def send_reply(self, data):
        """send reply

        stops recv loop on error
        """
        raise NotImplementedError

    def format(self):
        """
        Format available connection data into something recognizable for
        logging.

        For example, the remote IP address or a connection identifier.
        """
        raise NotImplementedError

# TODO: server baseclass?
