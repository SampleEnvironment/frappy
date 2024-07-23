# *****************************************************************************
# MLZ library of Tango servers
# Copyright (c) 2015-2024 by the authors, see LICENSE
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
#   Georg Brandl <g.brandl@fz-juelich.de>
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

import threading
from time import sleep, time

from frappy.core import Parameter, Command, nopoll, Readable
from frappy.io import HasIO, BytesIO
from frappy.lib import mkthread
from frappy.errors import CommunicationFailedError
from frappy.datatypes import IntRange, StringType, StatusType

# SSI protocol operations
CMD_ACK = 0xD0
CMD_NAK = 0xD1
DECODE_DATA = 0xF3
BEEP = 0xE6
REQUEST_REVISION = 0xA3
REPLY_REVISION = 0xA4
SCAN_ENABLE = 0xE9
SCAN_DISABLE = 0xEA

# source byte
HOST = 4
DECODER = 0


BARCODE_TYPES = {
    0x2d: 'Aztec',
    0x2e: 'Aztec Rune',
    0x16: 'Bookland',
    0x72: 'C 2 of 5',
    0x02: 'Codabar',
    0x0c: 'Code 11',
    0x03: 'Code 128',
    0x12: 'Code 16K',
    0x20: 'Code 32',
    0x01: 'Code 39',
    0x13: 'Code 39 ASCII',
    0x0d: 'Code 49',
    0x07: 'Code 93',
    0x17: 'Coupon',
    0x38: 'Cue CAT',
    0x04: 'D25',
    0x1b: 'Data Matrix',
    0x0f: 'GS1-128',
    0xc2: 'GS1 QR',
    0x0b: 'EAN-13',
    0x4b: 'EAN-13 + 2',
    0x8b: 'EAN-13 + 5',
    0x0a: 'EAN-8',
    0x4a: 'EAN-8 + 2',
    0x8a: 'EAN-8 + 5',
    0x2f: 'French Lottery',
    0x32: 'GS1 DataBar Expanded',
    0x31: 'GS1 DataBar Limited',
    0x30: 'GS1 DataBar-14',
    0xc1: 'GS1 Datamatrix',
    0xb7: 'Han Xin',
    0x05: 'IATA',
    0x19: 'ISBT-128',
    0x21: 'ISBT-128 Concat',
    0x36: 'ISSN',
    0x06: 'ITF',
    0x73: 'Korean 2 of 5',
    0x9a: 'Macro Micro PDF',
    0x28: 'Macro PDF-417',
    0x29: 'Macro QR',
    0x39: 'Matrix 2 of 5',
    0x25: 'Maxicode',
    0x1a: 'Micro PDF',
    0x1d: 'Micro PDF CCA',
    0x2c: 'Micro QR',
    0x0e: 'MSI',
    0x99: 'Multipacket Format',
    0x18: 'NW7',
    0xa0: 'OCRB',
    0x33: 'Parameter FNC3',
    0x11: 'PDF-417',
    0x1f: 'Planet US',
    0x23: 'Postal AUS',
    0x24: 'Postal NL',
    0x22: 'Postal JAP',
    0x27: 'Postal UK',
    0x26: 'Postbar CA',
    0x1e: 'Postnet US',
    0x1c: 'QR',
    0xe0: 'RFID Raw',
    0xe1: 'RFID URI',
    0xb4: 'RSS Expanded',
    0x37: 'Scanlet Webcode',
    0x69: 'Signature',
    0x5a: 'TLC-39',
    0x15: 'Trioptic',
    0x08: 'UPCA',
    0x48: 'UPCA + 2',
    0x88: 'UPCA + 5',
    0x14: 'UPCD',
    0x09: 'UPCE',
    0x49: 'UPCE + 2',
    0x89: 'UPCE + 5',
    0x10: 'UPCE1',
    0x50: 'UPCE1 + 2',
    0x90: 'UPCE1 + 5',
    0x34: '4State US',
    0x35: '4State US4',
}


def decode_bytes(byte_list):
    return bytes(byte_list).decode('latin1')


