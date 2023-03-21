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

import time
from frappy.lib.multievent import MultiEvent


def test_without_timeout():
    m = MultiEvent()
    s1 = m.get_trigger(name='s1')
    s2 = m.get_trigger(name='s2')
    assert not m.wait(0)
    assert m.deadline() is None
    assert m.waiting_for() == {'s1', 's2'}
    s2()
    assert m.waiting_for() == {'s1'}
    assert not m.wait(0)
    s1()
    assert not m.waiting_for()
    assert m.wait(0)


def test_with_timeout(monkeypatch):
    current_time = 1000
    monkeypatch.setattr(time, 'monotonic', lambda: current_time)
    m = MultiEvent()
    assert m.deadline() == 0
    m.name = 's1'
    s1 = m.get_trigger(10)
    assert m.deadline() == 1010
    m.name = 's2'
    s2 = m.get_trigger(20)
    assert m.deadline() == 1020
    current_time += 21
    assert not m.wait(0)
    assert m.waiting_for() == {'s1', 's2'}
    s1()
    assert m.waiting_for() == {'s2'}
    s2()
    assert not m.waiting_for()
    assert m.wait(0)
