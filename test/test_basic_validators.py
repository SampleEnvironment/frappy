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
"""test basic validators."""

# no fixtures needed
import pytest

from secop.basic_validators import BoolProperty, EnumProperty, FloatProperty, \
    FmtStrProperty, IntProperty, NoneOr, NonNegativeFloatProperty, \
    NonNegativeIntProperty, OneOfProperty, PositiveFloatProperty, \
    PositiveIntProperty, StringProperty, TupleProperty, UnitProperty


class unprintable:
    def __str__(self):
        raise NotImplementedError

@pytest.mark.parametrize('validators_args', [
    [FloatProperty,            [None, 'a'],              [1, 1.23, '1.23', '9e-12']],
    [PositiveFloatProperty,    ['x', -9, '-9', 0],       [1, 1.23, '1.23', '9e-12']],
    [NonNegativeFloatProperty, ['x', -9, '-9'],          [0, 1.23, '1.23', '9e-12']],
    [IntProperty,              [None, 'a', 1.2, '1.2'],  [1, '-1']],
    [PositiveIntProperty,      ['x', 1.9, '-9', '1e-4'], [1, '1']],
    [NonNegativeIntProperty,   ['x', 1.9, '-9', '1e-6'], [0, '1']],
    [BoolProperty,             ['x', 3],                 ['on', 'off', True, False]],
    [StringProperty,           [unprintable()],          ['1', 1.2, [{}]]],
    [UnitProperty,             [unprintable(), '3', 9],  ['mm', 'Gbarn', 'acre']],
    [FmtStrProperty,           [1, None, 'a', '%f'],     ['%.0e', '%.3f','%.1g']],
])
def test_validators(validators_args):
    v, fails, oks = validators_args
    for value in fails:
        with pytest.raises(Exception):
            v(value)
    for value in oks:
        v(value)


@pytest.mark.parametrize('checker_inits', [
    [OneOfProperty, lambda: OneOfProperty(a=3),],  # pylint: disable=unexpected-keyword-arg
    [NoneOr,        lambda: NoneOr(None),],
    [EnumProperty,  lambda: EnumProperty(1),],  # pylint: disable=too-many-function-args
    [TupleProperty, lambda: TupleProperty(1,2,3),],
])
def test_checker_fails(checker_inits):
    empty, badargs = checker_inits
    with pytest.raises(Exception):
        empty()
    with pytest.raises(Exception):
        badargs()


@pytest.mark.parametrize('checker_args', [
    [OneOfProperty(1,2,3), ['x', None, 4], [1, 2, 3]],
    [NoneOr(IntProperty),  ['a', 1.2, '1.2'], [None, 1, '-1', '999999999999999']],
    [EnumProperty(a=1, b=2), ['x', None, 3], ['a', 'b', 1, 2]],
    [TupleProperty(IntProperty, StringProperty), [1, 'a', ('x', 2)], [(1,'x')]],
])
def test_checkers(checker_args):
    v, fails, oks = checker_args
    for value in fails:
        with pytest.raises(Exception):
            v(value)
    for value in oks:
        v(value)
