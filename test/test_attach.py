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

from frappy.io import HasIO
from frappy.modules import Module, Attached
from frappy.protocol.dispatcher import Dispatcher


class LoggerStub:
    def debug(self, fmt, *args):
        print(fmt % args)
    info = warning = exception = debug
    handlers = []

    def getChild(self, name):
        return self


logger = LoggerStub()


class SecNodeStub:
    def __init__(self):
        self.modules = {}

    def add_module(self, module, modname):
        self.modules[modname] = module

    def get_module(self, modname):
        return self.modules[modname]


class ServerStub:
    restart = None
    shutdown = None

    def __init__(self):
        self.secnode = SecNodeStub()
        self.dispatcher = Dispatcher('dispatcher', logger, {}, self)
        self.log = logger


def test_attach():
    class Mod(Module):
        att = Attached()

    srv = ServerStub()
    a = Module('a', logger, {'description': ''}, srv)
    m = Mod('m', logger, {'description': '', 'att': 'a'}, srv)
    assert m.propertyValues['att'] == 'a'
    srv.secnode.add_module(a, 'a')
    srv.secnode.add_module(m, 'm')
    assert m.att == a


def test_attach_hasio_uri():
    class TestIO(Module):
        def __init__(self, name, logger, cfgdict, srv):
            self._uri = cfgdict.pop('uri')
            super().__init__(name, logger, cfgdict, srv)

    class HasIOTest(HasIO):
        ioClass = TestIO

    srv = ServerStub()
    m = HasIOTest('m', logger, {'description': '', 'uri': 'abc'}, srv)
    assert srv.secnode.modules['m_io']._uri == 'abc'
    assert m.io == srv.secnode.modules['m_io']
    # two modules with the same IO should use the same io module
    m2 = HasIOTest('m', logger, {'description': '', 'uri': 'abc'}, srv)
    assert m2.io == srv.secnode.modules['m_io']

