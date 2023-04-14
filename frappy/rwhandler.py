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
#   Markus Zolliker <markus.zolliker@psi.ch>
# *****************************************************************************

"""decorator class for common read_<param>/write_<param> methods

Usage:

Example 1: combined read/write for multiple parameters

.. code:

    PID_PARAMS = ['p', 'i', 'd']

    @CommonReadHandler(PID_PARAMS)
    def read_pid(self):
        self.p, self.i, self.d = self.get_pid_from_hw()
        # no return value

    @CommonWriteHandler(PID_PARAMS)
    def write_pid(self, values):
        # values is a dict[pname] of value, we convert it to a tuple here
        self.put_pid_to_hw(values.as_tuple('p', 'i', 'd''))   # or .as_tuple(*PID_PARAMS)
        self.read_pid()
        # no return value

Example 2: addressable HW parameters

.. code:

    HW_ADDR = {'p': 25, 'i': 26, 'd': 27}

    @ReadHandler(HW_ADDR)
    def read_addressed(self, pname):
        return self.get_hw_register(HW_ADDR[pname])

    @WriteHandler(HW_ADDR)
    def write_addressed(self, pname, value):
        self.put_hw_register(HW_ADDR[pname], value)
        return self.get_hw_register(HW_ADDR[pname])
"""

import functools
from frappy.errors import ProgrammingError


def wraps(func):
    """decorator to copy function attributes of wrapped function"""
    # we modify the default here:
    # copy __doc__ , __module___ and attributes from __dict__
    # but not __name__ and __qualname__
    return functools.wraps(func, assigned=('__doc__', '__module__'))


class Handler:
    func = None
    prefix = None  # 'read_' or 'write_'
    method_names = set()  # global set registering used method names
    poll = None

    def __init__(self, keys):
        """initialize the decorator

        :param keys: parameter names (an iterable)
        """
        self.keys = set(keys)

    def __call__(self, func):
        """decorator call"""
        if (func.__module__, func.__qualname__) in self.method_names:
            # make sure method name is not used twice
            # (else __set_name__ will not be called)
            raise ProgrammingError(f'duplicate method {func.__qualname__!r}')
        self.func = func
        func.wrapped = False
        self.method_names.add((func.__module__, func.__qualname__))
        return self

    def __get__(self, obj, owner=None):
        """allow access to the common method"""
        if obj is None:
            return self
        return self.func.__get__(obj, owner)

    def __set_name__(self, owner, name):
        """create the wrapped read_* or write_* methods"""
        # at this point, this 'method_names' entry is no longer used -> delete
        self.method_names.discard((self.func.__module__, self.func.__qualname__))
        owner.checkedMethods.add(name)
        for key in self.keys:
            wrapped = self.wrap(key)
            method_name = self.prefix + key
            wrapped.wrapped = True
            if self.poll is not None:
                # wrapped.poll is False when the nopoll decorator is applied either to self.func or to self
                wrapped.poll = getattr(wrapped, 'poll', self.poll)
            func = getattr(owner, method_name, None)
            if func and method_name in owner.__dict__:
                raise ProgrammingError(f'superfluous method {owner.__name__}.' \
                                       f'{method_name} (overwritten by {self.__class__.__name__})')
            setattr(owner, method_name, wrapped)

    def wrap(self, key):
        """create wrapped method from self.func

        with name self.prefix + key"""
        raise NotImplementedError


class ReadHandler(Handler):
    """decorator for read handler methods"""
    prefix = 'read_'
    poll = True

    def wrap(self, key):
        def method(module, pname=key, func=self.func):
            with module.accessLock:
                value = func(module, pname)
                setattr(module, pname, value)
                return value

        return wraps(self.func)(method)


class CommonReadHandler(ReadHandler):
    """decorator for a handler reading several parameters in one go"""
    def __init__(self, keys):
        """initialize the decorator

        :param keys: parameter names (an iterable)
        """
        super().__init__(keys)
        self.first_key = next(iter(keys))

    def wrap(self, key):
        def method(module, pname=key, func=self.func):
            with module.accessLock:
                ret = func(module)
                if ret is not None:
                    raise ProgrammingError('a method wrapped with CommonReadHandler must not return any value')
                return getattr(module, pname)

        method = wraps(self.func)(method)
        method.poll = self.poll and getattr(method, 'poll', True) if key == self.first_key else False
        return method


class WriteHandler(Handler):
    """decorator for write handler methods"""
    prefix = 'write_'

    def wrap(self, key):
        @wraps(self.func)
        def method(module, value, pname=key, func=self.func):
            with module.accessLock:
                value = func(module, pname, value)
                setattr(module, pname, value)
                return value
        return method


class WriteParameters(dict):
    def __init__(self, modobj):
        super().__init__()
        self.obj = modobj

    def __missing__(self, key):
        try:
            return self.obj.writeDict.pop(key)
        except KeyError:
            return getattr(self.obj, key)

    def as_tuple(self, *keys):
        """return values of given keys as a tuple"""
        return tuple(self[k] for k in keys)


class CommonWriteHandler(WriteHandler):
    """decorator for common write handler

    calls the wrapped write method function with values as an argument.

    - values[pname] returns the to be written value

    - values['key'] returns a value taken from writeDict
      or, if not available return obj.key

    - values.as_tuple() returns a tuple with the items in the same order as keys

    """

    def wrap(self, key):
        @wraps(self.func)
        def method(module, value, pname=key, func=self.func):
            with module.accessLock:
                values = WriteParameters(module)
                values[pname] = value
                ret = func(module, values)
                if ret is not None:
                    raise ProgrammingError('a method wrapped with CommonWriteHandler must not return any value')
                # remove pname from writeDict. this was not removed in WriteParameters, as it was not missing
                module.writeDict.pop(pname, None)
        return method


def nopoll(func):
    """decorator to indicate that a read method is not to be polled"""
    func.poll = False
    return func
