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
"""PPMS driver

The PPMS hardware has some special requirements:

- the communication to the hardware happens through windows COM
- all measured data including state are handled by one request/reply pair GETDAT?<mask>
- for each channel, the settings are handled through a single request/reply pair,
  needing a mechanism to treat a single parameter change correctly.

Polling of value and status is done commonly for all modules. For each registered module
<module>.update_value_status() is called in order to update their value and status.
"""

import threading
import time
from ast import literal_eval  # convert string as comma separated numbers into tuple

from secop.datatypes import BoolType, EnumType, \
    FloatRange, IntRange, StatusType, StringType
from secop.errors import HardwareError
from secop.lib import clamp
from secop.lib.enum import Enum
from secop.modules import Communicator, Done, \
    Drivable, Parameter, Property, Readable
from secop.io import HasIO
from secop.rwhandler import CommonReadHandler, CommonWriteHandler

try:
    import secop_psi.ppmswindows as ppmshw
except ImportError:
    print('use simulation instead')
    import secop_psi.ppmssim as ppmshw


class Main(Communicator):
    """ppms communicator module"""

    pollinterval = Parameter('poll interval', FloatRange(), readonly=False, default=2)
    data = Parameter('internal', StringType(), export=True,  # export for test only
                     default="", readonly=True)

    class_id = Property('Quantum Design class id', StringType(), export=False)

    _channel_names = [
        'packed_status', 'temp', 'field', 'position', 'r1', 'i1', 'r2', 'i2',
        'r3', 'i3', 'r4', 'i4', 'v1', 'v2', 'digital', 'cur1', 'pow1', 'cur2', 'pow2',
        'p', 'u20', 'u21', 'u22', 'ts', 'u24', 'u25', 'u26', 'u27', 'u28', 'u29']
    assert len(_channel_names) == 30
    _channel_to_index = dict(((channel, i) for i, channel in enumerate(_channel_names)))
    _status_bitpos = {'temp': 0, 'field': 4, 'chamber': 8, 'position': 12}

    def earlyInit(self):
        super().earlyInit()
        self.modules = {}
        self._ppms_device = ppmshw.QDevice(self.class_id)
        self.lock = threading.Lock()

    def register(self, other):
        self.modules[other.channel] = other

    def communicate(self, command):
        """GPIB command"""
        with self.lock:
            self.comLog('> %s' % command)
            reply = self._ppms_device.send(command)
            self.comLog("< %s", reply)
            return reply

    def doPoll(self):
        self.read_data()

    def read_data(self):
        mask = 1  # always get packed_status
        for channelname, channel in self.modules.items():
            if channel.enabled:
                mask |= 1 << self._channel_to_index.get(channelname, 0)
        # send, read and convert to floats and ints
        data = self.communicate('GETDAT? %d' % mask)
        reply = data.split(',')
        mask = int(reply.pop(0))
        reply.pop(0)  # pop timestamp
        result = {}
        for bitpos, channelname in enumerate(self._channel_names):
            if mask & (1 << bitpos):
                result[channelname] = float(reply.pop(0))
        if 'temp' in result:
            result['tv'] = result['temp']
        if 'ts' in result:
            result['temp'] = result['ts']
        packed_status = int(result['packed_status'])
        result['chamber'] = None  # 'chamber' must be in result for status, but value is ignored
        for channelname, channel in self.modules.items():
            channel.update_value_status(result.get(channelname, None), packed_status)
        return data  # return data as string


class PpmsBase(HasIO, Readable):
    """common base for all ppms modules"""
    value = Parameter(needscfg=False)
    status = Parameter(needscfg=False)

    enabled = True  # default, if no parameter enable is defined
    _last_settings = None  # used by several modules
    slow_pollfactor = 1

    # as this pollinterval affects only the polling of settings
    # it would be confusing to export it.
    pollinterval = Parameter(export=False)

    def initModule(self):
        super().initModule()
        self.io.register(self)

    def doPoll(self):
        # polling is done by the main module
        # and PPMS does not deliver really more fresh values when polled more often
        pass

    def update_value_status(self, value, packed_status):
        # update value and status
        # to be reimplemented for modules looking at packed_status
        if not self.enabled:
            self.status = (self.Status.DISABLED, 'disabled')
            return
        if value is None:
            self.status = (self.Status.ERROR, 'invalid value')
        else:
            self.value = value
            self.status = (self.Status.IDLE, '')

    def comm_write(self, command):
        """write command and check if result is OK"""
        reply = self.communicate(command)
        if reply != 'OK':
            raise HardwareError('bad reply %r to command %r' % (reply, command))


