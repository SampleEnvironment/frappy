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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

# This is based upon the entangle-nicos integration
"""This module contains the MLZ SECoP - TANGO integration.

Here we support devices which fulfill the official
MLZ TANGO interface for the respective device classes.
"""
from __future__ import division

import re
from time import sleep, time as currenttime
import threading

import PyTango

from secop.lib import lazy_property
from secop.protocol import status

from secop.datatypes import IntRange, FloatRange, StringType, TupleOf, \
    ArrayOf, EnumType
from secop.errors import ConfigError, ProgrammingError, CommunicationError, \
    HardwareError
from secop.modules import Param, Command, Override, Module, Readable, Drivable

#####


# Only export these classes for 'from secop_mlz import *'
__all__ = [
    'AnalogInput', 'Sensor',
    'AnalogOutput', 'Actuator', 'Motor',
    'TemperatureController', 'PowerSupply',
    'DigitalInput', 'NamedDigitalInput', 'PartialDigitalInput',
    'DigitalOutput', 'NamedDigitalOutput', 'PartialDigitalOutput',
    'StringIO',
]

EXC_MAPPING = {
    PyTango.CommunicationFailed: CommunicationError,
    PyTango.WrongNameSyntax: ConfigError,
    PyTango.DevFailed: HardwareError,
}

REASON_MAPPING = {
    'Entangle_ConfigurationError': ConfigError,
    'Entangle_WrongAPICall': ProgrammingError,
    'Entangle_CommunicationFailure': CommunicationError,
    'Entangle_InvalidValue': ValueError,
    'Entangle_ProgrammingError': ProgrammingError,
    'Entangle_HardwareFailure': HardwareError,
}

# Tango DevFailed reasons that should not cause a retry
FATAL_REASONS = set((
    'Entangle_ConfigurationError',
    'Entangle_UnrecognizedHardware',
    'Entangle_WrongAPICall',
    'Entangle_InvalidValue',
    'Entangle_NotSupported',
    'Entangle_ProgrammingError',
    'DB_DeviceNotDefined',
    'API_DeviceNotDefined',
    'API_CantConnectToDatabase',
    'API_TangoHostNotSet',
    'API_ServerNotRunning',
    'API_DeviceNotExported',
))


def describe_dev_error(exc):
    """Return a better description for a Tango exception.

    Most Tango exceptions are quite verbose and not suitable for user
    consumption.  Map the most common ones, that can also happen during normal
    operation, to a bit more friendly ones.
    """
    # general attributes
    reason = exc.reason.strip()
    fulldesc = reason + ': ' + exc.desc.strip()
    # reduce Python tracebacks
    if '\n' in exc.origin and 'File ' in exc.origin:
        origin = exc.origin.splitlines()[-2].strip()
    else:
        origin = exc.origin.strip()

    # we don't need origin info for Tango itself
    if origin.startswith(('DeviceProxy::', 'DeviceImpl::', 'Device_3Impl::',
                          'Device_4Impl::', 'Connection::', 'TangoMonitor::')):
        origin = None

    # now handle specific cases better
    if reason == 'API_AttrNotAllowed':
        m = re.search(r'to (read|write) attribute (\w+)', fulldesc)
        if m:
            if m.group(1) == 'read':
                fulldesc = 'reading %r not allowed in current state'
            else:
                fulldesc = 'writing %r not allowed in current state'
            fulldesc %= m.group(2)
    elif reason == 'API_CommandNotAllowed':
        m = re.search(r'Command (\w+) not allowed when the '
                      r'device is in (\w+) state', fulldesc)
        if m:
            fulldesc = 'executing %r not allowed in state %s' \
                % (m.group(1), m.group(2))
    elif reason == 'API_DeviceNotExported':
        m = re.search(r'Device ([\w/]+) is not', fulldesc)
        if m:
            fulldesc = 'Tango device %s is not exported, is the server ' \
                'running?' % m.group(1)
    elif reason == 'API_CorbaException':
        if 'TRANSIENT_CallTimedout' in fulldesc:
            fulldesc = 'Tango client-server call timed out'
        elif 'TRANSIENT_ConnectFailed' in fulldesc:
            fulldesc = 'connection to Tango server failed, is the server ' \
                'running?'
    elif reason == 'API_CantConnectToDevice':
        m = re.search(r'connect to device ([\w/]+)', fulldesc)
        if m:
            fulldesc = 'connection to Tango device %s failed, is the server ' \
                'running?' % m.group(1)
    elif reason == 'API_CommandTimedOut':
        if 'acquire serialization' in fulldesc:
            fulldesc = 'Tango call timed out waiting for lock on server'

    # append origin if wanted
    if origin:
        fulldesc += ' in %s' % origin
    return fulldesc


