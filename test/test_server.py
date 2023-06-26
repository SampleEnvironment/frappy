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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

import pytest
# pylint: disable=redefined-outer-name

from frappy.server import Server

from .test_config import direc  # pylint: disable=unused-import


class LoggerStub:
    def debug(self, fmt, *args):
        pass

    def getChild(self, *args):
        return self

    info = warning = exception = error = debug
    handlers = []


@pytest.fixture
def log():
    return LoggerStub()


def test_name_only(direc, log):
    """only see that this does not throw. get config from name."""
    s = Server('pyfile', log)
    s._processCfg()


def test_file(direc, log):
    """only see that this does not throw. get config from cfgfiles."""
    s = Server('foo', log, cfgfiles='pyfile_cfg.py')
    s._processCfg()
