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
"""test Enum type."""


# no fixtures needed
import pytest

from secop.lib.enum import Enum, EnumMember


def test_EnumMember():
    with pytest.raises(TypeError):
        a = EnumMember(None, 'name', 'value')
    with pytest.raises(TypeError):
        a = EnumMember(None, 'name', 1)

    e1=Enum('X')
    with pytest.raises(ValueError):
        a = EnumMember(e1, 'a', 'value')
    a = EnumMember(e1, 'a', 1)

    with pytest.raises(TypeError):
        a.value = 2

    with pytest.raises(TypeError):
        a.value += 2

    with pytest.raises(TypeError):
        a += 2

    # this shall work
    assert 2 == (a + 1)  # pylint: disable=C0122
    assert (a - 1) == 0
    assert a
    assert a + a
    assert (2 - a) == 1
    assert -a == -1  # numeric negation
    assert ~a == -2  # bitmask like NOT
    assert (a & 3) == 1
    assert (a | 6) == 7
    assert (a ^ 7) == 6
    assert a < 2
    assert a > 0
    assert a != 3
    assert a == 1


def test_Enum():
    e1 = Enum('e1')
    e2 = Enum('e2', e1, a=1, b=3)
    e3 = Enum('e3', e2, c='a')
    assert e3.c == 2
    with pytest.raises(TypeError):
        e2.c = 2
    assert e3.a < e2.b
    assert e2.b > e3.a
    assert e3.c >= e2.a
    assert e3.b <= e2.b
    assert Enum({'self': 0, 'other': 1})('self') == 0


def test_Enum_bool():
    e = Enum('OffOn', off=0, on=1)
    assert bool(e(0)) is False
    assert bool(e(1)) is True
