#!/usr/bin/env python
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
"""Software calibration"""

import math
import os
from os.path import basename, dirname, exists, join

import numpy as np
from scipy.interpolate import splev, splrep  # pylint: disable=import-error

from frappy.core import Attached, BoolType, Parameter, Readable, StringType, \
    FloatRange


def linear(x):
    return x


nplog = np.vectorize(math.log10)
npexp = np.vectorize(lambda x: 10 ** x)


class StdParser:
    """parser used for reading columns"""
    def __init__(self, **kwds):
        """keys may be other 'x' or 'logx' and either 'y' or 'logy'

        default is x=0, y=1
        """
        self.xcol = int(kwds.get('x', kwds.get('logx', 0)))
        self.ycol = int(kwds.get('y', kwds.get('logy', 1)))
        self.logx = 'logx' in kwds
        self.logy = 'logy' in kwds
        self.xdata, self.ydata = [], []

    def parse(self, line):
        """get numbers from a line and put them to self.xdata / self.ydata"""
        row = line.split()
        try:
            self.xdata.append(float(row[self.xcol]))
            self.ydata.append(float(row[self.ycol]))
        except (IndexError, ValueError):
            # skip bad lines
            return


class Parser340(StdParser):
    """parser for LakeShore *.340 files"""

    def __init__(self):
        super().__init__()
        self.header = True
        self.xcol, self.ycol = 1, 2
        self.logx, self.logy = False, False

    def parse(self, line):
        """scan header for data format"""
        if self.header:
            key, _, value = line.partition(':')
            if value:  # this is a header line, as it contains ':'
                value = value.split()[0]
                key = ''.join(key.split()).lower()
                if key == 'dataformat':
                    if value == '4':
                        self.logx, self.logy = True, False  # logOhm
                    elif value == '5':
                        self.logx, self.logy = True, True  # logOhm, logK
                    elif value not in ('1', '2', '3'):
                        raise ValueError('invalid Data Format')
            elif 'No.' in line:
                self.header = False
            return
        super().parse(line)


KINDS = {
    "340": (Parser340, {}),  # lakeshore 340 format
    "inp": (StdParser, {}),  # M. Zollikers *.inp calcurve format
    "caldat": (StdParser, {'x': 1, 'y': 2}),  # format from sea/tcl/startup/calib_ext.tcl
    "dat": (StdParser, {}),  # lakeshore raw data *.dat format
}


class CalCurve:
    def __init__(self, calibspec):
        """calibspec format:
        [<full path> | <name>][,<key>=<value> ...]
        for <key>/<value> as in parser arguments
        """
        sensopt = calibspec.split(',')
        calibname = sensopt.pop(0)
        _, dot, ext = basename(calibname).rpartition('.')
        kind = None
        pathlist = os.environ.get('FRAPPY_CALIB_PATH', '').split(',')
        pathlist.append(join(dirname(__file__), 'calcurves'))
        for path in pathlist:
            # first try without adding kind
            filename = join(path.strip(), calibname)
            if exists(filename):
                kind = ext if dot else None
                break
            # then try adding all kinds as extension
            for nam in calibname, calibname.upper(), calibname.lower():
                for kind in KINDS:
                    filename = join(path.strip(), f'{nam}.{kind}')
                    if exists(filename):
                        break
                else:
                    continue
                break
            else:
                continue
            break
        else:
            raise FileNotFoundError(calibname)
        optargs = {}
        for opts in sensopt:
            key, _, value = opts.lower().rpartition('=')
            value = value.strip()
            if value:
                optargs[key.strip()] = value
        kind = optargs.pop('kind', kind)
        cls, args = KINDS.get(kind, (StdParser, {}))
        args.update(optargs)

        try:
            parser = cls(**args)
            with open(filename, encoding='utf-8') as f:
                for line in f:
                    parser.parse(line)
        except Exception as e:
            raise ValueError(f'calib curve {calibspec}: {e}') from e
        self.convert_x = nplog if parser.logx else linear
        self.convert_y = npexp if parser.logy else linear
        x = np.asarray(parser.xdata)
        y = np.asarray(parser.ydata)
        if np.all(x[:-1] > x[1:]):  # all decreasing
            x = np.flip(x)
            y = np.flip(y)
        elif np.any(x[:-1] >= x[1:]):  # some not increasing
            raise ValueError(f'calib curve {calibspec} is not monotonic')
        try:
            self.spline = splrep(x, y, s=0, k=min(3, len(x) - 1))
        except (ValueError, TypeError) as e:
            raise ValueError(f'invalid calib curve {calibspec}') from e

    def __call__(self, value):
        """convert value

        value might be a single value or an numpy array
        """
        result = splev(self.convert_x(value), self.spline)
        return self.convert_y(result)


class Sensor(Readable):
    rawsensor = Attached()

    calib = Parameter('calibration name', datatype=StringType(), readonly=False)
    abs = Parameter('True: take abs(raw) before calib', datatype=BoolType(), readonly=False, default=True)
    value = Parameter(datatype=FloatRange(unit='K'))
    pollinterval = Parameter(export=False)
    status = Parameter(default=(Readable.Status.ERROR, 'unintialized'), update_unchanged='never')

    description = 'a calibrated sensor value'
    _value_error = None

    def checkProperties(self):
        if 'description' not in self.propertyValues:
            self.description = '_'  # avoid complaining about missing description
        super().checkProperties()

    def initModule(self):
        super().initModule()
        self.rawsensor.registerCallbacks(self, ['status'])  # auto update status
        self._calib = CalCurve(self.calib)
        if self.description == '_':
            self.description = f'{self.rawsensor!r} calibrated with curve {self.calib!r}'

    def doPoll(self):
        self.read_status()

    def write_calib(self, value):
        self._calib = CalCurve(value)
        return value

    def update_value(self, value):
        if self.abs:
            value = abs(float(value))
        self.value = self._calib(value)
        self._value_error = None

    def error_update_value(self, err):
        if self.abs and str(err) == 'R_UNDER':  # hack: ignore R_UNDER from ls370
            self._value_error = None
            return None
        self._value_error = repr(err)
        raise err

    def update_status(self, value):
        if self._value_error is None:
            self.status = value
        else:
            self.status = self.Status.ERROR, self._value_error

    def read_value(self):
        return self._calib(self.rawsensor.read_value())

    def read_status(self):
        self.update_status(self.rawsensor.status)
        return self.status