class Channel(PpmsBase):
    """channel base class"""

    value = Parameter('main value of channels')
    enabled = Parameter('is this channel used?', readonly=False,
                        datatype=BoolType(), default=False)

    channel = Property('channel name',
                       datatype=StringType(), export=False, default='')
    no = Property('channel number',
                  datatype=IntRange(1, 4), export=False)

    def earlyInit(self):
        super().earlyInit()
        if not self.channel:
            self.channel = self.name


class UserChannel(Channel):
    """user channel"""

    no = Property('channel number',
                  datatype=IntRange(0, 0), export=False, default=0)
    linkenable = Property('name of linked channel for enabling',
                          datatype=StringType(), export=False, default='')

    def write_enabled(self, enabled):
        other = self.io.modules.get(self.linkenable, None)
        if other:
            other.enabled = enabled
        return enabled


class DriverChannel(Channel):
    """driver channel"""

    current = Parameter('driver current', readonly=False,
                        datatype=FloatRange(0., 5000., unit='uA'))
    powerlimit = Parameter('power limit', readonly=False,
                           datatype=FloatRange(0., 1000., unit='uW'))

    param_names = 'current', 'powerlimit'

    @CommonReadHandler(param_names)
    def read_params(self):
        no, self.current, self.powerlimit = literal_eval(
            self.communicate('DRVOUT? %d' % self.no))
        if self.no != no:
            raise HardwareError('DRVOUT command: channel number in reply does not match')

    @CommonWriteHandler(param_names)
    def write_params(self, values):
        """write parameters

        :param values: a dict like object containing the parameters to be written
        """
        self.read_params()  # make sure parameters are up to date
        self.comm_write('DRVOUT %(no)d,%(current)g,%(powerlimit)g' % values)
        self.read_params()  # read back


class BridgeChannel(Channel):
    """bridge channel"""

    excitation = Parameter('excitation current', readonly=False,
                           datatype=FloatRange(0.01, 5000., unit='uA'))
    powerlimit = Parameter('power limit', readonly=False,
                           datatype=FloatRange(0.001, 1000., unit='uW'))
    dcflag = Parameter('True when excitation is DC (else AC)', readonly=False,
                       datatype=BoolType())
    readingmode = Parameter('reading mode', readonly=False,
                            datatype=EnumType(standard=0, fast=1, highres=2))
    voltagelimit = Parameter('voltage limit', readonly=False,
                             datatype=FloatRange(0.0001, 100., unit='mV'))

    param_names = 'enabled', 'enabled', 'powerlimit', 'dcflag', 'readingmode', 'voltagelimit'

    @CommonReadHandler(param_names)
    def read_params(self):
        no, excitation, powerlimit, self.dcflag, self.readingmode, voltagelimit = literal_eval(
            self.communicate('BRIDGE? %d' % self.no))
        if self.no != no:
            raise HardwareError('DRVOUT command: channel number in reply does not match')
        self.enabled = excitation != 0 and powerlimit != 0 and voltagelimit != 0
        if excitation:
            self.excitation = excitation
        if powerlimit:
            self.powerlimit = powerlimit
        if voltagelimit:
            self.voltagelimit = voltagelimit

    @CommonWriteHandler(param_names)
    def write_params(self, values):
        """write parameters

        :param values: a dict like object containing the parameters to be written
        """
        self.read_params()  # make sure parameters are up to date
        if not values['enabled']:
            values['excitation'] = 0
            values['powerlimit'] = 0
            values['voltagelimit'] = 0
        self.comm_write('BRIDGE %(no)d,%(enabled)g,%(powerlimit)g,%(dcflag)d,'
                        '%(readingmode)d,%(voltagelimit)g' % values)
        self.read_params()  # read back


class Level(PpmsBase):
    """helium level"""

    value = Parameter(datatype=FloatRange(unit='%'))

    channel = 'level'

    def doPoll(self):
        self.read_value()

    def update_value_status(self, value, packed_status):
        pass
        # must be a no-op
        # when called from Main.read_data, value is always None
        # value and status is polled via settings

    def read_value(self):
        # ignore 'old reading' state of the flag, as this happens only for a short time
        return literal_eval(self.communicate('LEVEL?'))[0]


