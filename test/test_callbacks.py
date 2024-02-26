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
"""test parameter callbacks"""

from test.test_modules import LoggerStub, ServerStub
import pytest
from frappy.core import Module, Parameter, FloatRange
from frappy.errors import WrongTypeError


WRONG_TYPE = WrongTypeError()


class Mod(Module):
    a = Parameter('', FloatRange())
    b = Parameter('', FloatRange())
    c = Parameter('', FloatRange())

    def read_a(self):
        raise WRONG_TYPE

    def read_b(self):
        raise WRONG_TYPE

    def read_c(self):
        raise WRONG_TYPE


class Dbl(Module):
    a = Parameter('', FloatRange())
    b = Parameter('', FloatRange())
    c = Parameter('', FloatRange())
    _error_a = None
    _value_b = None
    _error_c = None

    def update_a(self, value, err=None):
        # treat error updates
        try:
            self.a = value * 2
        except TypeError:  # value is None -> err
            self.announceUpdate('a', None, err)

    def update_b(self, value):
        self._value_b = value
        # error updates are ignored
        self.b = value * 2


def make(cls):
    logger = LoggerStub()
    srv = ServerStub({})
    return cls('mod1', logger, {'description': ''}, srv)


def test_simple_callback():
    mod1 = make(Mod)
    result = []

    def cbfunc(arg1, arg2, value):
        result[:] = arg1, arg2, value

    mod1.addCallback('a', cbfunc, 'ARG1', 'arg2')

    mod1.a = 1.5
    assert result == ['ARG1', 'arg2', 1.5]

    result.clear()

    with pytest.raises(WrongTypeError):
        mod1.read_a()

    assert not result  # callback function is NOT called


def test_combi_callback():
    mod1 = make(Mod)
    result = []

    def cbfunc(arg1, arg2, value, err=None):
        result[:] = arg1, arg2, value, err

    mod1.addCallback('a', cbfunc, 'ARG1', 'arg2')

    mod1.a = 1.5
    assert result == ['ARG1', 'arg2', 1.5, None]

    result.clear()

    with pytest.raises(WrongTypeError):
        mod1.read_a()

    assert result[:3] == ['ARG1', 'arg2', None]  # callback function called with value None
    assert isinstance(result[3], WrongTypeError)


def test_autoupdate():
    mod1 = make(Mod)
    mod2 = make(Dbl)
    mod1.registerCallbacks(mod2, autoupdate=['c'])

    result = {}

    def cbfunc(pname, *args):
        result[pname] = args

    for param in 'a', 'b', 'c':
        mod2.addCallback(param, cbfunc, param)

    # test update_a without error
    mod1.a = 5
    assert mod2.a == 10
    assert result.pop('a') == (10,)

    # test update_a with error
    with pytest.raises(WrongTypeError):
        mod1.read_a()

    assert result.pop('a') == (None, WRONG_TYPE)

    # test that update_b is ignored in case of error
    mod1.b = 3
    assert mod2.b == 6  # no error
    assert result.pop('b') == (6,)

    with pytest.raises(WrongTypeError):
        mod1.read_b()
    assert 'b' not in result

    # test autoupdate
    mod1.c = 3
    assert mod2.c == 3
    assert result['c'] == (3,)

    with pytest.raises(WrongTypeError):
        mod1.read_c()
    assert result['c'] == (None, WRONG_TYPE)
