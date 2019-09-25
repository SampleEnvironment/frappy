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


# no fixtures needed
import pytest

from secop.datatypes import BoolType, IntRange
from secop.params import Command, Override, Parameter, Parameters


def test_Command():
    cmd = Command('do_something')
    assert cmd.description == 'do_something'
    assert cmd.ctr
    assert cmd.argument is None
    assert cmd.result is None
    assert cmd.for_export() == {'datainfo': {'type': 'command'},
                                'description': 'do_something'}

    cmd = Command('do_something', argument=IntRange(-9,9), result=IntRange(-1,1))
    assert cmd.description
    assert isinstance(cmd.argument, IntRange)
    assert isinstance(cmd.result, IntRange)
    assert cmd.for_export() == {'datainfo': {'type': 'command', 'argument': {'type': 'int', 'min':-9, 'max':9},
                                                           'result': {'type': 'int', 'min':-1, 'max':1}},
                                'description': 'do_something'}
    assert cmd.exportProperties() == {'datainfo': {'type': 'command', 'argument': {'type': 'int', 'max': 9, 'min': -9},
                                                                 'result': {'type': 'int', 'max': 1, 'min': -1}},
                                      'description': 'do_something'}


def test_Parameter():
    p1 = Parameter('description1', datatype=IntRange(), default=0)
    p2 = Parameter('description2', datatype=IntRange(), constant=1)
    assert p1 != p2
    assert p1.ctr != p2.ctr
    with pytest.raises(ValueError):
        Parameter(None, datatype=float)
    p3 = p1.copy()
    assert p1.ctr != p3.ctr
    p3.ctr = p1.ctr # manipulate ctr for next line
    assert repr(p1) == repr(p3)
    assert p1.datatype != p2.datatype


def test_Override():
    p = Parameter('description1', datatype=BoolType, default=False)
    o = Override(default=True, reorder=True)
    assert o.ctr != p.ctr
    q = o.apply(p)
    assert q.ctr != o.ctr  # override shall be useable to influence the order, hence copy the ctr value
    assert q.ctr != p.ctr
    assert o.ctr != p.ctr
    assert q != p

    p2 = Parameter('description2', datatype=BoolType, default=False)
    o2 = Override(default=True)
    assert o2.ctr != p2.ctr
    q2 = o2.apply(p2)
    assert q2.ctr != o2.ctr
    assert q2.ctr != p2.ctr  # EVERY override makes a new parameter object -> ctr++
    assert o2.ctr != p2.ctr
    assert q2 != p2

def test_Parameters():
    ps = Parameters(dict(p1=Parameter('p1', datatype=BoolType, default=True)))
    ps['p2'] = Parameter('p2', datatype=BoolType, default=True, export=True)
    assert ps['_p2'].export == '_p2'
