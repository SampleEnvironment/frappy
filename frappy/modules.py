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
#   Markus Zolliker <markus.zolliker@psi.ch>
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
"""Define base classes for real Modules implemented in the server"""


from frappy.datatypes import FloatRange, \
    StatusType, StringType
from frappy.errors import ConfigError, ProgrammingError
from frappy.lib.enum import Enum
from frappy.params import Command, Parameter
from frappy.properties import Property
from frappy.logging import HasComlog

from .modulebase import Module


class Readable(Module):
    """basic readable module"""
    # pylint: disable=invalid-name
    Status = Enum('Status',
                  IDLE=StatusType.IDLE,
                  WARN=StatusType.WARN,
                  ERROR=StatusType.ERROR,
                  )  #: status code Enum: extended automatically in inherited modules
    value = Parameter('current value of the module', FloatRange())
    status = Parameter('current status of the module', StatusType(Status),
                       default=(StatusType.IDLE, ''))
    pollinterval = Parameter('default poll interval', FloatRange(0.1, 120, unit='s'),
                             default=5, readonly=False, export=True)

    def doPoll(self):
        self.read_value()
        self.read_status()


class Writable(Readable):
    """basic writable module"""
    target = Parameter('target value of the module',
                       default=0, readonly=False, datatype=FloatRange(unit='$'))

    def __init__(self, name, logger, cfgdict, srv):
        super().__init__(name, logger, cfgdict, srv)
        value_dt = self.parameters['value'].datatype
        target_dt = self.parameters['target'].datatype
        try:
            # this handles also the cases where the limits on the value are more
            # restrictive than on the target
            target_dt.compatible(value_dt)
        except Exception:
            if type(value_dt) == type(target_dt):
                raise ConfigError(f'{name}: the target range extends beyond the value range') from None
            raise ProgrammingError(f'{name}: the datatypes of target and value are not compatible') from None


class Drivable(Writable):
    """basic drivable module"""

    status = Parameter(datatype=StatusType(Readable, 'BUSY'))  # extend Readable.status

    def isBusy(self, status=None):
        """check for busy, treating substates correctly

        returns True when busy (also when finalizing)
        """
        return StatusType.BUSY <= (status or self.status)[0] < StatusType.ERROR

    def isDriving(self, status=None):
        """check for driving, treating status substates correctly

        returns True when busy, but not finalizing
        """
        return StatusType.BUSY <= (status or self.status)[0] < StatusType.FINALIZING

    @Command(None, result=None)
    def stop(self):
        """not implemented - this is a no-op"""


class Communicator(HasComlog, Module):
    """basic abstract communication module"""

    @Command(StringType(), result=StringType())
    def communicate(self, command):
        """communicate command

        :param command: the command to be sent
        :return: the reply
        """
        raise NotImplementedError()


SECoP_BASE_CLASSES = {Readable, Writable, Drivable, Communicator}


class Attached(Property):
    """a special property, defining an attached module

    assign a module name to this property in the cfg file,
    and the server will create an attribute with this module

    When mandatory is set to False, and there is no value or an empty string
    given in the config file, the value of the attribute will be None.
    """
    def __init__(self, basecls=Module, description='attached module', mandatory=True):
        self.basecls = basecls
        super().__init__(description, StringType(), mandatory=mandatory)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        modobj = obj.attachedModules.get(self.name)
        if not modobj:
            modulename = super().__get__(obj, owner)
            if not modulename:
                return None  # happens when mandatory=False and modulename is not given
            modobj = obj.secNode.get_module(modulename)
            if not modobj:
                raise ConfigError(f'attached module {self.name}={modulename!r} '
                                  f'does not exist')
            if not isinstance(modobj, self.basecls):
                raise ConfigError(f'attached module {self.name}={modobj.name!r} '
                                  f'must inherit from {self.basecls.__qualname__!r}')
            obj.attachedModules[self.name] = modobj
        return modobj

    def copy(self):
        return Attached(self.basecls, self.description, self.mandatory)
