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


import sys
import linecache
import traceback

def formatExtendedFrame(frame):
    ret = []
    for key, value in frame.f_locals.iteritems():
        try:
            valstr = repr(value)[:256]
        except Exception:
            valstr = '<cannot be displayed>'
        ret.append('        %-20s = %s\n' % (key, valstr))
    ret.append('\n')
    return ret

def formatExtendedTraceback(etype, value, tb):
    ret = ['Traceback (most recent call last):\n']
    while tb is not None:
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        item = '  File "%s", line %d, in %s\n' % (filename, tb.tb_lineno,
                                                  frame.f_code.co_name)
        linecache.checkcache(filename)
        line = linecache.getline(filename, tb.tb_lineno, frame.f_globals)
        if line:
            item = item + '    %s\n' % line.strip()
        ret.append(item)
        if filename not in ('<script>', '<string>'):
            ret += formatExtendedFrame(tb.tb_frame)
        tb = tb.tb_next
    ret += traceback.format_exception_only(etype, value)
    return ''.join(ret).rstrip('\n')

def formatExtendedStack(level=1):
    f = sys._getframe(level)
    ret = ['Stack trace (most recent call last):\n\n']
    while f is not None:
        lineno = f.f_lineno
        co = f.f_code
        filename = co.co_filename
        name = co.co_name
        item = '  File "%s", line %d, in %s\n' % (filename, lineno, name)
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        if line:
            item = item + '    %s\n' % line.strip()
        ret.insert(1, item)
        if filename != '<script>':
            ret[2:2] = formatExtendedFrame(f)
        f = f.f_back
    return ''.join(ret).rstrip('\n')

def formatException(cut=0, exc_info=None):
    """Format an exception with traceback, but leave out the first `cut`
    number of frames.
    """
    if exc_info is None:
        typ, val, tb = sys.exc_info()
    else:
        typ, val, tb = exc_info
    res = ['Traceback (most recent call last):\n']
    tbres = traceback.format_tb(tb, sys.maxsize)
    res += tbres[cut:]
    res += traceback.format_exception_only(typ, val)
    return ''.join(res)


if __name__ == '__main__':
    print "minimal testing: lib"
    d = attrdict(a=1, b=2)
    _ = d.a + d['b']
    d.c = 9
    d['d'] = 'c'
    assert d[d.d] == 9
