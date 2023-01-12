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


from frappy.core import Drivable, Parameter
from frappy.datatypes import StatusType, Enum
from frappy.states import StateMachine, Stop, Retry, Finish, Start, HasStates, StatusCode


class LoggerStub:
    def info(self, fmt, *args):
        print(fmt % args)

    def debug(self, fmt, *args):
        pass

    warning = exception = error = info
    handlers = []


def rise(state):
    state.step += 1
    if state.init:
        state.status = 'rise'
    state.level += 1
    if state.level > 3:
        return turn
    return Retry


def turn(state):
    state.step += 1
    if state.init:
        state.status = 'turn'
    state.direction += 1
    if state.direction > 3:
        return fall
    return Retry


def fall(state):
    state.step += 1
    if state.init:
        state.status = 'fall'
    state.level -= 1
    if state.level < 0:
        raise ValueError('crash')
    return fall  # retry until crash!


def finish(state):
    return None


class Result:
    cleanup_reason = None

    def __init__(self):
        self.states = []

    def on_error(self, sm):
        self.cleanup_reason = sm.cleanup_reason

    def on_transition(self, sm, newstate):
        self.states.append(newstate)


def test_fun():
    obj = Result()
    s = StateMachine(step=0, status='', transition=obj.on_transition, logger=LoggerStub())
    assert s.step == 0
    assert s.status == ''
    s.cycle()  # do nothing
    assert s.step == 0
    s.start(rise, cleanup=obj.on_error, level=0, direction=0)
    s.cycle()
    for i in range(1, 4):
        assert s.status == 'rise'
        assert s.step == i
        assert s.level == i
        assert s.direction == 0
        s.cycle()
    for i in range(5, 8):
        assert s.status == 'turn'
        assert s.step == i
        assert s.level == 4
        assert s.direction == i - 4
        s.cycle()
    s.cycle()  # -> crash
    assert isinstance(obj.cleanup_reason, ValueError)
    assert str(obj.cleanup_reason) == 'crash'
    assert obj.states == [rise, turn, fall, fall, fall, fall, fall, None]
    assert s.statefunc is None


def test_max_chain():
    obj = Result()
    s = StateMachine(step=0, status='', transition=obj.on_transition, logger=LoggerStub())
    s.start(fall, cleanup=obj.on_error, level=999+1, direction=0)
    s.cycle()
    assert isinstance(obj.cleanup_reason, RuntimeError)
    assert s.statefunc is None


def test_stop():
    obj = Result()
    s = StateMachine(step=0, status='', transition=obj.on_transition, logger=LoggerStub())
    s.start(rise, cleanup=obj.on_error, level=0, direction=0)
    for _ in range(3):
        s.cycle()
    s.stop()
    s.cycle()
    assert isinstance(obj.cleanup_reason, Stop)
    assert obj.states == [rise, None]
    assert s.statefunc is None


def test_error_handling():
    obj = Result()
    s = StateMachine(step=0, status='', transition=obj.on_transition, logger=LoggerStub())
    s.start(rise, cleanup=obj.on_error, level=0, direction=0)
    s.cycle()
    s.cycle()
    s.level = None
    s.cycle()
    assert isinstance(obj.cleanup_reason, TypeError)
    assert obj.states == [rise, None]
    assert s.statefunc is None


def test_on_restart():
    obj = Result()
    s = StateMachine(step=0, status='', transition=obj.on_transition, logger=LoggerStub())
    s.start(rise, cleanup=obj.on_error, level=0, direction=0)
    s.cycle()
    s.cycle()
    s.start(turn)
    s.cycle()
    assert isinstance(obj.cleanup_reason, Start)
    obj.cleanup_reason = None
    s.cycle()
    assert s.statefunc is turn
    assert obj.cleanup_reason is None
    assert obj.states == [rise, None, turn]


def test_finish():
    obj = Result()
    s = StateMachine(step=0, status='', transition=obj.on_transition, logger=LoggerStub())
    s.start(finish, cleanup=obj.on_error, level=0, direction=0)
    s.cycle()
    s.cycle()
    assert obj.states == [finish, None]
    assert s.statefunc is None


Status = Enum(
    Drivable.Status,
    PREPARED=150,
    PREPARING=340,
    RAMPING=370,
    STABILIZING=380,
    FINALIZING=390,
)


