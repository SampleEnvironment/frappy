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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************


import time
import pytest
from frappy.io import StringIO


class Time:
    def __init__(self, items):
        self.items = items

    def sleep(self, seconds):
        self.items.append(seconds)


class IO(StringIO):
    def __init__(self):
        self.items = []
        self.propertyValues = {}
        self.earlyInit()

    def communicate(self, command, noreply=False):
        self.items.append(command)
        return command.upper()


class AppendedIO(IO):
    def communicate(self, command, noreply=False):
        self.items.append(command)
        if noreply:
            assert not '?' in command
            return None
        assert '?' in command
        return '1'

    def writeline(self, command):
        assert self.communicate(command + ';*OPC?') == '1'


class CompositeIO(AppendedIO):
    def writeline(self, command):
        # the following is not possible, as multicomm is recursively calling writeline:
        #   self.multicomm([(command, False, 0), ('*OPC?', True, 0)])
        # anyway, above code is less nice
        with self._lock:
            self.communicate(command, noreply=True)
            self.communicate('*OPC?')


def test_writeline_pure():
    io = IO()
    assert io.writeline('noreply') is None
    assert io.items == ['noreply']


@pytest.mark.parametrize(
    'ioclass, cmds', [
        (AppendedIO, ['SETP 1,1;*OPC?']),
        (CompositeIO, ['SETP 1,1', '*OPC?']),
    ])
def test_writeline_extended(ioclass, cmds):
    io = ioclass()
    io.writeline('SETP 1,1')
    assert io.items == cmds


def test_multicomm_simple():
    io = IO()
    assert io.multicomm(['first', 'second']) == ['FIRST', 'SECOND']
    assert io.items == ['first', 'second']


def test_multicomm_with_delay(monkeypatch):
    io = IO()
    tm = Time(io.items)
    monkeypatch.setattr(time, 'sleep', tm.sleep)
    assert io.multicomm([('noreply', False, 1), ('reply', True, 2)]) == ['REPLY']
    assert io.items == ['noreply', 1, 'reply', 2]
