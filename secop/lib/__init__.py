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
"""Define helpers"""

import threading


class attrdict(dict):
    """a normal dict, providing access also via attributes"""

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


def clamp(_min, value, _max):
    """return the median of 3 values,

    i.e. value if min <= value <= max, else min or max depending on which side
    value lies outside the [min..max] interval
    """
    # return median, i.e. clamp the the value between min and max
    return sorted([_min, value, _max])[1]


def get_class(spec):
    """loads a class given by string in dotted notaion (as python would do)"""
    modname, classname = spec.rsplit('.', 1)
    import importlib
    module = importlib.import_module('secop.' + modname)
    #    module = __import__(spec)
    return getattr(module, classname)


def mkthread(func, *args, **kwds):
    t = threading.Thread(
        name='%s:%s' % (func.__module__, func.__name__),
        target=func,
        args=args,
        kwargs=kwds)
    t.daemon = True
    t.start()
    return t


if __name__ == '__main__':
    print "minimal testing: lib"
    d = attrdict(a=1, b=2)
    _ = d.a + d['b']
    d.c = 9
    d['d'] = 'c'
    assert d[d.d] == 9
