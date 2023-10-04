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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

"""Supporting classes for FRM2 magnets, currently only Garfield (amagnet).
"""

# partially borrowed from nicos


import math

from frappy.datatypes import ArrayOf, FloatRange, StructOf, TupleOf
from frappy.errors import ConfigError, DisabledError
from frappy.lib.sequence import SequencerMixin, Step
from frappy.modules import Drivable, Parameter, Attached


class GarfieldMagnet(SequencerMixin, Drivable):
    """Garfield Magnet

    uses a polarity switch ('+' or '-') to flip polarity and an onoff switch
    to cut power (to be able to switch polarity) in addition to an
    unipolar current source.

        B(I) = Ic0 + c1*erf(c2*I) + c3*atan(c4*I)

    Coefficients c0..c4 are given as 'calibration_table' parameter,
    the symmetry setting selects which.
    """

    # attached submodules
    currentsource = Attached(description='(bipolar) Powersupply')
    enable = Attached(description='Switch to set for on/off')
    polswitch = Attached(description='Switch to set for polarity')
    symmetry = Attached(description='Switch to read for symmetry')
    # parameters
    userlimits = Parameter('User defined limits of device value',
                           datatype=TupleOf(FloatRange(unit='$'),
                                            FloatRange(unit='$')),
                           default=(float('-Inf'), float('+Inf')),
                           readonly=False)
    abslimits = Parameter('Absolute limits of device value',
                          datatype=TupleOf(FloatRange(unit='$'),
                                           FloatRange(unit='$')),
                          default=(-0.5, 0.5))
    precision = Parameter('Precision of the device value (allowed deviation '
                          'of stable values from target)',
                          datatype=FloatRange(0.001, unit='$'), default=0.001,
                          readonly=False,)
    ramp = Parameter('Target rate of field change per minute', readonly=False,
                     datatype=FloatRange(unit='$/min'), default=1.0)
    calibration = Parameter('Coefficients for calibration function: '
                            '[c0, c1, c2, c3, c4] calculates '
                            'B(I) = c0*I + c1*erf(c2*I) + c3*atan(c4*I) in T',
                            datatype=ArrayOf(FloatRange(), 5, 5),
                            default=(1.0, 0.0, 0.0, 0.0, 0.0))
    calibrationtable = Parameter('Map of Coefficients for calibration per '
                                 'symmetry setting',
                                 datatype=StructOf(
                                     symmetric=ArrayOf(FloatRange(), 5, 5),
                                     short=ArrayOf(FloatRange(), 5, 5),
                                     asymmetric=ArrayOf(FloatRange(), 5, 5)),
                                 export=False)

    def _current2field(self, current, *coefficients):
        """Return field in T for given current in A.

        Should be monotonic and asymetric or _field2current will fail!

        Note: This may be overridden in derived classes.
        """
        v = coefficients or self.calibration
        if len(v) != 5:
            self.log.warning('Wrong number of coefficients in calibration '
                             'data!  Need exactly 5 coefficients!')
        return current * v[0] + v[1] * math.erf(v[2] * current) + \
            v[3] * math.atan(v[4] * current)

    def _field2current(self, field):
        """Return required current in A for requested field in T.

        Default implementation does a binary search using _current2field,
        which must be monotonic for this to work!

        Note: This may be overridden in derived classes.
        """
        # binary search/bisection
        maxcurr = self.currentsource.abslimits[1]
        mincurr = -maxcurr
        maxfield = self._current2field(maxcurr)
        minfield = -maxfield
        if not minfield <= field <= maxfield:
            raise ValueError(self,
                             f'requested field {field:g} T out of range {minfield:g}..{maxfield:g} T')
        while minfield <= field <= maxfield:
            # binary search
            trycurr = 0.5 * (mincurr + maxcurr)
            tryfield = self._current2field(trycurr)
            if field == tryfield:
                self.log.debug('current for %g T is %g A', field, trycurr)
                return trycurr  # Gotcha!
            if field > tryfield:
                # retry upper interval
                mincurr = trycurr
                minfield = tryfield
            else:
                # retry lower interval
                maxcurr = trycurr
                maxfield = tryfield
            # if interval is so small, that any error within is acceptable:
            if maxfield - minfield < 1e-4:
                ratio = (field - minfield) / float(maxfield - minfield)
                trycurr = (maxcurr - mincurr) * ratio + mincurr
                self.log.debug('current for %g T is %g A', field, trycurr)
                return trycurr  # interpolated
        raise ConfigError(self, '_current2field polynome not monotonic!')

    def initModule(self):
        super().initModule()
        self.init_sequencer(fault_on_error=False, fault_on_stop=False)
        self.symmetry.read_value()

    def read_calibration(self):
        try:
            try:
                return self.calibrationtable[self.symmetry.value]
            except KeyError:
                return self.calibrationtable[self.symmetry.value.name]
        except KeyError:
            minslope = min(entry[0]
                           for entry in self.calibrationtable.values())
            self.log.error(
                'unconfigured calibration for symmetry %r',
                self.symmetry.value)
            return [minslope, 0, 0, 0, 0]

    def _checkLimits(self, limits):
        umin, umax = limits
        amin, amax = self.abslimits
        if umin > umax:
            raise ValueError(
                self, f'user minimum ({umin}) above the user maximum ({umax})')
        if umin < amin - abs(amin * 1e-12):
            umin = amin
        if umax > amax + abs(amax * 1e-12):
            umax = amax
        return (umin, umax)

    def write_userlimits(self, value):
        limits = self._checkLimits(value)
        return limits

    def read_abslimits(self):
        maxfield = self._current2field(self.currentsource.abslimits[1])
        # limit to configured value (if any)
        maxfield = min(maxfield, max(self.accessibles['abslimits'].default))
        return -maxfield, maxfield

    def read_ramp(self):
        # This is an approximation!
        return self.calibration[0] * abs(self.currentsource.ramp)

    def write_ramp(self, newramp):
        # This is an approximation!
        self.currentsource.ramp = float(newramp) / self.calibration[0]

    def _get_field_polarity(self):
        sign = int(self.polswitch.read_value())
        if self.enable.read_value():
            return sign
        return 0

    def _set_field_polarity(self, polarity):
        current_pol = self._get_field_polarity()
        polarity = int(polarity)
        if current_pol == polarity:
            return
        if polarity == 0:
            return
        if current_pol == 0:
            # safe to switch
            self.polswitch.write_target(
                '+1' if polarity > 0 else str(polarity))
            return
        if self.currentsource.value < 0.1:
            self.polswitch.write_target('0')
            return
        # unsafe to switch, go to safe state first
        self.currentsource.write_target(0)

    def read_value(self):
        return self._current2field(
            self.currentsource.read_value() *
            self._get_field_polarity())

    def readHwStatus(self):
        # called from SequencerMixin.read_status if no sequence is running
        if self.enable.value == 'Off':
            return self.Status.WARN, 'Disabled'
        if self.enable.read_status()[0] != self.Status.IDLE:
            return self.enable.status
        if self.polswitch.value in ['0', 0]:
            return self.Status.IDLE, 'Shorted, ' + self.currentsource.status[1]
        if self.symmetry.value in ['short', 0]:
            return self.currentsource.status[
                0], 'Shorted, ' + self.currentsource.status[1]
        return self.currentsource.read_status()

    def write_target(self, target):
        if target != 0 and self.symmetry.read_value() in ['short', 0]:
            raise DisabledError(
                'Symmetry is shorted, please select another symmetry first!')

        wanted_current = self._field2current(abs(target))
        wanted_polarity = -1 if target < 0 else (+1 if target else 0)
        current_polarity = int(self._get_field_polarity())

        # generate Step sequence and start it
        seq = []
        seq.append(Step('preparing', 0, self._prepare_ramp))
        seq.append(Step('recover', 0, self._recover))
        if current_polarity != wanted_polarity:
            if self.currentsource.read_value() > 0.1:
                # switching only allowed if current is low enough -> ramp down
                # first
                seq.append(
                    Step(
                        'ramping down',
                        0.3,
                        self._ramp_current,
                        0,
                        cleanup=self._ramp_current_cleanup))
            seq.append(
                Step(
                    f'set polarity {wanted_polarity}',
                    0.3,
                    self._set_polarity,
                    wanted_polarity))  # no cleanup
        seq.append(
            Step(
                f'ramping to {target:.3f}T ({wanted_current:.2f}A)',
                0.3,
                self._ramp_current,
                wanted_current,
                cleanup=self._ramp_current_cleanup))
        seq.append(Step('finalize', 0, self._finish_ramp))

        self.start_sequence(seq)
        self.status = 'BUSY', 'ramping'

    # steps for the sequencing
    def _prepare_ramp(self, store, *args):
        store.old_window = self.currentsource.window
        self.currentsource.window = 1

    def _finish_ramp(self, store, *args):
        self.currentsource.window = max(store.old_window, 10)

    def _recover(self, store):
        # check for interlock
        if self.currentsource.read_status()[0] != self.Status.ERROR:
            return
        # recover from interlock
        ramp = self.currentsource.ramp
        self.polswitch.write_target('0')  # short is safe...
        self.polswitch._hw_wait()
        self.enable.write_target('On')  # else setting ramp won't work
        self.enable._hw_wait()
        self.currentsource.ramp = 60000
        self.currentsource.target = 0
        self.currentsource.ramp = ramp
        # safe state.... if anything of the above fails, the tamperatures may
        # be too hot!

    def _ramp_current(self, store, target):
        if abs(self.currentsource.value - target) <= 0.05:
            # done with this step if no longer BUSY
            return self.currentsource.read_status()[0] == 'BUSY'
        if self.currentsource.status[0] != 'BUSY':
            if self.enable.status[0] == 'ERROR':
                self.enable.reset()
                self.enable.read_status()
            self.enable.write_target('On')
            self.enable._hw_wait()
            self.currentsource.write_target(target)
        return True  # repeat

    def _ramp_current_cleanup(self, store, step_was_busy, target):
        # don't cleanup if step finished
        if step_was_busy:
            self.currentsource.write_target(self.currentsource.read_value())
        self.currentsource.window = max(store.old_window, 10)

    def _set_polarity(self, store, target):
        if self.polswitch.read_status()[0] == self.Status.BUSY:
            return True
        if int(self.polswitch.value) == int(target):
            return False  # done with this step
        if self.polswitch.read_value() != 0:
            self.polswitch.write_target(0)
        else:
            self.polswitch.write_target(target)
        return True  # repeat
