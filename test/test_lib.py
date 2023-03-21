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
from frappy.lib import parseHostPort


@pytest.mark.parametrize('hostport, defaultport, result', [
    (('box.psi.ch', 9999), 1, ('box.psi.ch', 9999)),
    (('/dev/tty', 9999), 1, None),
    ('localhost:10767', 1, ('localhost', 10767)),
    ('www.psi.ch', 80, ('www.psi.ch', 80)),
    ('/dev/ttyx:2089', 10767, None),
    ('COM4:', 2089, None),
    ('underscore_valid.123.hyphen-valid.com', 80, ('underscore_valid.123.hyphen-valid.com', 80)),
])
def test_parse_host(hostport, defaultport, result):
    if result is None:
        with pytest.raises(ValueError):
            parseHostPort(hostport, defaultport)
    else:
        assert result == parseHostPort(hostport, defaultport)
