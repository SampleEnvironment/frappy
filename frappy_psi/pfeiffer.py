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
#   Markus Zolliker <markus.zolliker@psi.ch>
# *****************************************************************************
"""pfeiffer TPG vacuum pressure reading"""

from frappy.core import StringIO, HasIO, IntRange, \
    IDLE, WARN, ERROR, Readable, Parameter, Property
from frappy.errors import CommunicationFailedError

ACK = '\x06'
ENQ = '\x05'


class IO(StringIO):
    end_of_line = '\r\n'
    default_settings = {'baudrate': 9600}

    def communicate(self, command, noreply=False):
        with self._lock:
            ack = super().communicate(command)
            if ack != ACK:
                raise CommunicationFailedError('no ack received')
            if noreply:
                # to be used for changing parameters when needed
                return None
            return super().communicate(ENQ)


class Pressure(HasIO, Readable):
    value = Parameter(unit='mbar')
    channel = Property('channel number', IntRange(1, 2), default=1)

    STATUS_MAP = {
        '0': (IDLE, ''),
        '1': (WARN, 'underrange'),
        '2': (WARN, 'overrange'),
        '3': (ERROR, 'sensor error'),
        '4': (ERROR, 'sensor off'),
        '5': (ERROR, 'no sensor'),
        '6': (ERROR, 'identification error'),
    }

    ioClass = IO

    def read_value(self):
        reply = self.communicate(f'PR{self.channel}')
        status, strvalue = reply.split(',')
        self.status = self.STATUS_MAP.get(status, (ERROR, 'bad status'))
        return float(strvalue)
