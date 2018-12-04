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
"""test data types."""

from __future__ import division, print_function

import sys
from collections import OrderedDict
from os import path

import pytest

sys.path.insert(0, path.abspath(path.join(path.dirname(__file__), '..')))

from secop.parse import Parser


# pylint: disable=redefined-outer-name
@pytest.fixture(scope="module")
def parser():
    return Parser()


def test_Parser_parse_number(parser):
    assert parser.parse_number('1') == (1, '')
    assert parser.parse_number('') == (None, '')
    assert parser.parse_number('a') == (None, 'a')
    assert parser.parse_number('1,2,3') == (1, ',2,3')
    assert parser.parse_number('1.23e-04:9') == (1.23e-4, ':9')


def test_Parser_parse_string(parser):
    assert parser.parse_string('%') == (None, '%')
    assert parser.parse_string('a') == ('a', '')
    assert parser.parse_string('Hello World!') == ('Hello', ' World!')
    assert parser.parse_string('Hello<World!') == ('Hello', '<World!')
    assert parser.parse_string('"Hello World!\'') == (None, '"Hello World!\'')
    assert parser.parse_string('"Hello World!\\"') == (
        None, '"Hello World!\\"')
    assert parser.parse_string('"Hello World!"X') == ("Hello World!", 'X')


def test_Parser_parse_tuple(parser):
    assert parser.parse_tuple('(1,2.3)') == ((1, 2.3), '')
    assert parser.parse_tuple('[1,a]') == ((1, 'a'), '')
    assert parser.parse_tuple('[1,a>]') == (None, '>]')
    assert parser.parse_tuple('x') == (None, 'x')
    assert parser.parse_tuple('2') == (None, '2')


def test_Parser_parse_dict(parser):
    assert (parser.parse_dict('{a:1,b=2,"X y":\'a:9=3\'}') ==
            (OrderedDict([('a', 1), ('b', 2), ('X y', 'a:9=3')]), ''))


def test_Parser_parse(parser):
    assert parser.parse('1') == (1, '')
    assert parser.parse('') == (None, '')
    assert parser.parse('a') == ('a', '')
    assert parser.parse('1,2,3') == ((1, 2, 3), '')
    assert parser.parse('1.23e-04:9') == (1.23e-4, ':9')

    assert parser.parse('%') == (None, '%')
    assert parser.parse('Hello World!') == ('Hello', ' World!')
    assert parser.parse('Hello<World!') == ('Hello', '<World!')
    assert parser.parse('"Hello World!\'') == (None, '"Hello World!\'')
    assert parser.parse('"Hello World!\\"') == (None, '"Hello World!\\"')
    assert parser.parse('"Hello World!"X') == ("Hello World!", 'X')

    assert parser.parse('(1,2.3)') == ((1, 2.3), '')
    assert parser.parse('[1,a]') == ((1, 'a'), '')
    assert parser.parse('[1,a>]') == (None, '>]')
    assert parser.parse('x') == ('x', '')
    assert parser.parse('2') == (2, '')

    assert (parser.parse('{a:1,b=2,"X y":\'a:9=3\'}') ==
            (OrderedDict([('a', 1), ('b', 2), ('X y', 'a:9=3')]), ''))

    assert parser.parse('1, 2,a,c') == ((1, 2, 'a', 'c'), '')

    assert parser.parse('"\x09 \r"') == ('\t \r', '')
