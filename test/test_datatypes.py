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

import sys
sys.path.insert(0, sys.path[0]+'/..')

from secop.datatypes import DataType, FloatRange, IntRange, \
    EnumType, BLOBType, StringType, BoolType, ArrayOf, TupleOf, StructOf, \
    get_datatype, ProgrammingError


def test_DataType():
    dt = DataType()
    assert dt.as_json == ['undefined']

    with pytest.raises(TypeError):
        dt = DataType()
        dt.validate('')
        dt.export()

def test_FloatRange():
    dt = FloatRange(-3.14, 3.14)
    assert dt.as_json == ['double', -3.14, 3.14]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(ValueError):
        dt.validate([19,'X'])
    dt.validate(1)
    dt.validate(0)
    assert dt.export(-2.718) == -2.718
    with pytest.raises(ValueError):
        FloatRange('x','Y')

    dt = FloatRange()
    assert dt.as_json == ['double']

def test_IntRange():
    dt = IntRange(-3, 3)
    assert dt.as_json == ['int', -3, 3]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(ValueError):
        dt.validate([19,'X'])
    dt.validate(1)
    dt.validate(0)
    with pytest.raises(ValueError):
        IntRange('xc','Yx')

    dt = IntRange()
    assert dt.as_json == ['int']

def test_EnumType():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        EnumType(1)
    with pytest.raises(ValueError):
        EnumType('a',b=0)

    dt = EnumType(a=3, c=7, stuff=1)
    assert dt.as_json == ['enum', dict(a=3, c=7, stuff=1)]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate(-9)
    with pytest.raises(ValueError):
        dt.validate('XX')
    with pytest.raises(TypeError):
        dt.validate([19,'X'])

    assert dt.validate('a') == 'a'
    assert dt.validate('stuff') == 'stuff'
    assert dt.validate(1) == 'stuff'
    with pytest.raises(ValueError):
        dt.validate(2)

    assert dt.export('c') == 7
    assert dt.export('stuff') == 1
    assert dt.export(1) == 1
    with pytest.raises(ValueError):
        dt.export(2)

def test_BLOBType():
    # test constructor catching illegal arguments
    dt = BLOBType(3, 10)
    assert dt.as_json == ['blob', 10, 3]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')
    with pytest.raises(ValueError):
        dt.validate('abcdefghijklmno')
    assert dt.validate('abcd') == b'abcd'
    assert dt.validate(b'abcd') == b'abcd'
    assert dt.validate(u'abcd') == b'abcd'

    assert dt.export('abcd') == b'abcd'
    assert dt.export(b'abcd') == b'abcd'
    assert dt.export(u'abcd') == b'abcd'


def test_StringType():
    # test constructor catching illegal arguments
    dt = StringType(4, 11)
    assert dt.as_json == ['string', 11, 4]

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

    assert dt.export('abcd') == b'abcd'
    assert dt.export(b'abcd') == b'abcd'
    assert dt.export(u'abcd') == b'abcd'


def test_BoolType():
    # test constructor catching illegal arguments
    dt = BoolType()
    assert dt.as_json == ['bool']

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')

    assert dt.validate('true') == True
    assert dt.validate('off') == False
    assert dt.validate(1) == True

    assert dt.export('false') == False
    assert dt.export(0) == False
    assert dt.export('on') == True


def test_ArrayOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        ArrayOf(int)
    dt = ArrayOf(IntRange(-10,10),1,3)
    assert dt.as_json == ['array', ['int', -10, 10], 3, 1]
    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate('av')

    assert dt.validate([1,2,3]) == [1,2,3]

    assert dt.export([1,2,3]) == [1,2,3]


def test_TupleOf():
    # test constructor catching illegal arguments
    with pytest.raises(ValueError):
        TupleOf(2)

    dt = TupleOf(IntRange(-10,10), BoolType())
    assert dt.as_json == ['tuple', [['int', -10, 10], ['bool']]]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate([99,'X'])

    assert dt.validate([1,True]) == [1,True]

    assert dt.export([1,True]) == [1,True]


def test_StructOf():
    # test constructor catching illegal arguments
    with pytest.raises(TypeError):
        StructOf(IntRange)
    with pytest.raises(ProgrammingError):
        StructOf(IntRange=1)

    dt = StructOf(a_string=StringType(), an_int=IntRange(0, 999))
    assert dt.as_json == ['struct', {'a_string': ['string'],
                                     'an_int': ['int', 0, 999],
                                    }]

    with pytest.raises(ValueError):
        dt.validate(9)
    with pytest.raises(ValueError):
        dt.validate([99,'X'])
    with pytest.raises(ValueError):
        dt.validate(dict(a_string='XXX', an_int=1811))

    assert dt.validate(dict(a_string='XXX', an_int=8)) == {'a_string': 'XXX',
                                                           'an_int': 8}
    assert dt.export({'an_int':13, 'a_string':'WFEC'}) == {'a_string': 'WFEC',
                                                           'an_int': 13}

