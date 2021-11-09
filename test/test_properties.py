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

from secop.datatypes import FloatRange, IntRange, StringType, ValueType
from secop.errors import BadValueError, ConfigError, ProgrammingError
from secop.properties import HasProperties, Property


def Prop(*args, name=None, **kwds):
    # collect the args for Property
    return name, args, kwds


# Property(description, datatype, default, ...)
V_test_Property = [
    [Prop(StringType(), 'default', extname='extname', mandatory=False),
     dict(default='default', extname='extname', export=True, mandatory=False)
     ],
    [Prop(IntRange(), '42', export=True, name='custom', mandatory=True),
     dict(default=42, extname='_custom', export=True, mandatory=True),
     ],
    [Prop(IntRange(), '42', export=True, name='name'),
     dict(default=42, extname='_name', export=True, mandatory=False)
     ],
    [Prop(IntRange(), 42, '_extname', mandatory=True),
     dict(default=42, extname='_extname', export=True, mandatory=True)
     ],
    [Prop(IntRange(), 0, export=True, mandatory=True),
     dict(default=0, extname='', export=True, mandatory=True)
     ],
    [Prop(IntRange(), 0, export=True, mandatory=False),
     dict(default=0, extname='', export=True, mandatory=False)
     ],
    [Prop(IntRange(), 0, export=False, mandatory=True),
     dict(default=0, extname='', export=False, mandatory=True)
     ],
    [Prop(IntRange(), 0, export=False, mandatory=False),
     dict(default=0, extname='', export=False, mandatory=False)
     ],
    [Prop(IntRange()),
     dict(default=0, extname='', export=False, mandatory=True)  # mandatory not given, no default -> mandatory
     ],
    [Prop(ValueType(), 1),
     dict(default=1, extname='', export=False, mandatory=False)  # mandatory not given, default given -> NOT mandatory
     ],
]
@pytest.mark.parametrize('propargs, check', V_test_Property)
def test_Property(propargs, check):
    name, args, kwds = propargs
    p = Property('', *args, **kwds)
    if name:
        p.__set_name__(None, name)
    result = {k: getattr(p, k) for k in check}
    assert result == check


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
    class Cls(HasProperties):
        aa = Property('', IntRange(0, 99), '42', export=True)
        bb = Property('', IntRange(), 0, export=False)

    assert Cls.aa.default == 42
    assert Cls.aa.export is True
    assert Cls.aa.extname == '_aa'

    cc = Cls()
    with pytest.raises(BadValueError):
        cc.aa = 137

    assert Cls.bb.default == 0
    assert Cls.bb.export is False
    assert Cls.bb.extname == ''


class c(HasProperties):
    # properties
    a = Property('', IntRange(), 1)


class cl(c):
    # properties
    a = Property('', IntRange(), 3)
    b = Property('', FloatRange(), 3.14)
    minabc = Property('', IntRange(), 8)
    maxabc = Property('', IntRange(), 9)
    minx = Property('', IntRange(), 2)
    maxy = Property('', IntRange(), 1)


def test_HasProperties():
    o = c()
    assert o.a == 1
    o = cl()
    assert o.a == 3
    assert o.b == 3.14


def test_Property_checks():
    o = c()
    o.checkProperties()
    o = cl()
    o.checkProperties()
    # test for min/max check
    o.setProperty('maxabc', 1)
    with pytest.raises(ConfigError):
        o.checkProperties()


def test_Property_override():
    o1 = c()
    class co(c):
        a = 3
    o2 = co()
    assert o1.a == 1
    assert o2.a == 3

    with pytest.raises(ProgrammingError) as e:
        class cx(c): # pylint: disable=unused-variable
            def a(self):
                pass
    assert 'collides with' in str(e.value)

    with pytest.raises(ProgrammingError) as e:
        class cz(c): # pylint: disable=unused-variable
            a = 's'

    assert 'can not set' in str(e.value)


def test_Properties_mro():
    class Base(HasProperties):
        prop = Property('base', StringType(), 'base', export='always')

    class SubA(Base):
        pass

    class SubB(Base):
        prop = Property('sub', FloatRange(), extname='prop')

    class FinalBA(SubB, SubA):
        prop = 1

    class FinalAB(SubA, SubB):
        prop = 2

    assert SubA().exportProperties() == {'_prop': 'base'}
    assert FinalBA().exportProperties() == {'prop': 1.0}
    # in an older implementation the following would fail, as SubA.p is constructed first
    # and then SubA.p overrides SubB.p
    assert FinalAB().exportProperties() == {'prop': 2.0}
