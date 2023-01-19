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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************
"""testing devices"""


import random
import threading
import time

from frappy.datatypes import ArrayOf, BoolType, EnumType, \
    FloatRange, IntRange, StringType, StructOf, TupleOf
from frappy.lib.enum import Enum
from frappy.modules import Drivable
from frappy.modules import Parameter as SECoP_Parameter
from frappy.modules import Readable
from frappy.properties import Property


class Parameter(SECoP_Parameter):
    test = Property('A property for testing purposes', StringType(), default='', mandatory=False, extname='test')


PERSIST = 101


class Switch(Drivable):
    """switch it on or off....
    """

    value = Parameter('current state (on or off)',
                      datatype=EnumType(on=1, off=0), default=0,
                      )
    target = Parameter('wanted state (on or off)',
                       datatype=EnumType(on=1, off=0), default=0,
                       readonly=False,
                       )
    switch_on_time = Parameter('seconds to wait after activating the switch',
                               datatype=FloatRange(0, 60), unit='s',
                               default=10, export=False,
                               )
    switch_off_time = Parameter('cool-down time in seconds',
                                datatype=FloatRange(0, 60), unit='s',
                                default=10, export=False,
                                )

    description = Property('The description of the Module', StringType(),
                           default='no description', mandatory=False, extname='description')

    def read_value(self):
        # could ask HW
        # we just return the value of the target here.
        self._update()
        return self.value

    def read_target(self):
        # could ask HW
        return self.target

    def write_target(self, value):
        # could tell HW
        setattr(self, 'status', (self.Status.BUSY, 'switching %s' % value.name.upper()))
        # note: setting self.target to the new value is done after this....
        # note: we may also return the read-back value from the hw here

    def read_status(self):
        self.log.info("read status")
        info = self._update()
        if self.target == self.value:
            return self.Status.IDLE, ''
        return self.Status.BUSY, info

    def _update(self):
        started = self.parameters['target'].timestamp
        info = ''
        if self.target > self.value:
            info = 'waiting for ON'
            if time.time() > started + self.switch_on_time:
                info = 'is switched ON'
                self.value = self.target
        elif self.target < self.value:
            info = 'waiting for OFF'
            if time.time() > started + self.switch_off_time:
                info = 'is switched OFF'
                self.value = self.target
        if info:
            self.log.info(info)
        return info


class MagneticField(Drivable):
    """a liquid magnet
    """

    value = Parameter('current field in T',
                      unit='T', datatype=FloatRange(-15, 15), default=0,
                      )
    target = Parameter('target field in T',
                       unit='T', datatype=FloatRange(-15, 15), default=0,
                       readonly=False,
                       )
    ramp = Parameter('ramping speed',
                     unit='T/min', datatype=FloatRange(0, 1), default=0.1,
                     readonly=False,
                     )
    mode = Parameter('what to do after changing field',
                     default=1, datatype=EnumType(persistent=1, hold=0),
                     readonly=False,
                     )
    heatswitch = Parameter('name of heat switch device',
                           datatype=StringType(), export=False,
                           )

    Status = Enum(Drivable.Status, PERSIST=PERSIST, PREPARE=301, RAMPING=302, FINISH=303)

    status = Parameter(datatype=TupleOf(EnumType(Status), StringType()))

    def initModule(self):
        super().initModule()
        self._state = Enum('state', idle=1, switch_on=2, switch_off=3, ramp=4).idle
        self._heatswitch = self.DISPATCHER.get_module(self.heatswitch)
        _thread = threading.Thread(target=self._thread)
        _thread.daemon = True
        _thread.start()

    def read_value(self):
        return self.value

    def write_target(self, value):
        self.status = self.Status.BUSY, 'setting target'
        # could tell HW
        return round(value, 2)
        # note: setting self.target to the new value is done after this....
        # note: we may also return the read-back value from the hw here

    def read_status(self):
        if self._state == self._state.enum.idle:
            return (PERSIST, 'at field') if self.value else \
                   (self.Status.IDLE, 'zero field')
        if self._state == self._state.enum.switch_on:
            return (self.Status.PREPARE, self._state.name)
        if self._state == self._state.enum.switch_off:
            return (self.Status.FINISH, self._state.name)
        if self._state == self._state.enum.ramp:
            return (self.Status.RAMPING, self._state.name)
        return (self.Status.ERROR, self._state.name)

    def _thread(self):
        loopdelay = 1
        while True:
            ts = time.time()
            if self._state == self._state.enum.idle:
                if self.target != self.value:
                    self.log.debug('got new target -> switching heater on')
                    self._state = self._state.enum.switch_on
                    self._heatswitch.write_target('on')
            if self._state == self._state.enum.switch_on:
                # wait until switch is on
                if self._heatswitch.read_value() == 'on':
                    self.log.debug('heatswitch is on -> ramp to %.3f' %
                                   self.target)
                    self._state = self._state.enum.ramp
            if self._state == self._state.enum.ramp:
                if self.target == self.value:
                    self.log.debug('at field! mode is %r' % self.mode)
                    if self.mode:
                        self.log.debug('at field -> switching heater off')
                        self._state = self._state.enum.switch_off
                        self._heatswitch.write_target('off')
                    else:
                        self.log.debug('at field -> hold')
                        self._state = self._state.enum.idle
                        self.read_status()  # push async
                else:
                    step = self.ramp * loopdelay / 60.
                    step = max(min(self.target - self.value, step), -step)
                    self.value += step
            if self._state == self._state.enum.switch_off:
                # wait until switch is off
                if self._heatswitch.read_value() == 'off':
                    self.log.debug('heatswitch is off at %.3f' % self.value)
                    self._state = self._state.enum.idle
            self.read_status()  # update async
            time.sleep(max(0.01, ts + loopdelay - time.time()))
        self.log.error(self, 'main thread exited unexpectedly!')

    def stop(self):
        self.write_target(self.read_value())