def test_get_datatype():
    with pytest.raises(ValueError):
        get_datatype(1)
    with pytest.raises(ValueError):
        get_datatype(True)
    with pytest.raises(ValueError):
        get_datatype(str)
    with pytest.raises(ValueError):
        get_datatype(['undefined'])

    assert isinstance(get_datatype(['bool']), BoolType)
    with pytest.raises(ValueError):
        get_datatype(['bool', 3])

    assert isinstance(get_datatype(['int']), IntRange)
    assert isinstance(get_datatype(['int', -10]), IntRange)
    assert isinstance(get_datatype(['int', None, 10]), IntRange)
    assert isinstance(get_datatype(['int', -10, 10]), IntRange)

    with pytest.raises(ValueError):
        get_datatype(['int',10, -10])
    with pytest.raises(ValueError):
        get_datatype(['int', 1, 2, 3])


    assert isinstance(get_datatype(['double']), FloatRange)
    assert isinstance(get_datatype(['double', -2.718]), FloatRange)
    assert isinstance(get_datatype(['double', None, 3.14]), FloatRange)
    assert isinstance(get_datatype(['double', -9.9, 11.1]), FloatRange)

    with pytest.raises(ValueError):
        get_datatype(['double',10, -10])
    with pytest.raises(ValueError):
        get_datatype(['double', 1, 2, 3])


    with pytest.raises(ValueError):
        get_datatype(['enum'])
    assert isinstance(get_datatype(['enum', dict(a=-2.718)]), EnumType)

    with pytest.raises(ValueError):
        get_datatype(['enum',10, -10])
    with pytest.raises(ValueError):
        get_datatype(['enum', [1, 2, 3]])


    assert isinstance(get_datatype(['blob']), BLOBType)
    assert isinstance(get_datatype(['blob', 1]), BLOBType)
    assert isinstance(get_datatype(['blob', 1, 10]), BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['blob',10, -10])
    with pytest.raises(ValueError):
        get_datatype(['blob',10, -10, 1])


    assert isinstance(get_datatype(['string']), StringType)
    assert isinstance(get_datatype(['string', 1]), StringType)
    assert isinstance(get_datatype(['string', 1, 10]), StringType)

    with pytest.raises(ValueError):
        get_datatype(['string',10, -10])
    with pytest.raises(ValueError):
        get_datatype(['string',10, -10, 1])


    with pytest.raises(ValueError):
        get_datatype(['array'])
    with pytest.raises(ValueError):
        get_datatype(['array', 1])
    with pytest.raises(ValueError):
        get_datatype(['array', [1], 2, 3])
    assert isinstance(get_datatype(['array', ['blob']]), ArrayOf)
    assert isinstance(get_datatype(['array', ['blob']]).subtype, BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['array', ['blob'], -10])
    with pytest.raises(ValueError):
        get_datatype(['array', ['blob'], -10, 10])

    assert isinstance(get_datatype(['array', ['blob'], 1, 10]), ArrayOf)


    with pytest.raises(ValueError):
        get_datatype(['tuple'])
    with pytest.raises(ValueError):
        get_datatype(['tuple', 1])
    with pytest.raises(ValueError):
        get_datatype(['tuple', [1], 2, 3])
    assert isinstance(get_datatype(['tuple', [['blob']]]), TupleOf)
    assert isinstance(get_datatype(['tuple', [['blob']]]).subtypes[0], BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['tuple', [['blob']], -10])
    with pytest.raises(ValueError):
        get_datatype(['tuple', [['blob']], -10, 10])

    assert isinstance(get_datatype(['tuple', [['blob'],['int']]]), TupleOf)


    with pytest.raises(ValueError):
        get_datatype(['struct'])
    with pytest.raises(ValueError):
        get_datatype(['struct', 1])
    with pytest.raises(ValueError):
        get_datatype(['struct', [1], 2, 3])
    assert isinstance(get_datatype(['struct', {'blob':['blob']}]), StructOf)
    assert isinstance(get_datatype(['struct', {'blob':['blob']}]).named_subtypes['blob'], BLOBType)

    with pytest.raises(ValueError):
        get_datatype(['struct', [['blob']], -10])
    with pytest.raises(ValueError):
        get_datatype(['struct', [['blob']], -10, 10])

    assert isinstance(get_datatype(['struct', {'blob':['blob'], 'int':['int']}]), StructOf)
