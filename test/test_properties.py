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
"""test data types."""

import pytest

from secop.datatypes import IntRange, StringType, FloatRange, ValueType
from secop.errors import ProgrammingError
from secop.properties import Property, Properties, HasProperties


V_test_Property = [
    [(StringType(), 'default', 'extname', False, False),
     dict(default='default', extname='extname', export=True, mandatory=False)],
    [(IntRange(), '42', '_extname', False, True),
     dict(default=42, extname='_extname', export=True, mandatory=True)],
    [(IntRange(), '42', '_extname', True, False),
     dict(default=42, extname='_extname', export=True, mandatory=False)],
    [(IntRange(), 42, '_extname', True, True),
     dict(default=42, extname='_extname', export=True, mandatory=True)],
    [(IntRange(), 0, '', True, True),
     dict(default=0, extname='', export=True, mandatory=True)],
    [(IntRange(), 0, '', True, False),
     dict(default=0, extname='', export=True, mandatory=False)],
    [(IntRange(), 0, '', False, True),
     dict(default=0, extname='', export=False, mandatory=True)],
    [(IntRange(), 0, '', False, False),
     dict(default=0, extname='', export=False, mandatory=False)],
    [(IntRange(), None, '', False, False),
     dict(default=0, extname='', export=False, mandatory=True)], # 'normal types + no default -> mandatory
    [(ValueType(), None, '', False, False),
     dict(default=None, extname='', export=False, mandatory=False)], # 'special type + no default -> NOT mandatory
]
@pytest.mark.parametrize('args, check', V_test_Property)
def test_Property(args, check):
    p = Property('', *args)
    for k,v in check.items():
        assert getattr(p, k) == v

def test_Property_basic():
    with pytest.raises(TypeError):
        # pylint: disable=no-value-for-parameter
        Property()
    with pytest.raises(TypeError):
        # pylint: disable=no-value-for-parameter
        Property('')
    with pytest.raises(ValueError):
        Property('', 1)
    Property('', IntRange(), '42', 'extname', False, False)

def test_Properties():
    p = Properties()
    with pytest.raises(ProgrammingError):
        p[1] = 2
    p['a'] = Property('', IntRange(), '42', export=True)
    assert p['a'].default == 42
    assert p['a'].export is True
    assert p['a'].extname == '_a'
    with pytest.raises(ProgrammingError):
        p['a'] = 137
    with pytest.raises(ProgrammingError):
        del p[1]
    with pytest.raises(ProgrammingError):
        del p['a']
    p['a'] = Property('', IntRange(), 0, export=False)
    assert p['a'].default == 0
    assert p['a'].export is False
    assert p['a'].extname == ''


class c(HasProperties):
    properties = {
        'a' : Property('', IntRange(), 1),
    }

class cl(c):
    properties = {
        'a' : Property('', IntRange(), 3),
        'b' : Property('', FloatRange(), 3.14),
    }

def test_HasProperties():
    o = cl()
    assert o.properties['a'] == 3
    assert o.properties['b'] == 3.14
