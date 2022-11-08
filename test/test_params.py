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

from frappy.datatypes import BoolType, FloatRange, IntRange
from frappy.errors import ProgrammingError
from frappy.modules import HasAccessibles
from frappy.params import Command, Parameter


def test_Command():
    class Mod(HasAccessibles):
        @Command()
        def cmd(self):
            """do something"""
        @Command(IntRange(-9,9), result=IntRange(-1,1), description='do some other thing')
        def cmd2(self):
            pass

    assert Mod.cmd.description == 'do something'
    assert Mod.cmd.argument is None
    assert Mod.cmd.result is None
    assert Mod.cmd.for_export() == {'datainfo': {'type': 'command'},
                                'description': 'do something'}

    assert Mod.cmd2.description == 'do some other thing'
    assert isinstance(Mod.cmd2.argument, IntRange)
    assert isinstance(Mod.cmd2.result, IntRange)
    assert Mod.cmd2.for_export() == {'datainfo': {'type': 'command', 'argument': {'type': 'int', 'min': -9, 'max': 9},
                                                  'result': {'type': 'int', 'min': -1, 'max': 1}},
                                     'description': 'do some other thing'}
    assert Mod.cmd2.exportProperties() == {'datainfo': {'type': 'command', 'argument': {'type': 'int', 'max': 9, 'min': -9},
                                                        'result': {'type': 'int', 'max': 1, 'min': -1}},
                                           'description': 'do some other thing'}


def test_Parameter():
    class Mod(HasAccessibles):
        p1 = Parameter('desc1', datatype=FloatRange(), default=0)
        p2 = Parameter('desc2', datatype=FloatRange(), default=0, readonly=True)
        p3 = Parameter('desc3', datatype=FloatRange(), default=0, readonly=False)
        p4 = Parameter('desc4', datatype=FloatRange(), constant=1)
    assert repr(Mod.p1) != repr(Mod.p3)
    assert id(Mod.p1.datatype) != id(Mod.p2.datatype)
    assert Mod.p1.exportProperties() == {'datainfo': {'type': 'double'}, 'description': 'desc1', 'readonly': True}
    assert Mod.p2.exportProperties() == {'datainfo': {'type': 'double'}, 'description': 'desc2', 'readonly': True}
    assert Mod.p3.exportProperties() == {'datainfo': {'type': 'double'}, 'description': 'desc3', 'readonly': False}
    assert Mod.p4.exportProperties() == {'datainfo': {'type': 'double'}, 'description': 'desc4', 'readonly': True,
                                         'constant': 1.0}
    p3 = Mod.p1.copy()
    assert id(p3) != id(Mod.p1)
    assert repr(Mod.p1) == repr(p3)

    with pytest.raises(ProgrammingError):
        Parameter(None, datatype=float, inherit=False)


def test_Override():
    class Base(HasAccessibles):
        p1 = Parameter('description1', datatype=BoolType, default=False)
        p2 = Parameter('description1', datatype=BoolType, default=False)
        p3 = Parameter('description1', datatype=BoolType, default=False)

    class Mod(Base):
        p1 = Parameter(default=True)
        p2 = Parameter()  # override without change

    assert id(Mod.p1) != id(Base.p1)
    assert id(Mod.p2) != id(Base.p2)
    assert id(Mod.p3) == id(Base.p3)
    assert repr(Mod.p2) == repr(Base.p2)  # must be a clone
    assert repr(Mod.p3) == repr(Base.p3)  # must be a clone
    assert Mod.p1.default is True
    # manipulating default makes Base.p1 and Mod.p1 match
    Mod.p1.default = False
    assert repr(Mod.p1) == repr(Base.p1)

    for cls in locals().values():
        if hasattr(cls, 'accessibles'):
            for p in cls.accessibles.values():
                assert isinstance(p.ownProperties, dict)
                assert p.copy().ownProperties == {}


def test_Export():
    class Mod(HasAccessibles):
        param = Parameter('description1', datatype=BoolType, default=False)
    assert Mod.param.export == '_param'
