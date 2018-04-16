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

from secop.modules import Module, Readable, Writable, Drivable, Param
from secop.lib import mkthread
from secop.protocol import status
from secop.datatypes import FloatRange


class SimBase(object):
    def __init__(self, cfgdict):
        # spice up parameters if requested by extra property
        # hint: us a comma-separated list if mor than one extra_param
        # BIG FAT WARNING: changing extra params will NOT generate events!
        # XXX: implement default read_* and write_* methods to handle
        # read and change messages correctly
        if '.extra_params' in cfgdict:
            extra_params = cfgdict.pop('.extra_params')
            # make a copy of self.parameter
            self.parameters = dict((k, v.copy()) for k, v in self.parameters.items())
            for k in extra_params.split(','):
                k = k.strip()
                self.parameters[k] = Param('extra_param: %s' % k.strip(),
                                       datatype=FloatRange(),
                                       default=0.0)
                def reader(maxage=0, pname=k):
                    self.log.debug('simulated reading %s' % pname)
                    return self.parameters[pname].value
                setattr(self, 'read_' + k, reader)
                def writer(newval, pname=k):
                    self.log.debug('simulated writing %r to %s' % (newval, pname))
                    self.parameters[pname].value = newval
                    return newval
                setattr(self, 'write_' + k, writer)

    def late_init(self):
        self._sim_thread = mkthread(self._sim)

    def _sim(self):
        try:
            while not self.sim():
                pass
        except Exception as e:
            self.log.exception(e)
        self.log.info('sim thread ended')

    def sim(self):
        return True

    def read_value(self, maxage=0):
        if 'jitter' in self.parameters:
            return self._value + self.jitter*(0.5-random.random())
        return self._value


class SimModule(SimBase, Module):
    def __init__(self, logger, cfgdict, devname, dispatcher):
        SimBase.__init__(self, cfgdict)
        Module.__init__(self, logger, cfgdict, devname, dispatcher)


class SimReadable(SimBase, Readable):
    def __init__(self, logger, cfgdict, devname, dispatcher):
        SimBase.__init__(self, cfgdict)
        Readable.__init__(self, logger, cfgdict, devname, dispatcher)
        self._value = self.parameters['value'].default


class SimWritable(SimBase, Writable):
    def __init__(self, logger, cfgdict, devname, dispatcher):
        SimBase.__init__(self, cfgdict)
        Writable.__init__(self, logger, cfgdict, devname, dispatcher)
        self._value = self.parameters['value'].default
    def read_value(self, maxage=0):
        return self.target
    def write_target(self, value):
        self.value = value


class SimDrivable(SimBase, Drivable):
    def __init__(self, logger, cfgdict, devname, dispatcher):
        SimBase.__init__(self, cfgdict)
        Drivable.__init__(self, logger, cfgdict, devname, dispatcher)
        self._value = self.parameters['value'].default

    def sim(self):
        while self._value == self.target:
            sleep(0.3)
        self.status = status.BUSY, 'MOVING'
        speed = 0
        if 'ramp' in self.parameters:
            speed = self.ramp / 60.  # ramp is per minute!
        elif 'speed' in self.parameters:
            speed = self.speed
        if speed == 0:
            self._value = self.target
        speed *= 0.3

        while self._value != self.target:
            if self._value < self.target - speed:
                self._value += speed
            elif self._value > self.target + speed:
                self._value -= speed
            else:
                self._value = self.target
            sleep(0.3)
        self.status = status.OK, ''
