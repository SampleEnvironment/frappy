#  -*- coding: utf-8 -*-
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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""test message encoding and decoding."""

import pytest

from secop.protocol.interface import encode_msg_frame, decode_msg
import secop.protocol.messages as m

# args are: msg tuple, msg bytes
MSG = [
    [(m.DESCRIPTIONREQUEST, None, None), b'describe'],
    [(m.DESCRIPTIONREPLY, '.', dict(key=0)), b'describing . {"key": 0}'],
    [(m.ENABLEEVENTSREQUEST, 'module:param', None), b'activate module:param'],
    [(m.ERRORPREFIX + m.ENABLEEVENTSREQUEST,  None, ['ErrClass', 'text', {}]),
     b'error_activate  ["ErrClass", "text", {}]'],
    [(m.COMMANDREQUEST, 'module:stop', None), b'do module:stop'],
    [(m.COMMANDREPLY, 'module:cmd', ''), b'done module:cmd ""'],
    [(m.WRITEREQUEST, 'module', 0), b'change module 0'],
    [(m.WRITEREPLY, 'm:p', 'with space'), b'changed m:p "with space"'],
    [(m.EVENTREPLY, 'mod:par', [123, dict(t=12.25)]), b'update mod:par [123, {"t": 12.25}]'],
    [(m.HEARTBEATREQUEST, '0', None), b'ping 0'],
    [(m.HEARTBEATREPLY, None, [None, dict(t=11.75)]), b'pong  [null, {"t": 11.75}]'],
    [(m.ERRORPREFIX + m.WRITEREQUEST, 'm:p', ['ErrClass', 'text', dict()]),
     b'error_change m:p ["ErrClass", "text", {}]'],
]
@pytest.mark.parametrize('msg, line', MSG)
def test_encode(msg, line):
    assert line + b'\n' == encode_msg_frame(*msg)

@pytest.mark.parametrize('msg, line', MSG)
def test_decode(msg, line):
    assert decode_msg(line) == msg
