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


import random

from frappy.datatypes import FloatRange, StringType, ValueType, TupleOf, StructOf, ArrayOf
from frappy.modules import Communicator, Drivable, Parameter, Property, Readable, Module
from frappy.params import Command
from frappy.errors import RangeError


class LN2(Readable):
    """Just a readable.

    class name indicates it to be a sensor for LN2,
    but the implementation may do anything
    """

    def read_value(self):
        return round(100 * random.random(), 1)


class Heater(Drivable):
    """Just a driveable.

    class name indicates it to be some heating element,
    but the implementation may do anything
    """

    maxheaterpower = Parameter('maximum allowed heater power',
                               datatype=FloatRange(0, 100), unit='W',
                               )

    def read_value(self):
        return round(100 * random.random(), 1)

    def write_target(self, target):
        pass


class Temp(Drivable):
    """Just a driveable.

    class name indicates it to be some temperature controller,
    but the implementation may do anything
    """

    sensor = Parameter(
       "Sensor number or calibration id",
       datatype=StringType(
           8,
           16),
       readonly=True,
    )
    target = Parameter(
       "Target temperature",
       default=300.0,
       datatype=FloatRange(0),
       readonly=False,
       unit='K',
    )

    def read_value(self):
        return round(100 * random.random(), 1)

    def write_target(self, target):
        pass


class Lower(Communicator):
    """Communicator returning a lowercase version of the request"""

    @Command(argument=StringType(), result=StringType(), export='communicate')
    def communicate(self, command):
        """lowercase a string"""
        return str(command).lower()


class Mapped(Readable):
    value = Parameter(datatype=StringType())
    choices = Property('List of choices',
                        datatype=ValueType(list))

    def read_value(self):
        return self.choices[random.randrange(len(self.choices))]


class Commands(Module):
    """Command argument tests"""

    @Command(argument=TupleOf(FloatRange(0, 1), StringType()), result=StringType())
    def t(self, f, s):
        """a command with positional arguments (tuple)"""
        return '%g %r' % (f, s)

    @Command(argument=StructOf(a=FloatRange(0, 1), b=StringType()), result=StringType())
    def s(self, a=0, b=''):
        """a command with keyword arguments (struct)"""
        return 'a=%r b=%r' % (a, b)

    @Command(result=FloatRange(0, 1))
    def n(self):
        """no args, but returning a value"""
        return 2  # returning a value outside range should be allowed

    @Command(argument=ArrayOf(FloatRange()))
    def a(self, a):
        """array argument. raises an error when sum is negativ"""
        if sum(a) < 0:
            raise RangeError('sum must be >= 0')
