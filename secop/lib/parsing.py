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
"""Define parsing helpers"""

import re
import time
from datetime import tzinfo, timedelta, datetime

# format_time and parse_time could be simplified with external dateutil lib
# http://stackoverflow.com/a/15228038

# based on http://stackoverflow.com/a/39418771


class LocalTimezone(tzinfo):
    ZERO = timedelta(0)
    STDOFFSET = timedelta(seconds=-time.timezone)
    if time.daylight:
        DSTOFFSET = timedelta(seconds=-time.altzone)
    else:
        DSTOFFSET = STDOFFSET

    DSTDIFF = DSTOFFSET - STDOFFSET

    def utcoffset(self, dt):
        if self._isdst(dt):
            return self.DSTOFFSET
        else:
            return self.STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return self.DSTDIFF
        else:
            return self.ZERO

    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, 0)
        stamp = time.mktime(tt)
        tt = time.localtime(stamp)
        return tt.tm_isdst > 0


LocalTimezone = LocalTimezone()


def format_time(timestamp=None):
    # get time in UTC
    if timestamp is None:
        d = datetime.now(LocalTimezone)
    else:
        d = datetime.fromtimestamp(timestamp, LocalTimezone)
    return d.isoformat("T")

# Solution based on
# https://bugs.python.org/review/15873/diff/16581/Lib/datetime.py#newcode1418Lib/datetime.py:1418


class Timezone(tzinfo):

    def __init__(self, offset, name='unknown timezone'):
        self.offset = offset
        self.name = name

    def tzname(self, dt):
        return self.name

    def utcoffset(self, dt):
        return self.offset

    def dst(self, dt):
        return timedelta(0)


datetime_re = re.compile(
    r'(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})'
    r'[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})'
    r'(?::(?P<second>\d{1,2})(?:\.(?P<microsecond>\d{1,6})\d*)?)?'
    r'(?P<tzinfo>Z|[+-]\d{2}(?::?\d{2})?)?$')


def _parse_isostring(isostring):
    """Parses a string and return a datetime.datetime.
    This function supports time zone offsets. When the input contains one,
    the output uses a timezone with a fixed offset from UTC.
    """
    match = datetime_re.match(isostring)
    if match:
        kw = match.groupdict()
        if kw['microsecond']:
            kw['microsecond'] = kw['microsecond'].ljust(6, '0')
        _tzinfo = kw.pop('tzinfo')
        if _tzinfo == 'Z':
            _tzinfo = timezone.utc
        elif _tzinfo is not None:
            offset_mins = int(_tzinfo[-2:]) if len(_tzinfo) > 3 else 0
            offset_hours = int(_tzinfo[1:3])
            offset = timedelta(hours=offset_hours, minutes=offset_mins)
            if _tzinfo[0] == '-':
                offset = -offset
            _tzinfo = Timezone(offset)
        kw = {k: int(v) for k, v in kw.items() if v is not None}
        kw['tzinfo'] = _tzinfo
        return datetime(**kw)
    raise ValueError("%s is not a valid ISO8601 string I can parse!" %
                     isostring)


def parse_time(isostring):
    try:
        return float(isostring)
    except ValueError:
        dt = _parse_isostring(isostring)
        return time.mktime(dt.timetuple()) + dt.microsecond * 1e-6

# possibly unusable stuff below!


def format_args(args):
    if isinstance(args, list):
        return ','.join(format_args(arg) for arg in args).join('[]')
    if isinstance(args, tuple):
        return ','.join(format_args(arg) for arg in args).join('()')
    if isinstance(args, (str, unicode)):
        # XXX: check for 'easy' strings only and omit the ''
        return repr(args)
    return repr(args)  # for floats/ints/...