class DispatcherStub:
    # the first update from the poller comes a very short time after the
    # initial value from the timestamp. However, in the test below
    # the second update happens after the updates dict is cleared
    # -> we have to inhibit the 'omit unchanged update' feature
    omit_unchanged_within = 0

    def __init__(self, updates):
        self.updates = updates

    def announce_update(self, modulename, pname, pobj):
        assert modulename == 'obj'
        if pobj.readerror:
            self.updates.append((pname, pobj.readerror))
        else:
            self.updates.append((pname, pobj.value))


class ServerStub:
    def __init__(self, updates):
        self.dispatcher = DispatcherStub(updates)


class Mod(HasStates, Drivable):
    status = Parameter(datatype=StatusType(Status))
    _my_time = 0

    def artificial_time(self):
        return self._my_time

    def on_cleanup(self, sm):
        return self.cleanup_one

    def state_transition(self, sm, newstate):
        self.statelist.append(getattr(newstate, '__name__', None))
        super().state_transition(sm, newstate)

    def state_one(self, sm):
        if sm.init:
            return Retry
        return self.state_two

    @StatusCode('PREPARING', 'state 2')
    def state_two(self, sm):
        return self.state_three

    @StatusCode('FINALIZING')
    def state_three(self, sm):
        if sm.init:
            return Retry
        return self.final_status('IDLE', 'finished')

    @StatusCode('BUSY')
    def cleanup_one(self, sm):
        if sm.init:
            return Retry
        print('one 2')
        return self.cleanup_two

    def cleanup_two(self, sm):
        if sm.init:
            return Retry
        return Finish

    def doPoll(self):
        super().doPoll()
        self._my_time += 1


def create_module():
    updates = []
    obj = Mod('obj', LoggerStub(), {'description': ''}, ServerStub(updates))
    obj.initModule()
    obj.statelist = []
    try:
        obj._Module__pollThread(obj.polledModules, None)
    except TypeError:
        pass  # None is not callable
    updates.clear()
    return obj, updates


def test_updates():
    obj, updates = create_module()
    obj.start_machine(obj.state_one)
    for _ in range(10):
        obj.doPoll()
    assert updates == [
        ('status', (Status.BUSY, 'state one')),         # default: BUSY, function name without '_'
        ('status', (Status.PREPARING, 'state 2')),      # explicitly given
        ('status', (Status.FINALIZING, 'state three')),  # only code given
        ('status', (Status.IDLE, 'finished')),
    ]


def test_stop_without_cleanup():
    obj, updates = create_module()
    obj.start_machine(obj.state_one)
    obj.doPoll()
    obj.stop_machine()
    for _ in range(10):
        obj.doPoll()
    assert updates == [
        ('status', (Status.BUSY, 'state one')),
        ('status', (Status.BUSY, 'stopping')),
        ('status', (Status.IDLE, 'stopped')),
    ]
    assert obj.statelist == ['state_one', None]


def test_stop_with_cleanup():
    obj, updates = create_module()
    obj.start_machine(obj.state_one, cleanup=obj.on_cleanup)
    obj.doPoll()
    obj.stop_machine()
    for _ in range(10):
        obj.doPoll()
    assert updates == [
        ('status', (Status.BUSY, 'state one')),
        ('status', (Status.BUSY, 'stopping')),
        ('status', (Status.BUSY, 'stopping (cleanup one)')),
        ('status', (Status.IDLE, 'stopped')),
    ]
    assert obj.statelist == ['state_one', 'cleanup_one', 'cleanup_two', None]


def test_all_restart():
    obj, updates = create_module()
    obj.start_machine(obj.state_one, cleanup=obj.on_cleanup, statelist=[])
    obj.doPoll()
    obj.start_machine(obj.state_three)
    for _ in range(10):
        obj.doPoll()
    assert updates == [
        ('status', (Status.BUSY, 'state one')),
        ('status', (Status.FINALIZING, 'restarting')),
        ('status', (Status.FINALIZING, 'restarting (cleanup one)')),
        ('status', (Status.FINALIZING, 'state three')),
        ('status', (Status.IDLE, 'finished')),
    ]
    assert obj.statelist == ['state_one', 'cleanup_one', 'cleanup_two', None, 'state_three', None]
