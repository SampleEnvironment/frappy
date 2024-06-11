# *****************************************************************************
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
#   Jael Celia Lorenzana <jael-celia.lorenzana@psi.ch>
#
# *****************************************************************************

"""soft PI control"""

import time
import math
from frappy.core import Writable, Parameter, FloatRange, IDLE
from frappy.lib import clamp
from frappy.datatypes import LimitsType, EnumType
from frappy.mixins import HasOutputModule


class PImixin(HasOutputModule, Writable):
    p = Parameter('proportional term', FloatRange(0), readonly=False)
    i = Parameter('integral term', FloatRange(0), readonly=False)
    output_range = Parameter('min output',
                             LimitsType(FloatRange()), default=(0, 0), readonly=False)
    output_func = Parameter('output function',
                            EnumType(lin=0, square=1), readonly=False, default=0)
    value = Parameter(unit='K')
    _lastdiff = None
    _lasttime = 0
    _clamp_limits = None

    def doPoll(self):
        super().doPoll()
        if self._clamp_limits is None:
            out = self.output_module
            if hasattr(out, 'max_target'):
                if hasattr(self, 'min_target'):
                    self._clamp_limits = lambda v, o=out: clamp(v, o.read_min_target(), o.read_max_target())
                else:
                    self._clamp_limits = lambda v, o=out: clamp(v, 0, o.read_max_target())
            elif hasattr(out, 'limit'):  # mercury.HeaterOutput
                self._clamp_limits = lambda v, o=out: clamp(v, 0, o.read_limit())
            else:
                self._clamp_limits = lambda v: v
            if self.output_range == (0.0, 0.0):
                self.output_range = (0, self._clamp_limits(float('inf')))
        if not self.control_active:
            return
        self.status = IDLE, 'controlling'
        now = time.time()
        deltat = clamp(0, now-self._lasttime, 10)
        self._lasttime = now
        diff = self.target - self.value
        if self._lastdiff is None:
            self._lastdiff = diff
        deltadiff = diff - self._lastdiff
        self._lastdiff = diff
        out = self.output_module
        output = out.target
        if self.output_func == 'square':
            output = math.sqrt(max(0, output))
        output += self.p * deltadiff + self.i * deltat * diff
        if self.output_func == 'square':
            output = output ** 2
        output = self._clamp_limits(output)
        out.update_target(self.name, clamp(output, *self.output_range))

    def write_control_active(self, value):
        if not value:
            self.output_module.write_target(0)

    def write_target(self, _):
        if not self.control_active:
            self.activate_control()
