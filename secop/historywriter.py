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

import time
import frappyhistory  # pylint: disable=import-error
from secop.datatypes import get_datatype, IntRange, FloatRange, ScaledInteger,\
    EnumType, BoolType, StringType, TupleOf, StructOf


def make_cvt_list(dt, tail=''):
    """create conversion list

    list of tuple (<conversion function>, <tail>, <curve options>)
    tail is a postfix to be appended in case of tuples and structs
    """
    if isinstance(dt, (EnumType, IntRange, BoolType)):
        return[(int, tail, dict(type='NUM'))]
    if isinstance(dt, (FloatRange, ScaledInteger)):
        return [(dt.import_value, tail, dict(type='NUM', unit=dt.unit, period=5) if dt.unit else {})]
    if isinstance(dt, StringType):
        return [(lambda x: x, tail, dict(type='STR'))]
    if isinstance(dt, TupleOf):
        items = enumerate(dt.members)
    elif isinstance(dt, StructOf):
        items = dt.members.items()
    else:
        return []   # ArrayType, BlobType and TextType are ignored: too much data, probably not used
    result = []
    for subkey, elmtype in items:
        for fun,  tail_, opts in make_cvt_list(elmtype, '%s.%s' % (tail, subkey)):
            result.append((lambda v, k=subkey, f=fun: f(v[k]), tail_, opts))
    return result


class FrappyHistoryWriter(frappyhistory.FrappyWriter):
    """extend writer to be used as an internal frappy connection

    API of frappyhistory.FrappyWriter:

    :meth:`put_def`(key, opts):

       define or overwrite a new curve named <key> with options from dict <opts>
       options:

          - type:
              'NUM' (any number) or 'STR' (text)
              remark: tuples and structs create multiple curves
          - period:
              the typical 'lifetime' of a value.
              The intention is, that points in a chart may be connected by a straight line
              when the distance is lower than this value. If not, the line should be drawn
              horizontally from the last point to a point <period> before the next value.
              For example a setpoint should have period 0, which will lead to a stepped
              line, whereas for a measured value like a temperature, period should be
              slightly bigger than the poll interval. In order to make full use of this,
              we would need some additional parameter property.
          - show: True/False, whether this curve should be shown or not by default in
              a summary chart
          - label: a label for the curve in the chart

    :meth:`put`(timestamp, key, value)

        timestamp: the timestamp. must not decrease!
        key: the curve name
        value: the value to be stored, converted to a string. '' indicates an undefined value

    self.cache is a dict <key> of <value as string>, containing the last used value
    """
    def __init__(self, directory, predefined_names, dispatcher):
        super().__init__(directory)
        self.predefined_names = predefined_names
        self.cvt_lists = {}  # dict <mod:param> of <conversion list>
        self.activated = False
        self.dispatcher = dispatcher
        self._init_time = None

    def init(self, msg):
        """initialize from the 'describing' message"""
        action, _, description = msg
        assert action == 'describing'
        self._init_time = time.time()

        for modname, moddesc in description['modules'].items():
            for pname, pdesc in moddesc['accessibles'].items():
                ident = key = modname + ':' + pname
                if pname.startswith('_') and pname[1:] not in self.predefined_names:
                    key = modname + ':' + pname[1:]
                dt = get_datatype(pdesc['datainfo'])
                cvt_list = make_cvt_list(dt, key)
                for _, hkey, opts in cvt_list:
                    if pname == 'value':
                        opts['period'] = opts.get('period', 0)
                        opts['show'] = True
                        opts['label'] = modname
                    elif pname == 'target':
                        opts['period'] = 0
                        opts['label'] = modname + '_target'
                        opts['show'] = True
                    self.put_def(hkey, opts)
                self.cvt_lists[ident] = cvt_list
        # self.put(self._init_time, 'STR', 'vars', ' '.join(vars))
        self.dispatcher.handle_activate(self, None, None)
        self._init_time = None

    def send_reply(self, msg):
        action, ident, value = msg
        if not action.endswith('update'):
            print('unknown async message %r' % msg)
            return
        now = self._init_time or time.time()  # on initialisation, use the same timestamp for all
        if action == 'update':
            for fun, key, _ in self.cvt_lists[ident]:
                # we only look at the value, qualifiers are ignored for now
                # we do not use the timestamp here, as a potentially decreasing value might
                # bring the reader software into trouble
                self.put(now, key, str(fun(value[0])))

        else:  # error_update
            for _, key, _ in self.cvt_lists[ident]:
                old = self.cache.get(key)
                if old is None:
                    return  # ignore if this key is not yet used
                self.put(now, key, '')
