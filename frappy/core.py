#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2016 by the authors, see LICENSE
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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

# allow to import the most important classes from 'frappy'

# pylint: disable=unused-import
from frappy.datatypes import ArrayOf, BLOBType, BoolType, EnumType, \
    FloatRange, IntRange, ScaledInteger, StringType, StructOf, TupleOf, StatusType
from frappy.lib.enum import Enum
from frappy.modulebase import Done, Module, Feature
from frappy.modules import Attached, Communicator, \
    Drivable, Readable, Writable
from frappy.params import Command, Parameter, Limit
from frappy.properties import Property
from frappy.proxy import Proxy, SecNode, proxy_class
from frappy.io import HasIO, StringIO, BytesIO, HasIodev  # TODO: remove HasIodev (legacy stuff)
from frappy.persistent import PersistentMixin, PersistentParam, PersistentLimit
from frappy.rwhandler import ReadHandler, WriteHandler, CommonReadHandler, \
    CommonWriteHandler, nopoll

DISABLED = StatusType.DISABLED
IDLE = StatusType.IDLE
STANDBY = StatusType.STANDBY
PREPARED = StatusType.PREPARED
WARN = StatusType.WARN
WARN_STANDBY = StatusType.WARN_STANDBY
WARN_PREPARED = StatusType.WARN_PREPARED
UNSTABLE = StatusType.UNSTABLE  # no SECoP standard (yet)
BUSY = StatusType.BUSY
DISABLING = StatusType.DISABLING
INITIALIZING = StatusType.INITIALIZING
PREPARING = StatusType.PREPARING
STARTING = StatusType.STARTING
RAMPING = StatusType.RAMPING
STABILIZING = StatusType.STABILIZING
FINALIZING = StatusType.FINALIZING
ERROR = StatusType.ERROR
ERROR_STANDBY = StatusType.ERROR_STANDBY
ERROR_PREPARED = StatusType.ERROR_PREPARED
UNKNOWN = StatusType.UNKNOWN  # no SECoP standard (yet)
