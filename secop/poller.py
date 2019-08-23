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
'''general, advanced frappy poller

Usage examples:
    any Module which want to be polled with a specific Poller must define
    the pollerClass class variable:

    class MyModule(Readable):
        ...
        pollerClass = poller.Poller
        ...

    modules having a parameter 'iodev' with the same value will share the same poller
'''

import time
from threading import Event
from heapq import heapify, heapreplace
from secop.lib import mkthread, formatException
from secop.errors import ProgrammingError

# poll types:
AUTO = 1 # equivalent to True, converted to REGULAR, SLOW or DYNAMIC
SLOW = 2
REGULAR = 3
DYNAMIC = 4

class PollerBase(object):

    startup_timeout = 30 # default timeout for startup
    name = 'unknown' # to be overridden in implementors __init__ method

    @classmethod
    def add_to_table(cls, table, module):
        '''sort module into poller table

        table is a dict, with (<pollerClass>, <name>) as the key, and the
        poller as value.
        <name> is module.iodev or module.name, if iodev is not present
        '''
        try:
            pollerClass = module.pollerClass
        except AttributeError:
            return # no pollerClass -> fall back to simple poller
        # for modules with the same iodev, a common poller is used,
        # modules without iodev all get their own poller
        name = getattr(module, 'iodev', module.name)
        poller = table.get((pollerClass, name), None)
        if poller is None:
            poller = pollerClass(name)
            table[(pollerClass, name)] = poller
        poller.add_to_poller(module)

    def start(self, started_callback):
        '''start poller thread

        started_callback to be called after all poll items were read at least once
        '''
        mkthread(self.run, started_callback)
        return self.startup_timeout

    def run(self, started_callback):
        '''poller thread function

        started_callback to be called after all poll items were read at least once
        '''
        raise NotImplementedError

    def stop(self):
        '''stop polling'''
        raise NotImplementedError

    def __bool__(self):
        '''is there any poll item?'''
        raise NotImplementedError

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.name)

    __nonzero__ = __bool__  # Py2/3 compat


class Poller(PollerBase):
    '''a standard poller

    parameters may have the following polltypes:

    - REGULAR: by default used for readonly parameters with poll=True
    - SLOW: by default used for readonly=False parameters with poll=True.
            slow polls happen with lower priority, but at least one parameter
            is polled with regular priority within self.module.pollinterval.
            Scheduled to poll every slowfactor * module.pollinterval
    - DYNAMIC: by default used for 'value' and 'status'
            When busy, scheduled to poll every fastfactor * module.pollinterval
    '''

    DEFAULT_FACTORS = {SLOW: 4, DYNAMIC: 0.25, REGULAR: 1}

    def __init__(self, name):
        '''create a poller'''
        self.queues = {polltype: [] for polltype in self.DEFAULT_FACTORS}
        self._stopped = Event()
        self.maxwait = 3600
        self.name = name

    def add_to_poller(self, module):
        factors = self.DEFAULT_FACTORS.copy()
        try:
            factors[DYNAMIC] = module.fast_pollfactor
        except AttributeError:
            pass
        try:
            factors[SLOW] = module.slow_pollfactor
        except AttributeError:
            pass
        self.maxwait = min(self.maxwait, getattr(module, 'max_polltestperiod', 10))
        try:
            self.startup_timeout = max(self.startup_timeout, module.startup_timeout)
        except AttributeError:
            pass
        # at the beginning, queues are simple lists
        # later, they will be converted to heaps
        for pname, pobj in module.parameters.items():
            polltype = int(pobj.poll)
            rfunc = getattr(module, 'read_' + pname, None)
            if not polltype or not rfunc:
                continue
            if not hasattr(module, 'pollinterval'):
                raise ProgrammingError("module %s must have a pollinterval"
                                       % module.name)
            if polltype == AUTO: # covers also pobj.poll == True
                if pname == 'value' or pname == 'status':
                    polltype = DYNAMIC
                elif pobj.readonly:
                    polltype = REGULAR
                else:
                    polltype = SLOW
            # placeholders 0 are used for due, lastdue and idx
            self.queues[polltype].append((0, 0,
                (0, module, pobj, rfunc, factors[polltype])))

    def poll_next(self, polltype):
        '''try to poll next item

        advance in queue until
        - an item is found which is really due to poll. return 0 in this case
        - or until the next item is not yet due. return next due time in this case
        '''
        queue = self.queues[polltype]
        if not queue:
            return float('inf') # queue is empty
        now = time.time()
        done = False
        while not done:
            due, lastdue, pollitem = queue[0]
            if now < due:
                return due
            _, module, pobj, rfunc, factor = pollitem

            if polltype == DYNAMIC and not module.isBusy():
                interval = module.pollinterval   # effective interval
                mininterval = interval * factor  # interval for calculating next due
            else:
                interval = module.pollinterval * factor
                mininterval = interval
            due = max(lastdue + interval, pobj.timestamp + interval * 0.5)
            if now >= due:
                try:
                    rfunc()
                except Exception: # really all. errors are handled within rfunc
                    # TODO: filter repeated errors and log just statistics
                    module.log.error(formatException())
                done = True
                lastdue = due
                due = max(lastdue + mininterval, now + min(self.maxwait, mininterval * 0.5))
            # replace due, lastdue with new values and sort in
            heapreplace(queue, (due, lastdue, pollitem))
        return 0

    def run(self, started_callback):
        '''start poll loop

        To be called as a thread. After all parameters are polled once first,
        started_callback is called. To be called in Module.start_module.

        poll strategy:
        Slow polls are performed with lower priority than regular and dynamic polls.
        If more polls are scheduled than time permits, at least every second poll is a
        dynamic poll. After every n regular polls, one slow poll is done, if due
        (where n is the number of regular parameters).
        '''
        if not self:
            # nothing to do (else we might call time.sleep(float('inf')) below
            started_callback()
            return
        # do all polls once and, at the same time, insert due info
        for _, queue in sorted(self.queues.items()): # do SLOW polls first
            for idx, (_, _, (_, module, pobj, rfunc, factor)) in enumerate(queue):
                lastdue = time.time()
                try:
                    rfunc()
                except Exception: # really all. errors are handled within rfunc
                    module.log.error(formatException())
                due = lastdue + min(self.maxwait, module.pollinterval * factor)
                # in python 3 comparing tuples need some care, as not all objects
                # are comparable. Inserting a unique idx solves the problem.
                queue[idx] = (due, lastdue, (idx, module, pobj, rfunc, factor))
            heapify(queue)
        started_callback() # signal end of startup
        nregular = len(self.queues[REGULAR])
        while not self._stopped.is_set():
            due = float('inf')
            for _ in range(nregular):
                due = min(self.poll_next(DYNAMIC), self.poll_next(REGULAR))
                if due:
                    break # no dynamic or regular polls due
            due = min(due, self.poll_next(DYNAMIC), self.poll_next(SLOW))
            delay = due - time.time()
            if delay > 0:
                self._stopped.wait(delay)

    def stop(self):
        self._stopped.set()

    def __bool__(self):
        '''is there any poll item?'''
        return any(self.queues.values())

    __nonzero__ = __bool__  # Py2/3 compat
