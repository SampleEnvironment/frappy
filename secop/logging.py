#!/usr/bin/env python
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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************


import os
from os.path import dirname, join
from logging import DEBUG, INFO, addLevelName
import mlzlog

from secop.lib import generalConfig
from secop.datatypes import BoolType
from secop.properties import Property

OFF = 99
COMLOG = 15
addLevelName(COMLOG, 'COMLOG')
assert DEBUG < COMLOG < INFO
LOG_LEVELS = dict(mlzlog.LOGLEVELS, off=OFF, comlog=COMLOG)
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


class RemoteLogHandler(mlzlog.Handler):
    """handler for remote logging"""
    def __init__(self):
        super().__init__()
        self.subscriptions = {}  # dict[modname] of tuple(mobobj, dict [conn] of level)

    def emit(self, record):
        """unused"""

    def handle(self, record):
        modname = record.name.split('.')[-1]
        try:
            modobj, subscriptions = self.subscriptions[modname]
        except KeyError:
            return
        for conn, lev in subscriptions.items():
            if record.levelno >= lev:
                modobj.DISPATCHER.send_log_msg(
                    conn, modobj.name, LEVEL_NAMES[record.levelno],
                    record.getMessage())

    def set_conn_level(self, modobj, conn, level):
        level = check_level(level)
        modobj, subscriptions = self.subscriptions.setdefault(modobj.name, (modobj, {}))
        if level == OFF:
            subscriptions.pop(conn, None)
        else:
            subscriptions[conn] = level

    def __repr__(self):
        return 'RemoteLogHandler()'


class LogfileHandler(mlzlog.LogfileHandler):

    def __init__(self, logdir, rootname, max_days=0):
        self.rootname = rootname
        self.max_days = max_days
        super().__init__(logdir, rootname)

    def emit(self, record):
        if record.levelno != COMLOG:
            super().emit(record)

    def getChild(self, name):
        child = type(self)(dirname(self.baseFilename), name, self.max_days)
        child.setLevel(self.level)
        return child

    def doRollover(self):
        super().doRollover()
        if self.max_days:
            # keep only the last max_days files
            with os.scandir(dirname(self.baseFilename)) as it:
                files = sorted(entry.path for entry in it if entry.name != 'current')
            for filepath in files[-self.max_days:]:
                os.remove(filepath)


class ComLogfileHandler(LogfileHandler):
    """handler for logging communication"""

    def format(self, record):
        return '%s %s' % (self.formatter.formatTime(record), record.getMessage())


class HasComlog:
    """mixin for modules with comlog"""
    comlog = Property('whether communication is logged ', BoolType(),
                      default=True, export=False)
    _comLog = None

    def earlyInit(self):
        super().earlyInit()
        if self.comlog and generalConfig.initialized and generalConfig.comlog:
            self._comLog = mlzlog.Logger('COMLOG.%s' % self.name)
            self._comLog.handlers[:] = []
            directory = join(logger.logdir, logger.rootname, 'comlog', self.DISPATCHER.name)
            self._comLog.addHandler(ComLogfileHandler(
                directory, self.name, max_days=generalConfig.getint('comlog_days', 7)))
            return

    def comLog(self, msg, *args, **kwds):
        self.log.log(COMLOG, msg, *args, **kwds)
        if self._comLog:
            self._comLog.info(msg, *args)


class MainLogger:
    def __init__(self):
        self.log = None
        self.logdir = None
        self.rootname = None
        self.console_handler = None

    def init(self, console_level='info'):
        self.rootname = generalConfig.get('logger_root', 'frappy')
        # set log level to minimum on the logger, effective levels on the handlers
        # needed also for RemoteLogHandler
        # modified from mlzlog.initLogging
        mlzlog.setLoggerClass(mlzlog.MLZLogger)
        assert self.log is None
        self.log = mlzlog.log = mlzlog.MLZLogger(self.rootname)

        self.log.setLevel(DEBUG)
        self.log.addHandler(mlzlog.ColoredConsoleHandler())

        self.logdir = generalConfig.get('logdir', '/tmp/log')
        if self.logdir:
            logfile_days = generalConfig.getint('logfile_days')
            logfile_handler = LogfileHandler(self.logdir, self.rootname, max_days=logfile_days)
            logfile_handler.setLevel(LOG_LEVELS[generalConfig.get('logfile_level', 'info')])
            self.log.addHandler(logfile_handler)

        self.log.addHandler(RemoteLogHandler())
        self.log.handlers[0].setLevel(LOG_LEVELS[console_level])


logger = MainLogger()
