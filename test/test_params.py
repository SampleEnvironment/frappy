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

from frappy.datatypes import BoolType, FloatRange, IntRange, StructOf
from frappy.errors import ProgrammingError
from frappy.modulebase import HasAccessibles, Module
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


def test_cmd_struct_opt():
    with pytest.raises(ProgrammingError):
        class WrongName(HasAccessibles):  # pylint: disable=unused-variable
            @Command(StructOf(a=IntRange(), b=IntRange()))
            def cmd(self, a, c):
                pass
    class Mod(HasAccessibles):
        @Command(StructOf(a=IntRange(), b=IntRange()))
        def cmd(self, a=5, b=5):
            pass
    assert Mod.cmd.datatype.argument.optional == ['a', 'b']
    class Mod2(HasAccessibles):
        @Command(StructOf(a=IntRange(), b=IntRange()))
        def cmd(self, a, b=5):
            pass
    assert Mod2.cmd.datatype.argument.optional == ['b']
    class Mod3(HasAccessibles):
        @Command(StructOf(a=IntRange(), b=IntRange()))
        def cmd(self, a, b):
            pass
    assert Mod3.cmd.datatype.argument.optional == []


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


@pytest.mark.parametrize('arg, value', [
    ('always', 0),
    (0, 0),
    ('never', 999999999),
    (999999999, 999999999),
    (1, 1),
])
def test_update_unchanged_ok(arg, value):
    par = Parameter('', datatype=FloatRange(), default=0, update_unchanged=arg)
    assert par.update_unchanged == value


@pytest.mark.parametrize('arg', ['alws', '', -2, -0.1, None])
def test_update_unchanged_fail(arg):
    with pytest.raises(ProgrammingError):
        Parameter('', datatype=FloatRange(), default=0, update_unchanged=arg)


def make_module(cls):
    class DispatcherStub:
        def announce_update(self, moduleobj, pobj):
            pass

    class LoggerStub:
        def debug(self, fmt, *args):
            print(fmt % args)
        info = warning = exception = error = debug
        handlers = []

    class ServerStub:
        dispatcher = DispatcherStub()
        secnode = None

    return cls('test', LoggerStub(), {'description': 'test'}, ServerStub())


def test_optional_parameters():
    class Base(Module):
        p1 = Parameter('overridden', datatype=FloatRange(),
                       default=1, readonly=False, optional=True)
        p2 = Parameter('not overridden', datatype=FloatRange(),
                       default=2, readonly=False, optional=True)

    class Mod(Base):
        p1 = Parameter()

        def read_p1(self):
            return self.p1

        def write_p1(self, value):
            return value

    assert Base.accessibles['p2'].optional

    with pytest.raises(ProgrammingError):
        class Mod2(Base):  # pylint: disable=unused-variable
            def read_p2(self):
                pass

    with pytest.raises(ProgrammingError):
        class Mod3(Base):  # pylint: disable=unused-variable
            def write_p2(self):
                pass

    base = make_module(Base)
    mod = make_module(Mod)

    assert 'p1' not in base.accessibles
    assert 'p1' not in base.parameters
    assert 'p2' not in base.accessibles
    assert 'p2' not in base.parameters

    assert 'p1' in mod.accessibles
    assert 'p1' in mod.parameters
    assert 'p2' not in mod.accessibles
    assert 'p2' not in mod.parameters

    assert mod.p1 == 1
    assert mod.read_p1() == 1
    mod.p1 = 11
    assert mod.read_p1() == 11

    with pytest.raises(ProgrammingError):
        assert mod.p2
    with pytest.raises(AttributeError):
        mod.read_p2()
    with pytest.raises(ProgrammingError):
        mod.p2 = 2
    with pytest.raises(AttributeError):
        mod.write_p2(2)


def test_optional_commands():
    class Base(Module):
        c1 = Command(FloatRange(1), result=FloatRange(2), description='overridden', optional=True)
        c2 = Command(description='not overridden', optional=True)

    class Mod(Base):
        def c1(self, value):
            return value + 1

    base = make_module(Base)
    mod = make_module(Mod)

    assert 'c1' not in base.accessibles
    assert 'c1' not in base.commands
    assert 'c2' not in base.accessibles
    assert 'c2' not in base.commands

    assert 'c1' in mod.accessibles
    assert 'c1' in mod.commands
    assert 'c2' not in mod.accessibles
    assert 'c2' not in mod.commands

    assert mod.c1(7) == 8

    with pytest.raises(ProgrammingError):
        mod.c2()
