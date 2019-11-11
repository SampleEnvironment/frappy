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
Polling of module settings is using the same poller (secop.Poller is checking iodev).
Only the hidden (not exported) parameter 'settings' is polled, all the others are updated
by read_settings. The modules parameters related to the settings are updated only on change.
This allows for example for the field module to buffer ramp and approachmode until the
next target or persistent_mode change happens, because sending the common command for
settings and target would do a useless cycle of ramping up leads, heating switch etc.
"""

import time
import threading
import json

from secop.modules import Module, Readable, Drivable, Parameter, Override,\
    Communicator, Property
from secop.datatypes import EnumType, FloatRange, IntRange, StringType,\
    BoolType, StatusType
from secop.lib.enum import Enum
from secop.errors import HardwareError
from secop.poller import Poller

try:
    import secop_psi.ppmswindows as ppmshw
except ImportError:
    import secop_psi.ppmssim as ppmshw


def isDriving(status):
    """moving towards target"""
    return 300 <= status[0] < 390

class Main(Communicator):
    """general ppms dummy module"""

    parameters = {
        'pollinterval': Parameter('poll interval', readonly=False,
                                  datatype=FloatRange(), default=2),
        'communicate':  Override('GBIP command'),
        'data':         Parameter('internal', poll=True, export=True, # export for test only
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
        mask = 1 # always get packed_status
        for channelname, channel in self.modules.items():
            if channel.enabled:
                mask |= 1 << self._channel_to_index.get(channelname, 0)
        # send, read and convert to floats and ints
        data = self.do_communicate('GETDAT? %d' % mask)
        reply = data.split(',')
        mask = int(reply.pop(0))
        reply.pop(0) # pop timestamp
        result = {}
        for bitpos, channelname in enumerate(self._channel_names):
            if mask & (1 << bitpos):
                result[channelname] = float(reply.pop(0))
        if 'temp' in result:
            result['tv'] = result['temp']
        if 'ts' in result:
            result['temp'] = result['ts']
        packed_status = int(result['packed_status'])
        result['chamber'] = None # 'chamber' must be in result for status, but value is ignored
        for channelname, channel in self.modules.items():
            channel.update_value_status(result.get(channelname, None), packed_status)
        return data # return data as string


class PpmsMixin(Module):
    properties = {
        'iodev':
            Property('attached communicator module',
                     datatype=StringType(), export=False, default=''),
    }
    parameters = {
        'settings':
            Parameter('internal', export=False, poll=True, readonly=False,
                      default="", datatype=StringType()),
    }

    pollerClass = Poller
    enabled = True # default, if no parameter enable is defined
    STATUS_MAP = {} # a mapping converting ppms status codes into SECoP status values
    _settingnames = [] # names of the parameters in the settings command
    _last_target_change = 0
    slow_pollfactor = 1

    def initModule(self):
        self._main = self.DISPATCHER.get_module(self.iodev)
        self._main.register(self)

    def startModule(self, started_callback):
        # no polls except on main module
        started_callback()

    def send_cmd(self, writecmd, argdict):
        self._main.do_communicate(writecmd + ' ' +
                                  ','.join('%.7g' % argdict[key] for key in self._settingnames))

    def get_reply(self, settings, query):
        """return a dict with the values get from the reply

        if the reply has not changed, an empty dict is returned
        """
        reply = self._main.do_communicate(query)
        if getattr(self, settings) == reply:
            return {}
        setattr(self, settings, reply)
        return dict(zip(self._settingnames, json.loads('[%s]' % reply)))

    def apply_reply(self, reply, pname):
        """apply reply dict to the parameters

        except for reply[pname], which is returned
        """
        returnvalue = getattr(self, pname)
        for key, value in reply.items():
            if key == pname:
                returnvalue = value
            else:
                setattr(self, key, value)
        return returnvalue

    def make_argdict(self, pname, value):
        """make a dict from the parameters self._settingnames

        but result[pname] replaced by value
        """
        return {key: value if key == pname else getattr(self, key) for key in self._settingnames}

    def read_settings(self):
        return self.get_settings('settings')

    def read_value(self):
        """not very useful, as values are updated fast enough

        note: this will update all values, and the value of this module twice
        """
        self._main.read_data()
        return self.value

    def read_status(self):
        """not very useful, as status is updated fast enough

        note: this will update the status of all modules, and this module twice
        """
        self._main.read_data()
        return self.status

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
            Override('main value of channels', poll=False, default=0),
        'status':
            Override(poll=False),
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
    parameters = {
        'current':
            Parameter('driver current', readonly=False, poll=False,
                      datatype=FloatRange(0., 5000., unit='uA'), default=0),
        'powerlimit':
            Parameter('power limit', readonly=False, poll=False,
                      datatype=FloatRange(0., 1000., unit='uW'), default=0),
        'pollinterval':
            Override(visibility=3),
    }

    _settingnames = ['no', 'current', 'powerlimit']

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        reply = self.get_reply('settings', 'DRVOUT? %d' % self.no)
        if reply:
            if self.no != reply.pop('no'):
                raise HardwareError('DRVOUT command: channel number in reply does not match')
        return self.apply_reply(reply, pname)

    def put_settings(self, value, pname):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        self.send_cmd('DRVOUT', self.make_argdict(pname, value))
        return self.get_settings(pname)

    def read_current(self):
        return self.get_settings('current')

    def read_powerlimit(self):
        return self.get_settings('powerlimit')

    def write_settings(self):
        return self.get_settings('settings')

    def write_current(self, value):
        return self.put_settings(value, 'current')

    def write_powerlimit(self, value):
        return self.put_settings(value, 'powerlimit')


class BridgeChannel(Channel):
    # pylint: disable=invalid-name
    ReadingMode = Enum('ReadingMode', standard=0, fast=1, highres=2)
    parameters = {
        'excitation':
            Parameter('excitation current', readonly=False, poll=False,
                      datatype=FloatRange(0.01, 5000., unit='uA'), default=0.01),
        'powerlimit':
            Parameter('power limit', readonly=False, poll=False,
                      datatype=FloatRange(0.001, 1000., unit='uW'), default=0.001),
        'dcflag':
            Parameter('True when excitation is DC (else AC)', readonly=False, poll=False,
                      datatype=BoolType(), default=False),
        'readingmode':
            Parameter('reading mode', readonly=False, poll=False,
                      datatype=EnumType(ReadingMode), default=ReadingMode.standard),
        'voltagelimit':
            Parameter('voltage limit', readonly=False, poll=False,
                      datatype=FloatRange(0.0001, 100., unit='mV'), default=0.0001),
        'pollinterval':
            Override(visibility=3),
    }

    _settingnames = ['no', 'excitation', 'powerlimit', 'dcflag', 'readingmode', 'voltagelimit']

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        reply = self.get_reply('settings', 'BRIDGE? %d' % self.no)
        if reply:
            if self.no != reply['no']:
                raise HardwareError('BRIDGE command: channel number in reply does not match')
            reply['enabled'] = 1
            if reply['excitation'] == 0:
                reply['excitation'] = self.excitation
                reply['enabled'] = 0
            if reply['powerlimit'] == 0:
                reply['powerlimit'] = self.powerlimit
                reply['enabled'] = 0
            if reply['voltagelimit'] == 0:
                reply['voltagelimit'] = self.voltagelimit
                reply['enabled'] = 0
            del reply['no']
        returnvalue = self.apply_reply(reply, pname)
        return returnvalue

    def put_settings(self, value, pname):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        argdict = self.make_argdict(pname, value)
        enabled = value if pname == 'enabled' else self.enabled
        if not enabled:
            argdict['excitation'] = 0
            argdict['powerlimit'] = 0
            argdict['voltagelimit'] = 0
        self.send_cmd('BRIDGE', argdict)
        returnvalue = self.get_settings(pname)
        return returnvalue

    def read_enabled(self):
        return self.get_settings('enabled')

    def read_excitation(self):
        return self.get_settings('excitation')

    def read_powerlimit(self):
        return self.get_settings('powerlimit')

    def read_dcflag(self):
        return self.get_settings('dcflag')

    def read_readingmode(self):
        return self.get_settings('readingmode')

    def read_voltagelimit(self):
        return self.get_settings('voltagelimit')

    def write_settings(self):
        return self.get_settings('settings')

    def write_enabled(self, value):
        return self.put_settings(value, 'enabled')

    def write_excitation(self, value):
        return self.put_settings(value, 'excitation')

    def write_powerlimit(self, value):
        return self.put_settings(value, 'powerlimit')

    def write_dcflag(self, value):
        return self.put_settings(value, 'dcflag')

    def write_readingmode(self, value):
        return self.put_settings(value, 'readingmode')

    def write_voltagelimit(self, value):
        return self.put_settings(value, 'voltagelimit')


class Level(PpmsMixin, Readable):
    """helium level"""

    parameters = {
        'value':  Override(datatype=FloatRange(unit='%'), poll=False, default=0),
        'status': Override(poll=False),
        'pollinterval':
            Override(visibility=3),
    }

    channel = 'level'
    _settingnames = ['value', 'status']

    def update_value_status(self, value, packed_status):
        """must be a no-op

        when called from Main.read_data, value is always None
        value and status is polled via settings
        """

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        reply = self.get_reply('settings', 'LEVEL?')
        if reply:
            if reply['status']:
                reply['status'] = [self.Status.IDLE, '']
            else:
                reply['status'] = [self.Status.ERROR, 'old reading']
        return self.apply_reply(reply, pname)

    def read_value(self):
        return self.get_settings('value')

    def read_status(self):
        return self.get_settings('status')


class Chamber(PpmsMixin, Drivable):
    """sample chamber handling

    value is an Enum, which is redundant with the status text
    """

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
            Override(description='chamber state', poll=False,
                     datatype=EnumType(StatusCode), default='unknown'),
        'status':
            Override(poll=False),
        'target':
            Override(description='chamber command', poll=True,
                     datatype=EnumType(Operation), default=Operation.noop),
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
    _settingnames = ['target']

    def update_value_status(self, value, packed_status):
        """update value and status"""
        self.value = (packed_status >> 8) & 0xf
        self.status = self.STATUS_MAP[self.value]

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        reply = self.get_reply('settings', 'CHAMBER?')
        return self.apply_reply(reply, pname)

    def put_settings(self, value, pname):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        self.send_cmd('CHAMBER', self.make_argdict(pname, value))
        return self.get_settings(pname)

    def read_target(self):
        return self.get_settings('target')

    def write_target(self, value):
        if value == self.Operation.noop:
            return value
        return self.put_settings(value, 'target')


class Temp(PpmsMixin, Drivable):
    """temperature"""

    Status = Enum(Drivable.Status,
        RAMPING = 370,
        STABILIZING = 380,
    )
    # pylint: disable=invalid-name
    ApproachMode = Enum('ApproachMode', fast_settle=0, no_overshoot=1)
    parameters = {
        'value':
            Override(datatype=FloatRange(unit='K'), poll=False, default=0),
        'status':
            Override(poll=False, datatype=StatusType(Status)),
        'target':
            Override(datatype=FloatRange(1.7, 402.0, unit='K'), default=295, poll=False),
        'ramp':
            Parameter('ramping speed', readonly=False, poll=False,
                      datatype=FloatRange(0, 20, unit='K/min'), default=0.1),
        'approachmode':
            Parameter('how to approach target!', readonly=False, poll=False,
                      datatype=EnumType(ApproachMode), default=0),
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
        2: [Status.RAMPING, 'changing'],
        5: [Status.STABILIZING, 'within tolerance'],
        6: [Status.STABILIZING, 'outside tolerance'],
        10: [Status.WARN, 'standby'],
        13: [Status.WARN, 'control disabled'],
        14: [Status.ERROR, 'can not complete'],
        15: [Status.ERROR, 'general failure'],
    }

    channel = 'temp'
    _settingnames = ['target', 'ramp', 'approachmode']
    _stopped = False
    _expected_target = 0
    _last_change = 0 # 0 means no target change is pending

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
        if self._last_change: # there was a change, which is not yet confirmed by hw
            if isDriving(status):
                if now > self._last_change + 15 or status != self._status_before_change:
                    self._last_change = 0
                    self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
            else:
                if now < self._last_change + 15:
                    status = [self.Status.BUSY, 'changed target while %s' % status[1]]
                else:
                    status = [self.Status.WARN, 'temperature status (%r) does not change to BUSY' % status]
        if self._expected_target:
            # handle timeout
            if isDriving(status):
                if now > self._expected_target + self.timeout:
                    self.status = [self.Status.WARN, 'timeout while %s' % status[1]]
                    return
            else:
                self._expected_target = 0
        self.status = status

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        return self.apply_reply(self.get_reply('settings', 'TEMP?'), pname)

    def put_settings(self, value, pname):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        self.send_cmd('TEMP', self.make_argdict(pname, value))
        return self.get_settings(pname)

    def read_target(self):
        return self.get_settings('target')

    def read_ramp(self):
        return self.get_settings('ramp')

    def read_approachmode(self):
        return self.get_settings('approachmode')

    def write_settings(self):
        return self.get_settings('settings')

    def calc_expected(self, target, ramp):
        self._expected_target = time.time() + abs(target - self.value) * 60.0 / max(0.1, ramp)

    def write_target(self, target):
        self._stopped = False
        if abs(self.value - target) < 2e-5 and target == self.target:
            return target # no action needed
        self._status_before_change = self.status
        self.status = [self.Status.BUSY, 'changed_target']
        self._last_change = time.time()
        newtarget = self.put_settings(target, 'target')
        self.calc_expected(target, self.ramp)
        return newtarget

    def write_ramp(self, value):
        if not isDriving(self.status):
            # do not yet write settings, as this may change the status to busy
            return value
        if time.time() < self._expected_target: # recalc expected target
            self.calc_expected(self.target, value)
        return self.put_settings(value, 'ramp')

    def write_approachmode(self, value):
        if not isDriving(self.status):
            # do not yet write settings, as this may change the status to busy
            return value
        return self.put_settings(value, 'approachmode')

    def do_stop(self):
        if not isDriving(self.status):
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

    Status = Enum(Drivable.Status,
        PREPARED = 150,
        PREPARING = 340,
        RAMPING = 370,
        FINALIZING = 390,
    )
    # pylint: disable=invalid-name
    PersistentMode = Enum('PersistentMode', persistent = 0, driven = 1)
    ApproachMode = Enum('ApproachMode', linear=0, no_overshoot=1, oscillate=2)

    parameters = {
        'value':
            Override(datatype=FloatRange(unit='T'), poll=False, default=0),
        'status':
            Override(poll=False, datatype=StatusType(Status)),
        'target':
            Override(datatype=FloatRange(-15,15,unit='T'), poll=False),
        'ramp':
            Parameter('ramping speed', readonly=False, poll=False,
                      datatype=FloatRange(0.064, 1.19, unit='T/min'), default=0.064),
        'approachmode':
            Parameter('how to approach target', readonly=False, poll=False,
                      datatype=EnumType(ApproachMode), default=0),
        'persistentmode':
            Parameter('what to do after changing field', readonly=False, poll=False,
                      datatype=EnumType(PersistentMode), default=0),
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
    _settingnames = ['target', 'ramp', 'approachmode', 'persistentmode']
    _stopped = False
    _last_target = 0
    _last_change= 0 # means no target change is pending

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
        elif self._last_change: # there was a change, which is not yet confirmed by hw
            if status_code == 1: # persistent mode
                # leads are ramping (ppms has no extra status code for this!)
                if now < self._last_change + 30:
                    status = [self.Status.PREPARING, 'ramping leads']
                else:
                    status = [self.Status.WARN, 'timeout when ramping leads']
            elif isDriving(status):
                if now > self._last_change + 5 or status != self._status_before_change:
                    self._last_change = 0
                    self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
            else:
                if now < self._last_change + 5:
                    status = [self.Status.BUSY, 'changed target while %s' % status[1]]
                else:
                    status = [self.Status.WARN, 'field status (%r) does not change to BUSY' % status]


        self.status = status

    def _start(self):
        """common code for change target and change persistentmode"""
        self._last_change = time.time()
        self._status_before_change = list(self.status)

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        reply = self.get_reply('settings', 'FIELD?')
        if reply:
            reply['target'] *= 1e-4
            reply['ramp'] *= 6e-3
        return self.apply_reply(reply, pname)

    def put_settings(self, value, pname):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        argdict = self.make_argdict(pname, value)
        argdict['target'] *= 1e+4
        argdict['ramp'] /= 6e-3
        self.send_cmd('FIELD', argdict)
        return self.get_settings(pname)

    def read_target(self):
        return self.get_settings('target')

    def read_ramp(self):
        return self.get_settings('ramp')

    def read_approachmode(self):
        return self.get_settings('approachmode')

    def read_persistentmode(self):
        return self.get_settings('persistentmode')

    def write_settings(self):
        return self.get_settings('settings')

    def write_target(self, target):
        self._last_target = self.target # save for stop command
        self._stopped = False
        if abs(self.value - target) < 2e-5 and target == self.target:
            return target # no action needed
        self._start()
        result = self.put_settings(target, 'target')
        self._main.read_data() # update status
        return result

    def write_ramp(self, value):
        if not isDriving(self.status):
            # do not yet write settings, as this will trigger a ramp up of leads current
            return value
        return self.put_settings(value, 'ramp')

    def write_approachmode(self, value):
        if not isDriving(self.status):
            # do not yet write settings, as this will trigger a ramp up of leads current
            return value
        return self.put_settings(value, 'approachmode')

    def write_persistentmode(self, value):
        if self.persistentmode == value:
            return value # no action needed
        self._start()
        return self.put_settings(value, 'persistentmode')

    def do_stop(self):
        if not isDriving(self.status):
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

    Status = Drivable.Status
    parameters = {
        'value':
            Override(datatype=FloatRange(unit='deg'), poll=False, default=0),
        'status':
            Override(poll=False),
        'target':
            Override(datatype=FloatRange(-720., 720., unit='deg'), default=0., poll=False),
        'enabled':
            Parameter('is this channel used?', readonly=False, poll=False,
                      datatype=BoolType(), default=True),
        'speed':
            Parameter('motor speed', readonly=False, poll=False,
                      datatype=FloatRange(0.8, 12, unit='deg/sec'), default=12.0),
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
    _settingnames = ['target', 'mode', 'speed']
    _stopped = False
    _last_target = 0
    _last_change = 0 # means no target change is pending
    mode = 0 # always use normal mode

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
        if self._last_change: # there was a change, which is not yet confirmed by hw
            now = time.time()
            if isDriving(status):
                if now > self._last_change + 15 or status != self._status_before_change:
                    self._last_change = 0
                    self.log.debug('time needed to change to busy: %.3g', now - self._last_change)
            else:
                if now < self._last_change + 15:
                    status = [self.Status.BUSY, 'changed target while %s' % status[1]]
                else:
                    status = [self.Status.WARN, 'temperature status (%r) does not change to BUSY' % status]
        self.status = status

    def get_settings(self, pname):
        """read settings

        return the value for <pname> and update all other parameters
        """
        reply = self.get_reply('settings', 'MOVE?')
        if reply:
            reply['speed'] = (15 - reply['speed']) * 0.8
            reply.pop('mode', None)
        return self.apply_reply(reply, pname)

    def put_settings(self, value, pname):
        """write settings, combining <pname>=<value> and current attributes

        and request updated settings
        """
        argdict = self.make_argdict(pname, value)
        argdict['speed'] = int(round(min(14, max(0, 15 - argdict['speed'] / 0.8)), 0))
        self.send_cmd('MOVE', argdict)
        return self.get_settings(pname)

    def read_target(self):
        return self.get_settings('target')

    def read_speed(self):
        return self.get_settings('speed')

    def write_settings(self):
        return self.get_settings('settings')

    def write_target(self, value):
        self._last_target = self.target # save for stop command
        self._stopped = False
        self._last_change = 0
        self._status_before_change = self.status
        return self.put_settings(value, 'target')

    def write_speed(self, value):
        if not isDriving(self.status):
            return value
        return self.put_settings(value, 'speed')

    def do_stop(self):
        if not isDriving(self.status):
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
