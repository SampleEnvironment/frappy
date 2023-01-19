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
"""Define Simulation classes"""


import random
from time import sleep

from frappy.datatypes import FloatRange
from frappy.lib import mkthread
from frappy.modules import Drivable, Module, Parameter, Readable, Writable, Command


class SimBase:
    def __new__(cls, devname, logger, cfgdict, dispatcher):
        extra_params = cfgdict.pop('extra_params', '') or cfgdict.pop('.extra_params', '')
        attrs = {}
        if extra_params:
            for k in extra_params['default'].split(','):
                k = k.strip()
                attrs[k] = Parameter('extra_param: %s' % k.strip(),
                                     datatype=FloatRange(),
                                     default=0.0)

                def reader(self, pname=k):
                    self.log.debug('simulated reading %s' % pname)
                    return self.parameters[pname].value

                attrs['read_' + k] = reader

                def writer(self, newval, pname=k):
                    self.log.debug('simulated writing %r to %s' % (newval, pname))
                    self.parameters[pname].value = newval
                    return newval

                attrs['write_' + k] = writer

        return object.__new__(type('SimBase_%s' % devname, (cls,), attrs))

    def initModule(self):
        super().initModule()
        self._sim_thread = mkthread(self._sim)

    def _sim(self):
        try:
            if not self.sim():
                self.log.info('sim thread running')
                while not self.sim():
                    pass
                self.log.info('sim thread ended')
        except Exception as e:
            self.log.exception(e)

    def sim(self):
        return True  # nothing to do, stop thread


class SimModule(SimBase, Module):
    pass


class SimReadable(SimBase, Readable):
    def __init__(self, devname, logger, cfgdict, dispatcher):
        super().__init__(devname, logger, cfgdict, dispatcher)
        self._value = self.parameters['value'].default

    def read_value(self):
        if 'jitter' in self.parameters:
            return self._value + self.jitter * (0.5 - random.random())
        return self._value


class SimWritable(SimReadable, Writable):

    def read_value(self):
        return self.target

    def write_target(self, value):
        self.value = value

    def _hw_wait(self):
        pass


class SimDrivable(SimReadable, Drivable):
    interval = Parameter('simulation interval', FloatRange(0, 1), readonly=False, default=0.3)

    def sim(self):
        while self._value == self.target:
            sleep(self.interval)
        self.status = self.Status.BUSY, 'MOVING'
        speed = 0
        if 'ramp' in self.accessibles:
            speed = self.ramp / 60.  # ramp is per minute!
        elif 'speed' in self.accessibles:
            speed = self.speed
        if speed == 0:
            self._value = self.target
        speed *= self.interval
        try:
            self.doPoll()
        except Exception:
            pass

        while self._value != self.target:
            if self._value < self.target - speed:
                self._value += speed
            elif self._value > self.target + speed:
                self._value -= speed
            else:
                self._value = self.target
            sleep(self.interval)
            try:
                self.doPoll()
            except Exception:
                pass
        self.status = self.Status.IDLE, ''
        return False # keep thread running

    def _hw_wait(self):
        while self.status[0] == self.Status.BUSY:
            sleep(self.interval)

    @Command
    def stop(self):
        self.target = self.value
