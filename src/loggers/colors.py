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
#   Alexander Lenz <alexander.lenz@posteo.de>
#   Georg Brandl <georg@python.org>
#
# *****************************************************************************

"""Console coloring handlers."""


_codes = {}

_attrs = {
    'reset':     '39;49;00m',
    'bold':      '01m',
    'faint':     '02m',
    'standout':  '03m',
    'underline': '04m',
    'blink':     '05m',
}

for _name, _value in _attrs.items():
    _codes[_name] = '\x1b[' + _value

_colors = [
    ('black', 'darkgray'),
    ('darkred', 'red'),
    ('darkgreen', 'green'),
    ('brown', 'yellow'),
    ('darkblue', 'blue'),
    ('purple', 'fuchsia'),
    ('turquoise', 'teal'),
    ('lightgray', 'white'),
]

for _i, (_dark, _light) in enumerate(_colors):
    _codes[_dark] = '\x1b[%im' % (_i + 30)
    _codes[_light] = '\x1b[%i;01m' % (_i + 30)


def colorize(name, text):
    return _codes.get(name, '') + text + _codes.get('reset', '')


def colorcode(name):
    return _codes.get(name, '')


def nocolor():
    for key in list(_codes):
        _codes[key] = ''
