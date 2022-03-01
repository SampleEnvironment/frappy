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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************


from secop.rwhandler import ReadHandler, WriteHandler, \
    CommonReadHandler, CommonWriteHandler, nopoll
from secop.core import Module, Parameter, FloatRange, Done


class DispatcherStub:
    # the first update from the poller comes a very short time after the
    # initial value from the timestamp. However, in the test below
    # the second update happens after the updates dict is cleared
    # -> we have to inhibit the 'omit unchanged update' feature
    omit_unchanged_within = 0

    def __init__(self, updates):
        self.updates = updates

    def announce_update(self, modulename, pname, pobj):
        self.updates.setdefault(modulename, {})
        if pobj.readerror:
            self.updates[modulename]['error', pname] = str(pobj.readerror)
        else:
            self.updates[modulename][pname] = pobj.value


class LoggerStub:
    def debug(self, fmt, *args):
        print(fmt % args)
    info = warning = exception = error = debug
    handlers = []


logger = LoggerStub()


class ServerStub:
    def __init__(self, updates):
        self.dispatcher = DispatcherStub(updates)


class ModuleTest(Module):
    def __init__(self, updates=None, **opts):
        opts['description'] = ''
        super().__init__('mod', logger, opts, ServerStub(updates or {}))


def test_handler():
    data = []

    class Mod(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False, poll=True)
        b = Parameter('', FloatRange(), readonly=False, poll=True)

        @ReadHandler(['a', 'b'])
        def read_hdl(self, pname):
            value = data.pop()
            data.append(pname)
            return value

        @WriteHandler(['a', 'b'])
        def write_hdl(self, pname, value):
            data.append(pname)
            return value

    assert Mod.read_a.poll is True
    assert Mod.read_b.poll is True

    m = Mod()

    data.append(1.2)
    assert m.read_a() == 1.2
    assert data.pop() == 'a'

    data.append(1.3)
    assert m.read_b() == 1.3
    assert data.pop() == 'b'

    assert m.write_a(1.5) == 1.5
    assert m.a == 1.5
    assert data.pop() == 'a'

    assert m.write_b(7) == 7
    assert m.b == 7
    assert data.pop() == 'b'

    data.append(Done)
    assert m.read_b() == 7
    assert data.pop() == 'b'

    assert data == []


def test_common_handler():
    data = []

    class Mod(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False, poll=True)
        b = Parameter('', FloatRange(), readonly=False, poll=True)

        @CommonReadHandler(['a', 'b'])
        def read_hdl(self):
            self.a, self.b = data.pop()
            data.append('read_hdl')

        @CommonWriteHandler(['a', 'b'])
        def write_hdl(self, values):
            self.a = values['a']
            self.b = values['b']
            data.append('write_hdl')

    assert set([Mod.read_a.poll, Mod.read_b.poll]) == {True, False}

    m = Mod(a=1, b=2)
    assert m.writeDict == {'a': 1, 'b': 2}
    m.write_a(3)
    assert m.a == 3
    assert m.b == 2
    assert data.pop() == 'write_hdl'
    assert m.writeDict == {}

    m.write_b(4)
    assert m.a == 3
    assert m.b == 4
    assert data.pop() == 'write_hdl'

    data.append((3, 4))
    assert m.read_a() == 3
    assert m.a == 3
    assert m.b == 4
    assert data.pop() == 'read_hdl'
    data.append((5, 6))
    assert m.read_b() == 6
    assert data.pop() == 'read_hdl'

    data.append((1.1, 2.2))
    assert m.read_b() == 2.2
    assert m.a == 1.1
    assert m.b == 2.2
    assert data.pop() == 'read_hdl'

    assert data == []


def test_nopoll():
    class Mod1(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False, poll=True)
        b = Parameter('', FloatRange(), readonly=False, poll=True)

        @ReadHandler(['a', 'b'])
        def read_hdl(self):
            pass

    assert Mod1.read_a.poll is True
    assert Mod1.read_b.poll is True

    class Mod2(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False, poll=True)
        b = Parameter('', FloatRange(), readonly=False, poll=True)

        @CommonReadHandler(['a', 'b'])
        def read_hdl(self):
            pass

    assert Mod2.read_a.poll is True
    assert Mod2.read_b.poll is False

    class Mod3(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False, poll=True)
        b = Parameter('', FloatRange(), readonly=False, poll=True)

        @ReadHandler(['a', 'b'])
        @nopoll
        def read_hdl(self):
            pass

    assert Mod3.read_a.poll is False
    assert Mod3.read_b.poll is False

    class Mod4(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False, poll=True)
        b = Parameter('', FloatRange(), readonly=False, poll=True)

        @nopoll
        @ReadHandler(['a', 'b'])
        def read_hdl(self):
            pass

    assert Mod4.read_a.poll is False
    assert Mod4.read_b.poll is False

    class Mod5(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False)
        b = Parameter('', FloatRange(), readonly=False)

        @CommonReadHandler(['a', 'b'])
        @nopoll
        def read_hdl(self):
            pass

    assert Mod5.read_a.poll is False
    assert Mod5.read_b.poll is False

    class Mod6(ModuleTest):
        a = Parameter('', FloatRange(), readonly=False)
        b = Parameter('', FloatRange(), readonly=False)

        @nopoll
        @CommonReadHandler(['a', 'b'])
        def read_hdl(self):
            pass

    assert Mod6.read_a.poll is False
    assert Mod6.read_b.poll is False