class PyTangoDevice(Module):
    """
    Basic PyTango device.

    The PyTangoDevice uses an internal PyTango.DeviceProxy but wraps command
    execution and attribute operations with logging and exception mapping.
    """

    parameters = {
        'comtries': Param('Maximum retries for communication',
                          datatype=IntRange(1, 100), default=3, readonly=False,
                          group='communication'),
        'comdelay': Param('Delay between retries', datatype=FloatRange(0),
                          unit='s', default=0.1, readonly=False,
                          group='communication'),

        'tangodevice': Param('Tango device name',
                             datatype=StringType(), readonly=True,
                             # export=True,   # for testing only
                             export=False,
                             ),
    }

    tango_status_mapping = {
        PyTango.DevState.ON: status.OK,
        PyTango.DevState.ALARM: status.WARN,
        PyTango.DevState.OFF: status.ERROR,
        PyTango.DevState.FAULT: status.ERROR,
        PyTango.DevState.MOVING: status.BUSY,
    }

    @lazy_property
    def _com_lock(self):
        return threading.Lock()

    def _com_retry(self, info, function, *args, **kwds):
        """Try communicating with the hardware/device.

        Parameter "info" is passed to _com_return and _com_raise methods that
        process the return value or exception raised after maximum tries.
        """
        tries = self.comtries
        with self._com_lock:
            while True:
                tries -= 1
                try:
                    result = function(*args, **kwds)
                    return self._com_return(result, info)
                except Exception as err:
                    if tries == 0:
                        self._com_raise(err, info)
                    else:
                        name = getattr(function, '__name__', 'communication')
                        self._com_warn(tries, name, err, info)
                    sleep(self.comdelay)

    def init(self):
        # Wrap PyTango client creation (so even for the ctor, logging and
        # exception mapping is enabled).
        self._createPyTangoDevice = self._applyGuardToFunc(
            self._createPyTangoDevice, 'constructor')
        super(PyTangoDevice, self).init()

    @lazy_property
    def _dev(self):
        # for startup be very permissive, wait up to 15 min per device
        settings = self.comdelay, self.comtries
        self.comdelay, self.comtries = 10, 90
        res = self._createPyTangoDevice(self.tangodevice)
        self.comdelay, self.comtries = settings
        return res

    def _hw_wait(self):
        """Wait until hardware status is not BUSY."""
        while self.read_status(0)[0] == 'BUSY':
            sleep(0.3)

    def _getProperty(self, name, dev=None):
        """
        Utility function for getting a property by name easily.
        """
        if dev is None:
            dev = self._dev
        # Entangle and later API
        if dev.command_query('GetProperties').in_type == PyTango.DevVoid:
            props = dev.GetProperties()
            return props[props.index(name) + 1] if name in props else None
        # old (pre-Entangle) API
        return dev.GetProperties([name, 'device'])[2]

    def _createPyTangoDevice(self, address):  # pylint: disable=E0202
        """
        Creates the PyTango DeviceProxy and wraps command execution and
        attribute operations with logging and exception mapping.
        """
        device = PyTango.DeviceProxy(address)
        # detect not running and not exported devices early, because that
        # otherwise would lead to attribute errors later
        try:
            device.State
        except AttributeError:
            raise CommunicationError(
                self, 'connection to Tango server failed, '
                'is the server running?')
        return self._applyGuardsToPyTangoDevice(device)

    def _applyGuardsToPyTangoDevice(self, dev):
        """
        Wraps command execution and attribute operations of the given
        device with logging and exception mapping.
        """
        dev.command_inout = self._applyGuardToFunc(dev.command_inout)
        dev.write_attribute = self._applyGuardToFunc(dev.write_attribute,
                                                     'attr_write')
        dev.read_attribute = self._applyGuardToFunc(dev.read_attribute,
                                                    'attr_read')
        dev.attribute_query = self._applyGuardToFunc(dev.attribute_query,
                                                     'attr_query')
        return dev

    def _applyGuardToFunc(self, func, category='cmd'):
        """
        Wrap given function with logging and exception mapping.
        """
        def wrap(*args, **kwds):
            # handle different types for better debug output
            if category == 'cmd':
                self.log.debug('[PyTango] command: %s%r', args[0], args[1:])
            elif category == 'attr_read':
                self.log.debug('[PyTango] read attribute: %s', args[0])
            elif category == 'attr_write':
                self.log.debug('[PyTango] write attribute: %s => %r',
                               args[0], args[1:])
            elif category == 'attr_query':
                self.log.debug('[PyTango] query attribute properties: %s',
                               args[0])
            elif category == 'constructor':
                self.log.debug('[PyTango] device creation: %s', args[0])
            elif category == 'internal':
                self.log.debug('[PyTango integration] internal: %s%r',
                               func.__name__, args)
            else:
                self.log.debug('[PyTango] call: %s%r', func.__name__, args)

            info = category + ' ' + args[0] if args else category
            return self._com_retry(info, func, *args, **kwds)

        # hide the wrapping
        wrap.__name__ = func.__name__

        return wrap

    def _com_return(self, result, info):
        """Process *result*, the return value of communication.

        Can raise an exception to initiate a retry.  Default is to return
        result unchanged.
        """
        # XXX: explicit check for loglevel to avoid expensive reprs
        if isinstance(result, PyTango.DeviceAttribute):
            the_repr = repr(result.value)[:300]
        else:
            # This line explicitly logs '=> None' for commands which
            # does not return a value. This indicates that the command
            # execution ended.
            the_repr = repr(result)[:300]
        self.log.debug('\t=> %s', the_repr)
        return result

    def _tango_exc_desc(self, err):
        exc = str(err)
        if err.args:
            exc = err.args[0]  # Can be str or DevError
            if isinstance(exc, PyTango.DevError):
                return describe_dev_error(exc)
        return exc

    def _tango_exc_reason(self, err):
        if err.args and isinstance(err.args[0], PyTango.DevError):
            return err.args[0].reason.strip()
        return ''

    def _com_warn(self, retries, name, err, info):
        """Gives the opportunity to warn the user on failed tries.

        Can also call _com_raise to abort early.
        """
        if self._tango_exc_reason(err) in FATAL_REASONS:
            self._com_raise(err, info)
        if retries == self.comtries - 1:
            self.log.warning('%s failed, retrying up to %d times: %s',
                             info, retries, self._tango_exc_desc(err))

    def _com_raise(self, err, info):
        """Process the exception raised either by communication or _com_return.

        Should raise a NICOS exception.  Default is to raise
        CommunicationError.
        """
        reason = self._tango_exc_reason(err)
        exclass = REASON_MAPPING.get(
            reason, EXC_MAPPING.get(type(err), CommunicationError))
        fulldesc = self._tango_exc_desc(err)
        self.log.debug('PyTango error: %s', fulldesc)
        raise exclass(self, fulldesc)

    def read_status(self, maxage=0):
        # Query status code and string
        tangoState = self._dev.State()
        tangoStatus = self._dev.Status()

        # Map status
        myState = self.tango_status_mapping.get(tangoState, status.UNKNOWN)

        return (myState, tangoStatus)

    def do_reset(self):
        self._dev.Reset()


