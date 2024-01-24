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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

import re

import zapf
import zapf.spec as zspec
from zapf.io import PlcIO
from zapf.scan import Scanner

from frappy.core import BUSY, DISABLED, ERROR, FINALIZING, IDLE, \
    INITIALIZING, STARTING, UNKNOWN, WARN, Attached, Command, Communicator, \
    Drivable, Parameter, Property, Readable
from frappy.datatypes import UNLIMITED, ArrayOf, BLOBType, EnumType, \
    FloatRange, IntRange, StatusType, StringType, ValueType
from frappy.dynamic import Pinata
from frappy.errors import CommunicationFailedError, ImpossibleError, \
    IsBusyError, NoSuchParameterError, ReadOnlyError

# Untested with real hardware, only testplc_2021_09.py


def internalize_name(name):
    return re.sub(r'[^a-zA-Z0-9_]+', '_', name, re.ASCII)


ERROR_MAP = {
    # should not happen. but better to have it here anyway
    5: NoSuchParameterError,
    # if this occurs, something may have gone wrong with digesting the scanner
    # data
    6: ReadOnlyError,
    # Most likely from devices you cannot poll when busy.
    7: IsBusyError,
}


class ZapfPinata(Pinata):
    """The Pinata device for a PLC that can be accessed according to PILS.

    See https://forge.frm2.tum.de/public/doc/plc/master/html/

    Instantiates the classes with the base mapped class, which will be replaced
    by initModule, so modules can also be configured manually in the config
    file.
    """
    iodev = Property('Connection to PLC', StringType())

    def scanModules(self):
        try:
            self._plcio = PlcIO(self.iodev, self.log)
        except zapf.CommError as e:
            raise CommunicationFailedError('could not connect to plc') from e
        scanner = Scanner(self._plcio, self.log)
        for devinfo in scanner.scan_devices():
            if zspec.LOWLEVEL in devinfo.info.get('flags'):
                self.log.debug('device %d (%s) is lowlevel, skipping',
                              devinfo.number, devinfo.name)
                continue
            device = scanner.get_device(devinfo)
            if device is None:
                self.log.info(f'{devinfo.name} unsupported')
                continue
            basecls = CLS_MAP.get(device.__class__, None)
            if basecls is None:
                self.log.info('No mapping found for %s, (class %s)',
                              devinfo.name, device.__class__.__name__)
                continue
            mod_cls = basecls.makeModuleClass(device, devinfo)
            config = {
                'cls': mod_cls,
                'plcio': device,
                'description': devinfo.info['description'],
                'plc_name': devinfo.name,
                '_pinata': self.name,
            }
            if devinfo.info['basetype'] != 'enum' \
                and not issubclass(basecls, PLCCommunicator):
                config['value'] = {
                    # internal limit here is 2**64, zapf reports 2**128
                    'min': max(devinfo.info['absmin'], -UNLIMITED),
                    'max': min(devinfo.info['absmax'], UNLIMITED),
                }
                if devinfo.info['unit'] and devinfo.info['basetype'] == 'float':
                    config['value']['unit'] = devinfo.info['unit']
                if devinfo.info['access'] == 'rw':
                    config['target'] = {
                        'min': config['value']['min'],
                        'max': config['value']['max'],
                    }
            name = internalize_name(devinfo.name)
            yield (name, config)
        self._plcio.start_cache()

    def shutdownModule(self):
        """Shutdown the module, _plcio might be invalid after this. Needs to be
        recreated by scanModules."""
        self._plcio.stop_cache()
        self._plcio.proto.disconnect()


STATUS_MAP = {
    zspec.DevStatus.RESET: (INITIALIZING, 'resetting'),
    zspec.DevStatus.IDLE: (IDLE, 'idle'),
    zspec.DevStatus.DISABLED: (DISABLED, 'disabled'),
    zspec.DevStatus.WARN: (WARN, 'warning'),
    zspec.DevStatus.START: (STARTING, 'starting'),
    zspec.DevStatus.BUSY: (BUSY, 'busy'),
    zspec.DevStatus.STOP: (FINALIZING, 'stopping'),
    zspec.DevStatus.ERROR: (ERROR, 'error (please reset)'),
    zspec.DevStatus.DIAGNOSTIC_ERROR: (ERROR, 'hard error (please check plc)'),
}


