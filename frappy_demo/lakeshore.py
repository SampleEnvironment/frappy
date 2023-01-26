#!/usr/bin/env python
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
"""LakeShore demo

demo example for tutorial
"""

from frappy.core import Readable, Parameter, FloatRange, HasIO, StringIO, Property, StringType, \
    IDLE, BUSY, WARN, ERROR, Drivable, IntRange


class LakeshoreIO(StringIO):
    wait_before = 0.05  # Lakeshore requires a wait time of 50 ms between commands
    # Lakeshore commands (see manual)
    # '*IDN?' is sent on connect, and the reply is checked to match the regexp 'LSCI,.*'
    identification = [('*IDN?', 'LSCI,.*')]


class TemperatureSensor(HasIO, Readable):
    """a temperature sensor (generic for different models)"""
    # internal property to configure the channel
    channel = Property('the Lakeshore channel', datatype=StringType())
    # 0, 1500 is the allowed range by the LakeShore controller
    # this range should be further restricted in the configuration (see below)
    value = Parameter(datatype=FloatRange(0, 1500, unit='K'))

    def read_value(self):
        # the communicate method sends a command and returns the reply
        reply = self.communicate(f'KRDG?{self.channel}')
        return float(reply)

    def read_status(self):
        code = int(self.communicate(f'RDGST?{self.channel}'))
        if code >= 128:
            text = 'units overrange'
        elif code >= 64:
            text = 'units zero'
        elif code >= 32:
            text = 'temperature overrange'
        elif code >= 16:
            text = 'temperature underrange'
        elif code % 2:
            # ignore 'old reading', as this may happen in normal operation
            text = 'invalid reading'
        else:
            return IDLE, ''
        return ERROR, text


class TemperatureLoop(TemperatureSensor, Drivable):
    # lakeshore loop number to be used for this module
    loop = Property('lakeshore loop', IntRange(1, 2), default=1)
    target = Parameter(datatype=FloatRange(min=0, max=1500, unit='K'))
    heater_range = Property('heater power range', IntRange(0, 5))  # max. 3 on LakeShore 336
    tolerance = Parameter('convergence criterion', FloatRange(0), default=0.1, readonly = False)
    _driving = False

    def write_target(self, target):
        # reactivate heater in case it was switched off
        # the command has to be changed in case of model 340 to f'RANGE {self.heater_range};RANGE?'
        self.communicate(f'RANGE {self.loop},{self.heater_range};RANGE?{self.loop}')
        reply = self.communicate(f'SETP {self.loop},{target};SETP? {self.loop}')
        self._driving = True
        # Setting the status attribute triggers an update message for the SECoP status
        # parameter. This has to be done before returning from this method!
        self.status = BUSY, 'target changed'
        return float(reply)

    def read_target(self):
        return float(self.communicate(f'SETP?{self.loop}'))

    def read_status(self):
        code = int(self.communicate(f'RDGST?{self.channel}'))
        if code >= 128:
            text = 'units overrange'
        elif code >= 64:
            text = 'units zero'
        elif code >= 32:
            text = 'temperature overrange'
        elif code >= 16:
            text = 'temperature underrange'
        elif code % 2:
            # ignore 'old reading', as this may happen in normal operation
            text = 'invalid reading'
        elif abs(self.target - self.value) > self.tolerance:
            if self._driving:
                return BUSY, 'approaching setpoint'
            return WARN, 'temperature out of tolerance'
        else:  # within tolerance: simple convergence criterion
            self._driving = False
            return IDLE, ''
        return ERROR, text
