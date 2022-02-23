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
"""test poller."""

import sys
import threading
import time
import logging

import pytest

from secop.core import Module, Parameter, FloatRange, Readable, ReadHandler, nopoll
from secop.lib.multievent import MultiEvent


class Time:
    STARTTIME = 1000  # artificial time zero

    def __init__(self):
        self.reset()
        self.finish = float('inf')
        self.stop = lambda : None
        self.commtime = 0.05 # time needed for 1 poll

    def reset(self, lifetime=10):
        self.seconds = self.STARTTIME
        self.idletime = 0.0
        self.busytime = 0.0
        self.finish = self.STARTTIME + lifetime

    def time(self):
        if self.seconds > self.finish:
            self.finish = float('inf')
            self.stop()
        return self.seconds

    def sleep(self, seconds):
        assert 0 <= seconds <= 24*3600
        self.idletime += seconds
        self.seconds += seconds

    def busy(self, seconds):
        assert seconds >= 0
        self.seconds += seconds
        self.busytime += seconds


artime = Time() # artificial test time


class Event(threading.Event):
    def wait(self, timeout=None):
        artime.sleep(max(0, timeout))


class DispatcherStub:
    maxcycles = 10

    def announce_update(self, modulename, pname, pobj):
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
        self.dispatcher = DispatcherStub()


class Base(Module):
    def __init__(self):
        srv = ServerStub()
        super().__init__('mod', logging.getLogger('dummy'), dict(description=''), srv)
        self.dispatcher = srv.dispatcher
        self.nextPollEvent = Event()

    def run(self, maxcycles):
        self.dispatcher.maxcycles = maxcycles
        self.dispatcher.finish_event = threading.Event()
        self.startModule(MultiEvent())
        self.dispatcher.finish_event.wait(1)


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


@pytest.mark.parametrize(
    'ncycles, pollinterval, slowinterval, mspan, pspan',
    [  # normal case:                    5+-1     15+-1
     (    60,            5,          15, (4, 6), (14, 16)),
     # pollinterval faster then reading: mspan max 3 s (polls of value, status and ONE other parameter)
     (    60,            1,           5, (1, 3), (5, 16)),
    ])
def test_poll(ncycles, pollinterval, slowinterval, mspan, pspan, monkeypatch):
    monkeypatch.setattr(time, 'time', artime.time)
    artime.reset()
    m = Mod1()
    m.pollinterval = pollinterval
    m.slowInterval = slowinterval
    m.run(ncycles)
    assert not hasattr(m.parameters['param4'], 'stat')
    for pname in ['value', 'status']:
        pobj = m.parameters[pname]
        lowcnt = 0
        for t1, t2 in zip(pobj.stat[1:], pobj.stat[2:-1]):
            if t2 - t1 < mspan[0]:
                print(t2 - t1)
                lowcnt += 1
            assert t2 - t1 <= mspan[1]
        assert lowcnt <= 1
    for pname in ['param1', 'param2', 'param3']:
        pobj = m.parameters[pname]
        lowcnt = 0
        for t1, t2 in zip(pobj.stat[1:], pobj.stat[2:-1]):
            if t2 - t1 < pspan[0]:
                print(pname, t2 - t1)
                lowcnt += 1
            assert t2 - t1 <= pspan[1]
        assert lowcnt <= 1
