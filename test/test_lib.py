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

import pytest

from frappy.lib import parse_host_port


@pytest.mark.parametrize('hostport, defaultport, result', [
    ('box.psi.ch:9999', 1, ('box.psi.ch', 9999)),
    ('/dev/tty:9999', 1, None),
    ('localhost:10767', 1, ('localhost', 10767)),
    ('www.psi.ch', 80, ('www.psi.ch', 80)),
    ('/dev/ttyx:2089', 10767, None),
    ('COM4:', 2089, None),
    ('123.hyphen-valid.com', 80, ('123.hyphen-valid.com', 80)),
    ('underscore_invalid.123.hyphen-valid.com:10000', 80, None),
    ('::1.1111', 2, ('::1', 1111)),
    ('[2e::fe]:1', 50, ('2e::fe', 1)),
    ('127.0.0.1:50', 1337, ('127.0.0.1', 50)),
    ('234.40.128.3:13212', 1337, ('234.40.128.3', 13212)),

])
def test_parse_host(hostport, defaultport, result):
    if result is None:
        with pytest.raises(ValueError):
            parse_host_port(hostport, defaultport)
    else:
        assert result == parse_host_port(hostport, defaultport)
