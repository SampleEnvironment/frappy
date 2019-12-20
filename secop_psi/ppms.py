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

import time
import threading

from secop.modules import Module, Readable, Drivable, Parameter, Override,\
    Communicator, Property, Attached
from secop.datatypes import EnumType, FloatRange, IntRange, StringType,\
    BoolType, StatusType
from secop.lib.enum import Enum
from secop.errors import HardwareError
from secop.poller import Poller
import secop.commandhandler
from secop.stringio import HasIodev
from secop.metaclass import Done

try:
    import secop_psi.ppmswindows as ppmshw
except ImportError:
    import secop_psi.ppmssim as ppmshw


class CmdHandler(secop.commandhandler.CmdHandler):
    CMDARGS = ['no']
    CMDSEPARATOR = None  # no command chaining
    READ_BEFORE_WRITE = False

    def __init__(self, name, querycmd, replyfmt):
        changecmd = querycmd.split('?')[0] + ' '
        super().__init__(name, querycmd, replyfmt, changecmd)


class Main(Communicator):
    """general ppms dummy module"""

    parameters = {
        'pollinterval': Parameter('poll interval', readonly=False,
                                  datatype=FloatRange(), default=2),
        'communicate':  Override('GBIP command'),
        'data':         Parameter('internal', poll=True, export=True,  # export for test only
                                  default="", readonly=True, datatype=StringType()),
    }
    properties = {
        'class_id':     Property('Quantum Design class id', export=False,
                                 datatype=StringType()),
    }

    _channel_names = ['packed_status', 'temp', 'field', 'position', 'r1', 'i1', 'r2', 'i2',
        'r3', 'i3', 'r4', 'i4', 'v1', 'v2', 'digital', 'cur1', 'pow1', 'cur2', 'pow2',
        'p', 'u20', 'u21', 'u22', 'ts', 'u24', 'u25', 'u26', 'u27', 'u28', 'u29']
    assert len(_channel_names) == 30
    _channel_to_index = dict(((channel, i) for i, channel in enumerate(_channel_names)))
    _status_bitpos = {'temp': 0, 'field': 4, 'chamber': 8, 'position': 12}

    pollerClass = Poller

    def earlyInit(self):
        self.modules = {}
        self._ppms_device = ppmshw.QDevice(self.class_id)
        self.lock = threading.Lock()

    def register(self, other):
        self.modules[other.channel] = other

    def do_communicate(self, command):
        with self.lock:
            reply = self._ppms_device.send(command)
            self.log.debug("%s|%s", command, reply)
            return reply

    def read_data(self):
        mask = 1  # always get packed_status
        for channelname, channel in self.modules.items():
            if channel.enabled:
                mask |= 1 << self._channel_to_index.get(channelname, 0)
        # send, read and convert to floats and ints
        data = self.do_communicate('GETDAT? %d' % mask)
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


class PpmsMixin(HasIodev, Module):
    properties = {
        'iodev': Attached(),
    }

    pollerClass = Poller
    enabled = True  # default, if no parameter enable is defined
    _last_target_change = 0  # used by several modules
    _last_settings = None  # used by several modules
    slow_pollfactor = 1

    def initModule(self):
        self._iodev.register(self)

    def startModule(self, started_callback):
        # no polls except on main module
        started_callback()

    def read_value(self):
        """polling is done by the main module

        and PPMS does not deliver really more fresh values when polled more often
        """
        return Done

    def read_status(self):
        """polling is done by the main module

        and PPMS does not deliver really fresh status values anyway: the status is not
        changed immediately after a target change!
        """
        return Done

    def update_value_status(self, value, packed_status):
        """update value and status

        to be reimplemented for modules looking at packed_status
        """
        if not self.enabled:
            self.status = [self.Status.DISABLED, 'disabled']
            return
        if value is None:
            self.status = [self.Status.ERROR, 'invalid value']
        else:
            self.value = value
            self.status = [self.Status.IDLE, '']


