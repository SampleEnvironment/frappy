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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

import json

EOL = b'\n'
SPACE = b' '

def encode_msg_frame(action, specifier=None, data=None):
    """ encode a msg_tripel into an msg_frame, ready to be sent

    action (and optional specifier) are str strings,
    data may be an json-yfied python object"""
    action = action.encode('utf-8')
    if specifier is None:
        if data is None:
            return b''.join((action, EOL))
        # error_activate might have no specifier
        specifier = ''
    specifier = specifier.encode('utf-8')
    if data:
        data = json.dumps(data).encode('utf-8')
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
    """decode the (binary) msg into a (str) msg_tripel"""
    # check for leading/trailing CR and remove it
    res = msg.split(b' ', 2)
    action = res[0].decode('utf-8')
    if len(res) == 1:
        return action, None, None
    specifier = res[1].decode('utf-8')
    if len(res) == 2:
        return action, specifier, None
    data = json.loads(res[2].decode('utf-8'))
    return action, specifier, data
