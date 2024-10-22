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
"""Test discovery messages"""

from test.test_modules import LoggerStub
from frappy.protocol.discovery import UDPListener, MAX_MESSAGE_LEN
from frappy.version import get_version


def test_empty():
    logger = LoggerStub()
    udp = UDPListener('', '', ['tcp://0'], logger)
    udp.firmware = ''
    # 78 is the maximum overhead
    assert 78 == len(udp._getMessage(2**16-1))


def test_basic():
    logger = LoggerStub()
    udp = UDPListener('eq', 'desc', ['tcp://1234'], logger)
    assert udp.description == 'desc'
    assert udp.equipment_id == 'eq'
    assert udp.ports == [1234]
    assert udp.firmware == 'FRAPPY ' + get_version()


def test_ascii_truncation():
    logger = LoggerStub()
    desc = 'a' * MAX_MESSAGE_LEN
    udp = UDPListener('eq', desc, ['tcp://1234'], logger)
    assert MAX_MESSAGE_LEN == len(udp._getMessage(65535))
    fw = len(('FRAPPY ' + get_version()).encode('utf-8'))
    expected_length = 430 - fw - 2
    assert expected_length == len(udp.description)


def test_unicode_truncation():
    logger = LoggerStub()
    desc = '\U0001f604' * 400
    udp = UDPListener('eq', desc, ['tcp://1234'], logger)
    fw = len(('FRAPPY ' + get_version()).encode('utf-8'))
    # 4 bytes per symbol, rounded down for the potential cut
    expected_length = (430 - fw - 2) // 4
    assert expected_length == len(udp.description)
