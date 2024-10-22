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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
"""Discovery via UDP broadcasts."""

import os
import json
import socket

from frappy.lib import closeSocket
from frappy.protocol.interface.tcp import format_address
from frappy.version import get_version

UDP_PORT = 10767
MAX_MESSAGE_LEN = 508


class UDPListener:
    def __init__(self, equipment_id, description, ifaces, logger, *,
                 startup_broadcast=True):
        self.equipment_id = equipment_id
        self.log = logger
        self.description = description or ''
        self.firmware = 'FRAPPY ' + get_version()
        self.ports = [int(iface.split('://')[1])
                      for iface in ifaces if iface.startswith('tcp')]
        self.running = False
        self.is_enabled = True
        self.startup_broadcast = startup_broadcast

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if os.name == 'nt':
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        else:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        if startup_broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('0.0.0.0', UDP_PORT))

        available = MAX_MESSAGE_LEN - len(self._getMessage(2**16-1))
        if available < 0:
            desc_length = len(self.description.encode('utf-8'))
            if available + desc_length < 0:
                self.log.warn('Equipment id and firmware name exceed 430 byte '
                              'limit, not answering to udp discovery')
                self.is_enabled = False
            else:
                self.log.debug('truncating description for udp discovery')
                # with errors='ignore', cutting insite a utf-8 glyph will not
                # report an error but remove the rest of the glyph from the
                # output.
                self.description = self.description \
                                       .encode('utf-8')[:available] \
                                       .decode('utf-8', errors='ignore')

    def _getMessage(self, port):
        return json.dumps({
            'SECoP': 'node',
            'port': port,
            'equipment_id': self.equipment_id,
            'firmware': self.firmware,
            'description': self.description,
        }, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

    def run(self):
        if self.startup_broadcast:
            self.log.debug('Sending startup UDP broadcast.')
            for port in self.ports:
                self.sock.sendto(self._getMessage(port),
                                 ('255.255.255.255', UDP_PORT))
        self.running = True
        while self.running and self.is_enabled:
            try:
                msg, addr = self.sock.recvfrom(1024)
            except socket.error:
                return
            try:
                request = json.loads(msg.decode('utf-8'))
            except json.JSONDecodeError:
                continue
            if 'SECoP' not in request or request['SECoP'] != 'discover':
                continue
            self.log.debug('Answering UDP broadcast from: %s',
                           format_address(addr))
            for port in self.ports:
                self.sock.sendto(self._getMessage(port), addr)

    def shutdown(self):
        self.log.debug('shut down of discovery listener')
        self.running = False
        closeSocket(self.sock)
