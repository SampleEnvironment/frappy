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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

import os
import sys
import argparse
from os import path

# Pathes magic to make python find out stuff.
# also remember our basepath (for etc, pid lookup, etc)
basepath = path.abspath(path.join(sys.path[0], '..'))
etc_path = path.join(basepath, 'etc')
pid_path = path.join(basepath, 'pid')
log_path = path.join(basepath, 'log')
sys.path[0] = path.join(basepath, 'src')

import loggers
from server import Server



def parseArgv(argv):
    parser = argparse.ArgumentParser(description="Manage a SECoP server")
    loggroup = parser.add_mutually_exclusive_group()
    loggroup.add_argument("-v", "--verbose",
                          help="Output lots of diagnostic information",
                          action='store_true', default=False)
    loggroup.add_argument("-q", "--quiet", help="suppress non-error messages",
                          action='store_true', default=False)
    parser.add_argument("action",
                        help="What to do: (re)start, status or stop",
                        choices=['start', 'status', 'stop', 'restart'],
                        default="status")
    parser.add_argument("name",
                        help="Name of the instance.\n"
                        " Uses etc/name.cfg for configuration\n"
                        "may be omitted to mean ALL (which are configured)",
                        nargs='?', default='')
    parser.add_argument('-d',
                        '--daemonize',
                        action='store_true',
                        help='Run as daemon',
                        default=False)
    return parser.parse_args()


def main(argv=None):
    if argv is None:
        argv = sys.argv

    args = parseArgv(argv[1:])

    loglevel = 'debug' if args.verbose else ('error' if args.quiet else 'info')
    loggers.initLogging('secop', loglevel, path.join(log_path))
    logger = loggers.log

    srvNames = []

    if not args.name:
        print('No name given, iterating over all specified servers')
        for dirpath, dirs, files in os.walk(etc_path):
            for fn in files:
                if fn.endswith('.cfg'):
                    srvNames.append(fn[:-4])
                else:
                    logger.debug('configfile with strange extension found: %r'
                                 % path.basename(fn))
            # ignore subdirs!
            while (dirs):
                dirs.pop()
    else:
        srvNames = [args.name]

    srvs = []
    for entry in srvNames:
        srv = Server(entry, basepath)
        srvs.append(srv)

        if args.action == "restart":
            srv.stop()
            srv.start()
        elif args.action == "start":
            if len(srvNames) > 1 or args.daemonize:
                srv.start()
            else:
                srv.run()
        elif args.action == "stop":
            srv.stop()
        elif args.action == "status":
            if srv.isAlive():
                logger.info("Server %s is running." % entry)
            else:
                logger.info("Server %s is DEAD!" % entry)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
