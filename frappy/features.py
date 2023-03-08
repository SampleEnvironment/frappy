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
"""Define Mixin Features for real Modules implemented in the server"""


from frappy.datatypes import ArrayOf, BoolType, EnumType, \
    FloatRange, StringType, StructOf, TupleOf
from frappy.core import Command, Done, Drivable, Feature, \
    Parameter, Property, PersistentParam, Readable
from frappy.errors import RangeError, ConfigError
from frappy.lib import clamp


# --- proposals, to be used at SINQ (not agreed as standard yet) ---

class HasOffset(Feature):
    """has an offset parameter

    implementation to be done in the subclass
    """
    offset = PersistentParam('offset (physical value + offset = HW value)',
                             FloatRange(unit='deg'), readonly=False, default=0)

    def write_offset(self, value):
        self.offset = value
        if isinstance(self, HasLimits):
            self.read_limits()
        if isinstance(self, Readable):
            self.read_value()
        if isinstance(self, Drivable):
            self.read_target()
        self.saveParameters()
        return Done


class HasLimits(Feature):
    """user limits

    implementation to be done in the subclass

    for a drivable, abslimits is roughly the same as the target datatype limits,
    except for the offset
    """
    abslimits = Property('abs limits (raw values)', default=(-9e99, 9e99), extname='abslimits', export=True,
                         datatype=TupleOf(FloatRange(unit='deg'), FloatRange(unit='deg')))
    limits = PersistentParam('user limits', readonly=False, default=(-9e99, 9e99),
                             datatype=TupleOf(FloatRange(unit='deg'), FloatRange(unit='deg')))
    _limits = None

    def apply_offset(self, sign, *values):
        if isinstance(self, HasOffset):
            return tuple(v + sign * self.offset for v in values)
        return values

    def earlyInit(self):
        super().earlyInit()
        # make limits valid
        _limits = self.apply_offset(1, *self.limits)
        self._limits = tuple(clamp(self.abslimits[0], v, self.abslimits[1]) for v in _limits)
        self.read_limits()

    def checkProperties(self):
        pname = 'target' if isinstance(self, Drivable) else 'value'
        dt = self.parameters[pname].datatype
        min_, max_ = self.abslimits
        t_min, t_max = self.apply_offset(1, dt.min, dt.max)
        if t_min > max_ or t_max < min_:
            raise ConfigError('abslimits not within %s range' % pname)
        self.abslimits = clamp(t_min, min_, t_max), clamp(t_min, max_, t_max)
        super().checkProperties()

    def read_limits(self):
        return self.apply_offset(-1, *self._limits)

    def write_limits(self, value):
        min_, max_ = self.apply_offset(-1, *self.abslimits)
        if not min_ <= value[0] <= value[1] <= max_:
            if value[0] > value[1]:
                raise RangeError('invalid interval: %r' % value)
            raise RangeError('limits not within abs limits [%g, %g]' % (min_, max_))
        self.limits = value
        self.saveParameters()
        return Done

    def check_limits(self, value):
        """check if value is valid"""
        min_, max_ = self.limits
        if not min_ <= value <= max_:
            raise RangeError('limits violation: %g outside [%g, %g]' % (value, min_, max_))


# --- not used, not tested yet ---

class HAS_PID(Feature):
    # note: implementors should either use p,i,d or pid, but ECS must be handle both cases
    # note: if both p,i,d and pid are implemented, it MUST NOT matter which one gets a change, the final result should be the same
    # note: if there are additional custom accessibles with the same name as an element of the struct, the above applies
    # note: (i would still but them in the same group, though)
    # note: if extra elements are implemented in the pid struct they MUST BE
    #       properly described in the description of the pid Parameter

    # parameters
    use_pid = Parameter('use the pid mode', datatype=EnumType(openloop=0, pid_control=1), )
    # pylint: disable=invalid-name
    p = Parameter('proportional part of the regulation', datatype=FloatRange(0), )
    i = Parameter('(optional) integral part', datatype=FloatRange(0), optional=True)
    d = Parameter('(optional) derivative part', datatype=FloatRange(0), optional=True)
    base_output = Parameter('(optional) minimum output value', datatype=FloatRange(0), optional=True)
    pid = Parameter('(optional) Struct of p,i,d, minimum output value',
                    datatype=StructOf(p=FloatRange(0),
                                      i=FloatRange(0),
                                      d=FloatRange(0),
                                      base_output=FloatRange(0),
                                     ), optional=True,
                  )  # note: struct may be extended with custom elements (names should be prefixed with '_')
    output = Parameter('(optional) output of pid-control', datatype=FloatRange(0), optional=True, readonly=False)


