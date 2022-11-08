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
#
# *****************************************************************************


from os import path

from frappy.gui.qt import uic

uipath = path.dirname(__file__)


def loadUi(widget, uiname, subdir='ui'):
    uic.loadUi(path.join(uipath, subdir, uiname), widget)


class Value:
    def __init__(self, value, timestamp=None, readerror=None):
        self.value = value
        self.timestamp = timestamp
        self.readerror = readerror

    def __str__(self):
        """for display"""
        if self.readerror:
            return str('!!' + str(self.readerror) + '!!')
        return str(self.value)

    def __repr__(self):
        args = (self.value,)
        if self.timestamp:
            args += (self.timestamp,)
        if self.readerror:
            args += (self.readerror,)
        return 'Value%s' % repr(args)
