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
- Retry to keep the state and call the state function again
- or Finish for finishing


Initialisation Code
-------------------

For code to be called only after a state transition, use statemachine.init.

def state_x(statemachine):
    if statemachine.init:
        ... code to be execute only after entering state x ...
    ... further code ...


Restart
-------

To restart the statemachine, call statemachine.start. The current task is interrupted,
the cleanup sequence is called, and after this the machine is restarted with the
arguments of the start method.


Stop
----

To stop the statemachine, call statemachine.stop. The current task is interrupted,
the cleanup sequence is called, and the machine finishes.


Cleaning Up
-----------

A cleanup function might be added as arguments to StateMachine.start.
On error, stop or restart, the cleanup sequence will be executed.
The cleanup itself is not be interrupted:
- if a further exeception is raised, the machine is interrupted immediately
- if start or stop is called again, a previous start or stop is ignored.
  The currently running cleanup sequence is finished, and not started again.
"""

import time
import threading
from logging import getLogger
from frappy.lib import UniqueObject

Retry = UniqueObject('Retry')
Finish = UniqueObject('Finish')


class Start:
    def __init__(self, newstate, kwds):
        self.newstate = newstate
        self.kwds = kwds  # statemachine attributes


class Stop:
    pass


class StateMachine:
    """a simple, but powerful state machine"""
    # class attributes are not allowed to be overriden by kwds of __init__ or :meth:`start`
    statefunc = None  # the current statefunc
    now = None  # the current time (avoid mutiple calls within a state)
    init = True  # True only in the first call of a state after a transition
    next_task = None  # None or an instance of Start or Stop
    cleanup_reason = None  # None or an instance of Exception, Start or Stop
    _last_time = 0  # for delta method

    def __init__(self, statefunc=None, logger=None, **kwds):
        """initialize state machine

        :param statefunc: if given, this is the first statefunc
        :param logger: an optional logger
        :param kwds: any attributes for the state object
        """
        self.cleanup = None
        self.transition = None
        self.maxloops = 10  # the maximum number of statefunc functions called in sequence without Retry
        self.now = time.time()  # avoids calling time.time several times per statefunc
        self.log = logger or getLogger('dummy')
        self._lock = threading.Lock()
        self._update_attributes(kwds)
        if statefunc:
            self.start(statefunc)

    def _update_attributes(self, kwds):
        """update allowed attributes"""
        cls = type(self)
        for key, value in kwds.items():
            if hasattr(cls, key):
                raise AttributeError('can not set %s.%s' % (cls.__name__, key))
            setattr(self, key, value)

    def _cleanup(self, reason):
        if isinstance(reason, Exception):
            self.log.warning('%s: raised %r', self.statefunc.__name__, reason)
        elif isinstance(reason, Stop):
            self.log.debug('stopped in %s', self.statefunc.__name__)
        else:  # must be Start
            self.log.debug('restart %s during %s', reason.newstate.__name__, self.statefunc.__name__)
        if self.cleanup_reason is None:
            self.cleanup_reason = reason
        if not self.cleanup:
            return None  # no cleanup needed or cleanup already handled
        with self._lock:
            cleanup, self.cleanup = self.cleanup, None
        ret = None
        try:
            ret = cleanup(self)  # pylint: disable=not-callable  # None or function
            if not (ret is None or callable(ret)):
                self.log.error('%s: return value must be callable or None, not %r',
                               cleanup.__name__, ret)
                ret = None
        except Exception as e:
            self.log.exception('%r raised in cleanup', e)
        return ret

    @property
    def is_active(self):
        return bool(self.statefunc)

    def _new_state(self, statefunc):
        if self.transition:
            self.transition(self, statefunc)  # pylint: disable=not-callable  # None or function
        self.init = True
        self.statefunc = statefunc
        self._last_time = self.now

    def cycle(self):
        """do one cycle

        call state functions until Retry is returned
        """
        for _ in range(2):
            if self.statefunc:
                for _ in range(self.maxloops):
                    self.now = time.time()
                    if self.next_task and not self.cleanup_reason:
                        # interrupt only when not cleaning up
                        ret = self._cleanup(self.next_task)
                    else:
                        try:
                            ret = self.statefunc(self)
                            self.init = False
                            if ret is Retry:
                                return
                            if ret is Finish:
                                break
                            if not callable(ret):
                                ret = self._cleanup(RuntimeError(
                                    '%s: return value must be callable, Retry or Finish, not %r'
                                    % (self.statefunc.__name__, ret)))
                        except Exception as e:
                            ret = self._cleanup(e)
                    if ret is None:
                        break
                    self._new_state(ret)
                else:
                    ret = self._cleanup(RuntimeError(
                        '%s: too many states chained - probably infinite loop' % self.statefunc.__name__))
                    if ret:
                        self._new_state(ret)
                        continue
                if self.cleanup_reason is None:
                    self.log.debug('finish in state %r', self.statefunc.__name__)
                self._new_state(None)
            if self.next_task:
                with self._lock:
                    action, self.next_task = self.next_task, None
                self.cleanup_reason = None
                if isinstance(action, Start):
                    self._new_state(action.newstate)
                    self._update_attributes(action.kwds)

    def start(self, statefunc, **kwds):
        """start with a new state

        :param statefunc: the first state
        :param kwds: items to put as attributes on the state machine
        """
        kwds.setdefault('cleanup', None)  # cleanup must be given on each restart
        with self._lock:
            self.next_task = Start(statefunc, kwds)

    def stop(self):
        """stop machine, go to idle state"""
        with self._lock:
            self.next_task = Stop()

    def delta(self, mindelta=0):
        """helper method for time dependent control

        :param mindelta: minimum time since last call
        :return: time delta or None when less than min delta time has passed

        to be called from within an state function

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
