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

import json
import os
from os.path import join
import pytest
from frappy.config import Param
from frappy.core import Module, ScaledInteger, IntRange, StringType, StructOf
from frappy.lib import generalConfig
from frappy.persistent import PersistentParam, PersistentMixin


class SecNodeStub:
    pass


class DispatcherStub:
    def announce_update(self, moduleobj, pobj):
        pass


class LoggerStub:
    def debug(self, fmt, *args):
        print(fmt % args)
    info = warning = exception = error = debug
    handlers = []


logger = LoggerStub()


class ServerStub:
    def __init__(self, equipment_id):
        self.dispatcher = DispatcherStub()
        self.secnode = SecNodeStub()
        self.secnode.equipment_id = equipment_id


class Mod(PersistentMixin, Module):
    flt = PersistentParam('', ScaledInteger(0.1), default=1.0)
    stc = PersistentParam('', StructOf(i=IntRange(0, 10), s=StringType()))

    def write_flt(self, value):
        return value

    def write_stc(self, value):
        return value


save_tests = [
    ({'flt': Param(5.5), 'stc': Param({'i': 3, 's': 'test'})},
     {'flt': 55, 'stc': {'i': 3, 's': 'test'}}),
    ({'flt': Param(5.5)},
     {'flt': 55, 'stc': {'i': 0, 's': ''}}),  # saved default values
]
@pytest.mark.parametrize('cfg, data', save_tests)
def test_save(tmpdir, cfg, data):
    generalConfig.logdir = tmpdir

    cfg['description'] = ''
    m = Mod('m', logger, cfg, ServerStub('savetest'))
    assert m.writeDict == {k: getattr(m, k) for k in data}
    m.writeDict.clear()  # clear in order to indicate writing has happened
    m.saveParameters()
    with open(join(tmpdir, 'persistent', 'savetest.m.json'), encoding='utf-8') as f:
        assert json.load(f) == data


load_tests = [
    # check that value from cfg is overriding value from persistent file
    ({'flt': Param(5.5), 'stc': Param({'i': 3, 's': 'test'})},
     {'flt': 33, 'stc': {'i': 1, 's': 'bar'}},
     {'flt': 5.5, 'stc': {'i': 3, 's': 'test'}}),
    # check that value from file is taken when not in cfg
    ({'flt': Param(3.5)},
     {'flt': 35, 'stc': {'i': 2, 's': ''}},
     {'flt': 3.5, 'stc': {'i': 2, 's': ''}}),
    # check default is written when neither cfg is given nor persistent values present
    ({},
     {},
     {'flt': 1.0, 'stc': {'i': 0, 's': ''}}),
]
@pytest.mark.parametrize('cfg, data, written', load_tests)
def test_load(tmpdir, cfg, data, written):
    generalConfig.logdir = tmpdir

    os.makedirs(join(tmpdir, 'persistent'), exist_ok=True)
    with open(join(tmpdir, 'persistent', 'loadtest.m.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f)
    cfg['description'] = ''
    m = Mod('m', logger, cfg, ServerStub('loadtest'))
    assert m.writeDict == written
    # parameter given in config must override values from file
    for k, v in cfg.items():
        assert getattr(m, k) == v['value']
    for k, v in written.items():
        assert getattr(m, k) == v
