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

import threading
import time


ETERNITY = 1e99


class _SingleEvent:
    """Single Event

    remark: :meth:`wait` is not implemented on purpose
    """
    def __init__(self, multievent, timeout, name=None):
        self.multievent = multievent
        self.multievent.clear_(self)
        self.name = name
        if timeout is None:
            self.deadline = ETERNITY
        else:
            self.deadline = time.monotonic() + timeout

    def clear(self):
        self.multievent.clear_(self)

    def set(self):
        self.multievent.set_(self)

    def is_set(self):
        return self in self.multievent.events


class MultiEvent(threading.Event):
    """Class implementing multi event objects."""

    def __init__(self, default_timeout=None):
        self.events = set()
        self._lock = threading.Lock()
        self.default_timeout = default_timeout or None  # treat 0 as None
        self.name = None  # default event name
        self._actions = []  # actions to be executed on trigger
        super().__init__()

    def new(self, timeout=None, name=None):
        """create a single event like object"""
        return _SingleEvent(self, timeout or self.default_timeout,
                            name or self.name or '<unnamed>')

    def set(self):
        raise ValueError('a multievent must not be set directly')

    def clear(self):
        raise ValueError('a multievent must not be cleared directly')

    def is_set(self):
        return not self.events

    def set_(self, event):
        """internal: remove event from the event list"""
        with self._lock:
            self.events.discard(event)
            if self.events:
                return
            try:
                for action in self._actions:
                    action()
            except Exception:
                pass  # we silently ignore errors here
            self._actions = []
            super().set()

    def clear_(self, event):
        """internal: add event to the event list"""
        with self._lock:
            self.events.add(event)
            super().clear()

    def deadline(self):
        deadline = 0
        for event in self.events:
            deadline = max(event.deadline, deadline)
        return None if deadline == ETERNITY else deadline

    def wait(self, timeout=None):
        """wait for all events being set or timed out"""
        if not self.events:  # do not wait if events are empty
            return True
        deadline = self.deadline()
        if deadline is not None:
            deadline -= time.monotonic()
            timeout = deadline if timeout is None else min(deadline, timeout)
            if timeout <= 0:
                return False
        return super().wait(timeout)

    def waiting_for(self):
        return set(event.name for event in self.events)

    def get_trigger(self, timeout=None, name=None):
        """create a new single event and return its set method

        as a convenience method
        """
        return self.new(timeout, name).set

    def queue(self, action):
        """add an action to the queue of actions to be executed at end

        :param action: a function, to be executed after the last event is triggered,
            and before the multievent is set

        - if no events are waiting, the actions are executed immediately
        - if an action raises an exception, it is silently ignore and further
          actions in the queue are skipped
        - if this is not desired, the action should handle errors by itself
        """
        with self._lock:
            self._actions.append(action)
            if self.is_set():
                self.set_(None)
