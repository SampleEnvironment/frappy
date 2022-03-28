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


from secop.lib.statemachine import StateMachine, Stop, Retry


def rise(state):
    state.step += 1
    print('rise', state.step)
    if state.init:
        state.status = 'rise'
    state.level += 1
    if state.level > 3:
        return turn
    return Retry()


def turn(state):
    state.step += 1
    if state.init:
        state.status = 'turn'
    state.direction += 1
    if state.direction > 3:
        return fall
    return Retry()


def fall(state):
    state.step += 1
    if state.init:
        state.status = 'fall'
    state.level -= 1
    if state.level < 0:
        raise ValueError('crash')
    return Retry(0)  # retry until crash!


def error_handler(state):
    state.last_error_name = type(state.last_error).__name__


class LoggerStub:
    def debug(self, fmt, *args):
        print(fmt % args)
    info = warning = exception = error = debug
    handlers = []


class DummyThread:
    def is_alive(self):
        return True


def test_fun():
    s = StateMachine(step=0, status='', threaded=False, logger=LoggerStub())
    assert s.step == 0
    assert s.status == ''
    s.cycle()  # do nothing
    assert s.step == 0
    s.start(rise, level=0, direction=0)
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
    assert isinstance(s.last_error, ValueError)
    assert str(s.last_error) == 'crash'
    assert s.state is None


def test_max_chain():
    s = StateMachine(step=0, status='', threaded=False, logger=LoggerStub())
    s.start(fall, level=999+1, direction=0)
    s.cycle()
    assert isinstance(s.last_error, RuntimeError)
    assert s.state is None


def test_stop():
    s = StateMachine(step=0, status='', threaded=False, logger=LoggerStub())
    s.start(rise, level=0, direction=0)
    for _ in range(1, 3):
        s.cycle()
    s.stop()
    s.cycle()
    assert s.last_error is Stop
    assert s.state is None


def test_std_error_handling():
    s = StateMachine(step=0, status='', threaded=False, logger=LoggerStub())
    s.start(rise, level=0, direction=0)
    s.cycle()
    s.level = None  # -> TypeError on next step
    s.cycle()
    assert s.state is None  # default error handler: stop machine
    assert isinstance(s.last_error, TypeError)
    assert not hasattr(s, 'last_error_name')


def test_default_error_handling():
    s = StateMachine(step=0, status='', cleanup=error_handler, threaded=False, logger=LoggerStub())
    s.start(rise, level=0, direction=0)
    s.cycle()
    s.level = None
    s.cycle()
    assert s.state is None
    assert s.last_error_name == 'TypeError'
    assert isinstance(s.last_error, TypeError)


def test_cleanup_on_restart():
    s = StateMachine(step=0, status='', threaded=False, logger=LoggerStub())
    s.start(rise, level=0, direction=0)
    s.cycle()
    s.start(turn)
    s.cycle()
    assert s.state is turn
    assert s.last_error is None
