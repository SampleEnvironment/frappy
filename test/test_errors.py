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
"""test data types."""

import pytest
from frappy.errors import RangeError, WrongTypeError, ProgrammingError, \
    ConfigError, InternalError, DiscouragedConversion, secop_error, make_secop_error


@pytest.mark.parametrize('exc, name, text, echk', [
    (RangeError('out of range'), 'RangeError', 'out of range', None),
    (WrongTypeError('bad type'), 'WrongType', 'bad type', None),
    (ProgrammingError('x'), 'InternalError', 'ProgrammingError: x', None),
    (ConfigError('y'), 'InternalError', 'ConfigError: y', None),
    (InternalError('z'), 'InternalError', 'z', None),
    (DiscouragedConversion('w'), 'InternalError', 'DiscouragedConversion: w', None),
    (ValueError('v'), 'InternalError', "ValueError: v", InternalError("ValueError: v")),
    (None, 'InternalError', "UnknownError: v", InternalError("UnknownError: v")),
])
def test_errors(exc, name, text, echk):
    """check consistence of frappy.errors"""
    if exc:
        err = secop_error(exc)
        assert err.name == name
        assert str(err) == text
    recheck = make_secop_error(name, text)
    echk = echk or exc
    assert type(recheck) == type(echk)
    assert str(recheck) == str(echk)
