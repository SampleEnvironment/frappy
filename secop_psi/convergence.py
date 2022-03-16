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

from secop.core import Parameter, FloatRange, BUSY, IDLE, WARN, ERROR
from secop.lib.statemachine import StateMachine, Retry


class HasConvergence:
    """mixin for convergence checks

    Implementation based on tolerance, settling time and timeout.
    The algorithm does its best to support changes of these parameters on the
    fly. However, the full history is not considered, which means for example
    that the spent time inside tolerance stored already is not altered when
    changing tolerance.
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
    status = Parameter('status determined from convergence checks', default=(IDLE, ''))

    def earlyInit(self):
        super().earlyInit()
        self.convergence_state = StateMachine(threaded=False, logger=self.log, spent_inside=0)

    def doPoll(self):
        super().doPoll()
        state = self.convergence_state
        state.cycle()
        if not state.is_active and state.last_error is not None:
            self.status = ERROR, repr(state.last_error)

    def get_min_slope(self, dif):
        slope = getattr(self, 'workingramp', 0) or getattr(self, 'ramp', 0)
        if slope or not self.timeout:
            return slope
        return dif / self.timeout  # assume exponential decay of dif, with time constant <tolerance>

    def get_dif_tol(self):
        self.read_value()
        tol = self.tolerance
        if not tol:
            tol = 0.01 * max(abs(self.target), abs(self.value))
        dif = abs(self.target - self.value)
        return dif, tol

    def start_state(self):
        """to be called from write_target"""
        self.convergence_state.start(self.state_approach)
        self.convergence_state.cycle()

    def state_approach(self, state):
        """approaching, checking progress (busy)"""
        dif, tol = self.get_dif_tol()
        if dif < tol:
            state.timeout_base = state.now
            return self.state_inside
        if not self.timeout:
            return Retry()
        if state.init:
            state.timeout_base = state.now
            state.dif_crit = dif  # criterium for resetting timeout base
            self.status = BUSY, 'approaching'
        state.spent_inside = 0
        state.dif_crit -= self.get_min_slope(dif) * state.delta()
        if dif < state.dif_crit:  # progress is good: reset timeout base
            state.timeout_base = state.now
        elif state.now > state.timeout_base + self.timeout:
            self.status = WARN, 'convergence timeout'
            return self.state_instable
        return Retry()

    def state_inside(self, state):
        """inside tolerance, still busy"""
        if state.init:
            self.status = BUSY, 'inside tolerance'
        dif, tol = self.get_dif_tol()
        if dif > tol:
            return self.state_outside
        state.spent_inside += state.delta()
        if state.spent_inside > self.settling_time:
            self.status = IDLE, 'reached target'
            return self.state_stable
        return Retry()

    def state_outside(self, state):
        """temporarely outside tolerance, busy"""
        if state.init:
            self.status = BUSY, 'outside tolerance'
        dif, tol = self.get_dif_tol()
        if dif < tol:
            return self.state_inside
        if state.now > state.timeout_base + self.settling_time + self.timeout:
            self.status = WARN, 'settling timeout'
            return self.state_instable
        # do not reset the settling time on occasional outliers, count backwards instead
        state.spent_inside = max(0.0, state.spent_inside - state.delta())
        return Retry()

    def state_stable(self, state):
        """stable, after settling_time spent within tolerance, idle"""
        dif, tol = self.get_dif_tol()
        if dif <= tol:
            return Retry()
        self.status = WARN, 'instable'
        state.spent_inside = max(self.settling_time, state.spent_inside)
        return self.state_instable

    def state_instable(self, state):
        """went outside tolerance from stable, warning"""
        dif, tol = self.get_dif_tol()
        if dif <= tol:
            state.spent_inside += state.delta()
            if state.spent_inside > self.settling_time:
                self.status = IDLE, 'stable'  # = recovered from instable
                return self.state_stable
        else:
            state.spent_inside = max(0, state.spent_inside - state.delta())
        return Retry()