class AnalogInput(PyTangoDevice, Readable):
    """
    The AnalogInput handles all devices only delivering an analogue value.
    """

    def late_init(self):
        super(AnalogInput, self).late_init()
        # query unit from tango and update value property
        attrInfo = self._dev.attribute_query('value')
        # prefer configured unit if nothing is set on the Tango device, else
        # update
        if attrInfo.unit != 'No unit':
            self.parameters['value'].unit = attrInfo.unit

    def read_value(self, maxage=0):
        return self._dev.value


class Sensor(AnalogInput):
    """
    The sensor interface describes all analog read only devices.

    The difference to AnalogInput is that the “value” attribute can be
    converted from the “raw value” to a physical value with an offset and a
    formula.
    """
    # note: we don't transport the formula to secop....
    #       we support the adjust method

    commands = {
        'setposition': Command('Set the position to the given value.',
                               arguments=[FloatRange()], result=None,
                               ),
    }

    def do_setposition(self, value):
        self._dev.Adjust(value)


class AnalogOutput(PyTangoDevice, Drivable):
    """The AnalogOutput handles all devices which set an analogue value.

    The main application field is the output of any signal which may be
    considered as continously in a range. The values may have nearly any
    value between the limits. The compactness is limited by the resolution of
    the hardware.

    This class should be considered as a base class for motors, temperature
    controllers, ...
    """

    parameters = {
        'userlimits': Param('User defined limits of device value',
                            datatype=TupleOf(FloatRange(), FloatRange()),
                            default=(float('-Inf'), float('+Inf')),
                            unit='main', readonly=False, poll=10,
                            ),
        'abslimits': Param('Absolute limits of device value',
                           datatype=TupleOf(FloatRange(), FloatRange()),
                           unit='main',
                           ),
        'precision': Param('Precision of the device value (allowed deviation '
                           'of stable values from target)',
                           unit='main', datatype=FloatRange(1e-38),
                           readonly=False, group='stability',
                           ),
        'window': Param('Time window for checking stabilization if > 0',
                        unit='s', default=60.0, readonly=False,
                        datatype=FloatRange(0, 900), group='stability',
                        ),
        'timeout': Param('Timeout for waiting for a stable value (if > 0)',
                         unit='s', default=60.0, readonly=False,
                         datatype=FloatRange(0, 900), group='stability',
                         ),
    }
    _history = ()
    _timeout = None
    _moving = False

    def init(self):
        super(AnalogOutput, self).init()
        # init history
        self._history = []  # will keep (timestamp, value) tuple
        self._timeout = None  # keeps the time at which we will timeout, or None

    def late_init(self):
        super(AnalogOutput, self).late_init()
        # query unit from tango and update value property
        attrInfo = self._dev.attribute_query('value')
        # prefer configured unit if nothing is set on the Tango device, else
        # update
        if attrInfo.unit != 'No unit':
            self.parameters['value'].unit = attrInfo.unit

    def poll(self, nr):
        super(AnalogOutput, self).poll(nr)
        while len(self._history) > 2:
            # if history would be too short, break
            if self._history[-1][0] - self._history[1][0] <= self.window:
                break
            # else: remove a stale point
            self._history.pop(0)

    def read_value(self, maxage=0):
        value = self._dev.value
        self._history.append((currenttime(), value))
        return value

    def read_target(self, maxage=0):
        attrObj = self._dev.read_attribute('value')
        return attrObj.w_value

    def _isAtTarget(self):
        if self.target is None:
            return True  # avoid bootstrapping problems
        if not self._history:
            return False  # no history -> no knowledge
        # check subset of _history which is in window
        # also check if there is at least one value before window
        # to know we have enough datapoints
        hist = self._history[:]
        window_start = currenttime() - self.window
        hist_in_window = [v for (t, v) in hist if t >= window_start]

        max_in_hist = max(hist_in_window)
        min_in_hist = min(hist_in_window)
        stable = max_in_hist - min_in_hist <= 2*self.precision
        at_target = min_in_hist <= self.target <= max_in_hist

        return stable and at_target

    def read_status(self, maxage=0):
        if self._isAtTarget():
            self._timeout = None
            self._moving = False
            return super(AnalogOutput, self).read_status()
        if self._timeout:
            if self._timeout < currenttime():
                return status.UNSTABLE, 'timeout after waiting for stable value'
        return (status.BUSY, 'Moving') if self._moving else (status.OK, 'stable')

    @property
    def absmin(self):
        return self.abslimits[0]

    @property
    def absmax(self):
        return self.abslimits[1]

    def __getusermin(self):
        return self.userlimits[0]

    def __setusermin(self, value):
        self.userlimits = (value, self.userlimits[1])

    usermin = property(__getusermin, __setusermin)

    def __getusermax(self):
        return self.userlimits[1]

    def __setusermax(self, value):
        self.userlimits = (self.userlimits[0], value)

    usermax = property(__getusermax, __setusermax)

    del __getusermin, __setusermin, __getusermax, __setusermax

    def _checkLimits(self, limits):
        umin, umax = limits
        amin, amax = self.abslimits
        if umin > umax:
            raise ValueError(
                self, 'user minimum (%s) above the user '
                'maximum (%s)' % (umin, umax))
        if umin < amin - abs(amin * 1e-12):
            umin = amin
        if umax > amax + abs(amax * 1e-12):
            umax = amax
        return (umin, umax)

    def write_userlimits(self, value):
        return self._checkLimits(value)

    def write_target(self, value=FloatRange()):
        if self.status[0] == status.BUSY:
            # changing target value during movement is not allowed by the
            # Tango base class state machine. If we are moving, stop first.
            self.do_stop()
            self._hw_wait()
        self._dev.value = value
        # set meaningful timeout
        self._timeout = currenttime() + self.window + self.timeout
        if hasattr(self, 'ramp'):
            self._timeout += abs((self.target or self.value) - self.value) / \
                    ((self.ramp or 1e-8) * 60)
        elif hasattr(self, 'speed'):
            self._timeout += abs((self.target or self.value) - self.value) / \
                    (self.speed or 1e-8)
        if not self.timeout:
            self._timeout = None
        self._moving = True
        self._history = []  # clear history
        self.read_status(0)  # poll our status to keep it updated

    def _hw_wait(self):
        while super(AnalogOutput, self).read_status()[0] == status.BUSY:
            sleep(0.3)

    def do_stop(self):
        self._dev.Stop()