class Channel(PpmsMixin, Readable):
    parameters = {
        'value':
            Override('main value of channels', poll=True),
        'enabled':
            Parameter('is this channel used?', readonly=False, poll=False,
                      datatype=BoolType(), default=False),
        'pollinterval':
            Override(visibility=3),
    }
    properties = {
        'channel':
            Property('channel name',
                     datatype=StringType(), export=False, default=''),
        'no':
            Property('channel number',
                     datatype=IntRange(1, 4), export=False),
    }

    def earlyInit(self):
        Readable.earlyInit(self)
        if not self.channel:
            self.properties['channel'] = self.name

    def get_settings(self, pname):
        return ''


class UserChannel(Channel):
    parameters = {
        'pollinterval':
            Override(visibility=3),
    }
    properties = {
        'no':
            Property('channel number',
                     datatype=IntRange(0, 0), export=False, default=0),
    }


class DriverChannel(Channel):
    drvout = CmdHandler('drvout', 'DRVOUT? %(no)d', '%d,%g,%g')

    parameters = {
        'current':
            Parameter('driver current', readonly=False, handler=drvout,
                      datatype=FloatRange(0., 5000., unit='uA')),
        'powerlimit':
            Parameter('power limit', readonly=False, handler=drvout,
                      datatype=FloatRange(0., 1000., unit='uW')),
        'pollinterval':
            Override(visibility=3),
    }

    def analyze_drvout(self, no, current, powerlimit):
        if self.no != no:
            raise HardwareError('DRVOUT command: channel number in reply does not match')
        return dict(current=current, powerlimit=powerlimit)

    def change_drvout(self, change):
        self.readValues()
        return change.current, change.powerlimit


class BridgeChannel(Channel):
    bridge = CmdHandler('bridge', 'BRIDGE? %(no)d', '%d,%g,%g,%d,%d,%g')
    # pylint: disable=invalid-name
    ReadingMode = Enum('ReadingMode', standard=0, fast=1, highres=2)
    parameters = {
        'enabled':
            Override(handler=bridge),
        'excitation':
            Parameter('excitation current', readonly=False, handler=bridge,
                      datatype=FloatRange(0.01, 5000., unit='uA')),
        'powerlimit':
            Parameter('power limit', readonly=False, handler=bridge,
                      datatype=FloatRange(0.001, 1000., unit='uW')),
        'dcflag':
            Parameter('True when excitation is DC (else AC)', readonly=False, handler=bridge,
                      datatype=BoolType()),
        'readingmode':
            Parameter('reading mode', readonly=False, handler=bridge,
                      datatype=EnumType(ReadingMode)),
        'voltagelimit':
            Parameter('voltage limit', readonly=False, handler=bridge,
                      datatype=FloatRange(0.0001, 100., unit='mV')),
        'pollinterval':
            Override(visibility=3),
    }

    def analyze_bridge(self, no, excitation, powerlimit, dcflag, readingmode, voltagelimit):
        if self.no != no:
            raise HardwareError('DRVOUT command: channel number in reply does not match')
        return dict(
                enabled=excitation != 0 and powerlimit != 0 and voltagelimit != 0,
                excitation=excitation or self.excitation,
                powerlimit=powerlimit or self.powerlimit,
                dcflag=dcflag,
                readingmode=readingmode,
                voltagelimit=voltagelimit or self.voltagelimit,
            )

    def change_bridge(self, change):
        self.readValues()
        if change.enabled:
            return self.no, change.excitation, change.powerlimit, change.dcflag, change.readingmode, change.voltagelimit
        return self.no, 0, 0, change.dcflag, change.readingmode, 0


