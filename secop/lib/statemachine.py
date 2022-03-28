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
"""a simple, but powerful state machine

Mechanism
---------

The code for the state machine is NOT to be implemented as a subclass
of StateMachine, but usually as functions or methods of an other object.
The created state object may hold variables needed for the state.
A state function may return either:
- a function for the next state to transition to
- Retry(<delay>) to keep the state and call the
- or `None` for finishing


Initialisation Code
-------------------

For code to be called only after a state transition, use stateobj.init.

def state_x(stateobj):
    if stateobj.init:
        ... code to be execute only after entering state x ...
    ... further code ...


Cleanup Function
----------------

cleanup=<cleanup function> as argument in StateMachine.__init__ or .start
defines a cleanup function to be called whenever the machine is stopped or
an error is raised in a state function. A cleanup function may return
either None for finishing or a further state function for continuing.
In case of stop or restart, this return value is ignored.


State Specific Cleanup Code
---------------------------

To execute state specific cleanup, the cleanup may examine the current state
(stateobj.state) in order to decide what to be done.

If a need arises, a future extension to this library may support specific
cleanup functions by means of a decorator adding the specific cleanup function
as an attribute to the state function.


Threaded Use
------------

On start, a thread is started, which is waiting for a trigger event when the
machine is not active. For test purposes or special needs, the thread creation
may be disabled. :meth:`cycle` must be called periodically in this case.
"""

import time
import threading
import queue
from logging import getLogger
from secop.lib import mkthread, UniqueObject


Stop = UniqueObject('Stop')
Restart = UniqueObject('Restart')


class Retry:
    def __init__(self, delay=None):
        self.delay = delay


