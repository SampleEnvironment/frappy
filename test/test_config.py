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

# false positive with fixtures
# pylint: disable=redefined-outer-name
import pytest

from frappy.config import Collector, Config, Mod, NodeCollector, load_config, \
    process_file, to_config_path
from frappy.errors import ConfigError
from frappy.lib import generalConfig


class LoggerStub:
    def debug(self, fmt, *args):
        pass
    info = warning = exception = error = debug
    handlers = []


@pytest.fixture
def log():
    return LoggerStub()


PY_FILE = """Node('foonode', 'fodesc', 'fooface', _secnode_prop='secnode_prop')
Mod('foo', 'frappy.modules.Readable', 'description', value=5)
Mod('bar', 'frappy.modules.Readable', 'about me', export=False)
Mod('baz', 'frappy.modules.Readable', 'things', value=Param(3, unit='BAR'))
"""


# fixture file system, TODO: make a bit nicer?
@pytest.fixture
def direc(tmp_path_factory):
    d = tmp_path_factory.mktemp('cfgdir')
    a = d / 'a'
    b = d / 'b'
    a.mkdir()
    b.mkdir()
    f = a / 'config_cfg.py'
    pyfile = a / 'pyfile_cfg.py'
    ff = b / 'test_cfg.py'
    fff = b / 'alsoworks.py'
    f.touch()
    ff.touch()
    fff.touch()
    pyfile.write_text(PY_FILE)
    generalConfig.testinit(confdir=[a, b], piddir=d)
    return d


files = [('config', 'a/config_cfg.py'),
         ('config_cfg', 'a/config_cfg.py'),
         ('config_cfg.py', 'a/config_cfg.py'),
         ('test', 'b/test_cfg.py'),
         ('test_cfg', 'b/test_cfg.py'),
         ('test_cfg.py', 'b/test_cfg.py'),
         ('alsoworks', 'b/alsoworks.py'),
         ('alsoworks.py', 'b/alsoworks.py'),
         ]


@pytest.mark.parametrize('file, res', files)
def test_to_cfg_path(log, direc, file, res):
    assert str(to_config_path(file, log)).endswith(res)


def test_cfg_not_existing(direc, log):
    with pytest.raises(ConfigError):
        to_config_path('idonotexist', log)


def collector_helper(node, mods):
    n = NodeCollector()
    n.add(*node)
    m = Collector(Mod)
    m.list = [Mod(module, '', '') for module in mods]
    return n, m


configs = [
    (['n1', 'desc', 'iface'], ['foo', 'bar', 'baz'], ['n2', 'foo', 'bar'],
     ['foo', 'more', 'other'], ['n1', 'iface', 5, {'foo'}]),
    (['n1', 'desc', 'iface'], ['foo', 'bar', 'baz'], ['n2', 'foo', 'bar'],
     ['different', 'more', 'other'], ['n1', 'iface', 6, set()]),
]


@pytest.mark.parametrize('n1, m1, n2, m2, res', configs)
def test_merge(n1, m1, n2, m2, res):
    name, iface, num_mods, ambig = res
    c1 = Config(*collector_helper(n1, m1))
    c2 = Config(*collector_helper(n2, m2))
    c1.merge_modules(c2)
    assert c1['node']['equipment_id'] == name
    assert c1['node']['interface'] == iface
    assert len(c1.module_names) == num_mods
    assert c1.ambiguous == ambig


def do_asserts(ret):
    assert len(ret.module_names) == 3
    assert set(ret.module_names) == set(['foo', 'bar', 'baz'])
    assert ret['node']['equipment_id'] == 'foonode'
    assert ret['node']['interface'] == 'fooface'
    assert ret['foo'] == {'cls': 'frappy.modules.Readable',
                          'description': 'description', 'value': {'value': 5}}
    assert ret['bar'] == {'cls': 'frappy.modules.Readable',
                          'description': 'about me', 'export': {'value': False}}
    assert ret['baz'] == {'cls': 'frappy.modules.Readable',
                          'description': 'things',
                          'value': {'value': 3, 'unit': 'BAR'}}


def test_process_file(direc, log):
    ret = process_file(direc / 'a' / 'pyfile_cfg.py', log)
    do_asserts(ret)


def test_full(direc, log):
    ret = load_config('pyfile_cfg.py', log)
    do_asserts(ret)
