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
    StringType, StructOf, TupleOf, get_datatype, ScaledInteger


def test_DataType():
    dt = DataType()
    assert dt.as_json == ['undefined']

    with pytest.raises(NotImplementedError):
        dt = DataType()
        dt.validate('')
        dt.export_value('')
        dt.import_value('')


def test_FloatRange():
    dt = FloatRange(-3.14, 3.14)
    assert dt.as_json == ['double', {'min':-3.14, 'max':3.14}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(ValueError):
        dt.validate([19, 'X'])
    dt.validate(1)
    dt.validate(0)
    assert dt.export_value(-2.718) == -2.718
    assert dt.import_value(-2.718) == -2.718
    with pytest.raises(ValueError):
        FloatRange('x', 'Y')

    dt = FloatRange()
    assert dt.as_json == ['double', {}]

    dt = FloatRange(unit='X', fmtstr='%r', absolute_precision=1,
                    relative_precision=0.1)
    assert dt.as_json == ['double', {'unit':'X', 'fmtstr':'%r',
                                     'absolute_precision':1,
                                     'relative_precision':0.1}]
    assert dt.validate(4) == 4


def test_IntRange():
    dt = IntRange(-3, 3)
    assert dt.as_json == ['int', {'min':-3, 'max':3}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(ValueError):
        dt.validate([19, 'X'])
    dt.validate(1)
    dt.validate(0)
    with pytest.raises(ValueError):
        IntRange('xc', 'Yx')

    dt = IntRange()
    assert dt.as_json[0] == 'int'
    assert dt.as_json[1]['min'] < 0 < dt.as_json[1]['max']

    dt = IntRange(unit='X', fmtstr='%r')
    assert dt.as_json == ['int', {'fmtstr': '%r', 'max': 16777216,
                                  'min': -16777216, 'unit': 'X'}]


def test_ScaledInteger():
    dt = ScaledInteger(0.01, -3, 3)
    # serialisation of datatype contains limits on the 'integer' value
    assert dt.as_json == ['scaled', {'scale':0.01, 'min':-300, 'max':300}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(ValueError):
        dt.validate([19, 'X'])
    dt.validate(1)
    dt.validate(0)
    with pytest.raises(ValueError):
        ScaledInteger('xc', 'Yx')
    with pytest.raises(ValueError):
        ScaledInteger(scale=0, minval=1, maxval=2)
    with pytest.raises(ValueError):
        ScaledInteger(scale=-10, minval=1, maxval=2)

    assert dt.export_value(0.0001) == int(0)
    assert dt.export_value(2.71819) == int(272)
    assert dt.import_value(272) == 2.72

    dt = ScaledInteger(0.003, 0, 1, unit='X', fmtstr='%r',
                       absolute_precision=1, relative_precision=0.1)
    assert dt.as_json == ['scaled', {'scale':0.003,'min':0,'max':333,
                                     'unit':'X', 'fmtstr':'%r',
                                     'absolute_precision':1,
                                     'relative_precision':0.1}]
    assert dt.validate(0.4) == 0.399


def test_EnumType():
    # test constructor catching illegal arguments
    with pytest.raises(TypeError):
        EnumType(1)
    with pytest.raises(TypeError):
        EnumType(['b', 0])

    dt = EnumType('dt', a=3, c=7, stuff=1)
    assert dt.as_json == ['enum', dict(members=dict(a=3, c=7, stuff=1))]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(TypeError):
        dt.validate([19, 'X'])

    assert dt.validate('a') == 3
    assert dt.validate('stuff') == 1
    assert dt.validate(1) == 1
    with pytest.raises(ValueError):
        dt.validate(2)

    assert dt.export_value('c') == 7
    assert dt.export_value('stuff') == 1
    assert dt.export_value(1) == 1
    assert dt.import_value('c') == 7
    assert dt.import_value('a') == 3
    assert dt.import_value('stuff') == 1
    with pytest.raises(ValueError):
        dt.export_value(2)
    with pytest.raises(ValueError):
        dt.import_value('A')


def test_BLOBType():
    # test constructor catching illegal arguments
    dt = BLOBType()
    assert dt.as_json == ['blob', {'min':0, 'max':255}]
    dt = BLOBType(10)
    assert dt.as_json == ['blob', {'min':10, 'max':10}]

    dt = BLOBType(3, 10)
    assert dt.as_json == ['blob', {'min':3, 'max':10}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')
    with pytest.raises(ValueError):
        dt.validate('abcdefghijklmno')
    assert dt.validate('abcd') == b'abcd'
    assert dt.validate(b'abcd') == b'abcd'
    assert dt.validate(u'abcd') == b'abcd'

    assert dt.export_value('abcd') == 'YWJjZA=='
    assert dt.export_value(b'abcd') == 'YWJjZA=='
    assert dt.export_value(u'abcd') == 'YWJjZA=='
    assert dt.import_value('YWJjZA==') == 'abcd'


def test_StringType():
    # test constructor catching illegal arguments
    dt = StringType()
    dt = StringType(12)
    assert dt.as_json == ['string', {'min':12, 'max':12}]

    dt = StringType(4, 11)
    assert dt.as_json == ['string', {'min':4, 'max':11}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')
    with pytest.raises(ValueError):
        dt.validate('abcdefghijklmno')
    with pytest.raises(ValueError):
        dt.validate('abcdefg\0')
    assert dt.validate('abcd') == b'abcd'
    assert dt.validate(b'abcd') == b'abcd'
    assert dt.validate(u'abcd') == b'abcd'

    assert dt.export_value('abcd') == b'abcd'
    assert dt.export_value(b'abcd') == b'abcd'
    assert dt.export_value(u'abcd') == b'abcd'
    assert dt.import_value(u'abcd') == 'abcd'


def test_BoolType():
    # test constructor catching illegal arguments
    dt = BoolType()
    assert dt.as_json == ['bool', {}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')

    assert dt.validate('true') is True
    assert dt.validate('off') is False
    assert dt.validate(1) is True

    assert dt.export_value('false') is False
    assert dt.export_value(0) is False
    assert dt.export_value('on') is True

    assert dt.import_value(False) is False
    assert dt.import_value(True) is True
    with pytest.raises(ValueError):
        dt.import_value('av')


def test_ArrayOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        ArrayOf(int)
    with pytest.raises(ValueError):
        ArrayOf(-3, IntRange(-10,10))
    dt = ArrayOf(IntRange(-10, 10), 5)
    assert dt.as_json == ['array', {'min':5, 'max':5,
                                    'members':['int', {'min':-10, 'max':10}]}]

    dt = ArrayOf(IntRange(-10, 10), 1, 3)
    assert dt.as_json == ['array', {'min':1, 'max':3,
                                    'members':['int', {'min':-10, 'max':10}]}]
    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')

    assert dt.validate([1, 2, 3]) == [1, 2, 3]

    assert dt.export_value([1, 2, 3]) == [1, 2, 3]
    assert dt.import_value([1, 2, 3]) == [1, 2, 3]


def test_TupleOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        TupleOf(2)

    dt = TupleOf(IntRange(-10, 10), BoolType())
    assert dt.as_json == ['tuple', {'members':[['int', {'min':-10, 'max':10}],
                                               ['bool', {}]]}]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate([99, 'X'])

    assert dt.validate([1, True]) == [1, True]

    assert dt.export_value([1, True]) == [1, True]
    assert dt.import_value([1, True]) == [1, True]


def test_StructOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        StructOf(IntRange)  # pylint: disable=E1121
    with pytest.raises(ProgrammingError):
        StructOf(IntRange=1)

    dt = StructOf(a_string=StringType(0, 55), an_int=IntRange(0, 999),
                  optional=['an_int'])
    assert dt.as_json == [u'struct', {'members':{u'a_string':
                                         [u'string', {'min':0, 'max':55}],
                                     u'an_int':
                                         [u'int', {'min':0, 'max':999}],},
                                      'optional':['an_int'],
                                     }]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate([99, 'X'])
    with pytest.raises(ValueError):
        dt.validate(dict(a_string='XXX', an_int=1811))

    assert dt.validate(dict(a_string='XXX', an_int=8)) == {'a_string': 'XXX',
                                                           'an_int': 8}
    assert dt.export_value({'an_int': 13, 'a_string': 'WFEC'}) == {
        'a_string': 'WFEC', 'an_int': 13}
    assert dt.import_value({'an_int': 13, 'a_string': 'WFEC'}) == {
        'a_string': 'WFEC', 'an_int': 13}


def test_get_datatype():
    with pytest.raises(ValueError):
        get_datatype(1)
    with pytest.raises(ValueError):
        get_datatype(True)
    with pytest.raises(ValueError):
        get_datatype(str)
    with pytest.raises(ValueError):
        get_datatype(['undefined'])

    assert isinstance(get_datatype(['bool', {}]), BoolType)
    with pytest.raises(ValueError):
        get_datatype(['bool'])
    with pytest.raises(ValueError):
        get_datatype(['bool', 3])

    with pytest.raises(ValueError):
        get_datatype(['int', {'min':-10}])
    with pytest.raises(ValueError):
        get_datatype(['int', {'max':10}])
    assert isinstance(get_datatype(['int', {'min':-10, 'max':10}]), IntRange)

    with pytest.raises(ValueError):
        get_datatype(['int', {'min':10, 'max':-10}])
    with pytest.raises(ValueError):
        get_datatype(['int'])
    with pytest.raises(ValueError):
        get_datatype(['int', {}])
    with pytest.raises(ValueError):
        get_datatype(['int', 1, 2])

    assert isinstance(get_datatype(['double', {}]), FloatRange)
    assert isinstance(get_datatype(['double', {'min':-2.718}]), FloatRange)
    assert isinstance(get_datatype(['double', {'max':3.14}]), FloatRange)
    assert isinstance(get_datatype(['double', {'min':-9.9, 'max':11.1}]),
                      FloatRange)

    with pytest.raises(ValueError):
        get_datatype(['double'])
    with pytest.raises(ValueError):
        get_datatype(['double', {'min':10, 'max':-10}])
    with pytest.raises(ValueError):
        get_datatype(['double', 1, 2])

    with pytest.raises(ValueError):
        get_datatype(['scaled', {'scale':0.01,'min':-2.718}])
    with pytest.raises(ValueError):
        get_datatype(['scaled', {'scale':0.02,'max':3.14}])
    assert isinstance(get_datatype(['scaled', {'scale':0.03,
                                               'min':-99,
                                               'max':111}]), ScaledInteger)

    dt = ScaledInteger(scale=0.03, minval=0, maxval=9.9)
    assert dt.as_json == ['scaled', {'max':330, 'min':0, 'scale':0.03}]
    assert get_datatype(dt.as_json).as_json == dt.as_json

    with pytest.raises(ValueError):
        get_datatype(['scaled'])    # dict missing
    with pytest.raises(ValueError):
        get_datatype(['scaled', {'min':-10, 'max':10}])  # no scale
    with pytest.raises(ValueError):
        get_datatype(['scaled', {'min':10, 'max':-10}])  # limits reversed
    with pytest.raises(ValueError):
        get_datatype(['scaled', {}, 1, 2])  # trailing data

    with pytest.raises(ValueError):
        get_datatype(['enum'])
    with pytest.raises(ValueError):
        get_datatype(['enum', dict(a=-2)])
    assert isinstance(get_datatype(['enum', {'members':dict(a=-2)}]), EnumType)

    with pytest.raises(ValueError):
        get_datatype(['enum', 10, -10])
    with pytest.raises(ValueError):
        get_datatype(['enum', [1, 2, 3]])

    assert isinstance(get_datatype(['blob', {'max':1}]), BLOBType)
    assert isinstance(get_datatype(['blob', {'min':1, 'max':10}]), BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['blob', {'min':10, 'max':1}])
    with pytest.raises(ValueError):
        get_datatype(['blob', {'min':10, 'max':-10}])
    with pytest.raises(ValueError):
        get_datatype(['blob', 10, -10, 1])

    with pytest.raises(ValueError):
        get_datatype(['string'])
    assert isinstance(get_datatype(['string', {'min':1}]), StringType)
    assert isinstance(get_datatype(['string', {'min':1, 'max':10}]), StringType)

    with pytest.raises(ValueError):
        get_datatype(['string', {'min':10, 'max':1}])
    with pytest.raises(ValueError):
        get_datatype(['string', {'min':10, 'max':-10}])
    with pytest.raises(ValueError):
        get_datatype(['string', 10, -10, 1])

    with pytest.raises(ValueError):
        get_datatype(['array'])
    with pytest.raises(ValueError):
        get_datatype(['array', 1])
    with pytest.raises(ValueError):
        get_datatype(['array', [1], 2, 3])
    assert isinstance(get_datatype(['array', {'min':1, 'max':1,
                                              'members':['blob', {'max':1}]}]
                                   ), ArrayOf)
    assert isinstance(get_datatype(['array', {'min':1, 'max':1,
                                              'members':['blob', {'max':1}]}]
                                   ).subtype, BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['array', {'members':['blob', {'max':1}], 'min':-10}])
    with pytest.raises(ValueError):
        get_datatype(['array', {'members':['blob', {'max':1}],
                                'min':10, 'max':1}])
    with pytest.raises(ValueError):
        get_datatype(['array', ['blob', 1], 10, -10])

    with pytest.raises(ValueError):
        get_datatype(['tuple'])
    with pytest.raises(ValueError):
        get_datatype(['tuple', 1])
    with pytest.raises(ValueError):
        get_datatype(['tuple', [1], 2, 3])
    assert isinstance(get_datatype(['tuple', {'members':[['blob',
                                        {'max':1}]]}]), TupleOf)
    assert isinstance(get_datatype(['tuple', {'members':[['blob',
                                        {'max':1}]]}]).subtypes[0], BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['tuple', {}])
    with pytest.raises(ValueError):
        get_datatype(['tuple', 10, -10])

    assert isinstance(get_datatype(['tuple', {'members':[['blob', {'max':1}],
                                                    ['bool',{}]]}]), TupleOf)

    with pytest.raises(ValueError):
        get_datatype(['struct'])
    with pytest.raises(ValueError):
        get_datatype(['struct', 1])
    with pytest.raises(ValueError):
        get_datatype(['struct', [1], 2, 3])
    assert isinstance(get_datatype(['struct', {'members':
            {'name': ['blob', {'max':1}]}}]), StructOf)
    assert isinstance(get_datatype(['struct', {'members':
            {'name': ['blob', {'max':1}]}}]).named_subtypes['name'], BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['struct', {}])
    with pytest.raises(ValueError):
        get_datatype(['struct', {'members':[1,2,3]}])
