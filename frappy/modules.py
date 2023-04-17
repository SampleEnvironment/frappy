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

from frappy.datatypes import BoolType, FloatRange, StatusType, StringType
from frappy.errors import ConfigError, ProgrammingError
from frappy.lib.enum import Enum
from frappy.logging import HasComlog
from frappy.params import Command, Parameter

from .modulebase import Module
from .attached import AttachedDict

# import compatibility:
# pylint: disable=unused-import
from .properties import Property
from .attached import Attached


class Readable(Module):
    """basic readable module"""
    interface_classes = ['Readable']
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
    interface_classes = ['Writable']
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
    interface_classes = ['Drivable']
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


class AcquisitionChannel(Readable):
    """A Readable which is part of a data acquisition."""
    interface_classes = ['AcquisitionChannel', 'Readable']
    # copy Readable.status and extend it with BUSY
    status = Parameter(datatype=StatusType(Readable, 'BUSY'))
    goal = Parameter('stops the data acquisition when it is reached',
                     FloatRange(), default=0, readonly=False, optional=True)
    goal_enable = Parameter('enable goal', BoolType(), readonly=False,
                            default=False, optional=True)

    # clear is no longer part of the proposed spec, so it does not appear
    # as optional command here. however, a subclass may still implement it


class AcquisitionController(Module):
    """Controls other modules.

    Controls the data acquisition from AcquisitionChannels.
    """
    interface_classes = ['AcquisitionController']
    # channels might be configured to an arbitrary number of channels with arbitrary roles
    # - to forbid the use fo arbitrary roles, override base=None
    # - to restrict roles and base classes override elements={<key>: <basecls>}
    #   and/or optional={<key>: <basecls>}
    channels = AttachedDict('mapping of role to module name for attached channels',
                            elements=None, optional=None,
                            basecls=AcquisitionChannel,
                            extname='acquisition_channels')
    status = Drivable.status
    isBusy = Drivable.isBusy
    # add pollinterval parameter to enable faster polling of the status
    pollinterval = Readable.pollinterval

    def doPoll(self):
        self.read_status()

    @Command()
    def go(self):
        """Start the acquisition. No-op if the controller is already Busy."""
        raise NotImplementedError()

    @Command(optional=True)
    def prepare(self):
        """Prepare the hardware so 'go' can trigger immediately."""

    @Command(optional=True)
    def hold(self):
        """Pause the operation.

        The next go will continue without clearing any channels or resetting hardware."""

    @Command(optional=True)
    def stop(self):
        """Stop the data acquisition or operation."""


class Acquisition(AcquisitionController, AcquisitionChannel):  # pylint: disable=abstract-method
    """Combines AcquisitionController and AcquisitionChannel into one Module

    for the special case where there is only one channel.
    remark: when using multiple inheritance, Acquisition must appear
    before any base class inheriting from AcquisitionController
    """
    interface_classes = ['Acquisition', 'Readable']
    channels = None  # remove property
    acquisition_key = Property('acquisition role (equivalent to NICOS preset name)',
                               StringType(), export=True, default='')

    doPoll = Readable.doPoll


class Communicator(HasComlog, Module):
    """basic abstract communication module"""
    interface_classes = ['Communicator']

    @Command(StringType(), result=StringType())
    def communicate(self, command):
        """communicate command

        :param command: the command to be sent
        :return: the reply
        """
        raise NotImplementedError()
