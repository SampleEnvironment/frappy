#!/usr/bin/env python
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
"""state machine mixin

handles status depending on statemachine state
"""


from frappy.core import BUSY, IDLE, ERROR, Parameter, Command
from frappy.lib.statemachine import StateMachine, Finish, Start, Stop, \
    Retry  # pylint: disable=unused-import


def status_code(code, text=None):
    """decorator, attaching a status to a state function

    :param code: the first element of the secop status tuple
    :param text: the second element of the secop status tuple. if not given,
                 the name of the state function is used (underscores replaced by spaces)
    :return: the decorator function

    if a state function has no attached status and is a method of the module running
    the state machine, the status is inherited from an overridden method, if available

    a state function without attached status does not change the status, or, if it is
    used as the start function, BUSY is taken as default status code
    """
    def wrapper(func):
        func.status = code, func.__name__.replace('_', ' ') if text is None else text
        return func
    return wrapper


class HasStates:
    """mixin for modules needing a statemachine"""
    status = Parameter(update_unchanged='never')
    all_status_changes = True  # when True, send also updates for status changes within a cycle
    _state_machine = None
    _status = IDLE, ''
    statusMap = None  # cache for status values derived from state methods

    def init_state_machine(self, **kwds):
        """initialize the state machine

        might be overridden in order to add additional attributes initialized

        :param kwds: additional attributes
        """
        self._state_machine = StateMachine(
            logger=self.log,
            idle_status=(IDLE, ''),
            transition=self.state_transition,
            reset_fast_poll=False,
            status=(IDLE, ''),
            **kwds)

    def initModule(self):
        super().initModule()
        self.statusMap = {}
        self.init_state_machine()

    def state_transition(self, sm, newstate):
        """handle status updates"""
        status = self.get_status(newstate)
        if sm.next_task:
            if isinstance(sm.next_task, Stop):
                if newstate and status is not None:
                    status = status[0], f'stopping ({status[1]})'
            elif newstate:
                # restart case
                if status is not None:
                    if sm.status[1] == status[1]:
                        status = sm.status
                    else:
                        status = sm.status[0], f'restarting ({status[1]})'
            else:
                # start case
                status = self.get_status(sm.next_task.newstate, BUSY)
        if status:
            sm.status = status
        if self.all_status_changes:
            self.read_status()

    def get_status(self, statefunc, default_code=None):
        """get the status assigned to a statefunc

        :param statefunc: the state function to get the status from. if None, the idle_status attribute
            of the state machine is returned
        :param default_code: if None, None is returned in case no status_code is attached to statefunc
            otherwise the returned status is composed by default_code and the modified name of the statefuncs
        :return: a status or None
        """
        if statefunc is None:
            status = self._state_machine.idle_status or (ERROR, 'Finish was returned without final status')
        else:
            name = statefunc.__name__
            try:
                # look up in statusMap cache
                status = self.statusMap[name]
            except KeyError:
                # try to get status from method or inherited method
                cls = type(self)
                for base in cls.__mro__:
                    try:
                        status = getattr(base, name, None).status
                        break
                    except AttributeError:
                        pass
                else:
                    status = None
                # store it in the cache for all further calls
                self.statusMap[name] = status
            if status is None and default_code is not None:
                status = default_code, name.replace('_', ' ')
        return status

    def read_status(self):
        return self._state_machine.status

    def cycle_machine(self):
        sm = self._state_machine
        sm.cycle()
        if sm.statefunc is None:
            if sm.reset_fast_poll:
                sm.reset_fast_poll = False
                self.setFastPoll(False)
        self.read_status()

    def doPoll(self):
        super().doPoll()
        self.cycle_machine()

    def on_cleanup(self, sm):
        """general cleanup method

        override and super call for code to be executed for
        any cleanup case
        """
        if isinstance(sm.cleanup_reason, Exception):
            return self.on_error(sm)
        if isinstance(sm.cleanup_reason, Start):
            return self.on_restart(sm)
        if isinstance(sm.cleanup_reason, Stop):
            return self.on_stop(sm)
        self.log.error('bad cleanup reason %r', sm.cleanup_reason)
        return None

    def on_error(self, sm):
        """cleanup on error

        override and probably super call for code to be executed in
        case of error
        """
        self.log.error('handle error %r', sm.cleanup_reason)
        self.final_status(ERROR, repr(sm.cleanup_reason))

    def on_restart(self, sm):
        """cleanup on restart

        override for code to be executed before a restart
        """

    def on_stop(self, sm):
        """cleanup on stop

        override for code to be executed after stopping
        """

    def start_machine(self, statefunc, fast_poll=True, status=None, **kwds):
        """start or restart the state machine

        :param statefunc: the initial state to be called
        :param fast_poll: flag to indicate that polling has to switched to fast
        :param cleanup: a cleanup function
        :param status: override automatic immediate status before first state
        :param kwds: attributes to be added to the state machine on start

        If the state machine is already running, the following happens:
        1) the currently executing state function, if any, is finished
        2) in case the cleanup attribute on the state machine object is not None,
           it is called and subsequently the state functions returned are executed,
           until a state function returns None or Finish. However, in case a cleanup
           sequence is already running, this is finished instead.
        3) only then, the new cleanup function and all the attributes given
           in kwds are set on the state machine
        4) the state machine continues at the given statefunc
        """
        sm = self._state_machine
        if status is None:
            sm.status = self.get_status(statefunc, BUSY)
            if sm.statefunc:
                sm.status = sm.status[0], 'restarting'
        else:
            sm.status = status
        sm.start(statefunc, cleanup=kwds.pop('cleanup', self.on_cleanup), **kwds)
        self.read_status()
        if fast_poll:
            sm.reset_fast_poll = True
            self.setFastPoll(True)
        self.pollInfo.trigger(True)  # trigger poller

    def stop_machine(self, stopped_status=(IDLE, 'stopped')):
        """stop the currently running machine

        :param stopped_status: status to be set after stopping

        If the state machine is not running, nothing happens.
        Else the state machine is stoppen, the predefined cleanup
        sequence is executed and then the status is set to the value
        given in the sopped_status argument.
        An already running cleanup sequence is not executed again.
        """
        sm = self._state_machine
        if sm.is_active:
            sm.idle_status = stopped_status
            sm.stop()
            sm.status = self.get_status(sm.statefunc, sm.status[0])[0], 'stopping'
            self.read_status()
            self.pollInfo.trigger(True)  # trigger poller

    @Command
    def stop(self):
        self.stop_machine()

    def final_status(self, code=IDLE, text=''):
        """final status

        Usage:

            return self.final_status('IDLE', 'machine idle')
        """
        sm = self._state_machine
        sm.idle_status = code, text
        sm.cleanup = None
        return Finish
