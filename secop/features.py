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
"""Define Mixin Features for real Modules implemented in the server"""


from secop.datatypes import ArrayOf, BoolType, EnumType, \
    FloatRange, StringType, StructOf, TupleOf
from secop.metaclass import ModuleMeta
from secop.modules import Command, Parameter


class Feature(object, metaclass=ModuleMeta):
    """all things belonging to a small, predefined functionality influencing the working of a module"""
    pass


class HAS_PID(Feature):
    # note: implementors should either use p,i,d or pid, but ECS must be handle both cases
    # note: if both p,i,d and pid are implemented, it MUST NOT matter which one gets a change, the final result should be the same
    # note: if there are additional custom accessibles with the same name as an element of the struct, the above applies
    # note: (i would still but them in the same group, though)
    # note: if extra elements are implemented in the pid struct they MUST BE
    #       properly described in the description of the pid Parameter
    parameters = {
        'use_pid' : Parameter('use the pid mode', datatype=EnumType(openloop=0, pid_control=1), ),
        'p' :       Parameter('proportional part of the regulation', datatype=FloatRange(0), ),
        'i' :       Parameter('(optional) integral part', datatype=FloatRange(0), optional=True),
        'd' :       Parameter('(optional) derivative part', datatype=FloatRange(0), optional=True),
        'base_output' : Parameter('(optional) minimum output value', datatype=FloatRange(0), optional=True),
        'pid': Parameter('(optional) Struct of p,i,d, minimum output value',
                         datatype=StructOf(p=FloatRange(0),
                                           i=FloatRange(0),
                                           d=FloatRange(0),
                                           base_output=FloatRange(0),
                                          ), optional=True,
                       ),  # note: struct may be extended with custom elements (names should be prefixed with '_')
        'output' : Parameter('(optional) output of pid-control', datatype=FloatRange(0), optional=True, readonly=False),
    }


class Has_PIDTable(HAS_PID):
    parameters = {
        'use_pidtable' : Parameter('use the zoning mode', datatype=EnumType(fixed_pid=0, zone_mode=1)),
        'pidtable' : Parameter('Table of pid-values vs. target temperature', datatype=ArrayOf(TupleOf(FloatRange(0),
                               StructOf(p=FloatRange(0),
                               i=FloatRange(0),
                               d=FloatRange(0),
                               _heater_range=FloatRange(0),
                               _base_output=FloatRange(0),),),), optional=True),  # struct may include 'heaterrange'
    }


class HAS_Persistent(Feature):
    #extra_Status {
    #    'decoupled' : Status.IDLE+1,  # to be discussed.
    #    'coupling' : Status.BUSY+1,  # to be discussed.
    #    'coupled' : Status.BUSY+2,  # to be discussed.
    #    'decoupling' : Status.BUSY+3,  # to be discussed.
    #}
    parameters = {
        'persistent_mode': Parameter('Use persistent mode',
                                     datatype=EnumType(off=0,on=1),
                                     default=0, readonly=False),
        'is_persistent':   Parameter('current state of persistence',
                                     datatype=BoolType(), optional=True),
        'stored_value':    Parameter('current persistence value, often used as the modules value',
                                     datatype='main', unit='$', optional=True),
        'driven_value':    Parameter('driven value (outside value, syncs with stored_value if non-persistent)',
                                     datatype='main', unit='$' ),
    }


class HAS_Tolerance(Feature):
    # detects IDLE status by checking if the value lies in a given window:
    # tolerance is the maximum allowed deviation from target, value must lie in this interval
    # for at least ´timewindow´ seconds.
    parameters = {
        'tolerance':  Parameter('Half height of the Window',
                                 datatype=FloatRange(0), default=1, unit='$'),
        'timewindow': Parameter('Length of the timewindow to check',
                                datatype=FloatRange(0), default=30, unit='s',
                                optional=True),
    }


class HAS_Timeout(Feature):
    parameters = {
        'timeout': Parameter('timeout for movement',
                             datatype=FloatRange(0), default=0, unit='s'),
    }


class HAS_Pause(Feature):
    # just a proposal, can't agree on it....
    parameters = {
        'pause': Command('pauses movement', argument=None, result=None),
        'go':    Command('continues movement or start a new one if target was change since the last pause',
                         argument=None, result=None),
    }


class HAS_Ramp(Feature):
    parameters = {
        'ramp':     Parameter('speed of movement', unit='$/min',
                              datatype=FloatRange(0)),
        'use_ramp': Parameter('use the ramping of the setpoint, or jump',
                              datatype=EnumType(disable_ramp=0, use_ramp=1),
                              optional=True),
        'setpoint': Parameter('currently active setpoint',
                              datatype=FloatRange(0), unit='$',
                              readonly=True, ),
    }


class HAS_Speed(Feature):
    parameters = {
        'speed' : Parameter('(maximum) speed of movement (of the main value)',
                            unit='$/s', datatype=FloatRange(0)),
    }


class HAS_Accel(HAS_Speed):
    parameters = {
        'accel' : Parameter('acceleration of movement', unit='$/s^2',
                            datatype=FloatRange(0)),
        'decel' : Parameter('deceleration of movement', unit='$/s^2',
                            datatype=FloatRange(0), optional=True),
    }


class HAS_MotorCurrents(Feature):
    parameters = {
        'movecurrent' : Parameter('Current while moving',
                                  datatype=FloatRange(0)),
        'idlecurrent' : Parameter('Current while idle',
                                  datatype=FloatRange(0), optional=True),
    }


class HAS_Curve(Feature):
    # proposed, not yet agreed upon!
    parameters = {
        'curve' : Parameter('Calibration curve', datatype=StringType(80), default='<unset>'),
       # XXX: tbd. (how to upload/download/select a curve?)
    }
