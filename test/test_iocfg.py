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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

from logging import Logger
import pytest
from frappy.core import StringIO, Module, HasIO
from frappy.config import process_file, fix_io_modules, Param


class Mod(HasIO, Module):
    ioClass = StringIO


CONFIG = """
IO('io_a', 'tcp://test.psi.ch:7777', visibility='w--')
IO('io_b', 'tcp://test2.psi.ch:8080')

Mod('mod1', 'test.test_iocfg.Mod', '',
    io='io_a',
    )

Mod('mod2', 'test.test_iocfg.Mod', '',
    io='io_b',
    )

Mod('mod3', 'test.test_iocfg.Mod', '',
    io='io_b',
    )
"""


@pytest.mark.parametrize('mod, ioname, iocfg', [
    ('mod1', 'io_a', {
        'cls': 'test.test_iocfg.Mod.ioClass',
        'description': 'communicator for mod1',
        'uri': Param('tcp://test.psi.ch:7777'),
        'visibility': Param('w--')
    },),
    ('mod2', 'io_b', {
        'cls': 'test.test_iocfg.Mod.ioClass',
        'description': 'communicator for mod2, mod3',
        'uri': Param('tcp://test2.psi.ch:8080'),
    }),
])
def test_process_file(mod, ioname, iocfg):
    log = Logger('dummy')
    config = process_file('<test>',log, CONFIG)
    fix_io_modules(config, log)
    assert config[mod]['io'] == {'value': ioname}
    assert config[ioname] == iocfg
