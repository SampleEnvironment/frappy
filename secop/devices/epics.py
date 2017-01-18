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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#   Erik Dahlbäck <erik.dahlback@esss.se>
# *****************************************************************************

import random

from secop.lib.parsing import format_time
from secop.validators import enum, vector, floatrange, validator_to_str
from secop.devices.core import Readable, Device, Driveable, PARAM
from secop.protocol import status

try:
    from pvaccess import Channel #import EPIVSv4 functionallity, PV access
except ImportError:
    class Channel(object):
        def __init__(self, pv_name):
            self.pv_name = pv_name
            self.value = 0.0
        def get(self):
            return self
        def getDouble(self):
            return self.value
        def put(self, value):
            try:
                self.value = value
                self.value = float(value)
            except (TypeError, ValueError):
                pass
try:
    from epics import PV
except ImportError:
    class PV(object):
        def __init__(self, pv_name):
            self.pv_name = pv_name
            self.value = 0.0



class EpicsReadable(Readable):
    """EpicsDriveable handles a Driveable interfacing to EPICS v4"""
    # Commmon PARAMS for all EPICS devices
    PARAMS = {
        'value':         PARAM('EPICS generic value', validator=float,
                               default=300.0,),
        'epics_version': PARAM("EPICS version used, v3 or v4",
                               validator=str,),
        # 'private' parameters: not remotely accessible
        'value_pv':      PARAM('EPICS pv_name of value', validator=str,
                               default="unset", export=False),
        'status_pv':      PARAM('EPICS pv_name of status', validator=str,
                               default="unset", export=False),
    }

    # Generic read and write functions
    def _read_pv(self, pv_name):
        if self.epics_version == 'v4':
            pv_channel = Channel(pv_name)
            # TODO: cannot handle read of string (is there a .getText() or .getString() ?)
            return_value = pv_channel.get().getDouble()
        else: # Not EPICS v4
            # TODO: fix this, it does not work
            pv = PV(pv_name + ".VAL")
            return_value = pv.value
        return return_value

    def _write_pv(self, pv_name, write_value):
        #self.log.info('Write value = %s from EPICS PV = %s' %(write_value, pv_name))
        # try to convert value to float
        try:
            write_value = float(write_value)
        except (TypeError, ValueError):
            # can not convert to float, force to string
            write_value = str(write_value)

        if self.epics_version == 'v4':
            pv_channel = Channel(pv_name)
            pv_channel.put(write_value)
        else: # Not EPICS v4
            pv = PV(pv_name + ".VAL")
            pv.value = write_value

    def read_value(self, maxage=0):
        return self._read_pv(self.value_pv)

    def read_status(self, maxage=0):
        # XXX: comparison may need to be a little unsharp
        # XXX: Hardware may have it's own idea about the status: how to obtain?
        if self.status_pv != 'unset':
            # XXX: how to map an unknown type+value to an valid status ???
            return status.UNKNOWN, self._read_pv(self.status_pv)
        # status_pv is unset
        return (status.OK, 'no pv set')



class EpicsDriveable(Driveable):
    """EpicsDriveable handles a Driveable interfacing to EPICS v4"""
    # Commmon PARAMS for all EPICS devices
    PARAMS = {
        'target':        PARAM('EPICS generic target', validator=float,
                               default=300.0, readonly=False),
        'value':         PARAM('EPICS generic value', validator=float,
                               default=300.0,),
        'epics_version': PARAM("EPICS version used, v3 or v4",
                               validator=str,),
        # 'private' parameters: not remotely accessible
        'target_pv':     PARAM('EPICS pv_name of target', validator=str,
                               default="unset", export=False),
        'value_pv':      PARAM('EPICS pv_name of value', validator=str,
                               default="unset", export=False),
        'status_pv':      PARAM('EPICS pv_name of status', validator=str,
                               default="unset", export=False),
    }

    # Generic read and write functions
    def _read_pv(self, pv_name):
        if self.epics_version == 'v4':
            pv_channel = Channel(pv_name)
            # TODO: cannot handle read of string (is there a .getText() or .getString() ?)
            return_value = pv_channel.get().getDouble()
        else: # Not EPICS v4
            # TODO: fix this, it does not work
            pv = PV(pv_name + ".VAL")
            return_value = pv.value
        return return_value

    def _write_pv(self, pv_name, write_value):
        #self.log.info('Write value = %s from EPICS PV = %s' %(write_value, pv_name))
        # try to convert value to float
        try:
            write_value = float(write_value)
        except (TypeError, ValueError):
            # can not convert to float, force to string
            write_value = str(write_value)

        if self.epics_version == 'v4':
            pv_channel = Channel(pv_name)
            pv_channel.put(write_value)
        else: # Not EPICS v4
            pv = PV(pv_name + ".VAL")
            pv.value = write_value

    def read_target(self, maxage=0):
        return self._read_pv(self.target_pv)

    def write_target(self, write_value):
        self._write_pv(self.target_pv, write_value)

    def read_value(self, maxage=0):
        return self._read_pv(self.value_pv)

    def read_status(self, maxage=0):
        # XXX: comparison may need to be a little unsharp
        # XXX: Hardware may have it's own idea about the status: how to obtain?
        if self.status_pv != 'unset':
            # XXX: how to map an unknown type+value to an valid status ???
            return status.UNKNOWN, self._read_pv(self.status_pv)
        # status_pv is unset, derive status from equality of value + target
        return (status.OK, '') if self.read_value() == self.read_target() else \
               (status.BUSY, 'Moving')



"""Temperature control loop"""
# should also derive from secop.core.temperaturecontroller, once its features are agreed upon
class EpicsTempCtrl(EpicsDriveable):

    PARAMS = {
        # TODO: restrict possible values with oneof validator
        'heaterrange':    PARAM('Heater range', validator=str,
                                default='Off', readonly=False,),
        'tolerance':      PARAM('allowed deviation between value and target',
                                validator=floatrange(1e-6,1e6), default=0.1,
                                readonly=False,),
        # 'private' parameters: not remotely accessible
        'heaterrange_pv': PARAM('EPICS pv_name of heater range',
                                validator=str, default="unset", export=False,),
    }

    def read_target(self, maxage=0):
        return self._read_pv(self.target_pv)

    def write_target(self, write_value):
        # send target to HW
        self._write_pv(self.target_pv, write_value)
        # update our status
        self.read_status()

    def read_value(self, maxage=0):
        return self._read_pv(self.value_pv)

    def read_status(self, maxage=0):
        # XXX: comparison may need to collect a history to detect oscillations
        at_target = abs(self.read_value(maxage) - self.read_target(maxage)) \
                    <= self.tolerance
        return (status.OK, 'at Target') if at_target else (status.BUSY, 'Moving')

    # TODO: add support for strings over epics pv
    #def read_heaterrange(self, maxage=0):
    #    return self._read_pv(self.heaterrange_pv)

    # TODO: add support for strings over epics pv 
    #def write_heaterrange(self, range_value):
    #    self._write_pv(self.heaterrange_pv, range_value)