class ArgsParser(object):
    """returns a pythonic object from the input expression

    grammar:
    expr = number | string | array_expr | record_expr
    number = int | float
    string = '"' (chars - '"')* '"' | "'" (chars - "'")* "'"
    array_expr = '[' (expr ',')* expr ']'
    record_expr = '(' (name '=' expr ',')* ')'
    int = '-' pos_int | pos_int
    pos_int = [0..9]+
    float = int '.' pos_int ( [eE] int )?
    name = [A-Za-z_] [A-Za-z0-9_]*
    """

    DIGITS_CHARS = [c for c in '0123456789']
    NAME_CHARS = [
        c for c in '_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    ]
    NAME_CHARS2 = NAME_CHARS + DIGITS_CHARS

    def __init__(self, string=''):
        self.string = string
        self.idx = 0
        self.length = len(string)

    def setstring(self, string):
        print repr(string)
        self.string = string
        self.idx = 0
        self.length = len(string)
        self.skip()

    def peek(self):
        if self.idx >= self.length:
            return None
        return self.string[self.idx]

    def get(self):
        res = self.peek()
        self.idx += 1
        print "get->", res
        return res

    def skip(self):
        """skips whitespace"""
        while self.peek() in ('\t', ' '):
            self.get()

    def match(self, what):
        if self.peek() != what:
            return False
        self.get()
        self.skip()
        return True

    def parse(self, arg=None):
        """parses given or constructed_with string"""
        self.setstring(arg or self.string)
        res = []
        while self.idx < self.length:
            res.append(self.parse_exp())
            self.match(',')
        if len(res) > 1:
            return tuple(*res)
        return res[0]

    def parse_exp(self):
        """expr = array_expr | record_expr | string | number"""
        idx = self.idx
        res = self.parse_array()
        if res:
            print "is Array"
            return res
        self.idx = idx
        res = self.parse_record()
        if res:
            print "is record"
            return res
        self.idx = idx
        res = self.parse_string()
        if res:
            print "is string"
            return res
        self.idx = idx
        return self.parse_number()

    def parse_number(self):
        """number = float | int """
        idx = self.idx
        number = self.parse_float()
        if number is not None:
            return number
        self.idx = idx  # rewind
        return self.parse_int()

    def parse_string(self):
        """string = '"' (chars - '"')* '"' | "'" (chars - "'")* "'" """
        delim = self.peek()
        if delim in ('"', "'"):
            lastchar = self.get()
            string = []
            while self.peek() != delim or lastchar == '\\':
                lastchar = self.peek()
                string.append(self.get())
            self.get()
            self.skip()
            return ''.join(string)
        return self.parse_name()

    def parse_array(self):
        """array_expr = '[' (expr ',')* expr ']' """
        if self.get() != '[':
            return None
        self.skip()
        res = []
        while self.peek() != ']':
            el = self.parse_exp()
            if el is None:
                return el
            res.append(el)
            if self.match(']'):
                return res
            if self.get() != ',':
                return None
            self.skip()
        self.get()
        self.skip()
        return res

    def parse_record(self):
        """record_expr = '(' (name '=' expr ',')* ')' """
        if self.get != '(':
            return None
        self.skip()
        res = {}
        while self.peek() != ')':
            name = self.parse_name()
            if self.get() != '=':
                return None
            self.skip()
            value = self.parse_exp()
            res[name] = value
            if self.peek() == ')':
                self.get()
                self.skip()
                return res
            if self.get() != ',':
                return None
            self.skip()
        self.get()
        self.skip()
        return res

    def parse_int(self):
        """int = '-' pos_int | pos_int"""
        if self.peek() == '-':
            self.get()
            number = self.parse_pos_int()
            if number is None:
                return number
            return -number
        return self.parse_pos_int()

    def parse_pos_int(self):
        """pos_int = [0..9]+"""
        number = 0
        if self.peek() not in self.DIGITS_CHARS:
            return None
        while (self.peek() in self.DIGITS_CHARS):
            number = number * 10 + int(self.get())
        self.skip()
        return number

    def parse_float(self):
        """float = int '.' pos_int ( [eE] int )?"""
        number = self.parse_int()
        if self.get() != '.':
            return None
        idx = self.idx
        fraction = self.parse_pos_int()
        while idx < self.idx:
            fraction /= 10.
            idx += 1
        if number >= 0:
            number = number + fraction
        else:
            number = number - fraction
        exponent = 0
        if self.peek() in ('e', 'E'):
            self.get()
            exponent = self.parse_int()
            if exponent is None:
                return exponent
        while exponent > 0:
            number *= 10.
            exponent -= 1
        while exponent < 0:
            number /= 10.
            exponent += 1
        self.skip()
        return number

    def parse_name(self):
        """name = [A-Za-z_] [A-Za-z0-9_]*"""
        name = []
        if self.peek() in self.NAME_CHARS:
            name.append(self.get())
            while self.peek() in self.NAME_CHARS2:
                name.append(self.get())
            self.skip()
            return ''.join(name)
        return None


def parse_args(s):
    # QnD Hack! try to parse lists/tuples/ints/floats, ignore dicts, specials
    # XXX: replace by proper parsing. use ast?
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        # evaluate inner
        return [parse_args(part) for part in s[1:-1].split(',')]
    if s.startswith('(') and s.endswith(')'):
        # evaluate inner
        return tuple(parse_args(part) for part in s[1:-1].split(','))
    if s.startswith('"') and s.endswith('"'):
        # evaluate inner
        return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        # evaluate inner
        return s[1:-1]
    if '.' in s:
        return float(s)
    return int(s)


__ALL__ = ['format_time', 'parse_time', 'parse_args']

if __name__ == '__main__':
    print "minimal testing: lib/parsing:"
    print "time_formatting:",
    t = time.time()
    s = format_time(t)
    assert (abs(t - parse_time(s)) < 1e-6)
    print "OK"

    print "ArgsParser:"
    a = ArgsParser()
    print a.parse('[   "\'\\\"A" , "<>\'", \'",C\', [1.23e1, 123.0e-001] , ]')

    #import pdb
    #pdb.run('print a.parse()', globals(), locals())

    print "args_formatting:",
    for obj in [1, 2.3, 'X', (1, 2, 3), [1, (3, 4), 'X,y']]:
        s = format_args(obj)
        p = a.parse(s)
        print p,
        assert (parse_args(format_args(obj)) == obj)
        print "OK"
    print "OK"