class Level(PpmsMixin, Readable):
    """helium level"""

    level = CmdHandler('level', 'LEVEL?', '%g,%d')

    parameters = {
        'value':  Override(datatype=FloatRange(unit='%'), handler=level),
        'status': Override(handler=level),
        'pollinterval':
            Override(visibility=3),
    }

    channel = 'level'

    def update_value_status(self, value, packed_status):
        """must be a no-op

        when called from Main.read_data, value is always None
        value and status is polled via settings
        """

    def analyze_level(self, level, status):
        if status:
            self.status = [self.Status.IDLE, '']
        else:
            self.status = [self.Status.ERROR, 'old reading']
        return dict(value=level)


class Chamber(PpmsMixin, Drivable):
    """sample chamber handling

    value is an Enum, which is redundant with the status text
    """

    chamber = CmdHandler('chamber', 'CHAMBER?', '%d')
    Status = Drivable.Status
    # pylint: disable=invalid-name
    Operation = Enum(
        'Operation',
        seal_immediately=0,
        purge_and_seal=1,
        vent_and_seal=2,
        pump_continuously=3,
        vent_continuously=4,
        hi_vacuum=5,
        noop=10,
    )
    StatusCode = Enum(
        'StatusCode',
        unknown=0,
        purged_and_sealed=1,
        vented_and_sealed=2,
        sealed_unknown=3,
        purge_and_seal=4,
        vent_and_seal=5,
        pumping_down=6,
        at_hi_vacuum=7,
        pumping_continuously=8,
        venting_continuously=9,
        general_failure=15,
    )
    parameters = {
        'value':
            Override(description='chamber state', handler=chamber,
                     datatype=EnumType(StatusCode)),
        'target':
            Override(description='chamber command', handler=chamber,
                     datatype=EnumType(Operation)),
        'pollinterval':
            Override(visibility=3),
    }
    STATUS_MAP = {
        StatusCode.unknown: [Status.WARN, 'unknown'],
        StatusCode.purged_and_sealed: [Status.IDLE, 'purged and sealed'],
        StatusCode.vented_and_sealed: [Status.IDLE, 'vented and sealed'],
        StatusCode.sealed_unknown: [Status.WARN, 'sealed unknown'],
        StatusCode.purge_and_seal: [Status.BUSY, 'purge and seal'],
        StatusCode.vent_and_seal: [Status.BUSY, 'vent and seal'],
        StatusCode.pumping_down: [Status.BUSY, 'pumping down'],
        StatusCode.at_hi_vacuum: [Status.IDLE, 'at hi vacuum'],
        StatusCode.pumping_continuously: [Status.IDLE, 'pumping continuously'],
        StatusCode.venting_continuously: [Status.IDLE, 'venting continuously'],
        StatusCode.general_failure: [Status.ERROR, 'general failure'],
    }

    channel = 'chamber'

    def update_value_status(self, value, packed_status):
        """update value and status"""
        self.value = (packed_status >> 8) & 0xf
        self.status = self.STATUS_MAP[self.value]

    def analyze_chamber(self, target):
        return dict(target=target)

    def change_chamber(self, change):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        if change.target == self.Operation.noop:
            return None
        return (change.target,)


