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
"""playground dummy server

a dummy server for testing drivers interactively

Remarks:
- the poller is not started
"""

import sys
from logging import DEBUG, INFO, addLevelName
import mlzlog
from frappy.errors import NoSuchModuleError
from frappy.server import Server
from frappy.config import load_config, Mod as ConfigMod
from frappy.lib import generalConfig


USAGE = """create config on the fly:

   Mod('io', ...)
   Mod('mf', ...)
   play()

or use a config file:

   play('<configfile(s)>')


and then call methods for trying:

   io.communicate('...')
   mf.read_value()
   mf.write_target(...)
"""

OFF = 99
COMLOG = 15
addLevelName(COMLOG, 'COMLOG')
assert DEBUG < COMLOG < INFO
LOG_LEVELS = dict(mlzlog.LOGLEVELS, off=OFF, comlog=COMLOG)
LEVEL_NAMES = {v: k for k, v in LOG_LEVELS.items()}


main = sys.modules['__main__']


class MainLogger:
    def __init__(self):
        self.log = None
        self.console_handler = None
        mlzlog.setLoggerClass(mlzlog.MLZLogger)
        assert self.log is None
        self.log = mlzlog.log = mlzlog.MLZLogger('')
        self.log.setLevel(mlzlog.DEBUG)
        self.log.addHandler(mlzlog.ColoredConsoleHandler())
        self.log.handlers[0].setLevel(LOG_LEVELS['comlog'])


class Dispatcher:
    def __init__(self, name, log, opts, srv):
        self.log = log
        self._modules = {}

    def announce_update(self, modulename, pname, pobj):
        if pobj.readerror:
            value = repr(pobj.readerror)
        else:
            value = pobj.value
        self.log.info('%s:%s %r', modulename, pname, value)

    def register_module(self, moduleobj, modulename, export=True):
        setattr(main, modulename, moduleobj)
        self._modules[modulename] = moduleobj

    def get_module(self, modulename):
        if modulename in self._modules:
            return self._modules[modulename]
        raise NoSuchModuleError(f'Module {modulename!r} does not exist on this SEC-Node!')


logger = MainLogger()


class Playground(Server):
    def __init__(self, **kwds):  # pylint: disable=super-init-not-called
        for modname, cfg in kwds.items():
            cfg.setdefault('description', modname)
        self.log = logger.log
        self.node_cfg = {'cls': 'frappy.playground.Dispatcher', 'name': 'playground'}
        self._testonly = True  # stops before calling startModule
        self._cfgfiles = 'main'
        self.module_cfg = {}

    def __call__(self, cfgfiles=None):
        if cfgfiles:
            if not generalConfig.initialized:
                generalConfig.init()
            merged_cfg = load_config(cfgfiles, self.log)
            merged_cfg.pop('node', None)
            self.module_cfg = merged_cfg
        self._processCfg()


play = Playground()


def Mod(name, cls, description=None, **kwds):
    """like Mod() in config files, but description may be omitted"""
    description = description or name  # be lazy: fix missing description
    mod = ConfigMod(name, cls, description, **kwds)
    play.module_cfg[mod.pop('name')] = mod


def loglevel(level):
    """set log level (COMLOG by default)"""
    logger.log.handlers[0].setLevel(LOG_LEVELS.get(level, level))
