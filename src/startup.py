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

"""Define helpers"""
import os
import psutil
import ConfigParser

# apt install python-daemon !!!do not use pip install daemon <- wrong version!
import daemon
from daemon import pidlockfile

from lib import read_pidfile, write_pidfile, get_class
from protocol.dispatcher import Dispatcher
from protocol.interface import INTERFACES
from protocol.transport import ENCODERS, FRAMERS
from errors import ConfigError
from logger import get_logger

__ALL__ = ['kill_server', 'start_server']


def kill_server(pidfile):
    """kill a server specified by a pidfile"""
    pid = read_pidfile(pidfile)
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


def start_server(srvname, base_path, loglevel, daemonize=False):
    """start a server, part1

    handle the daemonizing and logging stuff and call the second step
    """
    pidfilename = os.path.join(base_path, 'pid', srvname + '.pid')
    pidfile = pidlockfile.TimeoutPIDLockFile(pidfilename, 3)
    if daemonize:
        with daemon.DaemonContext(
                #files_preserve=[logFileHandler.stream],
                pidfile=pidfile,
                ):
                try:
                    #write_pidfile(pidfilename, os.getpid())
                    startup(srvname, base_path, loglevel)
                except Exception as e:
                    logging.exception(e)
    else:
        write_pidfile(pidfilename, os.getpid())
        startup(srvname, base_path, loglevel)  # blocks!


# unexported stuff here

def startup(srvname, base_path, loglevel):
    """really start a server (part2)

    loads the config, initiate all objects, link them together
    and finally start the interface server.
    Never returns. (may raise)
    """
    cfgfile = os.path.join(base_path, 'etc', srvname + '.cfg')

    logger = get_logger(srvname, loglevel=loglevel)
    logger.debug('parsing %r' % cfgfile)

    parser = ConfigParser.SafeConfigParser()
    if not parser.read([cfgfile]):
        logger.error('Couldn\'t read cfg file !')
        raise ConfigError('Couldn\'t read cfg file %r' % cfgfile)

    # iterate over all sections, checking for devices/server
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
                logger.error('Device %s needs a class option!')
                raise ConfigError('cfgfile %r: Device %s needs a class option!'
                                  % (cfgfile, devname))
            # try to import the class, raise if this fails
            devopts['class'] = get_class(devopts['class'])
            # all went well so far
            deviceopts.append([devname, devopts])

    # there are several sections which resultin almost identical code: refactor
    def init_object(name, cls, logger, options={}, *args):
        logger.debug('Creating ' + name)
        # cls.__init__ should pop all used args from options!
        obj = cls(logger, options, *args)
        if options:
            raise ConfigError('%s: don\'t know how to handle option(s): %s' % (
                              cls.__name__,
                              ', '.join(options.keys())))
        return obj

    # evaluate Server specific stuff
    if not serveropts:
        raise ConfigError('cfg file %r needs a \'server\' section!' % cfgfile)

    # eval serveropts
    Framing = FRAMERS[serveropts.pop('framing')]
    Encoding = ENCODERS[serveropts.pop('encoding')]
    Interface = INTERFACES[serveropts.pop('interface')]

    dispatcher = init_object('Dispatcher', Dispatcher, logger,
                             dict(encoding=Encoding(),
                                  framing=Framing()))
    # split 'server' section to allow more than one interface
    # also means to move encoding and framing to the interface,
    # so that the dispatcher becomes agnostic
    interface = init_object('Interface', Interface, logger, serveropts,
                            dispatcher)

    # check devices opts by creating them
    devs = []
    for devname, devopts in deviceopts:
        devclass = devopts.pop('class')
        # create device
        logger.debug('Creating Device %r' % devname)
        devobj = devclass(logger, devopts, devname, dispatcher)
        devs.append([devname, devobj])

    # connect devices with dispatcher
    for devname, devobj in devs:
        logger.info('registering device %r' % devname)
        dispatcher.register_device(devobj, devname)
        # also call init on the devices
        logger.debug('device.init()')
        devobj.init()

    # handle requests until stop is requsted
    logger.info('startup done, handling transport messages')
    interface.serve_forever()