class ZebraIO(BytesIO):
    default_settings = {'baudrate': 115200}

    def _cksum(self, data):
        cksum = 0x10000 - sum(data)
        return [cksum >> 8, cksum & 0xFF]

    def _make_package(self, op, data):
        msg = [len(data) + 4, op, HOST, 0] + data
        return msg + self._cksum(msg)

    def _ssi_send(self, op, data):
        self.communicate(self._make_package(op, data), 0)

    def _ssi_read_n(self, n, timeout, buf):
        # read N bytes with specified timeout
        end = time() + timeout
        delay = 0.00005
        while n and time() < end:
            sleep(delay)
            delay = min(2 * delay, 0.01)
            newdata = self.readBytes(int(n))
            n -= len(newdata)
            buf.extend(newdata)
        return buf

    def _ssi_recv(self, expected_op, recv_timeout, rest_timeout):
        # first determine how much data there is to read
        buf = []
        if not self._ssi_read_n(1, recv_timeout, buf):
            return None
        # now read the rest of the data
        rest_len = buf[0] + 1
        self._ssi_read_n(rest_len, rest_timeout, buf)
        if len(buf) != rest_len + 1:
            return None
        if buf[2] != DECODER:
            raise CommunicationFailedError('invalid reply received')
        if self._cksum(buf[:-2]) != buf[-2:]:
            raise CommunicationFailedError('invalid checksum received')
        if buf[1] != expected_op:
            raise CommunicationFailedError('got op %r, expected %r' %
                                       (buf[0], expected_op))
        return buf[3:-2]

    def _ssi_comm(self, op, data):
        self._ssi_send(op, data)
        if self._ssi_recv(CMD_ACK, 1, 1) is None:
            raise CommunicationFailedError('ACK not received')


# Not yet tested
class ZebraReader(HasIO, Readable):
    """Reads scanned barcodes from a Zebra barcode reader, using the USB-CDC
    interface mode and the SSI protocol.

    TODO: CHANGE this paragraph
    The underlying IO device must be a BinaryIO since SSI framing and metadata
    is transferred in binary.

    Since reading barcodes is initiated by the device and not the host, the
    parameter decoded does not give the last decoded value when polled.
    Instead, activate updates for this parameter, which are then sent out when
    the barcode reader decodes a value. Polling will always return an empty
    string.

    The update for decoded then contains the decoded barcode type as a string,
    a comma as a separator, and then the barcode data.

    As a special API, there is a Beep command to make the reader emit some
    audible signal.
    """

    ioClass = ZebraIO

    decoded = Parameter('decoded barcode (updates-only)', StringType(),
                        update_unchanged='always', default='')
    # TODO: Decide, if this is useful, remove otherwise
    status = Parameter('status of the module',
                       StatusType('IDLE', 'WARN', 'ERROR'))
    value = Parameter(datatype=StringType(), default='',
                      update_unchanged='never')

    _thread = None
    _stoprequest = False

    def initModule(self):  # or startModule?
        super().initModule()
        self.io._ssi_send(REQUEST_REVISION, [])
        rev = self.io._ssi_recv(REPLY_REVISION, 1, 1)
        if rev is None:
            raise CommunicationFailedError('got no revision info from decoder')
        self.hw_version = decode_bytes(rev).split()[0]

        self._lock = threading.Lock()
        self._thread = mkthread(self._thread_func)

    def shutdownModule(self):
        self._stoprequest = True
        if self._thread and self._thread.is_alive():
            self._thread.join()

    @nopoll
    def read_value(self):
        return ''

    @nopoll
    def read_decoded(self):
        return ''

    def read_status(self):
        return self.Status.IDLE, ''

    def _thread_func(self):
        while not self._stoprequest:
            with self._lock:
                try:
                    code = self.io._ssi_recv(DECODE_DATA, 0.1, 1)
                    if code is not None:
                        self.io._ssi_send(CMD_ACK, [])
                # TODO: readBytes from BytesIO always uses self.timeout, so the
                # case where None can be returned after the timeout cannot be
                # used
                except TimeoutError:
                    code = None
                except Exception as e:
                    self.log.exception('while receiving barcode: %s', e)
                    self.status = self.Status.ERROR, f'{e!r}'
                    continue
            if code is not None:
                codetype = BARCODE_TYPES.get(code[0], str(code[0]))
                code = codetype + ',' + decode_bytes(code[1:])

                tstamp = time()
                self.log.info('decoded barcode %r with timestamp %s',
                              code, tstamp)
                self.decoded = code
                self.decoded = ''  # clear value of frappy client cache
            sleep(0.5)

    @Command()
    def on(self):
        """Enable the Scanner"""
        with self._lock:
            self.io._ssi_comm(SCAN_ENABLE, [])

    @Command()
    def off(self):
        """Disable the Scanner"""
        with self._lock:
            self.io._ssi_comm(SCAN_DISABLE, [])

    @Command(IntRange(0,26))
    def beep(self, pattern):
        """
        Emit an audible signal from the reader.
        :param pattern: The beep pattern (range 0 to 26;
        see the manual for interpretation).
        """
        with self._lock:
            self.io._ssi_comm(BEEP, [pattern])