class Chamber(PpmsBase, Drivable):
    """sample chamber handling

    value is an Enum, which is redundant with the status text
    """

    Status = Drivable.Status
    code_table = [
        # valuecode, status, statusname, opcode, targetname
        (0, Status.IDLE, 'unknown',             10, 'noop'),
        (1, Status.IDLE, 'purged_and_sealed',    1, 'purge_and_seal'),
        (2, Status.IDLE, 'vented_and_sealed',    2, 'vent_and_seal'),
        (3, Status.WARN, 'sealed_unknown',       0, 'seal_immediately'),
        (4, Status.BUSY, 'purge_and_seal',    None, None),
        (5, Status.BUSY, 'vent_and_seal',     None, None),
        (6, Status.BUSY, 'pumping_down',      None, None),
        (8, Status.IDLE, 'pumping_continuously', 3, 'pump_continuously'),
        (9, Status.IDLE, 'venting_continuously', 4, 'vent_continuously'),
        (15, Status.ERROR, 'general_failure', None, None),
    ]
    value_codes = {k: v for v, _, k, _, _ in code_table}
    target_codes = {k: v for v, _, _, _, k in code_table if k}
    name2opcode = {k: v for _, _, _, v, k in code_table if k}
    opcode2name = {v: k for _, _, _, v, k in code_table if k}
    status_map = {v: (c, k.replace('_', ' ')) for v, c, k, _, _ in code_table}
    value = Parameter(description='chamber state', datatype=EnumType(**value_codes), default=0)
    target = Parameter(description='chamber command', datatype=EnumType(**target_codes), default='noop')

    channel = 'chamber'

    def update_value_status(self, value, packed_status):
        status_code = (packed_status >> 8) & 0xf
        if status_code in self.status_map:
            self.value = status_code
            self.status = self.status_map[status_code]
        else:
            self.value = self.value_map['unknown']
            self.status = (self.Status.ERROR, 'unknown status code %d' % status_code)

    def read_target(self):
        opcode = int(self.communicate('CHAMBER?'))
        return self.opcode2name[opcode]

    def write_target(self, value):
        if value == self.target.noop:
            return self.target.noop
        opcode = self.name2opcode[self.target.enum(value).name]
        assert self.communicate('CHAMBER %d' % opcode) == 'OK'
        return self.read_target()


