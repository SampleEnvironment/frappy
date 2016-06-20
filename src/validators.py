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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************
"""Define validators."""


# a Validator validates a given object and raises an ValueError if it doesn't fit
# easy python validators: int(), float(), str()

class floatrange(object):
    def __init__(self, lower, upper):
        self.lower = float(lower)
        self.upper = float(upper)
    def __call__(self, value):
        value = float(value)
        if not self.lower <= value <= self.upper:
            raise ValueError('Floatrange: value %r must be within %f and %f' % (value, self.lower, self.upper))
        return value


def positive(obj):
    if obj <= 0:
        raise ValueError('Value %r must be positive!' % obj)
    return obj

def nonnegative(obj):
    if obj < 0:
        raise ValueError('Value %r must be zero or positive!' % obj)
    return obj

class mapping(object):
    def __init__(self, *args, **kwds):
        self.mapping = {}
        # use given kwds directly
        self.mapping.update(kwds)
        # enumerate args
        i = -1
        args = list(args)
        while args:
            i += 1
            if i in self.mapping:
                continue
            self.mapping[args.pop(0)] = i
        # generate reverse mapping too for use by protocol
        self.revmapping = {}
        for k, v in self.mapping.items():
            self.revmapping[v] = k

    def __call__(self, obj):
        if obj in self.mapping:
            return obj
        raise ValueError("%r should be one of %r" % (obj, list(self.mapping.keys())))

