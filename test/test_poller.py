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
"""test poller."""

import sys
import threading
from time import time as current_time
import time
import logging

import pytest

from frappy.core import Module, Parameter, FloatRange, Readable, ReadHandler, nopoll
from frappy.lib.multievent import MultiEvent
from frappy.lib import generalConfig


class Time:
    """artificial time, forwarded on sleep instead of waiting"""
    def __init__(self):
        self.offset = 0

    def time(self):
        return current_time() + self.offset

    def sleep(self, seconds):
        assert 0 <= seconds <= 24*3600
        self.offset += seconds


artime = Time()  # artificial test time


class DispatcherStub:
    maxcycles = 10

    def announce_update(self, moduleobj, pobj):
        now = artime.time()
        if hasattr(pobj, 'stat'):
            pobj.stat.append(now)
        else:
            pobj.stat = [now]
        self.maxcycles -= 1
        if self.maxcycles <= 0:
            self.finish_event.set()
            sys.exit()  # stop thread


class ServerStub:
    def __init__(self):
        generalConfig.testinit()
        self.dispatcher = DispatcherStub()
        self.secnode = None


class Base(Module):
    def __init__(self):
        srv = ServerStub()
        super().__init__('mod', logging.getLogger('dummy'), {'description': ''}, srv)
        self.dispatcher = srv.dispatcher

    def run(self, maxcycles):
        self.dispatcher.maxcycles = maxcycles
        self.dispatcher.finish_event = threading.Event()
        self.initModule()

        def wait(timeout=None, base=self.triggerPoll):
            """simplified simulation

            when an event is already set return True, else forward artificial time
            """
            if base.is_set():
                return True
            artime.sleep(max(0.0, 99.9 if timeout is None else timeout))
            return base.is_set()

        self.triggerPoll.wait = wait
        self.startModule(MultiEvent())
        assert self.dispatcher.finish_event.wait(1)


class Mod1(Base, Readable):
    param1 = Parameter('', FloatRange())
    param2 = Parameter('', FloatRange())
    param3 = Parameter('', FloatRange())
    param4 = Parameter('', FloatRange())

    @ReadHandler(('param1', 'param2', 'param3'))
    def read_param(self, name):
        artime.sleep(1.0)
        return 0

    @nopoll
    def read_param4(self):
        return 0

    def read_status(self):
        artime.sleep(1.0)
        return 0

    def read_value(self):
        artime.sleep(1.0)
        return 0


@pytest.mark.filterwarnings('ignore')  # ignore PytestUnhandledThreadExceptionWarning
@pytest.mark.parametrize(
    'ncycles, pollinterval, slowinterval, mspan, pspan',
    [  # normal case:
     (    60,            5,          15, (4.9, 5.1), (14, 16)),
     # pollinterval faster then reading: mspan max ~ 3 s (polls of value, status and ONE other parameter)
     (    60,            1,           5, (0.9, 3.1), (5, 17)),
    ])
def test_poll(ncycles, pollinterval, slowinterval, mspan, pspan, monkeypatch):
    monkeypatch.setattr(time, 'time', artime.time)
    m = Mod1()
    m.pollinterval = pollinterval
    m.slowInterval = slowinterval
    m.run(ncycles)
    print(getattr(m.parameters['param4'], 'stat', None))
    assert not hasattr(m.parameters['param4'], 'stat')
    for pname in ['value', 'status']:
        pobj = m.parameters[pname]
        lowcnt = 0
        print(pname, [t2 - t1 for t1, t2 in zip(pobj.stat[1:], pobj.stat[2:-1])])
        for t1, t2 in zip(pobj.stat[1:], pobj.stat[2:-1]):
            if t2 - t1 < mspan[0]:
                lowcnt += 1
            assert t2 - t1 <= mspan[1]
        assert lowcnt <= 2
    for pname in ['param1', 'param2', 'param3']:
        pobj = m.parameters[pname]
        lowcnt = 0
        print(pname, [t2 - t1 for t1, t2 in zip(pobj.stat[1:], pobj.stat[2:-1])])
        for t1, t2 in zip(pobj.stat[1:], pobj.stat[2:-1]):
            if t2 - t1 < pspan[0]:
                lowcnt += 1
            assert t2 - t1 <= pspan[1]
        assert lowcnt <= 2