class Temp(PpmsMixin, Drivable):
    """temperature"""

    temp = CmdHandler('temp', 'TEMP?', '%g,%g,%d')
    Status = Enum(Drivable.Status,
        RAMPING = 370,
        STABILIZING = 380,
    )
    # pylint: disable=invalid-name
    ApproachMode = Enum('ApproachMode', fast_settle=0, no_overshoot=1)
    parameters = {
        'value':
            Override(datatype=FloatRange(unit='K'), poll=True),
        'status':
            Override(datatype=StatusType(Status), poll=True),
        'target':
            Override(datatype=FloatRange(1.7, 402.0, unit='K'), handler=temp),
        'ramp':
            Parameter('ramping speed', readonly=False, handler=temp,
                      datatype=FloatRange(0, 20, unit='K/min')),
        'approachmode':
            Parameter('how to approach target!', readonly=False, handler=temp,
                      datatype=EnumType(ApproachMode)),
        'pollinterval':
            Override(visibility=3),
        'timeout':
            Parameter('drive timeout, in addition to ramp time', readonly=False,
                      datatype=FloatRange(0, unit='sec'), default=3600),
    }
    properties = {
        'general_stop': Property('respect general stop', datatype=BoolType(),
                                 export=True, default=True)
    }
    # pylint: disable=invalid-name
    TempStatus = Enum(
        'TempStatus',
        unknown=0,
        stable_at_target=1,
        changing=2,
        within_tolerance=5,
        outside_tolerance=6,
        standby=10,
        control_disabled=13,
        can_not_complete=14,
        general_failure=15,
    )
    STATUS_MAP = {
        0: [Status.ERROR, 'unknown'],
        1: [Status.IDLE, 'stable at target'],
        2: [Status.RAMPING, 'ramping'],
        5: [Status.STABILIZING, 'within tolerance'],
        6: [Status.STABILIZING, 'outside tolerance'],
        10: [Status.WARN, 'standby'],
        13: [Status.WARN, 'control disabled'],
        14: [Status.ERROR, 'can not complete'],
        15: [Status.ERROR, 'general failure'],
    }

    channel = 'temp'
    _stopped = False
    _expected_target = 0
    _last_change = 0  # 0 means no target change is pending

    def earlyInit(self):
        self.setProperty('general_stop', False)
        super().earlyInit()

    def update_value_status(self, value, packed_status):
        """update value and status"""
        if value is None:
            self.status = [self.Status.ERROR, 'invalid value']
            return
        self.value = value
        status = self.STATUS_MAP[packed_status & 0xf]
        now = time.time()
        if self._stopped:
            # combine 'stopped' with current status text
            if status[0] == self.Status.IDLE:
                self._stopped = False
            else:
                self.status = [self.Status.IDLE, 'stopped(%s)' % status[1]]
                return
        if self._last_change:  # there was a change, which is not yet confirmed by hw
            if now > self._last_change + 5:
                self._last_change = 0  # give up waiting for busy
            elif self.isDriving(status) and status != self._status_before_change:
                self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
                self._last_change = 0
            else:
                status = [self.Status.BUSY, 'changed target']
        if self._expected_target:
            # handle timeout
            if self.isDriving(status):
                if now > self._expected_target + self.timeout:
                    status = [self.Status.WARN, 'timeout while %s' % status[1]]
            else:
                self._expected_target = 0
        self.status = status

    def analyze_temp(self, target, ramp, approachmode):
        if (target, ramp, approachmode) == self._last_settings:
            # we update parameters only on change, as 'approachmode'
            # is not always sent to the hardware
            return {}
        self._last_settings = target, ramp, approachmode
        return dict(target=target, ramp=ramp, approachmode=approachmode)

    def change_temp(self, change):
        self.calc_expected(change.target, self.ramp)
        return change.target, change.ramp, change.approachmode

    def write_target(self, target):
        self._stopped = False
        if abs(self.target - self.value) < 2e-5 and target == self.target:
            return None
        self._status_before_change = self.status
        self.status = [self.Status.BUSY, 'changed target']
        self._last_change = time.time()
        return target

    def write_approachmode(self, value):
        if self.isDriving():
            return value
        return None  # change_temp will not be called, as this would trigger an unnecessary T change

    def write_ramp(self, value):
        if self.isDriving():
            return value
        return None  # change_temp will not be called, as this would trigger an unnecessary T change

    def calc_expected(self, target, ramp):
        self._expected_target = time.time() + abs(target - self.value) * 60.0 / max(0.1, ramp)

    def do_stop(self):
        if self.isDriving():
            return
        if self.status[0] == self.Status.STABILIZING:
            # we are already near target
            newtarget = self.target
        else:
            newtarget = self.value
        self.log.info('stop at %s K', newtarget)
        self.write_target(newtarget)
        self.status = [self.Status.IDLE, 'stopped']
        self._stopped = True


