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

"""decorator class for common read_/write_ methods

Usage:

Example 1: combined read/write for multiple parameters

    PID_PARAMS = ['p', 'i', 'd']

    @ReadHandler(PID_PARAMS)
    def read_pid(self, pname):
        self.p, self.i, self.d = self.get_pid_from_hw()
        return Done  # Done is indicating that the parameters are already assigned

    @WriteHandler(PID_PARAMS)
    def write_pid(self, pname, value):
        pid = self.get_pid_from_hw()  # assume this returns a list
        pid[PID_PARAMS.index(pname)] = value
        self.put_pid_to_hw(pid)
        return self.read_pid()

Example 2: addressable HW parameters

    HW_ADDR = {'p': 25, 'i': 26, 'd': 27}

    @ReadHandler(HW_ADDR)
    def read_addressed(self, pname):
        return self.get_hw_register(HW_ADDR[pname])

    @WriteHandler(HW_ADDR)
    def write_addressed(self, pname, value):
        self.put_hw_register(HW_ADDR[pname], value)
        return self.get_hw_register(HW_ADDR[pname])
"""

from functools import wraps
from secop.modules import Done
from secop.errors import ProgrammingError


class Handler:
    func = None
    method_names = set()  # this is shared among all instances of handlers!
    wrapped = True  # allow to use read_* or write_* as name of the decorated method

    def __init__(self, keys):
        """initialize the decorator

        :param keys: parameter names (an iterable)
        """
        self.keys = set(keys)

    def __call__(self, func):
        """decorator call"""
        self.func = func
        if func.__qualname__ in self.method_names:
            raise ProgrammingError('duplicate method %r' % func.__qualname__)
        func.wrapped = False
        # __qualname__ used here (avoid conflicts between different modules)
        self.method_names.add(func.__qualname__)
        return self

    def __get__(self, obj, owner=None):
        """allow access to the common method"""
        if obj is None:
            return self
        return self.func.__get__(obj, owner)


class ReadHandler(Handler):
    """decorator for read methods"""

    def __set_name__(self, owner, name):
        """create the wrapped read_* methods"""

        self.method_names.discard(self.func.__qualname__)
        for key in self.keys:

            @wraps(self.func)
            def wrapped(module, pname=key, func=self.func):
                value = func(module, pname)
                if value is not Done:
                    setattr(module, pname, value)
                return value

            wrapped.wrapped = True
            method = 'read_' + key
            if hasattr(owner, method):
                raise ProgrammingError('superfluous method %s.%s (overwritten by ReadHandler)'
                                       % (owner.__name__, method))
            setattr(owner, method, wrapped)


class WriteHandler(Handler):
    """decorator for write methods"""

    def __set_name__(self, owner, name):
        """create the wrapped write_* methods"""

        self.method_names.discard(self.func.__qualname__)
        for key in self.keys:

            @wraps(self.func)
            def wrapped(module, value, pname=key, func=self.func):
                value = func(module, pname, value)
                if value is not Done:
                    setattr(module, pname, value)
                return value

            wrapped.wrapped = True
            method = 'write_' + key
            if hasattr(owner, method):
                raise ProgrammingError('superfluous method %s.%s (overwritten by WriteHandler)'
                                       % (owner.__name__, method))
            setattr(owner, method, wrapped)
