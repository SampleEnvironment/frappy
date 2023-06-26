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

from frappy.core import Parameter, FloatRange, BUSY, IDLE, WARN
from frappy.lib.statemachine import StateMachine, Retry, Stop
from frappy.lib import merge_status


class HasConvergence:
    """mixin for convergence checks

    Implementation based on tolerance, settling time and timeout.
    The algorithm does its best to support changes of these parameters on the
    fly. However, the full history is not considered, which means for example
    that the spent time inside tolerance stored already is not altered when
    changing tolerance.

    does not inherit from HasStates (own state machine!)
    """
    tolerance = Parameter('absolute tolerance', FloatRange(0, unit='$'), readonly=False, default=0)
    settling_time = Parameter(
        '''settling time

        total amount of time the value has to be within tolerance before switching to idle.
        ''', FloatRange(0, unit='sec'), readonly=False, default=60)
    timeout = Parameter(
        '''timeout

        timeout = 0: disabled, else:
        A timeout event happens, when the difference abs(<target> - <value>) drags behind
        the expected difference for longer than <timeout>. The expected difference is determined
        by parameters 'workingramp' or 'ramp'. If ramp is not available, an exponential decay of
        the difference with <tolerance> as time constant is expected.
        As soon as the value is the first time within tolerance, the timeout criterium is changed:
        then the timeout event happens after this time + <settling_time> + <timeout>.
        ''', FloatRange(0, unit='sec'), readonly=False, default=3600)
    status = Parameter()  # make sure status is a parameter
    convergence_state = None  # the state machine

    def earlyInit(self):
        super().earlyInit()
        self.convergence_state = StateMachine(
            threaded=False, logger=self.log, cleanup=self.convergence_cleanup,
            status=(IDLE, ''), spent_inside=0, stop_status=(IDLE, 'stopped'))

    def convergence_cleanup(self, state):
        state.default_cleanup(state)
        if state.stopped:
            if state.stopped is Stop:  # and not Restart
                self.__set_status(WARN, 'stopped')
        else:
            self.__set_status(WARN, repr(state.last_error))

    def doPoll(self):
        super().doPoll()
        state = self.convergence_state
        state.cycle()

    def __set_status(self, *status):
        if status != self.convergence_state.status:
            self.convergence_state.status = status
            self.read_status()

    def read_status(self):
        try:
            return merge_status(super().read_status(), self.convergence_state.status)
        except AttributeError:
            return self.convergence_state.status  # no super().read_status

    def convergence_min_slope(self, dif):
        """calculate minimum expected slope"""
        slope = getattr(self, 'workingramp', 0) or getattr(self, 'ramp', 0)
        if slope or not self.timeout:
            return slope
        return dif / self.timeout  # assume exponential decay of dif, with time constant <tolerance>

    def convergence_dif(self):
        """get difference target - value and tolerance"""
        tol = self.tolerance
        if not tol:
            tol = 0.01 * max(abs(self.target), abs(self.value))
        dif = abs(self.target - self.value)
        return dif, tol

    def convergence_start(self):
        """to be called from write_target"""
        self.__set_status(BUSY, 'changed_target')
        self.convergence_state.start(self.convergence_approach)

    def convergence_approach(self, state):
        """approaching, checking progress (busy)"""
        state.spent_inside = 0
        dif, tol = self.convergence_dif()
        if dif <= tol:
            state.timeout_base = state.now
            return self.convergence_inside
        if not self.timeout:
            return Retry
        if state.init:
            state.timeout_base = state.now
            state.dif_crit = dif  # criterium for resetting timeout base
        self.__set_status(BUSY, '')
        state.dif_crit -= self.convergence_min_slope(dif) * state.delta()
        if dif < state.dif_crit:  # progress is good: reset timeout base
            state.timeout_base = state.now
        elif state.now > state.timeout_base + self.timeout:
            self.__set_status(WARN, 'convergence timeout')
            return self.convergence_instable
        return Retry

    def convergence_inside(self, state):
        """inside tolerance, still busy"""
        dif, tol = self.convergence_dif()
        if dif > tol:
            return self.convergence_outside
        state.spent_inside += state.delta()
        if state.spent_inside > self.settling_time:
            self.__set_status(IDLE, 'reached target')
            return self.convergence_stable
        if state.init:
            self.__set_status(BUSY, 'inside tolerance')
        return Retry

    def convergence_outside(self, state):
        """temporarely outside tolerance, busy"""
        dif, tol = self.convergence_dif()
        if dif <= tol:
            return self.convergence_inside
        if state.now > state.timeout_base + self.settling_time + self.timeout:
            self.__set_status(WARN, 'settling timeout')
            return self.convergence_instable
        if state.init:
            self.__set_status(BUSY, 'outside tolerance')
        # do not reset the settling time on occasional outliers, count backwards instead
        state.spent_inside = max(0.0, state.spent_inside - state.delta())
        return Retry

    def convergence_stable(self, state):
        """stable, after settling_time spent within tolerance, idle"""
        dif, tol = self.convergence_dif()
        if dif <= tol:
            return Retry
        self.__set_status(WARN, 'instable')
        state.spent_inside = max(self.settling_time, state.spent_inside)
        return self.convergence_instable

    def convergence_instable(self, state):
        """went outside tolerance from stable, warning"""
        dif, tol = self.convergence_dif()
        if dif <= tol:
            state.spent_inside += state.delta()
            if state.spent_inside > self.settling_time:
                self.__set_status(IDLE, 'stable')  # = recovered from instable
                return self.convergence_stable
        else:
            state.spent_inside = max(0, state.spent_inside - state.delta())
        return Retry

    def convergence_interrupt(self, state):
        """stopping"""
        self.__set_status(state.stop_status)  # stop called
        return self.convergence_instable

    def stop(self):
        """set to idle when busy

        does not stop control!
        """
        if self.isBusy():
            self.convergence_state.start(self.convergence_interrupt)

    def write_settling_time(self, value):
        if self.pollInfo:
            self.pollInfo.trigger(True)
        return value

    def write_tolerance(self, value):
        if self.pollInfo:
            self.pollInfo.trigger(True)
        return value
