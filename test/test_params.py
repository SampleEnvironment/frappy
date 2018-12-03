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

from __future__ import division, print_function

import sys
from os import path

# no fixtures needed
import pytest

from secop.datatypes import BoolType
from secop.params import Command, Override, Parameter

sys.path.insert(0, path.abspath(path.join(path.dirname(__file__), '..')))






def test_Command():
    cmd = Command('do_something')
    assert cmd.description
    assert cmd.ctr
    assert cmd.argument is None
    assert cmd.result is None



def test_Parameter():
    p1 = Parameter('description1', datatype=BoolType, default=False)
    p2 = Parameter('description2', datatype=BoolType, default=True)
    assert p1 != p2
    assert p1.ctr != p2.ctr
    with pytest.raises(ValueError):
        Parameter(None, datatype=float)

def test_Override():
    p = Parameter('description1', datatype=BoolType, default=False)
    o = Override(default=True)
    assert o.ctr != p.ctr
    q = o.apply(p)
    assert q.ctr == o.ctr  # override shall be useable to influence the order, hence copy the ctr value
    assert q.ctr != p.ctr
    assert o.ctr != p.ctr
    assert q != p
