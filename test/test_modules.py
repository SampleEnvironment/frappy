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

import sys
import threading
import pytest

from frappy.datatypes import BoolType, FloatRange, StringType, IntRange, ScaledInteger
from frappy.errors import ProgrammingError, ConfigError
from frappy.modules import Communicator, Drivable, Readable, Module
from frappy.params import Command, Parameter
from frappy.rwhandler import ReadHandler, WriteHandler, nopoll


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
    def debug(self, fmt, *args):
        print(fmt % args)
    info = warning = exception = error = debug
    handlers = []


logger = LoggerStub()


class ServerStub:
    def __init__(self, updates):
        self.dispatcher = DispatcherStub(updates)


class DummyMultiEvent(threading.Event):
    def get_trigger(self):

        def trigger(event=self):
            event.set()
            sys.exit()
        return trigger


def test_Communicator():
    o = Communicator('communicator', LoggerStub(), {'description': ''}, ServerStub({}))
    o.earlyInit()
    o.initModule()
    event = DummyMultiEvent()
    o.initModule()
    o.startModule(event)
    assert event.wait(timeout=0.1)


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
        target = Parameter(datatype=StringType(), default='')

        @Command(argument=BoolType(), result=BoolType())
        def cmd2(self, arg):
            """another stuff"""
            return not arg

        def read_param1(self):
            return True

        def read_param2(self):
            return False

        def read_a1(self):
            return True

        @nopoll
        def read_a2(self):
            return True

        def read_value(self):
            return 'second'

        def read_status(self):
            return 'IDLE', 'ok'

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
        target = Parameter(datatype=FloatRange(), default=0)
        a1 = Parameter(datatype=FloatRange(unit='$/s'), readonly=False)
        # remark: it might be a programming error to override the datatype
        # and not overriding the read_* method. This is not checked!
        b2 = Parameter('<b2>', datatype=StringType(), value='empty',
                       readonly=False)

        def write_a1(self, value):
            self._a1_written = value
            return value

        def write_b2(self, value):
            value = value.upper()
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
        o1 = newclass('o1', logger, {'description':''}, srv)
        o2 = newclass('o2', logger, {'description':''}, srv)
        for obj in [o1, o2]:
            objects.append(obj)
            for o in obj.accessibles.values():
                # check that instance accessibles are unique objects
                assert o not in params_found
                params_found.add(o)
            assert list(obj.accessibles) == sortcheck

    updates.clear()
    # check for inital updates working properly
    o1 = Newclass1('o1', logger, {'description':''}, srv)
    expectedBeforeStart = {'target': '', 'status': (Drivable.Status.IDLE, ''),
            'param1': False, 'param2': 1.0, 'a1': False, 'a2': True, 'pollinterval': 5.0,
            'value': 'first'}
    for k, v in expectedBeforeStart.items():
        assert getattr(o1, k) == v
    o1.earlyInit()
    event = DummyMultiEvent()
    o1.initModule()
    o1.startModule(event)
    assert event.wait(timeout=0.1)
    # should contain polled values
    expectedAfterStart = {
        'status': (Drivable.Status.IDLE, 'ok'), 'value': 'second',
        'param1': True, 'param2': 0.0, 'a1': True}
    assert updates.pop('o1') == expectedAfterStart

    # check in addition if parameters are written
    assert not updates
    o2 = Newclass2('o2', logger, {'description':'', 'a1': {'value': 2.7}}, srv)
    expectedBeforeStart.update(a1=2.7, b2='empty', target=0, value=0)
    for k, v in expectedBeforeStart.items():
        assert getattr(o2, k) == v
    o2.earlyInit()
    event = DummyMultiEvent()
    o2.initModule()
    o2.startModule(event)
    assert event.wait(timeout=0.1)
    # value has changed type, b2 and a1 are written
    expectedAfterStart.update(value=0, b2='EMPTY', a1=True)
    # ramerk: a1=True: this behaviour is a Porgamming error
    assert updates.pop('o2') == expectedAfterStart
    assert o2._a1_written == 2.7
    assert o2._b2_written == 'EMPTY'

    assert not updates

    o1 = Newclass1('o1', logger, {'description':''}, srv)
    o2 = Newclass2('o2', logger, {'description':''}, srv)
    assert o2.parameters['a1'].datatype.unit == 'deg/s'
    o2 = Newclass2('o2', logger, {'description':'', 'value':{'unit':'mm'},'param2':{'unit':'mm'}}, srv)
    # check datatype is not shared
    assert o1.parameters['param2'].datatype.unit == 'Ohm'
    assert o2.parameters['param2'].datatype.unit == 'mm'
    # check '$' in unit works properly
    assert o2.parameters['a1'].datatype.unit == 'mm/s'
    cfg = Newclass2.configurables
    assert set(cfg.keys()) == {
        'export', 'group', 'description', 'features',
        'meaning', 'visibility', 'implementation', 'interface_classes', 'target', 'stop',
        'status', 'param1', 'param2', 'cmd', 'a2', 'pollinterval', 'slowinterval', 'b2',
        'cmd2', 'value', 'a1'}
    assert set(cfg['value'].keys()) == {
        'group', 'export', 'relative_resolution',
        'visibility', 'unit', 'default', 'value', 'datatype', 'fmtstr',
        'absolute_resolution', 'max', 'min', 'readonly', 'constant',
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


def test_command_inheritance():
    class Base(Module):
        @Command(BoolType(), visibility=2)
        def cmd(self, arg):
            """base"""

    class Sub1(Base):
        @Command(group='grp')
        def cmd(self, arg):
            """first"""

    class Sub2(Sub1):
        @Command(None, result=BoolType())
        def cmd(self):  # pylint: disable=arguments-differ
            """second"""

    class Sub3(Base):
        # when either argument or result is given, the other one is assumed to be None
        # i.e. here we override the argument with None
        @Command(result=FloatRange())
        def cmd(self, arg):
            """third"""

    assert Sub1.accessibles['cmd'].for_export() == {
        'description': 'first', 'group': 'grp', 'visibility': 2,
        'datainfo': {'type': 'command', 'argument': {'type': 'bool'}}
    }

    assert Sub2.accessibles['cmd'].for_export() == {
        'description': 'second', 'group': 'grp', 'visibility': 2,
        'datainfo': {'type': 'command', 'result': {'type': 'bool'}}
    }

    assert Sub3.accessibles['cmd'].for_export() == {
        'description': 'third', 'visibility': 2,
        'datainfo': {'type': 'command', 'result': {'type': 'double'}}
    }

    for cls in locals().values():
        if hasattr(cls, 'accessibles'):
            for p in cls.accessibles.values():
                assert isinstance(p.ownProperties, dict)
                assert p.copy().ownProperties == {}


def test_command_check():
    srv = ServerStub({})

    class Good(Module):
        @Command(description='available')
        def with_description(self):
            pass
        @Command()
        def with_docstring(self):
            """docstring"""

    Good('o', logger, {'description': ''}, srv)

    class Bad1(Module):
        @Command
        def without_description(self):
            pass

    class Bad2(Module):
        @Command()
        def without_description(self):
            pass

    for cls in Bad1, Bad2:
        with pytest.raises(ConfigError) as e_info:
            cls('o', logger, {'description': ''}, srv)
        assert 'description' in repr(e_info.value)

    class BadDatatype(Module):
        @Command(FloatRange(0.1, 0.9), result=FloatRange())
        def cmd(self):
            """valid command"""

    BadDatatype('o', logger, {'description': ''}, srv)

    # test for command property checking
    with pytest.raises(ProgrammingError):
        BadDatatype('o', logger, {
            'description': '',
            'cmd': {'argument': {'type': 'double', 'min': 1, 'max': 0}},
        }, srv)

    with pytest.raises(ProgrammingError):
        BadDatatype('o', logger, {
            'description': '',
            'cmd': {'visibility': 'invalid'},
        }, srv)


def test_mixin():
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
        'param1': {'value': 0, 'description': 'param1'},
        'param2': {'datatype': {"type": "double"}},
    }, srv)

    with pytest.raises(ConfigError):
        MixedReadable('o', logger, {
            'description': '',
            'param1': {'value': 0, 'description': 'param1'},
            'param2': {'datatype': {"type": "double"}},
        }, srv)


