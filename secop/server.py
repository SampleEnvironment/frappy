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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************
"""Define helpers"""
from __future__ import print_function

import os
import ast
import time
import threading

try:
    import configparser  # py3
except ImportError:
    import ConfigParser as configparser  # py2

try:
    from queue import Queue # py 3
except ImportError:
    from Queue import Queue # py 2

from daemon import DaemonContext

try:
    import daemon.pidlockfile as pidlockfile
except ImportError:
    import daemon.pidfile as pidlockfile

from secop.lib import get_class, formatException, getGeneralConfig
from secop.protocol.dispatcher import Dispatcher
from secop.protocol.interface import INTERFACES
from secop.errors import ConfigError


class Server(object):

    def __init__(self, name, parent_logger=None):
        cfg = getGeneralConfig()

        # also handle absolut paths
        if os.path.abspath(name) == name and os.path.exists(name) and \
            name.endswith('.cfg'):
            self._cfgfile = name
            self._pidfile = os.path.join(cfg[u'piddir'],
                                         name[:-4].replace(os.path.sep, '_') + u'.pid')
            name = os.path.basename(name[:-4])
        else:
            self._cfgfile = os.path.join(cfg[u'confdir'], name + u'.cfg')
            self._pidfile = os.path.join(cfg[u'piddir'], name + u'.pid')

        self._name = name

        self.log = parent_logger.getChild(name, True)

        self._dispatcher = None
        self._interface = None

    def start(self):
        piddir = os.path.dirname(self._pidfile)
        if not os.path.isdir(piddir):
            os.makedirs(piddir)
        pidfile = pidlockfile.TimeoutPIDLockFile(self._pidfile)

        if pidfile.is_locked():
            self.log.error(u'Pidfile already exists. Exiting')

        with DaemonContext(
                pidfile=pidfile,
                files_preserve=self.log.getLogfileStreams()):
            self.run()

    def run(self):
        try:
            self._processCfg()
        except Exception:
            print(formatException(verbose=True))
            raise

        self.log.info(u'startup done, handling transport messages')
        self._threads = set()
        for _if in self._interfaces:
            self.log.debug(u'starting thread for interface %r' % _if)
            t = threading.Thread(target=_if.serve_forever)
            t.daemon = True
            t.start()
            self._threads.add(t)
        while self._threads:
            time.sleep(1)
            for t in self._threads:
                if not t.is_alive():
                    self.log.debug(u'thread %r died (%d still running)' %
                                   (t, len(self._threads)))
                    t.join()
                    self._threads.discard(t)

    def _processCfg(self):
        self.log.debug(u'Parse config file %s ...' % self._cfgfile)

        parser = configparser.SafeConfigParser()
        parser.optionxform = str

        if not parser.read([self._cfgfile]):
            self.log.error(u'Couldn\'t read cfg file !')
            raise ConfigError(u'Couldn\'t read cfg file %r' % self._cfgfile)

        self._interfaces = []

        moduleopts = []
        interfaceopts = []
        equipment_id = None
        nodeopts = []
        for section in parser.sections():
            if section.lower().startswith(u'module '):
                # module section
                # omit leading 'module ' string
                devname = section[len(u'module '):]
                devopts = dict(item for item in parser.items(section))
                if u'class' not in devopts:
                    self.log.error(u'Module %s needs a class option!')
                    raise ConfigError(
                        u'cfgfile %r: Module %s needs a class option!' %
                        (self._cfgfile, devname))
                # MAGIC: transform \n.\n into \n\n which are normally stripped
                # by the ini parser
                for k in devopts:
                    v = devopts[k]
                    while u'\n.\n' in v:
                        v = v.replace(u'\n.\n', u'\n\n')
                    devopts[k] = v
                # try to import the class, raise if this fails
                devopts[u'class'] = get_class(devopts[u'class'])
                # all went well so far
                moduleopts.append([devname, devopts])
            if section.lower().startswith(u'interface '):
                # interface section
                # omit leading 'interface ' string
                ifname = section[len(u'interface '):]
                ifopts = dict(item for item in parser.items(section))
                if u'interface' not in ifopts:
                    self.log.error(u'Interface %s needs an interface option!')
                    raise ConfigError(
                        u'cfgfile %r: Interface %s needs an interface option!' %
                        (self._cfgfile, ifname))
                # all went well so far
                interfaceopts.append([ifname, ifopts])
            if section.lower().startswith(u'equipment ') or section.lower().startswith(u'node '):
                if equipment_id is not None:
                    raise ConfigError(u'cfgfile %r: only one [node <id>] section allowed, found another [%s]!' % (
                        self._cfgfile, section))
                # equipment/node settings
                equipment_id = section.split(u' ', 1)[1].replace(u' ', u'_')
                nodeopts = dict(item for item in parser.items(section))
                nodeopts[u'equipment_id'] = equipment_id
                nodeopts[u'id'] = equipment_id
                # MAGIC: transform \n.\n into \n\n which are normally stripped
                # by the ini parser
                for k in nodeopts:
                    v = nodeopts[k]
                    while u'\n.\n' in v:
                        v = v.replace(u'\n.\n', u'\n\n')
                    nodeopts[k] = v

        if equipment_id is None:
            self.log.error(u'Need a [node <id>] section, none found!')
            raise ConfigError(
                u'cfgfile %r: need an [node <id>] option!' % (self._cfgfile))

        self._dispatcher = self._buildObject(
            u'Dispatcher', Dispatcher, nodeopts)
        self._processInterfaceOptions(interfaceopts)
        self._processModuleOptions(moduleopts)

    def _processModuleOptions(self, moduleopts):
        # check modules opts by creating them
        devs = []
        for devname, devopts in moduleopts:
            devclass = devopts.pop(u'class')
            # create module
            self.log.debug(u'Creating Module %r' % devname)
            export = devopts.pop(u'export', u'1')
            export = export.lower() in (u'1', u'on', u'true', u'yes')
            if u'default' in devopts:
                devopts[u'value'] = devopts.pop(u'default')
            # strip '"
            for k, v in devopts.items():
                try:
                    devopts[k] = ast.literal_eval(v)
                except Exception:
                    pass
            devobj = devclass(
                self.log.getChild(devname), devopts, devname, self._dispatcher)
            devs.append([devname, devobj, export])

        # connect modules with dispatcher
        for devname, devobj, export in devs:
            self.log.info(u'registering module %r' % devname)
            self._dispatcher.register_module(devobj, devname, export)
            # also call init on the modules
            devobj.init()
        # call postinit on each module after registering all
        for _devname, devobj, _export in devs:
            devobj.postinit()
        starting_modules = set()
        finished_modules = Queue()
        for _devname, devobj, _export in devs:
            starting_modules.add(devobj)
            devobj.late_init(started_callback=finished_modules.put)
        # remark: it is the module implementors responsibility to call started_callback
        # within reasonable time (using timeouts). If we find later, that this is not
        # enough, we might insert checking for a timeout here, and somehow set the remaining
        # starting_modules to an error state.
        while starting_modules:
            finished = finished_modules.get()
            self.log.info(u'%s has started' % finished.name)
            # use discard instead of remove here, catching the case when started_callback is called twice
            starting_modules.discard(finished)

    def _processInterfaceOptions(self, interfaceopts):
        # eval interfaces
        self._interfaces = []
        for ifname, ifopts in interfaceopts:
            ifclass = ifopts.pop(u'interface')
            ifclass = INTERFACES[ifclass]
            interface = self._buildObject(ifname, ifclass, ifopts,
                                          self._dispatcher)
            self._interfaces.append(interface)

    def _buildObject(self, name, cls, options, *args):
        self.log.debug(u'Creating %s ...' % name)
        # cls.__init__ should pop all used args from options!
        obj = cls(self.log.getChild(name.lower()), options, *args)
        if options:
            raise ConfigError(u'%s: don\'t know how to handle option(s): %s' %
                              (cls.__name__, u', '.join(options)))
        return obj