class Actuator(AnalogOutput):
    """The aAtuator interface describes all analog devices which DO something
    in a defined way.

    The difference to AnalogOutput is that there is a speed attribute, and the
    value attribute is converted from the “raw value” with a formula and
    offset.
    """
    # for secop: support the speed and ramp parameters

    parameters = {
        'speed': Param('The speed of changing the value',
                       unit='main/s', readonly=False, datatype=FloatRange(0),
                       ),
        'ramp': Param('The speed of changing the value',
                      unit='main/min', readonly=False, datatype=FloatRange(0),
                      poll=30,
                      ),
    }

    commands = {
        'setposition': Command('Set the position to the given value.',
                               arguments=[FloatRange()], result=None,
                               ),
    }

    def read_speed(self, maxage=0):
        return self._dev.speed

    def write_speed(self, value):
        self._dev.speed = value

    def read_ramp(self, maxage=0):
        return self.read_speed() * 60

    def write_ramp(self, value):
        self.write_speed(value / 60.)
        return self.read_speed(0) * 60

    def do_setposition(self, value=FloatRange()):
        self._dev.Adjust(value)


class Motor(Actuator):
    """This class implements a motor device (in a sense of a real motor
    (stepper motor, servo motor, ...)).

    It has the ability to move a real object from one place to another place.
    """

    parameters = {
        'refpos': Param('Reference position',
                        datatype=FloatRange(), unit='main',
                        ),
        'accel': Param('Acceleration',
                       datatype=FloatRange(), readonly=False, unit='main/s^2',
                       ),
        'decel': Param('Deceleration',
                       datatype=FloatRange(), readonly=False, unit='main/s^2',
                       ),
    }

    def read_refpos(self, maxage=0):
        return float(self._getProperty('refpos'))

    def read_accel(self, maxage=0):
        return self._dev.accel

    def write_accel(self, value):
        self._dev.accel = value

    def read_decel(self, maxage=0):
        return self._dev.decel

    def write_decel(self, value):
        self._dev.decel = value

    def do_reference(self):
        self._dev.Reference()
        return self.read_value()