class StateMachine:
    """a simple, but powerful state machine"""
    # class attributes are not allowed to be overriden by kwds of __init__ or :meth:`start`
    start_time = None  # the time of last start
    transition_time = None  # the last time when the state changed
    state = None  # the current state
    now = None
    init = True
    stopped = False
    last_error = None  # last exception raised or Stop or Restart
    _last_time = 0

    def __init__(self, state=None, logger=None, threaded=True, **kwds):
        """initialize state machine

        :param state: if given, this is the first state
        :param logger: an optional logger
        :param threaded: whether a thread should be started (default: True)
        :param kwds: any attributes for the state object
        """
        self.default_delay = 0.25  # default delay when returning None
        self.now = time.time()  # avoid calling time.time several times per state
        self.cleanup = self.default_cleanup  # default cleanup: finish on error
        self.log = logger or getLogger('dummy')
        self._update_attributes(kwds)
        self._lock = threading.RLock()
        self._threaded = threaded
        if threaded:
            self._thread_queue = queue.Queue()
        self._idle_event = threading.Event()
        self._thread = None
        self._restart = None
        if state:
            self.start(state)

    @staticmethod
    def default_cleanup(state):
        """default cleanup

        :param self: the state object
        :return: None (for custom cleanup functions this might be a new state)
        """
        if state.stopped:  # stop or restart
            state.log.debug('%sed in state %r', repr(state.stopped).lower(), state.status_string)
        else:
            state.log.warning('%r raised in state %r', state.last_error, state.status_string)

    def _update_attributes(self, kwds):
        """update allowed attributes"""
        cls = type(self)
        for key, value in kwds.items():
            if hasattr(cls, key):
                raise AttributeError('can not set %s.%s' % (cls.__name__, key))
            setattr(self, key, value)

    @property
    def is_active(self):
        return bool(self.state)

    @property
    def status_string(self):
        if self.state is None:
            return ''
        doc = self.state.__doc__
        return doc.split('\n', 1)[0] if doc else self.state.__name__

    @property
    def state_time(self):
        """the time spent already in this state"""
        return self.now - self.transition_time

    @property
    def run_time(self):
        """time since last (re-)start"""
        return self.now - self.start_time

    def _new_state(self, state):
        self.state = state
        self.init = True
        self.now = time.time()
        self.transition_time = self.now
        self.log.debug('state: %s', self.status_string)

    def cycle(self):
        """do one cycle in the thread loop

        :return: a delay or None when idle
        """
        if self.state is None:
            return None
        with self._lock:
            for _ in range(999):
                self.now = time.time()
                try:
                    ret = self.state(self)
                    self.init = False
                    if self.stopped:
                        self.last_error = self.stopped
                        self.cleanup(self)
                        self.stopped = False
                        ret = None
                except Exception as e:
                    self.last_error = e
                    ret = self.cleanup(self)
                    self.log.debug('called %r %sexc=%r', self.cleanup,
                                   'ret=%r ' % ret if ret else '', e)
                if ret is None:
                    self.log.debug('state: None')
                    self.state = None
                    self._idle_event.set()
                    return None
                if callable(ret):
                    self._new_state(ret)
                    continue
                if isinstance(ret, Retry):
                    if ret.delay == 0:
                        continue
                    if ret.delay is None:
                        return self.default_delay
                    return ret.delay
                self.last_error = RuntimeError('return value must be callable, Retry(...) or finish')
                break
            else:
                self.last_error = RuntimeError('too many states chained - probably infinite loop')
            self.cleanup(self)
            self.state = None
            return None

    def trigger(self, delay=0):
        if self._threaded:
            self._thread_queue.put(delay)

    def _run(self, delay):
        """thread loop

        :param delay: delay before first state is called
        """
        while True:
            try:
                ret = self._thread_queue.get(timeout=delay)
                if ret is not None:
                    delay = ret
                    continue
            except queue.Empty:
                pass
            delay = self.cycle()

    def _start(self, state, first_delay, **kwds):
        self._restart = None
        self._idle_event.clear()
        self.last_error = None
        self.stopped = False
        self._update_attributes(kwds)
        self._new_state(state)
        self.start_time = self.now
        self._last_time = self.now
        if self._threaded:
            if self._thread is None or not self._thread.is_alive():
                # restart thread if dead (may happen when cleanup failed)
                self._thread = mkthread(self._run, first_delay)
            else:
                self.trigger(first_delay)

    def start(self, state, **kwds):
        """start with a new state

        and interrupt the current state
        the cleanup function will be called with state.stopped=Restart

        :param state: the first state
        :param kwds: items to put as attributes on the state machine
        """
        self.log.debug('start %r', kwds)
        if self.state:
            self.stopped = Restart
            with self._lock:  # wait for running cycle finished
                if self.stopped:  # cleanup is not yet done
                    self.last_error = self.stopped
                    self.cleanup(self)  # ignore return state on restart
                    self.stopped = False
                delay = self.cycle()
                self._start(state, delay, **kwds)
        else:
            delay = self.cycle()  # important: call once (e.g. set status to busy)
            self._start(state, delay, **kwds)

    def stop(self):
        """stop machine, go to idle state

        the cleanup function will be called with state.stopped=Stop
        """
        self.log.debug('stop')
        self.stopped = Stop
        with self._lock:
            if self.stopped:  # cleanup is not yet done
                self.last_error = self.stopped
                self.cleanup(self)  # ignore return state on restart
                self.stopped = False
            self.state = None

    def wait(self, timeout=None):
        """wait for state machine being idle"""
        self._idle_event.wait(timeout)

    def delta(self, mindelta=0):
        """helper method for time dependent control

        :param mindelta: minimum time since last call
        :return: time delta or None when less than min delta time has passed

        to be called from within an state

        Usage:

        def state_x(self, state):
            delta = state.delta(5)
            if delta is None:
                return  # less than 5 seconds have passed, we wait for the next cycle
            # delta is >= 5, and the zero time for delta is set

            # now we can use delta for control calculations

        remark: in the first step after start, state.delta(0) returns nearly 0
        """
        delta = self.now - self._last_time
        if delta < mindelta:
            return None
        self._last_time = self.now
        return delta