def test_override():
    class Mod(Drivable):
        value = 5  # overriding the default value

        def stop(self):
            """no decorator needed"""

    assert Mod.value.value == 5
    assert Mod.stop.description == "no decorator needed"

    class Mod2(Drivable):
        @Command()
        def stop(self):
            pass

    assert Mod2.stop.description == Drivable.stop.description


def test_command_config():
    class Mod(Module):
        @Command(IntRange(0, 1), result=IntRange(0, 1))
        def convert(self, value):
            """dummy conversion"""
            return value

    srv = ServerStub({})
    mod = Mod('o', logger, {
        'description': '',
        'convert': {'argument': {'type': 'bool'}},
    }, srv)
    assert mod.commands['convert'].datatype.export_datatype() == {
        'type': 'command',
        'argument': {'type': 'bool'},
        'result': {'type': 'int', 'min': 0, 'max': 1},
    }

    mod = Mod('o', logger, {
        'description': '',
        'convert': {'datatype': {'type': 'command', 'argument': {'type': 'bool'}, 'result': {'type': 'bool'}}},
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


def test_bad_method():
    class Mod0(Drivable):  # pylint: disable=unused-variable
        def write_target(self, value):
            pass

    with pytest.raises(ProgrammingError):
        class Mod1(Drivable):  # pylint: disable=unused-variable
            def write_taget(self, value):
                pass

    class Mod2(Drivable):  # pylint: disable=unused-variable
        def read_value(self, value):
            pass

    with pytest.raises(ProgrammingError):
        class Mod3(Drivable):  # pylint: disable=unused-variable
            def read_valu(self, value):
                pass


def test_generic_access():
    class Mod(Module):
        param = Parameter('handled param', StringType(), readonly=False)
        unhandled = Parameter('unhandled param', StringType(), default='', readonly=False)
        data = {'param': ''}

        @ReadHandler(['param'])
        def read_handler(self, pname):
            value = self.data[pname]
            setattr(self, pname, value)
            return value

        @WriteHandler(['param'])
        def write_handler(self, pname, value):
            value = value.lower()
            self.data[pname] = value
            setattr(self, pname, value)
            return value

    updates = {}
    srv = ServerStub(updates)

    obj = Mod('obj', logger, {'description': '', 'param': {'value':'initial value'}}, srv)
    assert obj.param == 'initial value'
    assert obj.write_param('Cheese') == 'cheese'
    assert obj.write_unhandled('Cheese') == 'Cheese'
    assert updates == {'obj': {'param': 'cheese', 'unhandled': 'Cheese'}}
    updates.clear()
    assert obj.write_param('Potato') == 'potato'
    assert updates == {'obj': {'param': 'potato'}}
    updates.clear()
    assert obj.read_param() == 'potato'
    assert obj.read_unhandled()
    assert updates == {'obj': {'param': 'potato'}}
    updates.clear()
    assert not updates


def test_duplicate_handler_name():
    with pytest.raises(ProgrammingError):
        class Mod(Module):  # pylint: disable=unused-variable
            param = Parameter('handled param', StringType(), readonly=False)

            @ReadHandler(['param'])
            def handler(self, pname):
                pass

            @WriteHandler(['param'])
            def handler(self, pname, value):  # pylint: disable=function-redefined
                pass


def test_handler_overwrites_method():
    with pytest.raises(RuntimeError):
        class Mod1(Module):  # pylint: disable=unused-variable
            param = Parameter('handled param', StringType(), readonly=False)

            @ReadHandler(['param'])
            def read_handler(self, pname):
                pass

            def read_param(self):
                pass

    with pytest.raises(RuntimeError):
        class Mod2(Module):  # pylint: disable=unused-variable
            param = Parameter('handled param', StringType(), readonly=False)

            @WriteHandler(['param'])
            def write_handler(self, pname, value):
                pass

            def write_param(self, value):
                pass


def test_no_read_write():
    class Mod(Module):
        param = Parameter('test param', StringType(), readonly=False)

    updates = {}
    srv = ServerStub(updates)

    obj = Mod('obj', logger, {'description': '', 'param': {'value': 'cheese'}}, srv)
    assert obj.param == 'cheese'
    assert obj.read_param() == 'cheese'
    assert updates == {'obj': {'param': 'cheese'}}
    assert obj.write_param('egg') == 'egg'
    assert obj.param == 'egg'
    assert updates == {'obj': {'param': 'egg'}}


def test_incompatible_value_target():
    class Mod1(Drivable):
        value = Parameter('', FloatRange(0, 10), default=0)
        target = Parameter('', FloatRange(0, 11), default=0)

    class Mod2(Drivable):
        value = Parameter('', FloatRange(), default=0)
        target = Parameter('', StringType(), default='')

    class Mod3(Drivable):
        value = Parameter('', FloatRange(), default=0)
        target = Parameter('', ScaledInteger(1, 0, 10), default=0)

    srv = ServerStub({})

    with pytest.raises(ConfigError):
        obj = Mod1('obj', logger, {'description': ''}, srv)  # pylint: disable=unused-variable

    with pytest.raises(ProgrammingError):
        obj = Mod2('obj', logger, {'description': ''}, srv)

    obj = Mod3('obj', logger, {'description': ''}, srv)


def test_problematic_value_range():
    class Mod(Drivable):
        value = Parameter('', FloatRange(0, 10), default=0)
        target = Parameter('', FloatRange(0, 10), default=0)

    srv = ServerStub({})

    obj = Mod('obj', logger, {'description': '', 'value':{'max': 10.1}}, srv)  # pylint: disable=unused-variable

    with pytest.raises(ConfigError):
        obj = Mod('obj', logger, {'description': '', 'value.max': 9.9}, srv)

    class Mod2(Drivable):
        value = Parameter('', FloatRange(), default=0)
        target = Parameter('', FloatRange(), default=0)

    obj = Mod2('obj', logger, {'description': ''}, srv)
    obj = Mod2('obj', logger, {'description': '', 'target':{'min': 0, 'max': 10}}, srv)

    obj = Mod('obj', logger, {
        'value': {'min': 0, 'max': 10},
        'target': {'min': 0, 'max': 10}, 'description': ''}, srv)

    class Mod4(Drivable):
        value = Parameter('', FloatRange(0, 10), default=0)
        target = Parameter('', FloatRange(0, 10), default=0)
    obj = Mod4('obj', logger, {
        'value': {'min': 0, 'max': 10},
        'target': {'min': 0, 'max': 10}, 'description': ''}, srv)


@pytest.mark.parametrize('config, dynamicunit, finalunit, someunit', [
    ({}, 'K', 'K', 'K'),
    ({'value':{'unit': 'K'}}, 'C', 'C', 'C'),
    ({'value':{'unit': 'K'}}, '', 'K', 'K'),
    ({'value':{'unit': 'K'}, 'someparam':{'unit': 'A'}}, 'C', 'C', 'A'),
])
def test_deferred_main_unit(config, dynamicunit, finalunit, someunit):
    # this pattern is used in frappy_mlz.entangle.AnalogInput
    class Mod(Drivable):
        ramp = Parameter('', datatype=FloatRange(unit='$/min'))
        someparam = Parameter('', datatype=FloatRange(unit='$'))
        __main_unit = None

        def applyMainUnit(self, mainunit):
            # called from __init__ method
            # replacement of '$' by main unit must be done later
            self.__main_unit = mainunit

        def startModule(self, start_events):
            super().startModule(start_events)
            if dynamicunit:
                self.accessibles['value'].datatype.setProperty('unit', dynamicunit)
                self.__main_unit = dynamicunit
            if self.__main_unit:
                super().applyMainUnit(self.__main_unit)

    srv = ServerStub({})
    m = Mod('m', logger, {'description': '', **config}, srv)
    m.startModule(None)
    assert m.parameters['value'].datatype.unit == finalunit
    assert m.parameters['target'].datatype.unit == finalunit
    assert m.parameters['ramp'].datatype.unit == finalunit + '/min'
    # when someparam.unit is configured, this differs from finalunit
    assert m.parameters['someparam'].datatype.unit == someunit


def test_super_call():
    class Base(Readable):
        def read_status(self):
            return Readable.Status.IDLE, 'base'

    class Mod(Base):
        def read_status(self):
            code, text = super().read_status()
            return code, text + ' (extended)'

    class DispatcherStub1:
        def __init__(self, updates):
            self.updates = updates

        def announce_update(self, modulename, pname, pobj):
            if pobj.readerror:
                raise pobj.readerror
            self.updates.append((modulename, pname, pobj.value))

    class ServerStub1:
        def __init__(self, updates):
            self.dispatcher = DispatcherStub1(updates)

    updates = []
    srv = ServerStub1(updates)
    b = Base('b', logger, {'description': ''}, srv)
    b.read_status()
    assert updates == [('b', 'status', ('IDLE', 'base'))]

    updates.clear()
    m = Mod('m', logger, {'description': ''}, srv)
    m.read_status()
    # in the version before change 'allow super calls on read_/write_ methods'
    # updates would contain two items
    assert updates == [('m', 'status', ('IDLE', 'base (extended)'))]

    assert type(m).__name__ == '_Mod'
    assert type(m).__mro__[1:5] == (Mod, Base, Readable, Module)


def test_write_method_returns_none():
    class Mod(Module):
        a = Parameter('', FloatRange(), readonly=False)

        def write_a(self, value):
            return None

    mod = Mod('mod', LoggerStub(), {'description': ''}, ServerStub({}))
    mod.write_a(1.5)
    assert mod.a == 1.5