class Temp(PpmsBase, Drivable):
    """temperature"""

    Status = Enum(
        Drivable.Status,
        RAMPING=370,
        STABILIZING=380,
    )
    value = Parameter(datatype=FloatRange(unit='K'))
    status = Parameter(datatype=StatusType(Status))
    target = Parameter(datatype=FloatRange(1.7, 402.0, unit='K'), needscfg=False)
    setpoint = Parameter('intermediate set point',
                         datatype=FloatRange(1.7, 402.0, unit='K'))
    ramp = Parameter('ramping speed', readonly=False, default=0,
                     datatype=FloatRange(0, 20, unit='K/min'))
    workingramp = Parameter('intermediate ramp value',
                            datatype=FloatRange(0, 20, unit='K/min'), default=0)
    approachmode = Parameter('how to approach target!', readonly=False,
                             datatype=EnumType(fast_settle=0, no_overshoot=1), default=0)
    timeout = Parameter('drive timeout, in addition to ramp time', readonly=False,
                        datatype=FloatRange(0, unit='sec'), default=3600)
    general_stop = Property('respect general stop', datatype=BoolType(),
                            default=True, value=False)
    STATUS_MAP = {
        1: (Status.IDLE, 'stable at target'),
        2: (Status.RAMPING, 'ramping'),
        5: (Status.STABILIZING, 'within tolerance'),
        6: (Status.STABILIZING, 'outside tolerance'),
        7: (Status.STABILIZING, 'filling/emptying reservoir'),
        10: (Status.WARN, 'standby'),
        13: (Status.WARN, 'control disabled'),
        14: (Status.ERROR, 'can not complete'),
        15: (Status.ERROR, 'general failure'),
    }

    channel = 'temp'
    _stopped = False
    _expected_target_time = 0
    _last_change = 0  # 0 means no target change is pending
    _last_target = None  # last reached target
    _cool_deadline = 0
    _wait_at10 = False
    _ramp_at_limit = False

    param_names = 'setpoint', 'workingramp', 'approachmode'

    @CommonReadHandler(param_names)
    def read_params(self):
        settings = literal_eval(self.communicate('TEMP?'))
        if settings == self._last_settings:
            # update parameters only on change, as 'ramp' and 'approachmode' are
            # not always sent to the hardware
            return
        self.setpoint, self.workingramp, self.approachmode = self._last_settings = settings
        if self.setpoint != 10 or not self._wait_at10:
            self.log.debug('read back target %g %r' % (self.setpoint, self._wait_at10))
            self.target = self.setpoint
        if self.workingramp != 2 or not self._ramp_at_limit:
            self.log.debug('read back ramp %g %r' % (self.workingramp, self._ramp_at_limit))
            self.ramp = self.workingramp

    def _write_params(self, setpoint, ramp, approachmode):
        wait_at10 = False
        ramp_at_limit = False
        if self.value > 11:
            if setpoint <= 10:
                wait_at10 = True
                setpoint = 10
        elif self.value > setpoint:
            if ramp >= 2:
                ramp = 2
                ramp_at_limit = True
        self._wait_at10 = wait_at10
        self._ramp_at_limit = ramp_at_limit
        self.calc_expected(setpoint, ramp)
        self.log.debug(
            'change_temp v %r s %r r %r w %r l %r' % (self.value, setpoint, ramp, wait_at10, ramp_at_limit))
        self.comm_write('TEMP %g,%g,%d' % (setpoint, ramp, approachmode))
        self.read_params()

    def update_value_status(self, value, packed_status):
        if value is None:
            self.status = (self.Status.ERROR, 'invalid value')
            return
        self.value = value
        status_code = packed_status & 0xf
        status = self.STATUS_MAP.get(status_code, (self.Status.ERROR, 'unknown status code %d' % status_code))
        now = time.time()
        if value > 11:
            # when starting from T > 50, this will be 15 min.
            # when starting from lower T, it will be less
            # when ramping with 2 K/min or less, the deadline is now
            self._cool_deadline = max(self._cool_deadline, now + min(40, value - 10) * 30)  # 30 sec / K
        elif self._wait_at10:
            if now > self._cool_deadline:
                self._wait_at10 = False
                self._last_change = now
                self._write_params(self.target, self.ramp, self.approachmode)
            status = (self.Status.STABILIZING, 'waiting at 10 K')
        if self._last_change:  # there was a change, which is not yet confirmed by hw
            if now > self._last_change + 5:
                self._last_change = 0  # give up waiting for busy
            elif self.isDriving(status) and status != self._status_before_change:
                self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
                self._last_change = 0
            else:
                status = (self.Status.BUSY, 'changed target')
        if abs(self.value - self.target) < self.target * 0.01:
            self._last_target = self.target
        elif self._last_target is None:
            self._last_target = self.value
        if self._stopped:
            # combine 'stopped' with current status text
            if status[0] == self.Status.IDLE:
                status = (status[0], 'stopped')
            else:
                status = (status[0], 'stopping (%s)' % status[1])
        if self._expected_target_time:
            # handle timeout
            if self.isDriving(status):
                if now > self._expected_target_time + self.timeout:
                    status = (self.Status.WARN, 'timeout while %s' % status[1])
            else:
                self._expected_target_time = 0
        self.status = status

    def write_target(self, target):
        self._stopped = False
        if abs(self.target - self.value) <= 2e-5 * target and target == self.target:
            return None
        self._status_before_change = self.status
        self.status = (self.Status.BUSY, 'changed target')
        self._last_change = time.time()
        self._write_params(target, self.ramp, self.approachmode)
        self.log.debug('write_target %s' % repr((self.setpoint, target, self._wait_at10)))
        return target

    def write_approachmode(self, value):
        if self.isDriving():
            self._write_params(self.setpoint, self.ramp, value)
            return Done
        self.approachmode = value
        return Done  # do not execute TEMP command, as this would trigger an unnecessary T change

    def write_ramp(self, value):
        if self.isDriving():
            self._write_params(self.setpoint, value, self.approachmode)
            return Done
        self.ramp = value
        return Done  # do not execute TEMP command, as this would trigger an unnecessary T change

    def calc_expected(self, target, ramp):
        self._expected_target_time = time.time() + abs(target - self.value) * 60.0 / max(0.1, ramp)

    def stop(self):
        if not self.isDriving():
            return
        if self.status[0] != self.Status.STABILIZING:
            # we are not near target
            newtarget = clamp(self._last_target, self.value, self.target)
            if newtarget != self.target:
                self.log.debug('stop at %s K', newtarget)
                self.write_target(newtarget)
        self.status = self.status[0], 'stopping (%s)' % self.status[1]
        self._stopped = True


