#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ library of Tango servers
# Copyright (c) 2015-2017 by the authors, see LICENSE
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
#   Douglas Creager <dcreager@dcreager.net>
#   This file is placed into the public domain.
#
# *****************************************************************************


import os.path
from subprocess import PIPE, Popen

__all__ = ['get_version']

RELEASE_VERSION_FILE = os.path.join(os.path.dirname(__file__),
                                    'RELEASE-VERSION')
GIT_REPO = os.path.join(os.path.dirname(__file__), '..', '.git')


def get_git_version(abbrev=4, cwd=None):
    try:
        p = Popen(['git', '--git-dir=%s' % GIT_REPO,
                   'describe', '--abbrev=%d' % abbrev],
                  stdout=PIPE, stderr=PIPE)
        stdout, _stderr = p.communicate()
        return stdout.strip().decode('utf-8', 'ignore')
    except Exception:
        return None


def read_release_version():
    try:
        with open(RELEASE_VERSION_FILE) as f:
            return f.readline().strip()
    except Exception:
        return None


def write_release_version(version):
    with open(RELEASE_VERSION_FILE, 'w') as f:
        f.write("%s\n" % version)


def get_version(abbrev=4):
    # determine the version from git and from RELEASE-VERSION
    git_version = get_git_version(abbrev)
    release_version = read_release_version()

    # if we have a git version, it is authoritative
    if git_version:
        if git_version != release_version:
            write_release_version(git_version)
        return git_version
    elif release_version:
        return release_version
    else:
        raise ValueError('Cannot find a version number - make sure that '
                         'git is installed or a RELEASE-VERSION file is '
                         'present!')


if __name__ == "__main__":
    print(get_version())
