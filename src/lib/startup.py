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
import daemonize
import ConfigParser

from lib import read_pidfile, write_pidfile, get_class, make_logger
from server import DeviceServer as Server
from errors import ConfigError

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

def start_server(srvname, base_path, loglevel, daemon=False):
    """start a server, part1

    handle the daemonizing and logging stuff and call the second step
    """
    pidfile = os.path.join(base_path, 'pid', srvname + '.pid')
    if daemon:
# dysfunctional :(
        daemonproc = daemonize.Daemonize("server %s" % srvname,
                                         pid=pidfile,
                                         action=lambda: startup(srvname, base_path, loglevel),
                                         )
        daemonproc.start()


    else:
        write_pidfile(pidfile, os.getpid())
        startup(srvname, base_path, loglevel) # blocks!

# unexported stuff here
def startup(srvname, base_path, loglevel):
    """really start a server (part2)

    loads the config, initiate all objects, link them together
    and finally start the interface server.
    Never returns. (may raise)
    """
    cfgfile = os.path.join(base_path, 'etc', srvname + '.cfg')

    logger = make_logger('server', srvname, base_path=base_path, loglevel=loglevel)
    logger.debug("parsing %r" % cfgfile)

    parser = ConfigParser.SafeConfigParser()
    if not parser.read([cfgfile]):
        logger.error("Couldn't read cfg file !")
        raise ConfigError("Couldn't read cfg file %r" % cfgfile)

    # evaluate Server specific stuff
    if not parser.has_section('server'):
        logger.error("cfg file needs a 'server' section!")
        raise ConfigError("cfg file %r needs a 'server' section!" % cfgfile)
    serveropts = dict(item for item in parser.items('server'))

    # check serveropts (init server)
    # this raises if something wouldn't work
    logger.debug("Creating device server")
    server = Server(logger, serveropts)

    # iterate over all sections, checking for devices
    deviceopts = []
    for section in parser.sections():
        if section == "server":
            continue # already handled, see above
        if section.lower().startswith("device"):
            # device section
            devname = section[len('device '):] # omit leading 'device ' string
            devopts = dict(item for item in parser.items(section))
            if 'class' not in devopts:
                logger.error("Device %s needs a class option!")
                raise ConfigError("cfgfile %r: Device %s needs a class option!" % (cfgfile, devname))
            # try to import the class, raise if this fails
            devopts['class'] = get_class(devopts['class'])
            # all went well so far
            deviceopts.append([devname, devopts])

    # check devices by creating them
    devs = {}
    for devname, devopts in deviceopts:
        devclass = devopts.pop('class')
        # create device
        logger.debug("Creating Device %r" % devname)
        devobj = devclass(devname, server, logger, devopts)
        devs[devname] = devobj

    # connect devices with server
    for devname, devobj in devs.items():
        logger.info("registering device %r" % devname)
        server.register_device(devobj, devname)
        # also call init on the devices
        logger.debug("device.init()")
        devobj.init()

    # handle requests until stop is requsted
    logger.info('startup done, handling transport messages')
    server.serve_forever()