class Field(PpmsMixin, Drivable):
    """magnetic field"""

    field = CmdHandler('field', 'FIELD?', '%g,%g,%d,%d')
    Status = Enum(Drivable.Status,
        PREPARED = 150,
        PREPARING = 340,
        RAMPING = 370,
        FINALIZING = 390,
    )
    # pylint: disable=invalid-name
    PersistentMode = Enum('PersistentMode', persistent=0, driven=1)
    ApproachMode = Enum('ApproachMode', linear=0, no_overshoot=1, oscillate=2)

    parameters = {
        'value':
            Override(datatype=FloatRange(unit='T'), poll=True),
        'status':
            Override(datatype=StatusType(Status), poll=True),
        'target':
            Override(datatype=FloatRange(-15, 15, unit='T'), handler=field),
        'ramp':
            Parameter('ramping speed', readonly=False, handler=field,
                      datatype=FloatRange(0.064, 1.19, unit='T/min')),
        'approachmode':
            Parameter('how to approach target', readonly=False, handler=field,
                      datatype=EnumType(ApproachMode)),
        'persistentmode':
            Parameter('what to do after changing field', readonly=False, handler=field,
                      datatype=EnumType(PersistentMode)),
        'pollinterval':
            Override(visibility=3),
    }

    STATUS_MAP = {
        0: [Status.ERROR, 'unknown'],
        1: [Status.IDLE, 'persistent mode'],
        2: [Status.PREPARING, 'switch warming'],
        3: [Status.FINALIZING, 'switch cooling'],
        4: [Status.IDLE, 'driven stable'],
        5: [Status.FINALIZING, 'driven final'],
        6: [Status.RAMPING, 'charging'],
        7: [Status.RAMPING, 'discharging'],
        8: [Status.ERROR, 'current error'],
        15: [Status.ERROR, 'general failure'],
    }

    channel = 'field'
    _stopped = False
    _last_target = 0
    _last_change = 0  # means no target change is pending

    def update_value_status(self, value, packed_status):
        """update value and status"""
        if value is None:
            self.status = [self.Status.ERROR, 'invalid value']
            return
        self.value = round(value * 1e-4, 7)
        status_code = (packed_status >> 4) & 0xf
        status = self.STATUS_MAP[status_code]
        now = time.time()
        if self._stopped:
            # combine 'stopped' with current status text
            if status[0] == self.Status.IDLE:
                self._stopped = False
            else:
                self.status = [status[0], 'stopped (%s)' % status[1]]
                return
        elif self._last_change:  # there was a change, which is not yet confirmed by hw
            if status_code == 1:  # persistent mode
                # leads are ramping (ppms has no extra status code for this!)
                if now < self._last_change + 30:
                    status = [self.Status.PREPARING, 'ramping leads']
                else:
                    status = [self.Status.WARN, 'timeout when ramping leads']
            elif now > self._last_change + 5:
                self._last_change = 0 # give up waiting for driving
            elif self.isDriving(status) and status != self._status_before_change:
                self._last_change = 0
                self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
            else:
                status = [self.Status.BUSY, 'changed target']
        self.status = status

    def analyze_field(self, target, ramp, approachmode, persistentmode):
        if (target, ramp, approachmode, persistentmode) == self._last_settings:
            # we update parameters only on change, as 'ramp' and 'approachmode' are
            # not always sent to the hardware
            return {}
        self._last_settings = target, ramp, approachmode, persistentmode
        return dict(target=target * 1e-4, ramp=ramp * 6e-3, approachmode=approachmode,
                    persistentmode=persistentmode)

    def change_field(self, change):
        if change.doesInclude('target', 'persistentmode'):
            if change.doesInclude('target'):
                self._last_target = self.target  # save for stop command
            self._stopped = False
            self._last_change = time.time()
            self._status_before_change = list(self.status)
        else:
            # changed ramp or approachmode
            if not self.isDriving():
                return None  # nothing to be written, as this would trigger a ramp up of leads current
        return change.target * 1e+4, change.ramp / 6e-3, change.approachmode, change.persistentmode

    def do_stop(self):
        if not self.isDriving():
            return
        self.status = [self.Status.IDLE, '_stopped']
        self._stopped = True
        if abs(self.value - self.target) > 1e-4:
            # ramping is not yet at end
            if abs(self.value - self._last_target) < 1e-4:
                # ramping has not started yet, use more precise last target instead of current value
                self.target = self.put_settings(self._last_target, 'target')
            else:
                self.target = self.put_settings(self.value, 'target')