class TemperatureController(Actuator):
    """A temperature control loop device.
    """

    parameters = {
        'p': Param('Proportional control Parameter', datatype=FloatRange(),
                   readonly=False, group='pid',
                   ),
        'i': Param('Integral control Parameter', datatype=FloatRange(),
                   readonly=False, group='pid',
                   ),
        'd': Param('Derivative control Parameter', datatype=FloatRange(),
                   readonly=False, group='pid',
                   ),
        'pid': Param('pid control Parameters',
                     datatype=TupleOf(FloatRange(), FloatRange(), FloatRange()),
                     readonly=False, group='pid', poll=30,
                     ),
        'setpoint': Param('Current setpoint', datatype=FloatRange(), poll=1,
                          ),
        'heateroutput': Param('Heater output', datatype=FloatRange(), poll=1,
                              ),
        'ramp': Param('Temperature ramp', unit='main/min',
                      datatype=FloatRange(), readonly=False, poll=30),
    }

    overrides = {
        # We want this to be freely user-settable, and not produce a warning
        # on startup, so select a usually sensible default.
        'precision': Override(default=0.1),
    }

    def read_ramp(self, maxage=0):
        return self._dev.ramp

    def write_ramp(self, value):
        self._dev.ramp = value
        return self._dev.ramp

    def read_p(self, maxage=0):
        return self._dev.p

    def write_p(self, value):
        self._dev.p = value

    def read_i(self, maxage=0):
        return self._dev.i

    def write_i(self, value):
        self._dev.i = value

    def read_d(self, maxage=0):
        return self._dev.d

    def write_d(self, value):
        self._dev.d = value

    def read_pid(self, maxage=0):
        self.read_p()
        self.read_i()
        self.read_d()
        return self.p, self.i, self.d

    def write_pid(self, value):
        self._dev.p = value[0]
        self._dev.i = value[1]
        self._dev.d = value[2]

    def read_setpoint(self, maxage=0):
        return self._dev.setpoint

    def read_heateroutput(self, maxage=0):
        return self._dev.heaterOutput


