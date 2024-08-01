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

import mlzlog
import pytest

import frappy.logging
from frappy.logging import HasComlog, generalConfig, init_remote_logging, \
    logger
from frappy.modules import Module
from frappy.protocol.dispatcher import Dispatcher
from frappy.protocol.interface import decode_msg, encode_msg_frame


class SecNodeStub:
    def __init__(self):
        self.modules = {}
        self.name = ""

    def add_module(self, module, modname):
        self.modules[modname] = module

    def get_module(self, modname):
        return self.modules[modname]


class ServerStub:
    restart = None
    shutdown = None

    def __init__(self):
        self.secnode = SecNodeStub()
        self.dispatcher = Dispatcher('', logger.log.getChild('dispatcher'), {}, self)


class Connection:
    def __init__(self, name, dispatcher, result):
        self.result = result
        self.dispatcher = dispatcher
        self.name = name
        dispatcher.add_connection(self)

    def send_reply(self, msg):
        self.result.append(encode_msg_frame(*msg).strip().decode())

    def send(self, msg):
        request = decode_msg(msg.encode())
        assert self.dispatcher.handle_request(self, request) == request


@pytest.fixture(name='init')
def init_(monkeypatch):
    # pylint: disable=unnecessary-dunder-call
    logger.__init__()

    class Playground:
        def __init__(self, console_level='debug', comlog=True, com_module=True):
            self.result_dict = result_dict = dict(
                console=[], comlog=[], conn1=[], conn2=[])

            class ConsoleHandler(mlzlog.Handler):
                def __init__(self, *args, **kwds):
                    super().__init__()
                    self.result = result_dict['console']

                def emit(self, record):
                    if record.name != 'frappy.dispatcher':
                        self.result.append('%s %s %s' % (record.name, record.levelname, record.getMessage()))

            class ComLogHandler(mlzlog.Handler):
                def __init__(self, *args, **kwds):
                    super().__init__()
                    self.result = result_dict['comlog']

                def emit(self, record):
                    self.result.append('%s %s' % (record.name.split('.')[1], record.getMessage()))

            class LogfileHandler(mlzlog.Handler):
                def __init__(self, *args, **kwds):
                    super().__init__()

                def noop(self, *args):
                    pass

                close = flush = emit = noop

            monkeypatch.setattr(mlzlog, 'ColoredConsoleHandler', ConsoleHandler)
            monkeypatch.setattr(frappy.logging, 'ComLogfileHandler', ComLogHandler)
            monkeypatch.setattr(frappy.logging, 'LogfileHandler', LogfileHandler)

            class Mod(Module):
                result = []

                def __init__(self, name, srv, **kwds):
                    kwds['description'] = ''
                    super().__init__(name or 'mod', logger.log.getChild(name), kwds, srv)
                    srv.secnode.add_module(self, name)
                    self.result[:] = []

                def earlyInit(self):
                    pass

            class Com(HasComlog, Mod):
                def __init__(self, name, srv, **kwds):
                    super().__init__(name, srv, **kwds)
                    self.earlyInit()
                    self.log.handlers[-1].result = result_dict['comlog']

                def communicate(self, request):
                    self.comLog('> %s', request)

            generalConfig.testinit(logger_root='frappy', comlog=comlog)
            logger.init(console_level)
            init_remote_logging(logger.log)
            self.srv = ServerStub()

            self.conn1 = Connection('conn1', self.srv.dispatcher, self.result_dict['conn1'])
            self.conn2 = Connection('conn2', self.srv.dispatcher, self.result_dict['conn2'])
            self.mod = Mod('mod', self.srv)
            self.com = Com('com', self.srv, comlog=com_module)
            for item in self.result_dict.values():
                assert item == []

        def check(self, both=None, **expected):
            if both:
                expected['conn1'] = expected['conn2'] = both
            assert self.result_dict['console'] == expected.get('console', [])
            assert self.result_dict['comlog'] == expected.get('comlog', [])
            assert self.result_dict['conn1'] == expected.get('conn1', [])
            assert self.result_dict['conn2'] == expected.get('conn2', [])
            for item in self.result_dict.values():
                item[:] = []

        def comlog(self, flag):
            logger.comlog = flag

    yield Playground
    # revert settings
    generalConfig.testinit()
    logger.__init__()


