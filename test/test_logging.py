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


from mlzlog import MLZLogger, Handler, INFO, DEBUG
from secop.modules import Module
from secop.protocol.dispatcher import Dispatcher


class LogHandler(Handler):
    def __init__(self, result):
        super().__init__()
        self.result = result

    def emit(self, record):
        self.result.append('%s:%s' % (record.levelname, record.getMessage()))


class LogRecorder(MLZLogger):
    def __init__(self, result):
        super().__init__('root')
        self.setLevel(INFO)
        self.addHandler(LogHandler(result))


class ServerStub:
    restart = None
    shutdown = None


class Connection:
    def __init__(self, dispatcher):
        self.result = []
        dispatcher.add_connection(self)

    def send_reply(self, msg):
        self.result.append(msg)

    def check(self, *args):
        assert self.result == list(args)
        self.result[:] = []

    def send(self, *request):
        assert srv.dispatcher.handle_request(self, request) == request


class Mod(Module):
    def __init__(self, name):
        self.result = []
        super().__init__(name, LogRecorder(self.result), {'.description': ''}, srv)
        srv.dispatcher.register_module(self, name, name)

    def check(self, *args):
        assert self.result == list(args)
        self.result[:] = []


srv = ServerStub()
srv.dispatcher = Dispatcher('', LogRecorder([]), {}, srv)
conn1 = Connection(srv.dispatcher)
conn2 = Connection(srv.dispatcher)
o1 = Mod('o1')
o2 = Mod('o2')


def test_logging1():
    # test normal logging
    o1.log.setLevel(INFO)
    o2.log.setLevel(DEBUG)

    o1.log.info('i1')
    o1.log.debug('d1')
    o2.log.info('i2')
    o2.log.debug('d2')

    o1.check('INFO:i1')
    o2.check('INFO:i2', 'DEBUG:d2')
    conn1.check()
    conn2.check()

    # test remote logging on
    conn1.send('logging', 'o1', 'debug')
    conn2.send('logging', 'o1', 'info')
    conn2.send('logging', 'o2', 'debug')

    o1.log.info('i1')
    o1.log.debug('d1')
    o2.log.info('i2')
    o2.log.debug('d2')

    o1.check('INFO:i1')
    o2.check('INFO:i2', 'DEBUG:d2')
    conn1.check(('log', 'o1:info', 'i1'), ('log', 'o1:debug', 'd1'))
    conn2.check(('log', 'o1:info', 'i1'), ('log', 'o2:info', 'i2'), ('log', 'o2:debug', 'd2'))

    # test all remote logging
    conn1.send('logging', '', 'off')
    conn2.send('logging', '', 'off')

    o1.log.info('i1')
    o1.log.debug('d1')
    o2.log.info('i2')
    o2.log.debug('d2')

    o1.check('INFO:i1')
    o2.check('INFO:i2', 'DEBUG:d2')
    conn1.check()
    conn2.check()

    # test all modules on, warning level
    conn2.send('logging', '', 'warning')

    o1.log.info('i1')
    o1.log.warning('w1')
    o2.log.info('i2')
    o2.log.warning('w2')

    o1.check('INFO:i1', 'WARNING:w1')
    o2.check('INFO:i2', 'WARNING:w2')
    conn1.check()
    conn2.check(('log', 'o1:warning', 'w1'), ('log', 'o2:warning', 'w2'))