class PowerSupply(Actuator):
    """A power supply (voltage and current) device.
    """

    parameters = {
        'ramp': Param('Current/voltage ramp', unit='main/min',
                      datatype=FloatRange(), readonly=False, poll=30,),
        'voltage': Param('Actual voltage', unit='V',
                         datatype=FloatRange(), poll=-5),
        'current': Param('Actual current', unit='A',
                         datatype=FloatRange(), poll=-5),
    }

    def read_ramp(self, maxage=0):
        return self._dev.ramp

    def write_ramp(self, value):
        self._dev.ramp = value

    def read_voltage(self, maxage=0):
        return self._dev.voltage

    def read_current(self, maxage=0):
        return self._dev.current


class DigitalInput(PyTangoDevice, Readable):
    """A device reading a bitfield.
    """

    overrides = {
        'value': Override(datatype=IntRange()),
    }

    def read_value(self, maxage=0):
        return self._dev.value


class NamedDigitalInput(DigitalInput):
    """A DigitalInput with numeric values mapped to names.
    """

    parameters = {
        'mapping': Param('A dictionary mapping state names to integers',
                         datatype=StringType(), export=False),  # XXX:!!!
    }

    def init(self):
        super(NamedDigitalInput, self).init()
        try:
            # pylint: disable=eval-used
            self.parameters['value'].datatype = EnumType(**eval(self.mapping))
        except Exception as e:
            raise ValueError('Illegal Value for mapping: %r' % e)

    def read_value(self, maxage=0):
        value = self._dev.value
        return value  # mapping is done by datatype upon export()


class PartialDigitalInput(NamedDigitalInput):
    """Base class for a TANGO DigitalInput with only a part of the full
    bit width accessed.
    """

    parameters = {
        'startbit': Param('Number of the first bit',
                          datatype=IntRange(0), default=0),
        'bitwidth': Param('Number of bits',
                          datatype=IntRange(0), default=1),
    }

    def init(self):
        super(PartialDigitalInput, self).init()
        self._mask = (1 << self.bitwidth) - 1
        # self.parameters['value'].datatype = IntRange(0, self._mask)

    def read_value(self, maxage=0):
        raw_value = self._dev.value
        value = (raw_value >> self.startbit) & self._mask
        return value  # mapping is done by datatype upon export()


class DigitalOutput(PyTangoDevice, Drivable):
    """A device that can set and read a digital value corresponding to a
    bitfield.
    """

    overrides = {
        'value': Override(datatype=IntRange()),
        'target': Override(datatype=IntRange()),
    }

    def read_value(self, maxage=0):
        return self._dev.value  # mapping is done by datatype upon export()

    def write_target(self, value):
        self._dev.value = value
        self.read_value()

    def read_target(self, maxage=0):
        attrObj = self._dev.read_attribute('value')
        return attrObj.w_value


