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
import psutil
import ConfigParser

# apt install python-daemon !!!do not use pip install daemon <- wrong version!
import daemon
#from daemon import pidlockfile

import loggers
from lib import read_pidfile, write_pidfile, get_class, check_pidfile
from protocol.dispatcher import Dispatcher
from protocol.interface import INTERFACES
from protocol.transport import ENCODERS, FRAMERS
from errors import ConfigError


class Server(object):
    def __init__(self, name, workdir, parentLogger=None):
        self._name = name
        self._workdir = workdir

        if parentLogger is None:
            parentLogger = loggers.log
        self.log = parentLogger.getChild(name, True)

        self._pidfile = os.path.join(workdir, 'pid', name + '.pid')
        self._cfgfile = os.path.join(workdir, 'etc', name + '.cfg')

        self._dispatcher = None
        self._interface = None

    def start(self):
        pidfile = pidlockfile.TimeoutPIDLockFile(self._pidfile, 3)

        with daemon.DaemonContext(
                # files_preserve=[logFileHandler.stream],
                pidfile=pidfile,
        ):
            try:
                # write_pidfile(pidfilename, os.getpid())
                self.run()
            except Exception as e:
                self.log.exception(e)

    def stop(self):
        pid = read_pidfile(self._pidfile)
        if pid is None:
            # already dead/not started yet
            return
        # get process for this pid
        for proc in psutil.process_iter():
            if proc.pid == pid:
                break
        proc.terminate()
        proc.wait(3)
        proc.kill()

    def isAlive(self):
        if check_pidfile(self._pidfile):
            return True
        return False

    def run(self):
        # write pidfile before doing actual things
        write_pidfile(self._pidfile, os.getpid())
        self._processCfg()

        self.log.info('startup done, handling transport messages')
        self._interface.serve_forever()

    def _processCfg(self):
        self.log.debug('Parse config file %s ...' % self._cfgfile)

        parser = ConfigParser.SafeConfigParser()
        if not parser.read([self._cfgfile]):
            self.log.error('Couldn\'t read cfg file !')
            raise ConfigError('Couldn\'t read cfg file %r' % self._cfgfile)

        if not parser.has_section('server'):
            raise ConfigError(
                'cfg file %r needs a \'server\' section!' % self._cfgfile)

        deviceopts = []
        serveropts = {}
        for section in parser.sections():
            if section == 'server':
                # store for later
                serveropts = dict(item for item in parser.items('server'))
            if section.lower().startswith('device '):
                # device section
                # omit leading 'device ' string
                devname = section[len('device '):]
                devopts = dict(item for item in parser.items(section))
                if 'class' not in devopts:
                    self.log.error('Device %s needs a class option!')
                    raise ConfigError(
                        'cfgfile %r: Device %s needs a class option!'
                        % (self._cfgfile, devname))
                # try to import the class, raise if this fails
                devopts['class'] = get_class(devopts['class'])
                # all went well so far
                deviceopts.append([devname, devopts])

        self._processServerOptions(serveropts)
        self._processDeviceOptions(deviceopts)

    def _processDeviceOptions(self, deviceopts):
        # check devices opts by creating them
        devs = []
        for devname, devopts in deviceopts:
            devclass = devopts.pop('class')
            # create device
            self.log.debug('Creating Device %r' % devname)
            devobj = devclass(self.log.getChild(devname), devopts, devname,
                              self._dispatcher)
            devs.append([devname, devobj])

        # connect devices with dispatcher
        for devname, devobj in devs:
            self.log.info('registering device %r' % devname)
            self._dispatcher.register_device(devobj, devname)
            # also call init on the devices
            devobj.init()

    def _processServerOptions(self, serveropts):
        # eval serveropts
        framingClass = FRAMERS[serveropts.pop('framing')]
        encodingClass = ENCODERS[serveropts.pop('encoding')]
        interfaceClass = INTERFACES[serveropts.pop('interface')]

        self._dispatcher = self._buildObject('Dispatcher', Dispatcher,
                                             dict(encoding=encodingClass(),
                                                  framing=framingClass()))

        # split 'server' section to allow more than one interface
        # also means to move encoding and framing to the interface,
        # so that the dispatcher becomes agnostic
        self._interface = self._buildObject('Interface', interfaceClass,
                                            serveropts,
                                            self._dispatcher)

    def _buildObject(self, name, cls, options, *args):
        self.log.debug('Creating %s ...' % name)
        # cls.__init__ should pop all used args from options!
        obj = cls(self.log.getChild(name.lower()), options, *args)
        if options:
            raise ConfigError('%s: don\'t know how to handle option(s): %s' % (
                cls.__name__,
                ', '.join(options.keys())))
        return obj


