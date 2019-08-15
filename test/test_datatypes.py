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

# no fixtures needed
import pytest

from secop.datatypes import ArrayOf, BLOBType, BoolType, \
    DataType, EnumType, FloatRange, IntRange, ProgrammingError, \
    ScaledInteger, StringType, TextType, StructOf, TupleOf, get_datatype, CommandType


def copytest(dt):
    assert repr(dt) == repr(dt.copy())
    assert dt.export_datatype() == dt.copy().export_datatype()
    assert dt != dt.copy()

def test_DataType():
    dt = DataType()
    with pytest.raises(NotImplementedError):
        dt.export_datatype()
    with pytest.raises(NotImplementedError):
        dt('')
    dt.export_value('')
    dt.import_value('')


def test_FloatRange():
    dt = FloatRange(-3.14, 3.14)
    copytest(dt)
    assert dt.export_datatype() == [u'double', {u'min':-3.14, u'max':3.14}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(-9)
    with pytest.raises(ValueError):
        dt(u'XX')
    with pytest.raises(ValueError):
        dt([19, u'X'])
    dt(1)
    dt(0)
    dt(13.14 - 10)  # raises an error, if resolution is not handled correctly
    assert dt.export_value(-2.718) == -2.718
    assert dt.import_value(-2.718) == -2.718
    with pytest.raises(ValueError):
        FloatRange(u'x', u'Y')
    # check that unit can be changed
    dt.unit = u'K'
    assert dt.export_datatype() == [u'double', {u'min':-3.14, u'max':3.14, u'unit': u'K'}]

    dt = FloatRange()
    copytest(dt)
    assert dt.export_datatype() == [u'double', {}]

    dt = FloatRange(unit=u'X', fmtstr=u'%.2f', absolute_resolution=1,
                    relative_resolution=0.1)
    copytest(dt)
    assert dt.export_datatype() == [u'double', {u'unit':u'X', u'fmtstr':u'%.2f',
                                      u'absolute_resolution':1.0,
                                      u'relative_resolution':0.1}]
    assert dt(4) == 4
    assert dt.format_value(3.14) == u'3.14 X'
    assert dt.format_value(3.14, u'') == u'3.14'
    assert dt.format_value(3.14, u'#') == u'3.14 #'


def test_IntRange():
    dt = IntRange(-3, 3)
    copytest(dt)
    assert dt.export_datatype() == [u'int', {u'min':-3, u'max':3}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(-9)
    with pytest.raises(ValueError):
        dt(u'XX')
    with pytest.raises(ValueError):
        dt([19, u'X'])
    dt(1)
    dt(0)
    with pytest.raises(ValueError):
        IntRange(u'xc', u'Yx')

    dt = IntRange()
    copytest(dt)
    assert dt.export_datatype()[0] == u'int'
    assert dt.export_datatype()[1][u'min'] < 0 < dt.export_datatype()[1][u'max']
    assert dt.export_datatype() == [u'int', {u'max': 16777216, u'min': -16777216}]
    assert dt.format_value(42) == u'42'

def test_ScaledInteger():
    dt = ScaledInteger(0.01, -3, 3)
    copytest(dt)
    # serialisation of datatype contains limits on the 'integer' value
    assert dt.export_datatype() == [u'scaled', {u'scale':0.01, u'min':-300, u'max':300}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(-9)
    with pytest.raises(ValueError):
        dt(u'XX')
    with pytest.raises(ValueError):
        dt([19, u'X'])
    dt(1)
    dt(0)
    with pytest.raises(ValueError):
        ScaledInteger(u'xc', u'Yx')
    with pytest.raises(ValueError):
        ScaledInteger(scale=0, minval=1, maxval=2)
    with pytest.raises(ValueError):
        ScaledInteger(scale=-10, minval=1, maxval=2)
    # check that unit can be changed
    dt.unit = u'A'
    assert dt.export_datatype() == [u'scaled', {u'scale':0.01, u'min':-300, u'max':300, u'unit': u'A'}]

    assert dt.export_value(0.0001) == int(0)
    assert dt.export_value(2.71819) == int(272)
    assert dt.import_value(272) == 2.72

    dt = ScaledInteger(0.003, 0, 1, unit=u'X', fmtstr=u'%.1f',
                       absolute_resolution=0.001, relative_resolution=1e-5)
    copytest(dt)
    assert dt.export_datatype() == [u'scaled', {u'scale':0.003, u'min':0, u'max':333,
                                      u'unit':u'X', u'fmtstr':u'%.1f',
                                      u'absolute_resolution':0.001,
                                      u'relative_resolution':1e-5}]
    assert dt(0.4) == 0.399
    assert dt.format_value(0.4) == u'0.4 X'
    assert dt.format_value(0.4, u'') == u'0.4'
    assert dt.format_value(0.4, u'Z') == u'0.4 Z'
    assert dt(1.0029) == 0.999
    with pytest.raises(ValueError):
        dt(1.004)


def test_EnumType():
    # test constructor catching illegal arguments
    with pytest.raises(TypeError):
        EnumType(1)
    with pytest.raises(TypeError):
        EnumType([u'b', 0])

    dt = EnumType(u'dt', a=3, c=7, stuff=1)
    copytest(dt)
    assert dt.export_datatype() == [u'enum', dict(members=dict(a=3, c=7, stuff=1))]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(-9)
    with pytest.raises(ValueError):
        dt(u'XX')
    with pytest.raises(ValueError):
        dt([19, u'X'])

    assert dt(u'a') == 3
    assert dt(u'stuff') == 1
    assert dt(1) == 1
    with pytest.raises(ValueError):
        dt(2)

    assert dt.export_value(u'c') == 7
    assert dt.export_value(u'stuff') == 1
    assert dt.export_value(1) == 1
    assert dt.import_value(u'c') == 7
    assert dt.import_value(u'a') == 3
    assert dt.import_value(u'stuff') == 1
    with pytest.raises(ValueError):
        dt.export_value(2)
    with pytest.raises(ValueError):
        dt.import_value(u'A')

    assert dt.format_value(3) == u'a<3>'


def test_BLOBType():
    # test constructor catching illegal arguments
    dt = BLOBType()
    copytest(dt)
    assert dt.export_datatype() == [u'blob', {u'min':0, u'max':255}]
    dt = BLOBType(10)
    copytest(dt)
    assert dt.export_datatype() == [u'blob', {u'min':10, u'max':10}]

    dt = BLOBType(3, 10)
    copytest(dt)
    assert dt.export_datatype() == [u'blob', {u'min':3, u'max':10}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(u'av')
    with pytest.raises(ValueError):
        dt(u'abcdefghijklmno')
    assert dt('abcd') == b'abcd'
    assert dt(b'abcd') == b'abcd'
    assert dt(u'abcd') == b'abcd'

    assert dt.export_value('abcd') == u'YWJjZA=='
    assert dt.export_value(b'abcd') == u'YWJjZA=='
    assert dt.export_value(u'abcd') == u'YWJjZA=='
    assert dt.import_value(u'YWJjZA==') == b'abcd'

    # XXX: right? or different format?
    assert dt.format_value(b'ab\0cd') == '\'ab\\x00cd\''


def test_StringType():
    # test constructor catching illegal arguments
    dt = StringType()
    copytest(dt)
    dt = StringType(12)
    copytest(dt)
    assert dt.export_datatype() == [u'string', {u'min':12, u'max':12}]

    dt = StringType(4, 11)
    copytest(dt)
    assert dt.export_datatype() == [u'string', {u'min':4, u'max':11}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(u'av')
    with pytest.raises(ValueError):
        dt(u'abcdefghijklmno')
    with pytest.raises(ValueError):
        dt('abcdefg\0')
    assert dt('abcd') == b'abcd'
    assert dt(b'abcd') == b'abcd'
    assert dt(u'abcd') == b'abcd'

    assert dt.export_value('abcd') == b'abcd'
    assert dt.export_value(b'abcd') == b'abcd'
    assert dt.export_value(u'abcd') == b'abcd'
    assert dt.import_value(u'abcd') == u'abcd'

    assert dt.format_value(u'abcd') == u"u'abcd'"


def test_TextType():
    # test constructor catching illegal arguments
    dt = TextType(12)
    assert dt.export_datatype() == [u'string', {u'min':0, u'max':12}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(u'abcdefghijklmno')
    with pytest.raises(ValueError):
        dt('abcdefg\0')
    assert dt('ab\n\ncd\n') == b'ab\n\ncd\n'
    assert dt(b'ab\n\ncd\n') == b'ab\n\ncd\n'
    assert dt(u'ab\n\ncd\n') == b'ab\n\ncd\n'

    assert dt.export_value('abcd') == b'abcd'
    assert dt.export_value(b'abcd') == b'abcd'
    assert dt.export_value(u'abcd') == b'abcd'
    assert dt.import_value(u'abcd') == u'abcd'


def test_BoolType():
    # test constructor catching illegal arguments
    dt = BoolType()
    copytest(dt)
    assert dt.export_datatype() == [u'bool', {}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(u'av')

    assert dt(u'true') is True
    assert dt(u'off') is False
    assert dt(1) is True

    assert dt.export_value(u'false') is False
    assert dt.export_value(0) is False
    assert dt.export_value(u'on') is True

    assert dt.import_value(False) is False
    assert dt.import_value(True) is True
    with pytest.raises(ValueError):
        dt.import_value(u'av')

    assert dt.format_value(0) == u"False"
    assert dt.format_value(True) == u"True"


def test_ArrayOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        ArrayOf(int)
    with pytest.raises(ValueError):
        ArrayOf(-3, IntRange(-10,10))
    dt = ArrayOf(IntRange(-10, 10), 5)
    copytest(dt)
    assert dt.export_datatype() == [u'array', {u'min':5, u'max':5,
                                     u'members':[u'int', {u'min':-10,
                                                          u'max':10}]}]

    dt = ArrayOf(FloatRange(-10, 10, unit=u'Z'), 1, 3)
    copytest(dt)
    assert dt.export_datatype() == [u'array', {u'min':1, u'max':3,
                                     u'members':[u'double', {u'min':-10,
                                                             u'max':10,
                                                             u'unit':u'Z'}]}]
    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt(u'av')

    assert dt([1, 2, 3]) == [1, 2, 3]

    assert dt.export_value([1, 2, 3]) == [1, 2, 3]
    assert dt.import_value([1, 2, 3]) == [1, 2, 3]

    assert dt.format_value([1,2,3]) == u'[1, 2, 3] Z'
    assert dt.format_value([1,2,3], u'') == u'[1, 2, 3]'
    assert dt.format_value([1,2,3], u'Q') == u'[1, 2, 3] Q'


def test_TupleOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        TupleOf(2)

    dt = TupleOf(IntRange(-10, 10), BoolType())
    copytest(dt)
    assert dt.export_datatype() == [u'tuple', {u'members':[[u'int', {u'min':-10,
                                                           u'max':10}],
                                                 [u'bool', {}]]}]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt([99, 'X'])

    assert dt([1, True]) == [1, True]

    assert dt.export_value([1, True]) == [1, True]
    assert dt.import_value([1, True]) == [1, True]

    assert dt.format_value([3,0]) == u"(3, False)"


def test_StructOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        StructOf(IntRange)  # pylint: disable=E1121
    with pytest.raises(ProgrammingError):
        StructOf(IntRange=1)

    dt = StructOf(a_string=StringType(0, 55), an_int=IntRange(0, 999),
                  optional=[u'an_int'])
    copytest(dt)
    assert dt.export_datatype() == [u'struct', {u'members':{u'a_string':
                                         [u'string', {u'min':0, u'max':55}],
                                      u'an_int':
                                         [u'int', {u'min':0, u'max':999}],},
                                      u'optional':[u'an_int'],
                                     }]

    with pytest.raises(ValueError):
        dt(9)
    with pytest.raises(ValueError):
        dt([99, u'X'])
    with pytest.raises(ValueError):
        dt(dict(a_string=u'XXX', an_int=1811))

    assert dt(dict(a_string=u'XXX', an_int=8)) == {u'a_string': u'XXX',
                                                            u'an_int': 8}
    assert dt.export_value({u'an_int': 13, u'a_string': u'WFEC'}) == {
        u'a_string': u'WFEC', u'an_int': 13}
    assert dt.import_value({u'an_int': 13, u'a_string': u'WFEC'}) == {
        u'a_string': u'WFEC', u'an_int': 13}

    assert dt.format_value({u'an_int':2, u'a_string':u'Z'}) == u"{a_string=u'Z', an_int=2}"


def test_Command():
    dt = CommandType()
    assert dt.export_datatype() == [u'command', {u'argument':None, u'result':None}]

    dt = CommandType(IntRange(-1,1))
    assert dt.export_datatype() == [u'command', {u'argument':[u'int', {u'min':-1, u'max':1}], u'result':None}]

    dt = CommandType(IntRange(-1,1), IntRange(-3,3))
    assert dt.export_datatype() == [u'command', {u'argument':[u'int', {u'min':-1, u'max':1}],
                                                 u'result':[u'int', {u'min':-3, u'max':3}]}]


def test_get_datatype():
    with pytest.raises(ValueError):
        get_datatype(1)
    with pytest.raises(ValueError):
        get_datatype(True)
    with pytest.raises(ValueError):
        get_datatype(str)
    with pytest.raises(ValueError):
        get_datatype([u'undefined'])

    assert isinstance(get_datatype([u'bool', {}]), BoolType)
    with pytest.raises(ValueError):
        get_datatype([u'bool'])
    with pytest.raises(ValueError):
        get_datatype([u'bool', 3])

    with pytest.raises(ValueError):
        get_datatype([u'int', {u'min':-10}])
    with pytest.raises(ValueError):
        get_datatype([u'int', {u'max':10}])
    assert isinstance(get_datatype([u'int', {u'min':-10, u'max':10}]), IntRange)

    with pytest.raises(ValueError):
        get_datatype([u'int', {u'min':10, u'max':-10}])
    with pytest.raises(ValueError):
        get_datatype([u'int'])
    with pytest.raises(ValueError):
        get_datatype([u'int', {}])
    with pytest.raises(ValueError):
        get_datatype([u'int', 1, 2])

    assert isinstance(get_datatype([u'double', {}]), FloatRange)
    assert isinstance(get_datatype([u'double', {u'min':-2.718}]), FloatRange)
    assert isinstance(get_datatype([u'double', {u'max':3.14}]), FloatRange)
    assert isinstance(get_datatype([u'double', {u'min':-9.9, u'max':11.1}]),
                      FloatRange)

    with pytest.raises(ValueError):
        get_datatype([u'double'])
    with pytest.raises(ValueError):
        get_datatype([u'double', {u'min':10, u'max':-10}])
    with pytest.raises(ValueError):
        get_datatype([u'double', 1, 2])

    with pytest.raises(ValueError):
        get_datatype([u'scaled', {u'scale':0.01,u'min':-2.718}])
    with pytest.raises(ValueError):
        get_datatype([u'scaled', {u'scale':0.02,u'max':3.14}])
    assert isinstance(get_datatype([u'scaled', {u'scale':0.03,
                                                u'min':-99,
                                                u'max':111}]), ScaledInteger)

    dt = ScaledInteger(scale=0.03, minval=0, maxval=9.9)
    assert dt.export_datatype() == [u'scaled', {u'max':330, u'min':0, u'scale':0.03}]
    assert get_datatype(dt.export_datatype()).export_datatype() == dt.export_datatype()

    with pytest.raises(ValueError):
        get_datatype([u'scaled'])    # dict missing
    with pytest.raises(ValueError):
        get_datatype([u'scaled', {u'min':-10, u'max':10}])  # no scale
    with pytest.raises(ValueError):
        get_datatype([u'scaled', {u'min':10, u'max':-10}])  # limits reversed
    with pytest.raises(ValueError):
        get_datatype([u'scaled', {}, 1, 2])  # trailing data

    with pytest.raises(ValueError):
        get_datatype([u'enum'])
    with pytest.raises(ValueError):
        get_datatype([u'enum', dict(a=-2)])
    assert isinstance(get_datatype([u'enum', {u'members':dict(a=-2)}]), EnumType)

    with pytest.raises(ValueError):
        get_datatype([u'enum', 10, -10])
    with pytest.raises(ValueError):
        get_datatype([u'enum', [1, 2, 3]])

    assert isinstance(get_datatype([u'blob', {u'max':1}]), BLOBType)
    assert isinstance(get_datatype([u'blob', {u'min':1, u'max':10}]), BLOBType)

    with pytest.raises(ValueError):
        get_datatype([u'blob', {u'min':10, u'max':1}])
    with pytest.raises(ValueError):
        get_datatype([u'blob', {u'min':10, u'max':-10}])
    with pytest.raises(ValueError):
        get_datatype([u'blob', 10, -10, 1])

    with pytest.raises(ValueError):
        get_datatype([u'string'])
    assert isinstance(get_datatype([u'string', {u'min':1}]), StringType)
    assert isinstance(get_datatype([u'string', {u'min':1, u'max':10}]), StringType)

    with pytest.raises(ValueError):
        get_datatype([u'string', {u'min':10, u'max':1}])
    with pytest.raises(ValueError):
        get_datatype([u'string', {u'min':10, u'max':-10}])
    with pytest.raises(ValueError):
        get_datatype([u'string', 10, -10, 1])

    with pytest.raises(ValueError):
        get_datatype([u'array'])
    with pytest.raises(ValueError):
        get_datatype([u'array', 1])
    with pytest.raises(ValueError):
        get_datatype([u'array', [1], 2, 3])
    assert isinstance(get_datatype([u'array', {u'min':1, u'max':1,
                                               u'members':[u'blob', {u'max':1}]}]
                                   ), ArrayOf)
    assert isinstance(get_datatype([u'array', {u'min':1, u'max':1,
                                               u'members':[u'blob', {u'max':1}]}]
                                   ).members, BLOBType)

    with pytest.raises(ValueError):
        get_datatype([u'array', {u'members':[u'blob', {u'max':1}], u'min':-10}])
    with pytest.raises(ValueError):
        get_datatype([u'array', {u'members':[u'blob', {u'max':1}],
                                 u'min':10, 'max':1}])
    with pytest.raises(ValueError):
        get_datatype([u'array', [u'blob', 1], 10, -10])

    with pytest.raises(ValueError):
        get_datatype([u'tuple'])
    with pytest.raises(ValueError):
        get_datatype([u'tuple', 1])
    with pytest.raises(ValueError):
        get_datatype([u'tuple', [1], 2, 3])
    assert isinstance(get_datatype([u'tuple', {u'members':[[u'blob',
                                        {u'max':1}]]}]), TupleOf)
    assert isinstance(get_datatype([u'tuple', {u'members':[[u'blob',
                                        {u'max':1}]]}]).members[0], BLOBType)

    with pytest.raises(ValueError):
        get_datatype([u'tuple', {}])
    with pytest.raises(ValueError):
        get_datatype([u'tuple', 10, -10])

    assert isinstance(get_datatype([u'tuple', {u'members':[[u'blob', {u'max':1}],
                                                    [u'bool',{}]]}]), TupleOf)

    with pytest.raises(ValueError):
        get_datatype([u'struct'])
    with pytest.raises(ValueError):
        get_datatype([u'struct', 1])
    with pytest.raises(ValueError):
        get_datatype([u'struct', [1], 2, 3])
    assert isinstance(get_datatype([u'struct', {u'members':
            {u'name': [u'blob', {u'max':1}]}}]), StructOf)
    assert isinstance(get_datatype([u'struct', {u'members':
            {u'name': [u'blob', {u'max':1}]}}]).members[u'name'], BLOBType)

    with pytest.raises(ValueError):
        get_datatype([u'struct', {}])
    with pytest.raises(ValueError):
        get_datatype([u'struct', {u'members':[1,2,3]}])
