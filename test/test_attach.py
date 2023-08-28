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

from frappy.modules import Module, Attached
from frappy.protocol.dispatcher import Dispatcher


# class DispatcherStub:
#     # omit_unchanged_within = 0
#
#     # def __init__(self, updates):
#     #     self.updates = updates
#     #
#     # def announce_update(self, modulename, pname, pobj):
#     #     self.updates.setdefault(modulename, {})
#     #     if pobj.readerror:
#     #         self.updates[modulename]['error', pname] = str(pobj.readerror)
#     #     else:
#     #         self.updates[modulename][pname] = pobj.value
#
#     def __init__(self):
#         self.modules = {}
#
#     def get_module(self, name):
#         return self.modules[name]
#
#     def register_module(self, name, module):
#         self.modules[name] = module


class LoggerStub:
    def debug(self, fmt, *args):
        print(fmt % args)
    info = warning = exception = debug
    handlers = []


logger = LoggerStub()


class ServerStub:
    restart = None
    shutdown = None

    def __init__(self):
        self.dispatcher = Dispatcher('dispatcher', logger, {}, self)


def test_attach():
    class Mod(Module):
        att = Attached()

    srv = ServerStub()
    a = Module('a', logger, {'description': ''}, srv)
    m = Mod('m', logger, {'description': '', 'att': 'a'}, srv)
    assert m.propertyValues['att'] == 'a'
    srv.dispatcher.register_module(a, 'a')
    srv.dispatcher.register_module(m, 'm')
    assert m.att == a
