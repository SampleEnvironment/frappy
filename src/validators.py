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


# a Validator returns a validated object or raises an ValueError
# easy python validators: int(), float(), str()
# also validators should have a __repr__ returning a 'python' string
# which recreates them

class Validator(object):
    # list of tuples: (name, converter)
    params = []
    valuetype = float

    def __init__(self, *args, **kwds):
        plist = self.params[:]
        if len(args) > len(plist):
            raise ProgrammingError('%s takes %d parameters only (%d given)' % (
                                   self.__class__.__name__,
                                   len(plist), len(args)))
        for pval in args:
            pname, pconv = plist.pop(0)
            if pname in kwds:
                raise ProgrammingError('%s: positional parameter %s als given '
                                       'as keyword!' % (
                                           self.__class__.__name__,
                                           pname))
            self.__dict__[pname] = pconv(pval)
        for pname, pconv in plist:
            if pname in kwds:
                pval = kwds.pop(pname)
                self.__dict__[pname] = pconv(pval)
            else:
                raise ProgrammingError('%s: param %s left unspecified!' % (
                                       self.__class__.__name__,
                                       pname))

        if kwds:
            raise ProgrammingError('%s got unknown arguments: %s' % (
                                   self.__class__.__name__,
                                   ', '.join(list(kwds.keys()))))

    def __repr__(self):
        params = ['%s=%r' % (pn, self.__dict__[pn]) for pn in self.params]
        return ('%s(%s)' % (self.__class__.__name__, ', '.join(params)))

    def __call__(self, value):
        return self.check(self.valuetype(value))


class floatrange(Validator):
    params = [('lower', float), ('upper', float)]

    def check(self, value):
        if self.lower <= value <= self.upper:
            return value
        raise ValueError('Floatrange: value %r must be within %f and %f' %
                         (value, self.lower, self.upper))


class positive(Validator):
    def check(self, value):
        if value > 0:
            return value
        raise ValueError('Value %r must be positive!' % obj)


class nonnegative(Validator):
    def check(self, value):
        if value >= 0:
            return value
        raise ValueError('Value %r must be positive!' % obj)


# more complicated validator may not be able to use validator base class
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
        raise ValueError("%r should be one of %r" %
                         (obj, list(self.mapping.keys())))

    def __repr__(self):
        params = ['%s=%r' % (mname, mval) for mname, mval in self.mapping]
        return ('%s(%s)' % (self.__class__.__name__, ', '.join(params)))