class NamedDigitalOutput(DigitalOutput):
    """A DigitalOutput with numeric values mapped to names.
    """

    parameters = {
        'mapping': Param('A dictionary mapping state names to integers',
                         datatype=StringType(), export=False),
    }

    def init(self):
        super(NamedDigitalOutput, self).init()
        try:
            # pylint: disable=eval-used
            self.parameters['value'].datatype = EnumType(**eval(self.mapping))
            # pylint: disable=eval-used
            self.parameters['target'].datatype = EnumType(**eval(self.mapping))
        except Exception as e:
            raise ValueError('Illegal Value for mapping: %r' % e)

    def write_target(self, value):
        # map from enum-str to integer value
        self._dev.value = self.parameters[
            'target'].datatype.reversed.get(value, value)
        self.read_value()


class PartialDigitalOutput(NamedDigitalOutput):
    """Base class for a TANGO DigitalOutput with only a part of the full
    bit width accessed.
    """

    parameters = {
        'startbit': Param('Number of the first bit',
                          datatype=IntRange(0), default=0),
        'bitwidth': Param('Number of bits',
                          datatype=IntRange(0), default=1),
    }

    def init(self):
        super(PartialDigitalOutput, self).init()
        self._mask = (1 << self.bitwidth) - 1
        # self.parameters['value'].datatype = IntRange(0, self._mask)
        # self.parameters['target'].datatype = IntRange(0, self._mask)

    def read_value(self, maxage=0):
        raw_value = self._dev.value
        value = (raw_value >> self.startbit) & self._mask
        return value  # mapping is done by datatype upon export()

    def write_target(self, value):
        curvalue = self._dev.value
        newvalue = (curvalue & ~(self._mask << self.startbit)) | \
                   (value << self.startbit)
        self._dev.value = newvalue
        self.read_value()


class StringIO(PyTangoDevice, Module):
    """StringIO abstracts communication over a hardware bus that sends and
    receives strings.
    """

    parameters = {
        'bustimeout': Param('Communication timeout',
                            datatype=FloatRange(), readonly=False,
                            unit='s', group='communication'),
        'endofline': Param('End of line',
                           datatype=StringType(), readonly=False,
                           group='communication'),
        'startofline': Param('Start of line',
                             datatype=StringType(), readonly=False,
                             group='communication'),
    }

    def read_bustimeout(self, maxage=0):
        return self._dev.communicationTimeout

    def write_bustimeout(self, value):
        self._dev.communicationTimeout = value

    def read_endofline(self, maxage=0):
        return self._dev.endOfLine

    def write_endofline(self, value):
        self._dev.endOfLine = value

    def read_startofline(self, maxage=0):
        return self._dev.startOfLine

    def write_startofline(self, value):
        self._dev.startOfLine = value

    commands = {
        'communicate': Command('Send a string and return the reply',
                               arguments=[StringType()],
                               result=StringType()),
        'flush': Command('Flush output buffer',
                         arguments=[], result=None),
        'read': Command('read some characters from input buffer',
                        arguments=[IntRange()], result=StringType()),
        'write': Command('write some chars to output',
                         arguments=[StringType()], result=None),
        'readLine': Command('Read sol - a whole line - eol',
                            arguments=[], result=StringType()),
        'writeLine': Command('write sol + a whole line + eol',
                             arguments=[StringType()], result=None),
        'availablechars': Command('return number of chars in input buffer',
                                  arguments=[], result=IntRange(0)),
        'availablelines': Command('return number of lines in input buffer',
                                  arguments=[], result=IntRange(0)),
        'multicommunicate': Command('perform a sequence of communications',
                                    arguments=[ArrayOf(
                                        TupleOf(StringType(), IntRange()), 100)],
                                    result=ArrayOf(StringType(), 100)),
    }

    def do_communicate(self, value=StringType()):
        return self._dev.Communicate(value)

    def do_flush(self):
        self._dev.Flush()

    def do_read(self, value):
        return self._dev.Read(value)

    def do_write(self, value):
        return self._dev.Write(value)

    def do_readLine(self):
        return self._dev.ReadLine()

    def do_writeLine(self, value):
        return self._dev.WriteLine(value)

    def do_multiCommunicate(self, value):
        return self._dev.MultiCommunicate(value)

    def do_availablechars(self):
        return self._dev.availableChars

    def do_availablelines(self):
        return self._dev.availableLines
