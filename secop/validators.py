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

# if a validator does a mapping, it normally maps to the external representation (used for print/log/protocol/...)
# to get the internal representation (for the code), call method convert

from errors import ProgrammingError


class Validator(object):
    # list of tuples: (name, converter)
    params = []
    valuetype = float
    argstr = ''

    def __init__(self, *args, **kwds):
        plist = self.params[:]
        if len(args) > len(plist):
            raise ProgrammingError('%s takes %d parameters only (%d given)' % (
                                   self.__class__.__name__,
                                   len(plist), len(args)))
        for pval in args:
            pname, pconv = plist.pop(0)
            if pname in kwds:
                raise ProgrammingError('%s: positional parameter %s is given '
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
        params = []
        for pn, pt in self.params:
            pv = getattr(self, pn)
            if callable(pv):
                params.append('%s=%s' % (pn, validator_to_str(pv)))
            else:
                params.append('%s=%r' % (pn, pv))
        self.argstr = ', '.join(params)

    def __call__(self, value):
        return self.check(self.valuetype(value))

    def __repr__(self):
        return self.to_string()

    def to_string(self):
        return ('%s(%s)' % (self.__class__.__name__, self.argstr))


class floatrange(Validator):
    params = [('lower', float), ('upper', float)]

    def check(self, value):
        if self.lower <= value <= self.upper:
            return value
        raise ValueError('Floatrange: value %r must be within %f and %f' %
                         (value, self.lower, self.upper))


class intrange(Validator):
    params = [('lower', int), ('upper', int)]
    valuetype = int

    def check(self, value):
        if self.lower <= value <= self.upper:
            return value
        raise ValueError('Intrange: value %r must be within %f and %f' %
                         (value, self.lower, self.upper))


class array(Validator):
    """integral amount of data-elements which are described by the SAME validator

    The size of the array can also be described by an validator
    """
    valuetype = list
    params = [('size', lambda x: x),
              ('datatype', lambda x: x)]

    def check(self, values):
        requested_size = len(values)
        if callable(self.size):
            try:
                allowed_size = self.size(requested_size)
            except ValueError as e:
                raise ValueError(
                    'illegal number of elements %d, need %r: (%s)' %
                    (requested_size, self.size, e))
        else:
            allowed_size = self.size
        if requested_size != allowed_size:
            raise ValueError(
                'need %d elements (got %d)' %
                (allowed_size, requested_size))
        # apply data-type validator to all elements and return
        res = []
        for idx, el in enumerate(values):
            try:
                res.append(self.datatype(el))
            except ValueError as e:
                raise ValueError(
                    'Array Element %s (=%r) not conforming to %r: (%s)' %
                    (idx, el, self.datatype, e))
        return res


# more complicated validator may not be able to use validator base class
class vector(Validator):
    """fixed length, eache element has its own validator"""
    valuetype = tuple

    def __init__(self, *args):
        self.validators = args
        self.argstr = ', '.join([validator_to_str(e) for e in args])

    def __call__(self, args):
        if len(args) != len(self.validators):
            raise ValueError('Vector: need exactly %d elementes (got %d)' %
                             len(self.validators), len(args))
        return tuple(v(e) for v, e in zip(self.validators, args))


# XXX: fixme!
class record(Validator):
    """fixed length, eache element has its own name and validator"""

    def __init__(self, **kwds):
        self.validators = kwds
        self.argstr = ', '.join(
            ['%s=%s' % (e[0], validator_to_str(e[1])) for e in kwds.items()])

    def __call__(self, **args):
        if len(args) != len(self.validators):
            raise ValueError('Vector: need exactly %d elementes (got %d)' %
                             len(self.validators), len(args))
        return tuple(v(e) for v, e in zip(self.validators, args))


class oneof(Validator):
    """needs to comply with one of the given validators/values"""

    def __init__(self, *args):
        self.oneof = args
        self.argstr = ', '.join(
            [validator_to_str(e) if callable(e) else repr(e) for e in args])

    def __call__(self, arg):
        for v in self.oneof:
            if callable(v):
                try:
                    if (v == int) and (float(arg) != int(arg)):
                        continue
                    return v(arg)
                except ValueError:
                    pass  # try next validator
            elif v == arg:
                return v
        raise ValueError('Oneof: %r should be one of: %s' % (arg, self.argstr))


class enum(Validator):

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
        params = []
        for k, v in sorted(self.mapping.items(), key=lambda x: x[1]):
            self.revmapping[v] = k
            params.append('%s=%r' % (k, v))
        self.argstr = ', '.join(params)

    def __call__(self, obj):
        try:
            obj = int(obj)
        except ValueError:
            pass
        if obj in self.mapping:
            return obj
        if obj in self.revmapping:
            return self.revmapping[obj]
        raise ValueError("%r should be one of %s" %
                         (obj, ', '.join(map(repr, self.mapping.keys()))))

    def convert(self, arg):
        return self.mapping.get(arg, arg)


# Validators without parameters:
def positive(value=Ellipsis):
    if value != Ellipsis:
        if value > 0:
            return value
        raise ValueError('Value %r must be > 0!' % value)
    return -1e-38  # small number > 0
positive.__repr__ = lambda x: validator_to_str(x)


def nonnegative(value=Ellipsis):
    if value != Ellipsis:
        if value >= 0:
            return value
        raise ValueError('Value %r must be >= 0!' % value)
    return 0.0
nonnegative.__repr__ = lambda x: validator_to_str(x)


# helpers

def validator_to_str(validator):
    if isinstance(validator, Validator):
        return validator.to_string()
    if hasattr(validator, 'func_name'):
        return getattr(validator, 'func_name')
    for s in 'int str float'.split(' '):
        t = eval(s)
        if validator == t or isinstance(validator, t):
            return s
    print "##########", type(validator), repr(validator)


# XXX: better use a mapping here!
def validator_from_str(validator_str):
    return eval(validator_str)

if __name__ == '__main__':
    print "minimal testing: validators"
    for val, good, bad in [(floatrange(3.09, 5.47), 4.13, 9.27),
                           (intrange(3, 5), 4, 8),
                           (array(size=3, datatype=int), (1, 2, 3), (1, 2, 3, 4)),
                           (vector(int, int), (12, 6), (1.23, 'X')),
                           (oneof('a', 'b', 'c', 1), 'b', 'x'),
                           #(record(a=int, b=float), dict(a=2,b=3.97), dict(c=9,d='X')),
                           (positive, 2, 0),
                           (nonnegative, 0, -1),
                           (enum(a=1, b=20), 1, 12),
                           ]:
        print validator_to_str(val), repr(validator_from_str(validator_to_str(val)))
        print val(good), 'OK'
        try:
            val(bad)
            print "FAIL"
            raise ProgrammingError
        except Exception as e:
            print bad, e, 'OK'
        print
