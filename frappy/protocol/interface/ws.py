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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

import json
from functools import partial

from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from websockets.sync.server import CloseCode, serve

from frappy.protocol.interface.handler import ConnectionClose, \
    RequestHandler, DecodeError
from frappy.protocol.messages import HELPREQUEST


def encode_msg_frame_str(action, specifier=None, data=None):
    """ encode a msg_triple into an msg_frame, ready to be sent

    action (and optional specifier) are str strings,
    data may be an json-yfied python object"""
    msg = (action, specifier or '', '' if data is None else json.dumps(data))
    return ' '.join(msg).strip()


class WSRequestHandler(RequestHandler):
    """Handles a Websocket connection."""

    def __init__(self, conn, server):
        self.conn = conn
        client_address = conn.remote_address
        request = conn.socket
        super().__init__(request, client_address, server)

    def setup(self):
        super().setup()
        self.server.connections.add(self)

    def finish(self):
        """called when handle() terminates, i.e. the socket closed"""
        super().finish()
        self.server.connections.discard(self)
        # this will be called for a second time if the server is shutting down,
        # but in that case it will be a no-op
        self.conn.close()

    def ingest(self, newdata):
        # recv on the websocket connection returns one message, we don't save
        # anything in data
        self.data = newdata

    def next_message(self):
        """split the string into a message triple."""
        if self.data is None:
            return None
        try:
            message = self.data.strip()
            if message == '':
                return HELPREQUEST, None, None
            res = message.split(' ', 2) + ['', '']
            action, specifier, data = res[0:3]
            self.data = None
            return (
                action,
                specifier or None,
                None if data == '' else json.loads(data)
            )
        except Exception as e:
            raise DecodeError('exception when reading in message',
                              raw_msg=bytes(message, 'utf-8')) from e

    def receive(self):
        """receives one message from the websocket."""
        try:
            return self.conn.recv()
        except TimeoutError:
            return None
        except ConnectionClosedOK:
            raise ConnectionClose from None
        except ConnectionClosedError as e:
            self.log.error('No close frame received from %s', self.format())
            raise ConnectionClose from e
        except OSError as e:
            self.log.exception(e)
            raise ConnectionClose from e

    def send_reply(self, data):
        """send reply

        stops recv loop on error (including timeout when output buffer full for
        more than 1 sec)
        """
        if not data:
            self.log.error('should not reply empty data!')
            return
        outdata = encode_msg_frame_str(*data)
        with self.send_lock:
            if self.running:
                try:
                    self.conn.send(outdata)
                except (BrokenPipeError, IOError) as e:
                    self.log.debug('send_reply got an %r, connection closed?',
                                   e)
                    self.running = False
                except Exception as e:
                    self.log.error('ERROR in send_reply %r', e)
                    self.running = False

    def format(self):
        return f'{self.conn.id} from {self.client_address}'

class WSServer:
    """Server for providing a websocket interface.

    Implementation note:
    The websockets library doesn't provide an option to subclass its server, so
    we take the returned value as an attribute and provide the neccessary
    function calls.
    """
    def __init__(self, name, logger, options, srv):
        self.connections = set()  # keep track for shutting down
        self.dispatcher = srv.dispatcher
        self.name = name
        self.log = logger
        self.port = int(options.pop('uri').split('://', 1)[-1])
        self.detailed_errors = options.pop('detailed_errors', False)

        handle = partial(WSRequestHandler, server=self)
        # websockets only gives the serve method without an option to subclass
        self.ws_server = serve(handle, '', self.port, logger=logger)
        self.log.info("Websocket server %s binding to port %d", name, self.port)

    def serve_forever(self):
        self.ws_server.serve_forever()

    def shutdown(self):
        for c in list(self.connections):
            c.conn.close(code=CloseCode.GOING_AWAY, reason='shutting down')
        self.ws_server.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.shutdown()
