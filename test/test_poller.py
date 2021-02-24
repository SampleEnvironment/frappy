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

import time
from collections import OrderedDict

import pytest

from secop.modules import Drivable
from secop.poller import DYNAMIC, REGULAR, SLOW, Poller

Status = Drivable.Status

class Time:
    STARTTIME = 1000 # artificial time zero
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

@pytest.fixture(autouse=True)
def patch_time(monkeypatch):
    monkeypatch.setattr(time, 'time', artime.time)


class Event:
    def __init__(self):
        self.flag = False

    def wait(self, timeout):
        artime.sleep(max(0,timeout))

    def set(self):
        self.flag = True

    def clear(self):
        self.flag = False

    def is_set(self):
        return self.flag


class Parameter:
    def __init__(self, name, readonly, poll, polltype, interval):
        self.poll = poll
        self.polltype = polltype # used for check only
        self.export = name
        self.readonly = readonly
        self.interval = interval
        self.timestamp = 0
        self.handler = None
        self.reset()

    def reset(self):
        self.cnt = 0
        self.span = 0
        self.maxspan = 0

    def rfunc(self):
        artime.busy(artime.commtime)
        now = artime.time()
        self.span = now - self.timestamp
        self.maxspan = max(self.maxspan, self.span)
        self.timestamp = now
        self.cnt += 1
        return True

    def __repr__(self):
        return 'Parameter(%s)' % ", ".join("%s=%r" % item for item in self.__dict__.items())


class Module:
    properties = {}
    pollerClass = Poller
    iodev = 'common_iodev'
    def __init__(self, name, pollinterval=5, fastfactor=0.25, slowfactor=4, busy=False,
                 counts=(), auto=None):
        '''create a dummy module

        nauto, ndynamic, nregular, nslow are the number of parameters of each polltype
        '''
        self.pollinterval = pollinterval
        self.fast_pollfactor = fastfactor
        self.slow_pollfactor = slowfactor
        self.parameters = OrderedDict()
        self.name = name
        self.is_busy = busy
        if auto is not None:
            self.pvalue = self.addPar('value', True, auto or DYNAMIC, DYNAMIC)
            # readonly = False should not matter:
            self.pstatus = self.addPar('status', False, auto or DYNAMIC, DYNAMIC)
            self.pregular = self.addPar('regular', True, auto or REGULAR, REGULAR)
            self.pslow = self.addPar('slow', False, auto or SLOW, SLOW)
            self.addPar('notpolled', True, False, 0)
            self.counts = 'auto'
        else:
            ndynamic, nregular, nslow = counts
            for i in range(ndynamic):
                self.addPar('%s:d%d' % (name, i), True, DYNAMIC, DYNAMIC)
            for i in range(nregular):
                self.addPar('%s:r%d' % (name, i), True, REGULAR, REGULAR)
            for i in range(nslow):
                self.addPar('%s:s%d' % (name, i), False, SLOW, SLOW)
            self.counts = counts

    def addPar(self, name, readonly, poll, expected_polltype):
        # self.count[polltype] += 1
        expected_interval = self.pollinterval
        if expected_polltype == SLOW:
            expected_interval *= self.slow_pollfactor
        elif expected_polltype == DYNAMIC and self.is_busy:
            expected_interval *= self.fast_pollfactor
        pobj = Parameter(name, readonly, poll, expected_polltype, expected_interval)
        setattr(self, 'read_' + pobj.export, pobj.rfunc)
        self.parameters[pobj.export] = pobj
        return pobj

    def isBusy(self):
        return self.is_busy

    def pollOneParam(self, pname):
        getattr(self, 'read_' + pname)()

    def writeInitParams(self):
        pass

    def __repr__(self):
        rdict = self.__dict__.copy()
        rdict.pop('parameters')
        return 'Module(%r, counts=%r, f=%r, pollinterval=%g, is_busy=%r)' % (self.name,
            self.counts, (self.fast_pollfactor, self.slow_pollfactor, 1),
            self.pollinterval, self.is_busy)

module_list = [
        [Module('x', 3.0, 0.125, 10, False, auto=True),
         Module('y', 3.0, 0.125, 10, False, auto=False)],
        [Module('a', 1.0, 0.25, 4, True, (5, 5, 10)),
         Module('b', 2.0, 0.25, 4, True, (5, 5, 50))],
        [Module('c', 1.0, 0.25, 4, False, (5, 0, 0))],
        [Module('d', 1.0, 0.25, 4, True, (0, 9, 0))],
        [Module('e', 1.0, 0.25, 4, True, (0, 0, 9))],
        [Module('f', 1.0, 0.25, 4, True, (0, 0, 0))],
    ]
@pytest.mark.parametrize('modules', module_list)
def test_Poller(modules):
    # check for proper timing

    for overloaded in False, True:
        artime.reset()
        count = {DYNAMIC: 0, REGULAR: 0, SLOW: 0}
        maxspan = {DYNAMIC: 0, REGULAR: 0, SLOW: 0}
        pollTable = dict()
        for module in modules:
            Poller.add_to_table(pollTable, module)
            for pobj in module.parameters.values():
                if pobj.poll:
                    maxspan[pobj.polltype] = max(maxspan[pobj.polltype], pobj.interval)
                    count[pobj.polltype] += 1
                    pobj.reset()
        assert len(pollTable) == 1
        poller = pollTable[(Poller, 'common_iodev')]
        artime.stop = poller.stop
        poller._event = Event() # patch Event.wait

        assert (sum(count.values()) > 0) == bool(poller)

        def started_callback(modules=modules):
            for module in modules:
                for pobj in module.parameters.values():
                    assert pobj.cnt == bool(pobj.poll) # all parameters have to be polled once
                    pobj.reset() # set maxspan and cnt to 0

        if overloaded:
            # overloaded scenario
            artime.commtime = 1.0
            ncycles = 10
            if count[SLOW] > 0:
                cycletime = (count[REGULAR] + 1) * count[SLOW] * 2
            else:
                cycletime = max(count[REGULAR], count[DYNAMIC]) * 2
            artime.reset(cycletime * ncycles * 1.01)  # poller will quit given time
            poller.run(started_callback)
            total = artime.time() - artime.STARTTIME
            for module in modules:
                for pobj in module.parameters.values():
                    if pobj.poll:
                        # average_span = total / (pobj.cnt + 1)
                        assert total / (pobj.cnt + 1) <= max(cycletime, pobj.interval * 1.1)
        else:
            # normal scenario
            artime.commtime = 0.001
            artime.reset(max(maxspan.values()) * 5) # poller will quit given time
            poller.run(started_callback)
            total = artime.time() - artime.STARTTIME
            for module in modules:
                for pobj in module.parameters.values():
                    if pobj.poll:
                        assert pobj.cnt > 0
                        assert pobj.maxspan <= maxspan[pobj.polltype] * 1.1
                        assert (pobj.cnt + 1) * pobj.interval >= total * 0.99
                        assert abs(pobj.span - pobj.interval) < 0.01
                        pobj.reset()
