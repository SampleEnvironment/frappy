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

# allow to import the most important classes from 'secop'

# pylint: disable=unused-import
from secop.datatypes import FloatRange, IntRange, ScaledInteger, \
    BoolType, EnumType, BLOBType, StringType, TupleOf, ArrayOf, StructOf
from secop.lib.enum import Enum
from secop.modules import Module, Readable, Writable, Drivable, Communicator, Attached
from secop.properties import Property
from secop.params import Parameter, Command, Override, usercommand
from secop.poller import AUTO, REGULAR, SLOW, DYNAMIC
from secop.metaclass import Done
from secop.iohandler import IOHandler, IOHandlerBase
from secop.stringio import StringIO, HasIodev
from secop.proxy import SecNode, Proxy, proxy_class
