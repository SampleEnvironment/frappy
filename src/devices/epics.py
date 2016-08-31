#!/usr/bin/env python
#  -*- coding: utf-8 -*-
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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
# *****************************************************************************

"""testing devices"""

import random

from devices.core import Readable, Driveable, PARAM


try:
    from epics import PV
except ImportError:
    PV = None


class EPICS_PV(Driveable):
    """pyepics test device."""

    PARAMS = {
        'sensor': PARAM("Sensor number or calibration id",
                        validator=str, readonly=True),
        'max_rpm': PARAM("Maximum allowed rpm",
                         validator=str, readonly=True),
    }

    def read_value(self, maxage=0):
        p1 = PV('testpv.VAL')
        return p1.value

    def write_target(self, target):
        p1 = PV('test.VAL')
        p1.value = target
