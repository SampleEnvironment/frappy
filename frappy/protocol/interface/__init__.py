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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

import json

EOL = b'\n'


def encode_msg_frame(action, specifier=None, data=None):
    """ encode a msg_triple into an msg_frame, ready to be sent

    action (and optional specifier) are str strings,
    data may be an json-yfied python object"""
    msg = (action, specifier or '', '' if data is None else json.dumps(data))
    return ' '.join(msg).strip().encode('utf-8') + EOL


def get_msg(_bytes):
    """try to deframe the next msg in (binary) input
    always return a tuple (msg, remaining_input)
    msg may also be None
    """
    if EOL not in _bytes:
        return None, _bytes
    return _bytes.split(EOL, 1)


def decode_msg(msg):
    """decode the (binary) msg into a (str) msg_triple"""
    res = msg.strip().decode('utf-8').split(' ', 2) + ['', '']
    action, specifier, data = res[0:3]
    return action, specifier or None, None if data == '' else json.loads(data)
