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
#
# *****************************************************************************
"""testing devices"""

try:
    # py2
    unicode
except NameError:
    # py3
    unicode = str  # pylint: disable=redefined-builtin

import random

from secop.modules import Readable, Drivable, Communicator, Parameter
from secop.datatypes import FloatRange, StringType


class LN2(Readable):
    """Just a readable.

    class name indicates it to be a sensor for LN2,
    but the implementation may do anything
    """

    def read_value(self, maxage=0):
        return round(100 * random.random(), 1)


class Heater(Drivable):
    """Just a driveable.

    class name indicates it to be some heating element,
    but the implementation may do anything
    """
    parameters = {
        'maxheaterpower': Parameter('maximum allowed heater power',
                                datatype=FloatRange(0, 100), unit='W',
                                ),
    }

    def read_value(self, maxage=0):
        return round(100 * random.random(), 1)

    def write_target(self, target):
        pass


class Temp(Drivable):
    """Just a driveable.

    class name indicates it to be some temperature controller,
    but the implementation may do anything
    """
    parameters = {
        'sensor': Parameter(
            "Sensor number or calibration id",
            datatype=StringType(
                8,
                16),
            readonly=True,
        ),
        'target': Parameter(
            "Target temperature",
            default=300.0,
            datatype=FloatRange(0),
            readonly=False,
            unit='K',
        ),
    }

    def read_value(self, maxage=0):
        return round(100 * random.random(), 1)

    def write_target(self, target):
        pass


class Lower(Communicator):
    """Communicator returning a lowercase version of the request"""
    def do_communicate(self, request):
        return unicode(request).lower()
