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
#   Georg Brandl <g.brandl@fz-juelich.de>
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

"""Utilities for modules that require sequenced actions on value change."""

from __future__ import division, print_function

from time import sleep

from secop.errors import IsBusyError
from secop.lib import mkthread


class Namespace(object):
    pass


class Step(object):

    def __init__(self, desc, waittime, func, *args, **kwds):
        self.desc = desc
        self.waittime = waittime
        self.func = func
        self.args = args
        self.kwds = kwds


class SequencerMixin(object):
    """Mixin for worker classes that need to execute a sequence of actions,
    including waits, that exceeds the usual Tango timeout (about 3 seconds)
    and should be executed asynchronously.

    .. automethod:: init_sequencer

    .. automethod:: start_sequence

    .. automethod:: seq_is_alive

    .. method:: _ext_state()

       Implement this to return a custom state tuple when the sequence is
       not active.
    """

    def init_sequencer(self, fault_on_error=True, fault_on_stop=False):
        """Initialize the sequencer.  Must be called in the worker's init().

        *fault_on_error* and *fault_on_stop* control the behavior when
        exceptions are raised, or stop is activated, during the sequence, see
        below.
        """
        # thread variable init
        self._seq_thread = None
        self._seq_fault_on_error = fault_on_error
        self._seq_fault_on_stop = fault_on_stop
        self._seq_stopflag = False
        self._seq_phase = u''
        self._seq_error = None
        self._seq_stopped = None

    def start_sequence(self, seq, **store_init):
        """Start the sequence, given the list of steps.

        Each step should be a ``Step`` instance:

            Step('phase description', waittime, callable)

        where the callable should take one argument and execute an atomic step
        of the sequence.  The description is added to the status string while
        the step is active.  The waittime is a sleep after the step completes.

        As long as the callable returns a true value, the step is repeated.

        The argument to the step callable is a featureless "store" object on
        which data can be transferred between steps.  This is provided so that
        steps don't save temporary variables on ``self``.  Keyword arguments
        given to ``start_sequence`` are added to the store at the beginning.

        **Error handling**

        If *fault_on_error* in ``init_sequencer`` is true and an exception is
        raised during an atomic step, the module goes into an ERROR state
        because it cannot be ensured that further actions will be safe to
        execute.  A manual reset is required.

        Otherwise, the module goes into the WARN state and can be started
        again normally.

        **Stop handling**

        Between each atomic step, the "stop" flag for the sequence is checked,
        which is set by the mixin's ``Stop`` method.

        The *fault_on_stop* argument in ``init_sequencer`` controls which state
        the module enters when the sequence is interrupted by a stop.  Here,
        the default is to only go into ALARM.
        """
        if self.seq_is_alive():
            raise IsBusyError(u'move sequence already in progress')

        self._seq_stopflag = False
        self._seq_error = self._seq_stopped = None

        self._seq_thread = mkthread(self._seq_thread_outer, seq, store_init)

    def seq_is_alive(self):
        """Can be called to check if a sequence is currently running."""
        return self._seq_thread and self._seq_thread.isAlive()

    def read_status(self, maxage=0):
        if self.seq_is_alive():
            return self.Status.BUSY, u'moving: ' + self._seq_phase
        elif self._seq_error:
            if self._seq_fault_on_error:
                return self.Status.ERROR, self._seq_error
            return self.Status.WARN, self._seq_error
        elif self._seq_stopped:
            if self._seq_fault_on_stop:
                return self.Status.ERROR, self._seq_stopped
            return self.Status.WARN, self._seq_stopped
        if hasattr(self, u'read_hw_status'):
            return self.read_hw_status(maxage)
        return self.Status.IDLE, u''

    def do_stop(self):
        if self.seq_is_alive():
            self._seq_stopflag = True

    def _seq_thread_outer(self, seq, store_init):
        try:
            self._seq_thread_inner(seq, store_init)
        except Exception as e:
            self.log.exception(u'unhandled error in sequence thread: %s', e)
            self._seq_error = str(e)
        finally:
            self._seq_thread = None
            self.poll(0)

    def _seq_thread_inner(self, seq, store_init):
        store = Namespace()
        store.__dict__.update(store_init)
        self.log.debug(u'sequence: starting, values %s', store_init)

        for step in seq:
            self._seq_phase = step.desc
            self.log.debug(u'sequence: entering phase: %s', step.desc)
            try:
                i = 0
                while True:
                    store.i = i
                    result = step.func(store, *step.args)
                    if self._seq_stopflag:
                        if result:
                            self._seq_stopped = u'stopped while %s' % step.desc
                        else:
                            self._seq_stopped = u'stopped after %s' % step.desc
                        cleanup_func = step.kwds.get(u'cleanup', None)
                        if callable(cleanup_func):
                            try:
                                cleanup_func(store, result, *step.args)
                            except Exception as e:
                                self.log.exception(e)
                                raise
                        return
                    sleep(step.waittime)
                    if not result:
                        break
                    i += 1
            except Exception as e:
                self.log.exception(
                    u'error in sequence step %r: %s', step.desc, e)
                self._seq_error = u'during %s: %s' % (step.desc, e)
                break