class Field(PpmsBase, Drivable):
    """magnetic field"""

    Status = Enum(
        Drivable.Status,
        PREPARED=150,
        PREPARING=340,
        RAMPING=370,
        STABILIZING=380,
        FINALIZING=390,
    )
    value = Parameter(datatype=FloatRange(unit='T'))
    status = Parameter(datatype=StatusType(Status))
    target = Parameter(datatype=FloatRange(-15, 15, unit='T'))  # poll only one parameter
    ramp = Parameter('ramping speed', readonly=False,
                     datatype=FloatRange(0.064, 1.19, unit='T/min'), default=0.19)
    approachmode = Parameter('how to approach target', readonly=False,
                             datatype=EnumType(linear=0, no_overshoot=1, oscillate=2), default=0)
    persistentmode = Parameter('what to do after changing field', readonly=False,
                               datatype=EnumType(persistent=0, driven=1), default=0)

    STATUS_MAP = {
        1: (Status.IDLE, 'persistent mode'),
        2: (Status.PREPARING, 'switch warming'),
        3: (Status.FINALIZING, 'switch cooling'),
        4: (Status.IDLE, 'driven stable'),
        5: (Status.STABILIZING, 'driven final'),
        6: (Status.RAMPING, 'charging'),
        7: (Status.RAMPING, 'discharging'),
        8: (Status.ERROR, 'current error'),
        11: (Status.ERROR, 'probably quenched'),
        15: (Status.ERROR, 'general failure'),
    }

    channel = 'field'
    _stopped = False
    _last_target = None  # last reached target
    _last_change = 0  # means no target change is pending

    param_names = 'target', 'ramp', 'approachmode', 'persistentmode'

    @CommonReadHandler(param_names)
    def read_params(self):
        settings = literal_eval(self.communicate('FIELD?'))
        # print('last_settings tt %s' % repr(self._last_settings))
        if settings == self._last_settings:
            # we update parameters only on change, as 'ramp' and 'approachmode' are
            # not always sent to the hardware
            return
        target, ramp, self.approachmode, self.persistentmode = self._last_settings = settings
        self.target = round(target * 1e-4, 7)
        self.ramp = ramp * 6e-3

    def _write_params(self, target, ramp, approachmode, persistentmode):
        self.comm_write('FIELD %g,%g,%d,%d' % (
            target * 1e+4, ramp / 6e-3, approachmode, persistentmode))
        self.read_params()

    def update_value_status(self, value, packed_status):
        if value is None:
            self.status = (self.Status.ERROR, 'invalid value')
            return
        self.value = round(value * 1e-4, 7)
        status_code = (packed_status >> 4) & 0xf
        status = self.STATUS_MAP.get(status_code, (self.Status.ERROR, 'unknown status code %d' % status_code))
        now = time.time()
        if self._last_change:  # there was a change, which is not yet confirmed by hw
            if status_code == 1:  # persistent mode
                # leads are ramping (ppms has no extra status code for this!)
                if now < self._last_change + 30:
                    status = (self.Status.PREPARING, 'ramping leads')
                else:
                    status = (self.Status.WARN, 'timeout when ramping leads')
            elif now > self._last_change + 5:
                self._last_change = 0  # give up waiting for driving
            elif self.isDriving(status) and status != self._status_before_change:
                self._last_change = 0
                self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
            else:
                status = (self.Status.BUSY, 'changed target')
        if abs(self.target - self.value) <= 1e-4:
            self._last_target = self.target
        elif self._last_target is None:
            self._last_target = self.value
        if self._stopped:
            # combine 'stopped' with current status text
            if status[0] == self.Status.IDLE:
                status = (status[0], 'stopped')
            else:
                status = (status[0], 'stopping (%s)' % status[1])
        self.status = status

    def write_target(self, target):
        if abs(self.target - self.value) <= 2e-5 and target == self.target:
            self.target = target
            return None  # avoid ramping leads
        self._status_before_change = self.status
        self._stopped = False
        self._last_change = time.time()
        self.status = (self.Status.BUSY, 'changed target')
        self._write_params(target, self.ramp, self.approachmode, self.persistentmode)
        return Done

    def write_persistentmode(self, mode):
        if abs(self.target - self.value) <= 2e-5 and mode == self.persistentmode:
            self.persistentmode = mode
            return None  # avoid ramping leads
        self._last_change = time.time()
        self._status_before_change = self.status
        self._stopped = False
        self.status = (self.Status.BUSY, 'changed persistent mode')
        self._write_params(self.target, self.ramp, self.approachmode, mode)
        return Done

    def write_ramp(self, value):
        self.ramp = value
        if self.isDriving():
            self._write_params(self.target, value, self.approachmode, self.persistentmode)
            return Done
        return None  # do not execute FIELD command, as this would trigger a ramp up of leads current

    def write_approachmode(self, value):
        if self.isDriving():
            self._write_params(self.target, self.ramp, value, self.persistentmode)
            return Done
        return None  # do not execute FIELD command, as this would trigger a ramp up of leads current

    def stop(self):
        if not self.isDriving():
            return
        newtarget = clamp(self._last_target, self.value, self.target)
        if newtarget != self.target:
            self.log.debug('stop at %s T', newtarget)
            self.write_target(newtarget)
        self.status = (self.status[0], 'stopping (%s)' % self.status[1])
        self._stopped = True