def test_mod_info(init):
    p = init()
    p.mod.log.info('i')
    p.check(console=['frappy.mod INFO i'])
    p.conn1.send('logging mod "debug"')
    p.conn2.send('logging mod "info"')
    p.mod.log.info('i')
    p.check(console=['frappy.mod INFO i'], both=['log mod:info "i"'])


def test_mod_debug(init):
    p = init()
    p.mod.log.debug('d')
    p.check(console=['frappy.mod DEBUG d'])
    p.conn1.send('logging mod "debug"')
    p.conn2.send('logging mod "info"')
    p.mod.log.debug('d')
    p.check(console=['frappy.mod DEBUG d'], conn1=['log mod:debug "d"'])


def test_com_info(init):
    p = init()
    p.com.log.info('i')
    p.check(console=['frappy.com INFO i'])
    p.conn1.send('logging com "info"')
    p.conn2.send('logging com "debug"')
    p.com.log.info('i')
    p.check(console=['frappy.com INFO i'], both=['log com:info "i"'])


def test_com_debug(init):
    p = init()
    p.com.log.debug('d')
    p.check(console=['frappy.com DEBUG d'])
    p.conn2.send('logging com "debug"')
    p.com.log.debug('d')
    p.check(console=['frappy.com DEBUG d'], conn2=['log com:debug "d"'])


def test_com_com(init):
    p = init()
    p.com.communicate('x')
    p.check(console=['frappy.com COMLOG > x'], comlog=['com > x'])
    p.conn1.send('logging mod "debug"')
    p.conn2.send('logging mod "info"')
    p.conn2.send('logging com "debug"')
    p.com.communicate('x')
    p.check(console=['frappy.com COMLOG > x'], comlog=['com > x'], conn2=['log com:comlog "> x"'])


def test_main_info(init):
    p = init(console_level='info')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.check(comlog=['com > x'])
    p.conn1.send('logging mod "debug"')
    p.conn2.send('logging mod "info"')
    p.conn2.send('logging com "debug"')
    p.com.communicate('x')
    p.check(comlog=['com > x'], conn2=['log com:comlog "> x"'])


def test_comlog_off(init):
    p = init(console_level='info', comlog=False)
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.check()


def test_comlog_module_off(init):
    p = init(console_level='info', com_module=False)
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.check()


def test_remote_all_off(init):
    p = init()
    p.conn1.send('logging mod "debug"')
    p.conn2.send('logging mod "info"')
    p.conn2.send('logging com "debug"')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.mod.log.info('i')
    checks = dict(
        console=['frappy.mod DEBUG d', 'frappy.com COMLOG > x', 'frappy.mod INFO i'],
        comlog=['com > x'],
        conn1=['log mod:debug "d"', 'log mod:info "i"'],
        conn2=['log com:comlog "> x"', 'log mod:info "i"'])
    p.check(**checks)
    p.conn1.send('logging  "off"')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.mod.log.info('i')
    checks.pop('conn1')
    p.check(**checks)
    p.conn2.send('logging . "off"')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.mod.log.info('i')
    checks.pop('conn2')
    p.check(**checks)


def test_remote_single_off(init):
    p = init()
    p.conn1.send('logging mod "debug"')
    p.conn2.send('logging mod "info"')
    p.conn2.send('logging com "debug"')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.mod.log.info('i')
    checks = dict(
        console=['frappy.mod DEBUG d', 'frappy.com COMLOG > x', 'frappy.mod INFO i'],
        comlog=['com > x'],
        conn1=['log mod:debug "d"', 'log mod:info "i"'],
        conn2=['log com:comlog "> x"', 'log mod:info "i"'])
    p.check(**checks)
    p.conn2.send('logging com "off"')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.mod.log.info('i')
    checks['conn2'] = ['log mod:info "i"']
    p.check(**checks)
    p.conn2.send('logging mod "off"')
    p.mod.log.debug('d')
    p.com.communicate('x')
    p.mod.log.info('i')
    checks['conn2'] = []
    p.check(**checks)
