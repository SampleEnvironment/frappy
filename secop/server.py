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
import os
import ast
import time
import threading
import ConfigParser

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

    def __init__(self, name, parentLogger=None):
        self._name = name

        self.log = parentLogger.getChild(name, True)

        cfg = getGeneralConfig()
        self._pidfile = os.path.join(cfg['piddir'], name + '.pid')
        self._cfgfile = os.path.join(cfg['confdir'], name + '.cfg')

        self._dispatcher = None
        self._interface = None

    def start(self):
        piddir = os.path.dirname(self._pidfile)
        if not os.path.isdir(piddir):
            os.makedirs(piddir)
        pidfile = pidlockfile.TimeoutPIDLockFile(self._pidfile)

        if pidfile.is_locked():
            self.log.error('Pidfile already exists. Exiting')

        with DaemonContext(
                pidfile=pidfile,
                files_preserve=self.log.getLogfileStreams()):
            self.run()

    def run(self):
        try:
            self._processCfg()
        except Exception:
            print formatException(verbose=True)
            raise

        self.log.info('startup done, handling transport messages')
        self._threads = set()
        for _if in self._interfaces:
            self.log.debug('starting thread for interface %r' % _if)
            t = threading.Thread(target=_if.serve_forever)
            t.daemon = True
            t.start()
            self._threads.add(t)
        while self._threads:
            time.sleep(1)
            for t in self._threads:
                if not t.is_alive():
                    self.log.debug('thread %r died (%d still running)' %
                                   (t, len(self._threads)))
                    t.join()
                    self._threads.discard(t)

    def _processCfg(self):
        self.log.debug('Parse config file %s ...' % self._cfgfile)

        parser = ConfigParser.SafeConfigParser()
        parser.optionxform = str

        if not parser.read([self._cfgfile]):
            self.log.error("Couldn't read cfg file !")
            raise ConfigError("Couldn't read cfg file %r" % self._cfgfile)

        self._interfaces = []

        moduleopts = []
        interfaceopts = []
        equipment_id = None
        nodeopts = []
        for section in parser.sections():
            if section.lower().startswith('module '):
                # module section
                # omit leading 'module ' string
                devname = section[len('module '):]
                devopts = dict(item for item in parser.items(section))
                if 'class' not in devopts:
                    self.log.error('Module %s needs a class option!')
                    raise ConfigError(
                        'cfgfile %r: Module %s needs a class option!' %
                        (self._cfgfile, devname))
                # MAGIC: transform \n.\n into \n\n which are normally stripped
                # by the ini parser
                for k in devopts:
                    v = devopts[k]
                    while '\n.\n' in v:
                        v = v.replace('\n.\n', '\n\n')
                    devopts[k] = v
                # try to import the class, raise if this fails
                devopts['class'] = get_class(devopts['class'])
                # all went well so far
                moduleopts.append([devname, devopts])
            if section.lower().startswith('interface '):
                # interface section
                # omit leading 'interface ' string
                ifname = section[len('interface '):]
                ifopts = dict(item for item in parser.items(section))
                if 'interface' not in ifopts:
                    self.log.error('Interface %s needs an interface option!')
                    raise ConfigError(
                        'cfgfile %r: Interface %s needs an interface option!' %
                        (self._cfgfile, ifname))
                # all went well so far
                interfaceopts.append([ifname, ifopts])
            if section.lower().startswith('equipment ') or section.lower().startswith('node '):
                if equipment_id is not None:
                    raise ConfigError('cfgfile %r: only one [node <id>] section allowed, found another [%s]!' % (
                        self._cfgfile, section))
                # equipment/node settings
                equipment_id = section.split(' ', 1)[1].replace(' ', '_')
                nodeopts = dict(item for item in parser.items(section))
                nodeopts['equipment_id'] = equipment_id
                nodeopts['id'] = equipment_id
                # MAGIC: transform \n.\n into \n\n which are normally stripped
                # by the ini parser
                for k in nodeopts:
                    v = nodeopts[k]
                    while '\n.\n' in v:
                        v = v.replace('\n.\n', '\n\n')
                    nodeopts[k] = v

        if equipment_id is None:
            self.log.error('Need a [node <id>] section, none found!')
            raise ConfigError(
                'cfgfile %r: need an [node <id>] option!' % (self._cfgfile))

        self._dispatcher = self._buildObject(
            'Dispatcher', Dispatcher, nodeopts)
        self._processInterfaceOptions(interfaceopts)
        self._processModuleOptions(moduleopts)

    def _processModuleOptions(self, moduleopts):
        # check modules opts by creating them
        devs = []
        for devname, devopts in moduleopts:
            devclass = devopts.pop('class')
            # create module
            self.log.debug('Creating Module %r' % devname)
            export = devopts.pop('export', '1')
            export = export.lower() in ('1', 'on', 'true', 'yes')
            if 'default' in devopts:
                devopts['value'] = devopts.pop('default')
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
            self.log.info('registering module %r' % devname)
            self._dispatcher.register_module(devobj, devname, export)
            # also call init on the modules
            devobj.init()
        # call a possibly empty postinit on each module after registering all
        for _devname, devobj, _export in devs:
            postinit = getattr(devobj, 'postinit', None)
            if postinit:
                postinit()

    def _processInterfaceOptions(self, interfaceopts):
        # eval interfaces
        self._interfaces = []
        for ifname, ifopts in interfaceopts:
            ifclass = ifopts.pop('interface')
            ifclass = INTERFACES[ifclass]
            interface = self._buildObject(ifname, ifclass, ifopts,
                                          self._dispatcher)
            self._interfaces.append(interface)

    def _buildObject(self, name, cls, options, *args):
        self.log.debug('Creating %s ...' % name)
        # cls.__init__ should pop all used args from options!
        obj = cls(self.log.getChild(name.lower()), options, *args)
        if options:
            raise ConfigError('%s: don\'t know how to handle option(s): %s' %
                              (cls.__name__, ', '.join(options.keys())))
        return obj