class CoilTemp(Readable):
    """a coil temperature
    """

    value = Parameter('Coil temperatur',
                      unit='K', datatype=FloatRange(), default=0,
                      )
    sensor = Parameter("Sensor number or calibration id",
                       datatype=StringType(), readonly=True,
                       )

    def read_value(self):
        return round(2.3 + random.random(), 3)


class SampleTemp(Drivable):
    """a sample temperature
    """

    value = Parameter('Sample temperature',
                      unit='K', datatype=FloatRange(), default=10,
                      )
    sensor = Parameter("Sensor number or calibration id",
                       datatype=StringType(), readonly=True,
                       )
    ramp = Parameter('moving speed in K/min',
                     datatype=FloatRange(0, 100), unit='K/min', default=0.1,
                     readonly=False,
                     )

    def initModule(self):
        super().initModule()
        _thread = threading.Thread(target=self._thread)
        _thread.daemon = True
        _thread.start()

    def write_target(self, value):
        # could tell HW
        return round(value, 2)
        # note: setting self.target to the new value is done after this....
        # note: we may also return the read-back value from the hw here

    def _thread(self):
        loopdelay = 1
        while True:
            ts = time.time()
            if self.value == self.target:
                if self.status[0] != self.Status.IDLE:
                    self.status = self.Status.IDLE, ''
            else:
                self.status = self.Status.BUSY, 'ramping'
                step = self.ramp * loopdelay / 60.
                step = max(min(self.target - self.value, step), -step)
                self.value += step
            time.sleep(max(0.01, ts + loopdelay - time.time()))
        self.log.error(self, 'main thread exited unexpectedly!')


class Label(Readable):
    """Displays the status of a cryomagnet

       by composing its (stringtype) value from the status/value
       of several subdevices. used for demoing connections between
       modules.
    """

    system = Parameter("Name of the magnet system",
                       datatype=StringType(), export=False,
                       )
    subdev_mf = Parameter("name of subdevice for magnet status",
                          datatype=StringType(), export=False,
                          )
    subdev_ts = Parameter("name of subdevice for sample temp",
                          datatype=StringType(), export=False,
                          )
    value = Parameter("final value of label string", default='',
                      datatype=StringType(),
                      )

    def read_value(self):
        strings = [self.system]

        dev_ts = self.DISPATCHER.get_module(self.subdev_ts)
        if dev_ts:
            strings.append('at %.3f %s' %
                           (dev_ts.read_value(), dev_ts.parameters['value'].datatype.unit))
        else:
            strings.append('No connection to sample temp!')

        dev_mf = self.DISPATCHER.get_module(self.subdev_mf)
        if dev_mf:
            mf_stat = dev_mf.read_status()
            mf_mode = dev_mf.mode
            mf_val = dev_mf.value
            mf_unit = dev_mf.parameters['value'].datatype.unit
            if mf_stat[0] == self.Status.IDLE:
                state = 'Persistent' if mf_mode else 'Non-persistent'
            else:
                state = mf_stat[1] or 'ramping'
            strings.append('%s at %.1f %s' % (state, mf_val, mf_unit))
        else:
            strings.append('No connection to magnetic field!')

        return '; '.join(strings)


class DatatypesTest(Readable):
    """for demoing all datatypes
    """

    enum = Parameter('enum', datatype=EnumType(boo=None, faar=None, z=9),
                     readonly=False, default=1)
    tupleof = Parameter('tuple of int, float and str',
                        datatype=TupleOf(IntRange(), FloatRange(),
                                         StringType()),
                        readonly=False, default=(1, 2.3, 'a'))
    arrayof = Parameter('array: 2..3 times bool',
                        datatype=ArrayOf(BoolType(), 2, 3),
                        readonly=False, default=[1, 0, 1])
    intrange = Parameter('intrange', datatype=IntRange(2, 9),
                         readonly=False, default=4)
    floatrange = Parameter('floatrange', datatype=FloatRange(-1, 1),
                           readonly=False, default=0)
    struct = Parameter('struct(a=str, b=int, c=bool)',
                       datatype=StructOf(a=StringType(), b=IntRange(),
                                         c=BoolType()))


class ArrayTest(Readable):
    x = Parameter('value', datatype=ArrayOf(FloatRange(), 0, 100000),
                  default=100000 * [0])
