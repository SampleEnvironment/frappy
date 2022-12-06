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
from frappy.errors import ProgrammingError
from frappy.lib.statemachine import StateMachine, Finish, Start, Stop, \
    Retry  # pylint: disable=unused-import


class StatusCode:
    """decorator for state methods

    :param code: the code assigned to the state function
    :param text: the text assigned to the state function
           if not given, the text is taken from the state functions name
    """
    def __init__(self, code, text=None):
        self.code = code
        self.text = text

    def __set_name__(self, owner, name):
        if not issubclass(owner, HasStates):
            raise ProgrammingError('when using decorator "status_code", %s must inherit HasStates' % owner.__name__)
        self.cls = owner
        self.name = name
        if 'statusMap' not in owner.__dict__:
            # we need a copy on each inheritance level
            owner.statusMap = owner.statusMap.copy()
        owner.statusMap[name] = self.code, name.replace('_', ' ') if self.text is None else self.text
        setattr(owner, name, self.func)  # replace with original method

    def __call__(self, func):
        self.func = func
        return self


class HasStates:
    """mixin for modules needing a statemachine"""
    status = Parameter()  # make sure this is a parameter
    _state_machine = None
    statusMap = {}  # a dict populated with status values for methods used as state functions

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
            status_text='',
            **kwds)

    def initModule(self):
        super().initModule()
        self.init_state_machine()

    def state_transition(self, sm, newstate):
        """handle status updates"""
        status = self.get_status(newstate)
        if status is not None:
            # if a status_code is given, remember the text of this state
            sm.status_text = status[1]
        if isinstance(sm.next_task, Stop):
            if newstate:
                status = self.status[0], 'stopping (%s)' % sm.status_text
        elif isinstance(sm.next_task, Start):
            next_status = self.get_status(sm.next_task.newstate, BUSY)
            if newstate:
                # restart case
                status = next_status[0], 'restarting (%s)' % sm.status_text
            else:
                # start case
                status = next_status
        if status is None:
            return  # no status_code given -> no change
        if status != self.status:
            self.status = status

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
            status = self.statusMap.get(name)
            if status is None and default_code is not None:
                status = default_code, name.replace('_', ' ')
        print('get_status', statefunc, status, default_code)
        return status

    def doPoll(self):
        super().doPoll()
        sm = self._state_machine
        sm.cycle()
        if sm.statefunc is None and sm.reset_fast_poll:
            sm.reset_fast_poll = False
            self.setFastPoll(False)

    def start_machine(self, statefunc, fast_poll=True, cleanup=None, **kwds):
        """start or restart the state machine

        :param statefunc: the initial state to be called
        :param fast_poll: flag to indicate that polling has to switched to fast
        :param cleanup: a cleanup function
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
        status = self.get_status(statefunc, BUSY)
        if sm.statefunc:
            status = status[0], 'restarting'
        self.status = status
        sm.status_text = status[1]
        sm.start(statefunc, cleanup=cleanup, **kwds)
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
            self.status = self.status[0], 'stopping'
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
        return Finish