class Has_PIDTable(HAS_PID):

    # parameters
    use_pidtable = Parameter('use the zoning mode', datatype=EnumType(fixed_pid=0, zone_mode=1))
    pidtable = Parameter('Table of pid-values vs. target temperature', datatype=ArrayOf(TupleOf(FloatRange(0),
                          StructOf(p=FloatRange(0),
                          i=FloatRange(0),
                          d=FloatRange(0),
                          _heater_range=FloatRange(0),
                          _base_output=FloatRange(0),),),), optional=True)  # struct may include 'heaterrange'


class HAS_Persistent(Feature):
    #extra_Status {
    #    'decoupled' : Status.IDLE+1,  # to be discussed.
    #    'coupling' : Status.BUSY+1,  # to be discussed.
    #    'coupled' : Status.BUSY+2,  # to be discussed.
    #    'decoupling' : Status.BUSY+3,  # to be discussed.
    #}

    # parameters
    persistent_mode = Parameter('Use persistent mode',
                                datatype=EnumType(off=0,on=1),
                                default=0, readonly=False)
    is_persistent =   Parameter('current state of persistence',
                                datatype=BoolType(), optional=True)
    # stored_value =    Parameter('current persistence value, often used as the modules value',
    #                             datatype='main', unit='$', optional=True)
    # driven_value =    Parameter('driven value (outside value, syncs with stored_value if non-persistent)',
    #                             datatype='main', unit='$' )


class HAS_Tolerance(Feature):
    # detects IDLE status by checking if the value lies in a given window:
    # tolerance is the maximum allowed deviation from target, value must lie in this interval
    # for at least ´timewindow´ seconds.

    # parameters
    tolerance =  Parameter('Half height of the Window',
                            datatype=FloatRange(0), default=1, unit='$')
    timewindow = Parameter('Length of the timewindow to check',
                           datatype=FloatRange(0), default=30, unit='s',
                           optional=True)


class HAS_Timeout(Feature):

    # parameters
    timeout = Parameter('timeout for movement',
                        datatype=FloatRange(0), default=0, unit='s')


class HAS_Pause(Feature):
    # just a proposal, can't agree on it....

    @Command(argument=None, result=None)
    def pause(self):
        """pauses movement"""

    @Command(argument=None, result=None)
    def go(self):
        """continues movement or start a new one if target was change since the last pause"""


class HAS_Ramp(Feature):

    # parameters
    ramp =Parameter('speed of movement', unit='$/min',
                         datatype=FloatRange(0))
    use_ramp = Parameter('use the ramping of the setpoint, or jump',
                         datatype=EnumType(disable_ramp=0, use_ramp=1),
                         optional=True)
    setpoint = Parameter('currently active setpoint',
                         datatype=FloatRange(0), unit='$',
                         readonly=True, )


class HAS_Speed(Feature):

    # parameters
    speed = Parameter('(maximum) speed of movement (of the main value)',
                       unit='$/s', datatype=FloatRange(0))


class HAS_Accel(HAS_Speed):

    # parameters
    accel = Parameter('acceleration of movement', unit='$/s^2',
                       datatype=FloatRange(0))
    decel = Parameter('deceleration of movement', unit='$/s^2',
                       datatype=FloatRange(0), optional=True)


class HAS_MotorCurrents(Feature):

    # parameters
    movecurrent = Parameter('Current while moving',
                             datatype=FloatRange(0))
    idlecurrent = Parameter('Current while idle',
                             datatype=FloatRange(0), optional=True)


class HAS_Curve(Feature):
    # proposed, not yet agreed upon!

    # parameters
    curve = Parameter('Calibration curve', datatype=StringType(), default='<unset>')
