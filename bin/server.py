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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

import os
import sys
from os import path

# Pathes magic to make python find out stuff.
# also remember our basepath (for etc, pid lookup, etc)
basepath = path.abspath(path.join(sys.path[0], '..'))
etc_path = path.join(basepath, 'etc')
pid_path = path.join(basepath, 'pid')
log_path = path.join(basepath, 'log')
sys.path[0] = path.join(basepath, 'src')


import argparse
from lib import check_pidfile, start_server, kill_server

parser = argparse.ArgumentParser(description = "Manage a SECoP server")
loggroup = parser.add_mutually_exclusive_group()
loggroup.add_argument("-v", "--verbose", help="Output lots of diagnostic information", 
                    action='store_true', default=False)
loggroup.add_argument("-q", "--quiet", help="suppress non-error messages", action='store_true',
                    default=False)
parser.add_argument("action", help="What to do with the server: (re)start, status or stop",
                    choices=['start', 'status', 'stop', 'restart'], default="status")
parser.add_argument("name", help="Name of the instance. Uses etc/name.cfg for configuration\n"
                    "may be omitted to mean ALL (which are configured)",
                    nargs='?', default='')
args = parser.parse_args()


import logging
loglevel =  logging.DEBUG if args.verbose else (logging.ERROR if args.quiet else logging.INFO)
logging.basicConfig(level=loglevel, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('server')
logger.setLevel(loglevel)
fh = logging.FileHandler(path.join(log_path, 'server.log'), 'w')
fh.setLevel(loglevel)
logger.addHandler(fh)

logger.debug("action specified %r" % args.action)

def handle_servername(name, action):
    pidfile = path.join(pid_path, name + '.pid')
    cfgfile = path.join(etc_path, name + '.cfg')
    if action == "restart":
        handle_servername(name, 'stop')
        handle_servername(name, 'start')
        return
    elif action == "start":
        logger.info("Starting server %s" % name)
        # XXX also do it !
        start_server(name, basepath, loglevel)
    elif action == "stop":
        pid = check_pidfile(pidfile)
        if pid:
            logger.info("Stopping server %s" % name)
            # XXX also do it!
            stop_server(pidfile)
        else:
            logger.info("Server %s already dead" % name)
    elif action == "status":
        if check_pidfile(pidfile):
            logger.info("Server %s is running." % name)
        else:
            logger.info("Server %s is DEAD!" % name)
    else:
        logger.error("invalid action specified: How can this ever happen???")

print "================================"
if not args.name:
    logger.debug("No name given, iterating over all specified servers")
    for dirpath, dirs, files in os.walk(etc_path):
        for fn in files:
            if fn.endswith('.cfg'):
                handle_servername(fn[:-4], args.action)
            else:
                logger.debug('configfile with strange extension found: %r' 
                             % path.basename(fn))
        # ignore subdirs!
        while(dirs):
            dirs.pop()
else:
    handle_servername(args.name, args.action)
print "================================"
