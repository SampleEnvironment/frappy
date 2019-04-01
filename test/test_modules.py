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

# no fixtures needed
#import pytest

import threading
from secop.datatypes import BoolType, EnumType, FloatRange
from secop.metaclass import ModuleMeta
from secop.modules import Communicator, Drivable, Module
from secop.params import Command, Override, Parameter



def test_Communicator():
    logger = type('LoggerStub', (object,), dict(
        debug = lambda self, *a: print(*a),
        info = lambda self, *a: print(*a),
    ))()

    dispatcher = type('DispatcherStub', (object,), dict(
        announce_update = lambda self, m, pn, pv: print('%s:%s=%r' % (m.name, pn, pv)),
    ))()

    srv = type('ServerStub', (object,), dict(
        dispatcher = dispatcher,
    ))()

    o = Communicator('communicator',logger, {}, srv)
    o.earlyInit()
    o.initModule()
    event = threading.Event()
    o.startModule(event.set)
    assert event.is_set() # event should be set immediately

def test_ModuleMeta():
    newclass1 = ModuleMeta.__new__(ModuleMeta, 'TestDrivable', (Drivable,), {
        "parameters" : {
            'pollinterval': Override(reorder=True),
            'param1' : Parameter('param1', datatype=BoolType(), default=False),
            'param2': Parameter('param2', datatype=BoolType(), default=True),
            "cmd": Command('stuff', BoolType(), BoolType())
        },
        "commands": {
            # intermixing parameters with commands is not recommended,
            # but acceptable for influencing the order
            'a1': Parameter('a1', datatype=BoolType(), default=False),
            'a2': Parameter('a2', datatype=BoolType(), default=True),
            'value': Override(datatype=BoolType(), default=True),
            'cmd2': Command('another stuff', BoolType(), BoolType()),
        },
        "do_cmd": lambda self, arg: not arg,
        "do_cmd2": lambda self, arg: not arg,
        "read_param1": lambda self, *args: True,
        "read_param2": lambda self, *args: False,
        "read_a1": lambda self, *args: True,
        "read_a2": lambda self, *args: False,
        "read_value": lambda self, *args: True,
        "init": lambda self, *args: [None for self.accessibles['value'].datatype in [EnumType('value', OK=1, Bad=2)]],
    })
    # first inherited accessibles, then Overrides with reorder=True and new accessibles
    sortcheck1 = ['value', 'status', 'target', 'pollinterval',
                 'param1', 'param2', 'cmd', 'a1', 'a2', 'cmd2']

    newclass2 = ModuleMeta.__new__(ModuleMeta, 'UpperClass', (newclass1,), {
        "parameters": {
            'cmd2': Override('another stuff'),
            'a1': Override(datatype=FloatRange(), reorder=True),
            'b2': Parameter('a2', datatype=BoolType(), default=True),
        },
    })
    sortcheck2 = ['value', 'status', 'target', 'pollinterval',
                 'param1', 'param2', 'cmd', 'a2', 'cmd2', 'a1', 'b2']

    logger = type('LoggerStub', (object,), dict(
        debug = lambda self, *a: print(*a),
        info = lambda self, *a: print(*a),
        exception = lambda self, *a: print(*a),
    ))()

    dispatcher = type('DispatcherStub', (object,), dict(
        announce_update = lambda self, m, pn, pv: print('%s:%s=%r' % (m.name, pn, pv)),
    ))()

    srv = type('ServerStub', (object,), dict(
        dispatcher = dispatcher,
    ))()

    params_found = set() # set of instance accessibles
    objects = []

    for newclass, sortcheck in [(newclass1, sortcheck1), (newclass2, sortcheck2)]:
        o1 = newclass('o1', logger, {}, srv)
        o2 = newclass('o2', logger, {}, srv)
        for obj in [o1, o2]:
            objects.append(obj)
            ctr_found = set()
            for n, o in obj.accessibles.items():
                # check that instance accessibles are unique objects
                assert o not in params_found
                params_found.add(o)
                assert o.ctr not in ctr_found
                ctr_found.add(o.ctr)
            check_order = [(obj.accessibles[n].ctr, n) for n in sortcheck]
            assert check_order == sorted(check_order)

    # check on the level of classes
    # this checks newclass1 too, as it is inherited by newclass2
    for baseclass in newclass2.__mro__:
        # every cmd/param has to be collected to accessibles
        acs = getattr(baseclass, 'accessibles', None)
        if issubclass(baseclass, Module):
            assert acs is not None
        else: # do not check object or mixin
            acs = {}
        for n, o in acs.items():
            # check that class accessibles are not reused as instance accessibles
            assert o not in params_found

    for o in objects:
        o.earlyInit()
    for o in objects:
        o.initModule()

    for o in objects:
        event = threading.Event()
        event2 = threading.Event()
        def started_callback(event=event, event2=event2):
            if event.is_set():
                event2.set()
            else:
                event.set()
            raise Exception("end test") # this will kill the polling thread on the second call

        o.startModule(started_callback)
        assert event2.wait(timeout=1)
        assert event.is_set()