class Position(PpmsMixin, Drivable):
    """rotator position"""

    move = CmdHandler('move', 'MOVE?', '%g,%g,%g')
    Status = Drivable.Status
    parameters = {
        'value':
            Override(datatype=FloatRange(unit='deg'), poll=True),
        'target':
            Override(datatype=FloatRange(-720., 720., unit='deg'), handler=move),
        'enabled':
            Parameter('is this channel used?', readonly=False, poll=False,
                      datatype=BoolType(), default=True),
        'speed':
            Parameter('motor speed', readonly=False, handler=move,
                      datatype=FloatRange(0.8, 12, unit='deg/sec')),
        'pollinterval':
            Override(visibility=3),
    }
    STATUS_MAP = {
        0: [Status.ERROR, 'unknown'],
        1: [Status.IDLE, 'at target'],
        5: [Status.BUSY, 'moving'],
        8: [Status.IDLE, 'at limit'],
        9: [Status.IDLE, 'at index'],
        15: [Status.ERROR, 'general failure'],
    }

    channel = 'position'
    _stopped = False
    _last_target = 0
    _last_change = 0  # means no target change is pending

    def update_value_status(self, value, packed_status):
        """update value and status"""
        if not self.enabled:
            self.status = [self.Status.DISABLED, 'disabled']
            return
        if value is None:
            self.status = [self.Status.ERROR, 'invalid value']
            return
        self.value = value
        status = self.STATUS_MAP[(packed_status >> 12) & 0xf]
        if self._stopped:
            # combine 'stopped' with current status text
            if status[0] == self.Status.IDLE:
                self._stopped = False
            else:
                status = [self.Status.IDLE, 'stopped(%s)' % status[1]]
        if self._last_change:  # there was a change, which is not yet confirmed by hw
            now = time.time()
            if now > self._last_change + 5:
                self._last_change = 0  # give up waiting for busy
            elif self.isDriving() and status != self._status_before_change:
                self._last_change = 0
                self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
            else:
                status = [self.Status.BUSY, 'changed target']
        self.status = status

    def analyze_move(self, target, mode, speed):
        if (target, speed) == self._last_settings:
            # we update parameters only on change, as 'speed' is
            # not always sent to the hardware
            return {}
        self._last_settings = target, speed
        return dict(target=target, speed=(15 - speed) * 0.8)

    def change_move(self, change):
        speed = int(round(min(14, max(0, 15 - change.speed / 0.8)), 0))
        return change.target, 0, speed

    def write_target(self, target):
        self._last_target = self.target  # save for stop command
        self._stopped = False
        self._last_change = 0
        self._status_before_change = self.status
        return target

    def write_speed(self, value):
        if self.isDriving():
            return value
        return None  # change_move not called: as this would trigger an unnecessary move

    def do_stop(self):
        if not self.isDriving():
            return
        self.status = [self.Status.BUSY, '_stopped']
        self._stopped = True
        if abs(self.value - self.target) > 1e-2:
            # moving is not yet at end
            if abs(self.value - self._last_target) < 1e-2:
                # moving has not started yet, use more precise last target instead of current value
                self.target = self.write_target(self._last_target)
            else:
                self.target = self.write_target(self.value)
