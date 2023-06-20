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
"""test frappy.mixins.HasCtrlPars"""


from test.test_modules import LoggerStub, ServerStub
from frappy.core import FloatRange, Module, Parameter
from frappy.structparam import StructParam


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
