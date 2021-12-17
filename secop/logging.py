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


from logging import LoggerAdapter
from mlzlog import LOGLEVELS

OFF = 99
LOG_LEVELS = dict(LOGLEVELS, off=OFF)
LEVEL_NAMES = {v: k for k, v in LOG_LEVELS.items()}


def check_level(level):
    try:
        if isinstance(level, str):
            return LOG_LEVELS[level.lower()]
        if level in LEVEL_NAMES:
            return level
    except KeyError:
        pass
    raise ValueError('%r is not a valid level' % level)


class Adapter(LoggerAdapter):
    def __init__(self, modobj):
        super().__init__(modobj.log, {})
        self.subscriptions = {}  # dict [conn] of level
        self.modobj = modobj

    def log(self, level, msg, *args, **kwargs):
        super().log(level, msg, *args, **kwargs)
        for conn, lev in self.subscriptions.items():
            if level >= lev:
                self.modobj.DISPATCHER.send_log_msg(
                    conn, self.modobj.name, LEVEL_NAMES[level], msg % args)

    def set_log_level(self, conn, level):
        level = check_level(level)
        if level == OFF:
            self.subscriptions.pop(conn, None)
        else:
            self.subscriptions[conn] = level


def set_log_level(modobj, conn, level):
    if not isinstance(modobj.log, Adapter):
        modobj.log = Adapter(modobj)
    modobj.log.set_log_level(conn, level)
