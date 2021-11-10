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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""test data types."""

import threading

import pytest

from secop.datatypes import BoolType, FloatRange, StringType, IntRange
from secop.errors import ProgrammingError, ConfigError
from secop.modules import Communicator, Drivable, Readable, Module
from secop.params import Command, Parameter
from secop.poller import BasicPoller


class DispatcherStub:
    # the first update from the poller comes a very short time after the
    # initial value from the timestamp. However, in the test below
    # the second update happens after the updates dict is cleared
    # -> we have to inhibit the 'omit unchanged update' feature
    omit_unchanged_within = 0

    def __init__(self, updates):
        self.updates = updates

    def announce_update(self, modulename, pname, pobj):
        self.updates.setdefault(modulename, {})
        if pobj.readerror:
            self.updates[modulename]['error', pname] = str(pobj.readerror)
        else:
            self.updates[modulename][pname] = pobj.value


class LoggerStub:
    def debug(self, *args):
        print(*args)
    info = warning = exception = debug


logger = LoggerStub()


class ServerStub:
    def __init__(self, updates):
        self.dispatcher = DispatcherStub(updates)


def test_Communicator():
    o = Communicator('communicator', LoggerStub(), {'.description':''}, ServerStub({}))
    o.earlyInit()
    o.initModule()
    event = threading.Event()
    o.startModule(event.set)
    assert event.is_set() # event should be set immediately


def test_ModuleMagic():
    class Newclass1(Drivable):
        param1 = Parameter('param1', datatype=BoolType(), default=False)
        param2 = Parameter('param2', datatype=FloatRange(unit='Ohm'), default=True)

        @Command(argument=BoolType(), result=BoolType())
        def cmd(self, arg):
            """stuff"""
            return not arg

        a1 = Parameter('a1', datatype=BoolType(), default=False)
        a2 = Parameter('a2', datatype=BoolType(), default=True)
        value = Parameter(datatype=StringType(), default='first')

        @Command(argument=BoolType(), result=BoolType())
        def cmd2(self, arg):
            """another stuff"""
            return not arg

        pollerClass = BasicPoller

        def read_param1(self):
            return True

        def read_param2(self):
            return False

        def read_a1(self):
            return True

        def read_a2(self):
            return True

        def read_value(self):
            return 'second'

    with pytest.raises(ProgrammingError):
        class Mod1(Module):  # pylint: disable=unused-variable
            def do_this(self):  # old style command
                pass

    with pytest.raises(ProgrammingError):
        class Mod2(Module):  # pylint: disable=unused-variable
            param = Parameter(),  # pylint: disable=trailing-comma-tuple


    # first inherited accessibles
    sortcheck1 = ['value', 'status', 'pollinterval', 'target', 'stop',
                 'param1', 'param2', 'cmd', 'a1', 'a2', 'cmd2']

    class Newclass2(Newclass1):
        paramOrder = 'param1', 'param2', 'cmd', 'value'

        @Command(description='another stuff')
        def cmd2(self, arg):
            return arg

        value = Parameter(datatype=FloatRange(unit='deg'))
        a1 = Parameter(datatype=FloatRange(unit='$/s'), readonly=False)
        b2 = Parameter('<b2>', datatype=BoolType(), default=True,
                       poll=True, readonly=False, initwrite=True)

        def write_a1(self, value):
            self._a1_written = value
            return value

        def write_b2(self, value):
            self._b2_written = value
            return value

        def read_value(self):
            return 0

    # first inherited items not mentioned, then the ones mentioned in paramOrder, then the other new ones
    sortcheck2 = ['status', 'pollinterval', 'target', 'stop',
                  'a1', 'a2', 'cmd2', 'param1', 'param2', 'cmd', 'value', 'b2']

    updates = {}
    srv = ServerStub(updates)

    params_found = set()  # set of instance accessibles
    objects = []

    for newclass, sortcheck in [(Newclass1, sortcheck1), (Newclass2, sortcheck2)]:
        o1 = newclass('o1', logger, {'.description':''}, srv)
        o2 = newclass('o2', logger, {'.description':''}, srv)
        for obj in [o1, o2]:
            objects.append(obj)
            for o in obj.accessibles.values():
                # check that instance accessibles are unique objects
                assert o not in params_found
                params_found.add(o)
            assert list(obj.accessibles) == sortcheck

    # check for inital updates working properly
    o1 = Newclass1('o1', logger, {'.description':''}, srv)
    expectedBeforeStart = {'target': 0.0, 'status': (Drivable.Status.IDLE, ''),
            'param1': False, 'param2': 1.0, 'a1': 0.0, 'a2': True, 'pollinterval': 5.0,
            'value': 'first'}
    assert updates.pop('o1') == expectedBeforeStart
    o1.earlyInit()
    event = threading.Event()
    o1.startModule(event.set)
    event.wait()
    # should contain polled values
    expectedAfterStart = {'status': (Drivable.Status.IDLE, ''),
            'value': 'second'}
    assert updates.pop('o1') == expectedAfterStart

    # check in addition if parameters are written
    o2 = Newclass2('o2', logger, {'.description':'', 'a1': 2.7}, srv)
    # no update for b2, as this has to be written
    expectedBeforeStart['a1'] = 2.7
    assert updates.pop('o2') == expectedBeforeStart
    o2.earlyInit()
    event = threading.Event()
    o2.startModule(event.set)
    event.wait()
    # value has changed type, b2 and a1 are written
    expectedAfterStart.update(value=0, b2=True, a1=2.7)
    assert updates.pop('o2') == expectedAfterStart
    assert o2._a1_written == 2.7
    assert o2._b2_written is True

    assert not updates

    o1 = Newclass1('o1', logger, {'.description':''}, srv)
    o2 = Newclass2('o2', logger, {'.description':''}, srv)
    assert o2.parameters['a1'].datatype.unit == 'deg/s'
    o2 = Newclass2('o2', logger, {'.description':'', 'value.unit':'mm', 'param2.unit':'mm'}, srv)
    # check datatype is not shared
    assert o1.parameters['param2'].datatype.unit == 'Ohm'
    assert o2.parameters['param2'].datatype.unit == 'mm'
    # check '$' in unit works properly
    assert o2.parameters['a1'].datatype.unit == 'mm/s'
    cfg = Newclass2.configurables
    assert set(cfg.keys()) == {'export', 'group', 'description',
        'meaning', 'visibility', 'implementation', 'interface_classes', 'target', 'stop',
        'status', 'param1', 'param2', 'cmd', 'a2', 'pollinterval', 'b2', 'cmd2', 'value',
        'a1'}
    assert set(cfg['value'].keys()) == {'group', 'export', 'relative_resolution',
        'visibility', 'unit', 'default', 'datatype', 'fmtstr',
        'absolute_resolution', 'poll', 'max', 'min', 'readonly', 'constant',
        'description', 'needscfg'}

    # check on the level of classes
    # this checks Newclass1 too, as it is inherited by Newclass2
    for baseclass in Newclass2.__mro__:
        # every cmd/param has to be collected to accessibles
        acs = getattr(baseclass, 'accessibles', None)
        if issubclass(baseclass, Module):
            assert acs is not None
        else: # do not check object or mixin
            acs = {}
        for o in acs.values():
            # check that class accessibles are not reused as instance accessibles
            assert o not in params_found

    for o in objects:
        o.earlyInit()
    for o in objects:
        o.initModule()


def test_param_inheritance():
    srv = ServerStub({})

    class Base(Module):
        param = Parameter()

    class MissingDatatype(Base):
        param = Parameter('param')

    class MissingDescription(Base):
        param = Parameter(datatype=FloatRange(), default=0)

    # missing datatype and/or description of a parameter has to be detected
    # at instantation and only then
    with pytest.raises(ConfigError) as e_info:
        MissingDatatype('o', logger, {'description': ''}, srv)
    assert 'datatype' in repr(e_info.value)

    with pytest.raises(ConfigError) as e_info:
        MissingDescription('o', logger, {'description': ''}, srv)
    assert 'description' in repr(e_info.value)

    with pytest.raises(ConfigError) as e_info:
        Base('o', logger, {'description': ''}, srv)


def test_mixin():
    # srv = ServerStub({})

    class Mixin:  # no need to inherit from Module or HasAccessible
        value = Parameter(unit='K')  # missing datatype and description acceptable in mixins
        param1 = Parameter('no datatype yet', fmtstr='%.5f')
        param2 = Parameter('no datatype yet', default=1)

    class MixedReadable(Mixin, Readable):
        pass

    class MixedDrivable(MixedReadable, Drivable):
        value = Parameter(unit='Ohm', fmtstr='%.3f')
        param1 = Parameter(datatype=FloatRange())

    with pytest.raises(ProgrammingError):
        class MixedModule(Mixin):  # pylint: disable=unused-variable
            param1 = Parameter('', FloatRange(), fmtstr=0)  # fmtstr must be a string

    assert repr(MixedDrivable.status.datatype) == repr(Drivable.status.datatype)
    assert repr(MixedReadable.status.datatype) == repr(Readable.status.datatype)
    assert MixedReadable.value.datatype.unit == 'K'
    assert MixedDrivable.value.datatype.unit == 'Ohm'
    assert MixedDrivable.value.datatype.fmtstr == '%.3f'
    # when datatype is overridden, fmtstr falls back to default:
    assert MixedDrivable.param1.datatype.fmtstr == '%g'

    srv = ServerStub({})

    MixedDrivable('o', logger, {
        'description': '',
        'param1.description': 'param 1',
        'param1': 0,
        'param2.datatype': {"type": "double"},
    }, srv)

    with pytest.raises(ConfigError):
        MixedReadable('o', logger, {
            'description': '',
            'param1.description': 'param 1',
            'param1': 0,
            'param2.datatype': {"type": "double"},
        }, srv)


def test_override():
    class Mod(Drivable):
        value = 5  # overriding the default value

        def stop(self):
            """no decorator needed"""

    assert Mod.value.default == 5
    assert Mod.stop.description == "no decorator needed"


def test_command_config():
    class Mod(Module):
        @Command(IntRange(0, 1), result=IntRange(0, 1))
        def convert(self, value):
            return value

    srv = ServerStub({})
    mod = Mod('o', logger, {
        'description': '',
        'convert.argument': {'type': 'bool'},
    }, srv)
    assert mod.commands['convert'].datatype.export_datatype() == {
        'type': 'command',
        'argument': {'type': 'bool'},
        'result': {'type': 'int', 'min': 0, 'max': 1},
    }

    mod = Mod('o', logger, {
        'description': '',
        'convert.datatype': {'type': 'command', 'argument': {'type': 'bool'}, 'result': {'type': 'bool'}},
    }, srv)
    assert mod.commands['convert'].datatype.export_datatype() == {
        'type': 'command',
        'argument': {'type': 'bool'},
        'result': {'type': 'bool'},
    }


def test_command_none():
    srv = ServerStub({})

    class Mod(Drivable):
        pass

    class Mod2(Drivable):
        stop = None

    assert 'stop' in Mod('o', logger, {'description': ''}, srv).accessibles
    assert 'stop' not in Mod2('o', logger, {'description': ''}, srv).accessibles