class Position(PpmsBase, Drivable):
    """rotator position"""

    Status = Drivable.Status

    value = Parameter(datatype=FloatRange(unit='deg'))
    target = Parameter(datatype=FloatRange(-720., 720., unit='deg'))
    enabled = Parameter('is this channel used?', readonly=False,
                        datatype=BoolType(), default=True)
    speed = Parameter('motor speed', readonly=False, default=12,
                      datatype=FloatRange(0.8, 12, unit='deg/sec'))
    STATUS_MAP = {
        1: (Status.IDLE, 'at target'),
        5: (Status.BUSY, 'moving'),
        8: (Status.IDLE, 'at limit'),
        9: (Status.IDLE, 'at index'),
        15: (Status.ERROR, 'general failure'),
    }

    channel = 'position'
    _stopped = False
    _last_target = None  # last reached target
    _last_change = 0
    _within_target = 0  # time since we are within target

    param_names = 'target', 'speed'

    @CommonReadHandler(param_names)
    def read_params(self):
        settings = literal_eval(self.communicate('MOVE?'))
        if settings == self._last_settings:
            # we update parameters only on change, as 'speed' is
            # not always sent to the hardware
            return
        self.target, _, speed = self._last_settings = settings
        self.speed = (15 - speed) * 0.8

    def _write_params(self, target, speed):
        speed = int(round(min(14, max(0, 15 - speed / 0.8)), 0))
        self.comm_write('MOVE %g,%d,%d' % (target, 0, speed))
        return self.read_params()

    def update_value_status(self, value, packed_status):
        if not self.enabled:
            self.status = (self.Status.DISABLED, 'disabled')
            return
        if value is None:
            self.status = (self.Status.ERROR, 'invalid value')
            return
        self.value = value
        status_code = (packed_status >> 12) & 0xf
        status = self.STATUS_MAP.get(status_code, (self.Status.ERROR, 'unknown status code %d' % status_code))
        if self._last_change:  # there was a change, which is not yet confirmed by hw
            now = time.time()
            if now > self._last_change + 5:
                self._last_change = 0  # give up waiting for busy
            elif self.isDriving(status) and status != self._status_before_change:
                self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
                self._last_change = 0
            else:
                status = (self.Status.BUSY, 'changed target')
        # BUSY can not reliably be determined from the status code, we have to do it on our own
        if abs(value - self.target) < 0.1:
            self._last_target = self.target
            if not self._within_target:
                self._within_target = time.time()
            if time.time() > self._within_target + 1:
                if status[0] != self.Status.IDLE:
                    status = (self.Status.IDLE, status[1])
        elif status[0] != self.Status.BUSY:
            status = (self.Status.BUSY, status[1])
        if self._stopped:
            # combine 'stopped' with current status text
            if status[0] == self.Status.IDLE:
                status = (status[0], 'stopped')
            else:
                status = (status[0], 'stopping (%s)' % status[1])
        self.status = status

    def write_target(self, target):
        self._stopped = False
        self._last_change = 0
        self._status_before_change = self.status
        self.status = (self.Status.BUSY, 'changed target')
        self._write_params(target, self.speed)
        return Done

    def write_speed(self, value):
        if self.isDriving():
            self._write_params(self.target, value)
            return Done
        self.speed = value
        return None  # do not execute MOVE command, as this would trigger an unnecessary move

    def stop(self):
        if not self.isDriving():
            return
        newtarget = clamp(self._last_target, self.value, self.target)
        if newtarget != self.target:
            self.log.debug('stop at %s T', newtarget)
            self.write_target(newtarget)
        self.status = (self.status[0], 'stopping (%s)' % self.status[1])
        self._stopped = True