class PLCBase:
    status = Parameter(datatype=StatusType(Drivable, 'INITIALIZING',
                                           'DISABLED', 'STARTING'))
    plcio = Property('plc io device', ValueType())
    plc_name = Property('plc io device', StringType(), export=True)
    _pinata = Attached(ZapfPinata) # TODO: make this automatic?

    @classmethod
    def makeModuleClass(cls, device, devinfo):
        # add parameters and commands according to device info
        add_members = {}
        # set correct enums for value/target
        if devinfo.info['basetype'] == 'enum':
            rmap = {v: k for k, v in devinfo.info['enum_r'].items()}
            read_enum = EnumType(rmap)
            add_members['value'] = Parameter(datatype=read_enum)
            if hasattr(cls, 'target'):
                #wmap = {k:v for k, v in devinfo.info['enum_w'].items()}
                #write_enum = EnumType(wmap)
                write_enum = EnumType(devinfo.info['enum_w'])
                add_members['target'] = Parameter(datatype=write_enum)

        for parameter in device.list_params():
            info = devinfo.info['params'][parameter]
            iname = internalize_name(parameter)
            readonly = info.get('access', 'ro') != 'rw'
            dataty = cls._map_datatype(info)
            if dataty is None:
                continue
            if info['basetype'] == 'float' and info['unit']: # TODO: better handling
                param = Parameter(info['description'],
                                  dataty,
                                  unit=info['unit'],
                                  readonly=readonly)
            else:
                param = Parameter(info['description'],
                                  dataty,
                                  readonly=readonly)

            def read_param(self, parameter=parameter):
                code, val = self.plcio.get_param_raw(parameter)
                if code > 4:
                    raise ERROR_MAP[code](f'Error when reading parameter'
                                        f'{parameter}: {code}')
                return val

            def write_param(self, value, parameter=parameter):
                code, val = self.plcio.set_param_raw(parameter, value)
                if code > 4:
                    raise ERROR_MAP[code](f'Error when setting parameter'
                                        f'{parameter} to {value!r}: {code}')
                return val

            # enums can have asymmetric read and write variants. this should be
            # checked
            if info['basetype'] == 'enum':
                allowed = frozenset(info['enum_w'].values())
                #pylint: disable=function-redefined
                def write_param(self, value, allowed=allowed, parameter=parameter):
                    if value not in allowed:
                        raise ValueError(f'Invalid value for writing'
                                         f' {parameter}: {value!r}')

                    code, val = self.plcio.set_param_raw(parameter, value)
                    if code > 4:
                        raise ERROR_MAP[code](f'Error when setting parameter'
                                            f'{parameter} to {value!r}: {code}')
                    return val

            add_members[iname] = param
            add_members['read_' + iname] = read_param
            if readonly:
                continue
            add_members['write_' + iname] = write_param

        for command in device.list_funcs():
            info = devinfo.info['funcs'][command]
            iname = internalize_name(command)
            if info['argument']:
                arg = cls._map_datatype(info['argument'])
            else:
                arg = None
            if info['result']:
                result = cls._map_datatype(info['result'])
            else:
                result = None
            def exec_command(self, arg=None, command=command):
                # TODO: commands return <err/succ>, <result>
                return self.plcio.exec_func(command, arg)
            decorator = Command(arg,
                                result = result,
                                description=info['description'],
                                )

            func = decorator(exec_command)
            add_members['call_' + iname] = func
        if not add_members:
            return cls
        new_name = '_' + cls.__name__ + '_' \
                   + internalize_name("extended")
        return type(new_name, (cls,), add_members)

    @classmethod
    def _map_datatype(cls, info):
        dataty = info['basetype']
        if dataty == 'int':
            return IntRange(info['min_value'], info['max_value'])
        if dataty == 'float':
            return FloatRange(info['min_value'], info['max_value'])
        if dataty == 'enum':
            mapping = {v: k for k, v in info['enum_r'].items()}
            return EnumType(mapping)
        return None

    def read_status(self):
        state, reason, aux, err_id = self.plcio.read_status()
        if state in STATUS_MAP:
            status, m = STATUS_MAP[state]
        else:
            status, m = UNKNOWN, 'unknown state 0x%x' % state
        msg = [m]
        reason = zapf.spec.ReasonMap[reason]
        if reason:
            msg.append(reason)
        if aux:
            msg.append(self.plcio.decode_aux(aux))
        if err_id:
            msg.append(self.plcio.decode_errid(err_id))
        return status, ', '.join(msg)

    @Command()
    def stop(self):
        """Stop the operation of this module.

        :raises:
            ImpossibleError: if the command is called while the module is
            not busy
        """
        if not self.plcio.change_status((zapf.DevStatus.BUSY,),
                                        zapf.DevStatus.STOP):
            self.log.info('stop was called when device was not busy')
    # TODO: off/on?

    @Command()
    def reset(self):
        """Tries to reset this module.

        :raises:
            ImpossibleError: when called while the module is not in an error
            state.
        """
        if not self.plcio.reset():
            raise ImpossibleError('reset called when the device is not in'
                                  'an error state!')


