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
"""test frappy.extparams"""


from test.test_modules import LoggerStub, ServerStub
import pytest
from frappy.core import FloatRange, Module, Parameter
from frappy.structparam import StructParam
from frappy.extparams import FloatEnumParam
from frappy.errors import ProgrammingError


def test_with_read_ctrlpars():
    class Mod(Module):
        ctrlpars = StructParam('ctrlpar struct', dict(
            p = Parameter('control parameter p', FloatRange()),
            i = Parameter('control parameter i', FloatRange()),
            d = Parameter('control parameter d', FloatRange()),
        ), 'pid_', readonly=False)

        def read_ctrlpars(self):
            return self._ctrlpars

        def write_ctrlpars(self, value):
            self._ctrlpars = value
            return self.read_ctrlpars()

    logger = LoggerStub()
    updates = {}
    srv = ServerStub(updates)

    ms = Mod('ms', logger, {'description':''}, srv)

    value = {'p': 1, 'i': 2, 'd': 3}
    assert ms.write_ctrlpars(value) == value
    assert ms.read_ctrlpars() == value
    assert ms.read_pid_p() == 1
    assert ms.read_pid_i() == 2
    assert ms.read_pid_d() == 3
    assert ms.write_pid_i(5) == 5
    assert ms.write_pid_d(0) == 0
    assert ms.read_ctrlpars() == {'p': 1, 'i': 5, 'd': 0}
    assert set(Mod.ctrlpars.influences) == {'pid_p', 'pid_i', 'pid_d'}
    assert Mod.pid_p.influences == ('ctrlpars',)
    assert Mod.pid_i.influences == ('ctrlpars',)
    assert Mod.pid_d.influences == ('ctrlpars',)


def test_without_read_ctrlpars():
    class Mod(Module):
        ctrlpars = StructParam('ctrlpar struct', dict(
            p = Parameter('control parameter p', FloatRange()),
            i = Parameter('control parameter i', FloatRange()),
            d = Parameter('control parameter d', FloatRange()),
        ), readonly=False)

        _pid_p = 0
        _pid_i = 0

        def read_p(self):
            return self._pid_p

        def write_p(self, value):
            self._pid_p = value
            return self.read_p()

        def read_i(self):
            return self._pid_i

        def write_i(self, value):
            self._pid_i = value
            return self.read_i()

    logger = LoggerStub()
    updates = {}
    srv = ServerStub(updates)

    ms = Mod('ms', logger, {'description': ''}, srv)

    value = {'p': 1, 'i': 2, 'd': 3}
    assert ms.write_ctrlpars(value) == value
    assert ms.read_ctrlpars() == value
    assert ms.read_p() == 1
    assert ms.read_i() == 2
    assert ms.read_d() == 3
    assert ms.write_i(5) == 5
    assert ms.write_d(0) == 0
    assert ms.read_ctrlpars() == {'p': 1, 'i': 5, 'd': 0}
    assert set(Mod.ctrlpars.influences) == {'p', 'i', 'd'}
    assert Mod.p.influences == ('ctrlpars',)
    assert Mod.i.influences == ('ctrlpars',)
    assert Mod.d.influences == ('ctrlpars',)


def test_readonly():
    class Mod(Module):
        ctrlpars = StructParam('ctrlpar struct', dict(
            p = Parameter('control parameter p', FloatRange()),
            i = Parameter('control parameter i', FloatRange()),
            d = Parameter('control parameter d', FloatRange()),
        ), {'p': 'pp', 'i':'ii', 'd': 'dd'}, readonly=True)

    assert Mod.ctrlpars.readonly is True
    assert Mod.pp.readonly is True
    assert Mod.ii.readonly is True
    assert Mod.dd.readonly is True


def test_order_dependence1():
    test_without_read_ctrlpars()
    test_with_read_ctrlpars()


def test_order_dependence2():
    test_with_read_ctrlpars()
    test_without_read_ctrlpars()


def test_float_enum():
    class Mod(Module):
        vrange = FloatEnumParam('voltage range', [
            (1, '50uV'), '200 µV', '1mV', ('5mV', 0.006), (9, 'max', 0.024)], 'V')
        gain = FloatEnumParam('gain factor', ('1', '2', '4', '8'), idx_name='igain')
        dist = FloatEnumParam('distance', ('1m', '1mm', '1µm'), unit='m')

        _vrange_idx = None

        def write_vrange_idx(self, value):
            self._vrange_idx = value

    logger = LoggerStub()
    updates = {}
    srv = ServerStub(updates)

    m = Mod('m', logger, {'description': ''}, srv)

    assert m.write_vrange_idx(1) == 1
    assert m._vrange_idx == '50uV'
    assert m._vrange_idx == 1
    assert m.vrange == 5e-5

    assert m.write_vrange_idx(2) == 2
    assert m._vrange_idx == '200 µV'
    assert m._vrange_idx == 2
    assert m.vrange == 2e-4

    assert m.write_vrange(6e-5) == 5e-5  # round to the next value
    assert m._vrange_idx == '50uV'
    assert m._vrange_idx == 1
    assert m.write_vrange(20e-3) == 24e-3  # round to the next value
    assert m._vrange_idx == 'max'
    assert m._vrange_idx == 9

    for idx in range(4):
        value = 2 ** idx
        updates.clear()
        assert m.write_igain(idx) == idx
        assert updates == {'m': {'igain': idx, 'gain': value}}
        assert m.igain == idx
        assert m.igain == str(value)
        assert m.gain == value

    for idx in range(4):
        value = 2 ** idx
        assert m.write_gain(value) == value
        assert m.igain == idx
        assert m.igain == str(value)

    for idx in range(3):
        value = 10 ** (-3 * idx)
        assert m.write_dist(value) == value
        assert m.dist_idx == idx


@pytest.mark.parametrize('labels, unit, error', [
    (FloatRange(),      '', 'not a datatype'),     # 2nd arg must not be a datatype
    ([(1, 2, 3)],       '', 'must be strings'),    # label is not a string
    ([(1, '1V', 3, 4)], 'V', 'labels or tuples'),  # 4-tuple
    ([('1A', 3, 4)],    'A', 'labels or tuples'),  # two values after label
    (('1m', (0, '1k')), '', 'conflicts with'),     # two times index 0
    (['1mV', '10mA'],   'V', 'not the form'),      # wrong unit
    (['.mV'],           'V', 'not the form'),      # bad number
    (['mV'],            'V', 'not the form'),      # missing number
    (['1+mV'],          'V', 'not the form'),      # bad number
])
def test_bad_float_enum(labels, unit, error):
    with pytest.raises(ProgrammingError, match=error):
        class Mod(Module):  # pylint:disable=unused-variable
            param = FloatEnumParam('', labels, unit)
