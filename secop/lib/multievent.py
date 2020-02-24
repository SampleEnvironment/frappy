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

import threading


class MultiEvent(threading.Event):
    """Class implementing multi event objects.

    meth:`new` creates Event like objects
    meth:'wait` waits for all of them being set
    """

    class SingleEvent:
        """Single Event

        remark: :meth:`wait` is not implemented on purpose
        """
        def __init__(self, multievent):
            self.multievent = multievent
            self.multievent._clear(self)

        def clear(self):
            self.multievent._clear(self)

        def set(self):
            self.multievent._set(self)

        def is_set(self):
            return self in self.multievent.events

    def __init__(self):
        self.events = set()
        self._lock = threading.Lock()
        super().__init__()

    def new(self):
        """create a new SingleEvent"""
        return self.SingleEvent(self)

    def set(self):
        raise ValueError('a multievent must not be set directly')

    def clear(self):
        raise ValueError('a multievent must not be cleared directly')

    def _set(self, event):
        """internal: remove event from the event list"""
        with self._lock:
            self.events.discard(event)
            if self.events:
                return
            super().set()

    def _clear(self, event):
        """internal: add event to the event list"""
        with self._lock:
            self.events.add(event)
            super().clear()

    def wait(self, timeout=None):
        if not self.events:  # do not wait if events are empty
            return
        super().wait(timeout)