class PLCValue(PLCBase):
    """Base class for all but Communicator"""
    def read_value(self):
        return self.plcio.read_value_raw()  # read_value maps enums on zapf side

    def read_target(self):
        return self.plcio.read_target_raw()

    def write_target(self, value):
        self.plcio.change_target_raw(value)


class PLCReadable(PLCValue, Readable):
    """Readable value, scanned from PLC."""
    description = Property('the modules description',
                           datatype=StringType(isUTF8=True))


class PLCDrivable(PLCValue, Drivable):
    """Drivable, scanned from PLC."""
    description = Property('the modules description',
                           datatype=StringType(isUTF8=True))


class PLCCommunicator(PLCBase, Communicator):
    status = Parameter('current status of the module')

    @Command(BLOBType(), result=BLOBType())
    def communicate(self, command):
        return self.plcio.communicate(command)


class Sensor(PLCReadable):
    pass


class AnalogOutput(PLCDrivable):
    pass


class DiscreteInput(PLCReadable):
    value = Parameter(datatype=IntRange())

class DiscreteOutput(PLCDrivable):
    value = Parameter(datatype=IntRange())
    target = Parameter(datatype=IntRange())


class VectorInput(PLCReadable):
    value = Parameter(datatype=ArrayOf(FloatRange()))


class VectorOutput(PLCDrivable):
    value = Parameter(datatype=ArrayOf(FloatRange()))
    target = Parameter(datatype=ArrayOf(FloatRange()))


CLS_MAP = {
    zapf.device.SimpleDiscreteIn: DiscreteInput,
    zapf.device.SimpleAnalogIn: Sensor,
    zapf.device.Keyword: DiscreteOutput,
    zapf.device.RealValue: AnalogOutput,
    zapf.device.SimpleDiscreteOut: DiscreteOutput,
    zapf.device.SimpleAnalogOut: PLCDrivable,
    zapf.device.StatusWord: DiscreteInput,
    zapf.device.DiscreteIn: DiscreteInput,
    zapf.device.AnalogIn: Sensor,
    zapf.device.DiscreteOut: DiscreteOutput,
    zapf.device.AnalogOut: PLCDrivable,
    zapf.device.FlatIn: Sensor,
    zapf.device.FlatOut: AnalogOutput,
    zapf.device.ParamIn: Sensor,
    zapf.device.ParamOut: AnalogOutput,
    zapf.device.VectorIn: VectorInput,
    zapf.device.VectorOut: VectorOutput,
    zapf.device.MessageIO: PLCCommunicator,
}
