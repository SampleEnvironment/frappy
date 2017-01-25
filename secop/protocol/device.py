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
"""Define SECoP Device classes

"""
# XXX: is this still needed ???
# see devices.core ....

from secop.lib import attrdict
from secop.protocol import status


# XXX: deriving PARS/CMDS should be done in a suitable metaclass....
class Device(object):
    """Minimalist Device

    all others derive from this"""
    name = None

    def read_status(self):
        raise NotImplementedError('All Devices need a Status!')

    def read_name(self):
        return self.name


class Readable(Device):
    """A Readable Device"""
    unit = ''

    def read_value(self):
        raise NotImplementedError('A Readable MUST provide a value')

    def read_unit(self):
        return self.unit


class Writeable(Readable):
    """Writeable can be told to change it's vallue"""
    target = None

    def read_target(self):
        return self.target

    def write_target(self, target):
        self.target = target


class Driveable(Writeable):
    """A Moveable which may take a while to reach its target,

    hence stopping it may be desired"""

    def do_stop(self):
        raise NotImplementedError('A Driveable MUST implement the STOP() '
                                  'command')
