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
"""Define pidfile helpers"""

import atexit
import os

import psutil


def read_pidfile(pidfile):
    """read the given pidfile, return the pid as an int

    or None upon errors (file not existing)"""
    try:
        with open(pidfile, 'r', encoding='utf-8') as f:
            return int(f.read())
    except (OSError, IOError):
        return None


def remove_pidfile(pidfile):
    """remove the given pidfile, typically at end of the process"""
    os.remove(pidfile)


def write_pidfile(pidfile, pid):
    """write the given pid to the given pidfile"""
    with open(pidfile, 'w', encoding='utf-8') as f:
        f.write('%d\n' % pid)
    atexit.register(remove_pidfile, pidfile)


def check_pidfile(pidfile):
    """check if the process from a given pidfile is still running"""
    pid = read_pidfile(pidfile)
    return False if pid is None else psutil.pid_exists(pid)
