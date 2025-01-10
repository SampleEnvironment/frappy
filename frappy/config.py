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
# Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

import os
from pathlib import Path
import re
from collections import Counter

from frappy.errors import ConfigError
from frappy.lib import generalConfig


class Undef:
    pass


class Node(dict):
    def __init__(
            self,
            equipment_id,
            description,
            interface=None,
            cls='frappy.protocol.dispatcher.Dispatcher',
            **kwds
    ):
        super().__init__(
            equipment_id=equipment_id,
            description=description,
            interface=interface,
            cls=cls,
            **kwds
        )


class Param(dict):
    def __init__(self, value=Undef, **kwds):
        if value is not Undef:
            kwds['value'] = value
        super().__init__(**kwds)


class Group(tuple):
    def __new__(cls, *args):
        return super().__new__(cls, args)


class Mod(dict):
    def __init__(self, name, cls, description, **kwds):
        super().__init__(
            name=name,
            cls=cls,
            description=description
        )

        # matches name from spec
        if not re.match(r'^[a-zA-Z]\w{0,62}$', name, re.ASCII):
            raise ConfigError(f'Not a valid SECoP Module name: "{name}".'
                              ' Does it only contain letters, numbers and underscores?')
        # Make parameters out of all keywords
        groups = {}
        for key, val in kwds.items():
            if isinstance(val, Param):
                self[key] = val
            elif isinstance(val, Group):
                groups[key] = val
            else:
                # shortcut to only set value
                self[key] = Param(val)
        for group, members in groups.items():
            for member in members:
                self[member]['group'] = group


class Collector:
    def __init__(self, cls):
        self.list = []
        self.cls = cls

    def add(self, *args, **kwds):
        self.list.append(self.cls(*args, **kwds))

    def append(self, mod):
        self.list.append(mod)


class NodeCollector:
    def __init__(self):
        self.node = None

    def add(self, *args, **kwds):
        if self.node is None:
            self.node = Node(*args, **kwds)
        else:
            raise ConfigError('Only one Node is allowed per file!')


class Config(dict):
    def __init__(self, node, modules):
        super().__init__(
            node=node.node,
            **{mod['name']: mod for mod in modules.list}
        )
        self.module_names = {mod.pop('name') for mod in modules.list}
        self.ambiguous = set()

    def merge_modules(self, other):
        """ merges only the modules from 'other' into 'self'"""
        self.ambiguous |= self.module_names & other.module_names
        equipment_id = other['node']['equipment_id']
        for name, mod in other.items():
            if name == 'node':
                continue
            if name not in self.module_names:
                self.module_names.add(name)
                self[name] = mod
                mod['original_id'] = equipment_id


def process_file(filename, log):
    config_text = filename.read_bytes()
    node = NodeCollector()
    mods = Collector(Mod)
    ns = {'Node': node.add, 'Mod': mods.add, 'Param': Param, 'Command': Param, 'Group': Group}

    # pylint: disable=exec-used
    exec(compile(config_text, filename, 'exec'), ns)

    # check for duplicates in the file itself. Between files comes later
    duplicates = [name for name, count in Counter([mod['name']
                    for mod in mods.list]).items() if count > 1]
    if duplicates:
        log.warning('Duplicate module name in file \'%s\': %s',
                    filename, ','.join(duplicates))
    return Config(node, mods)


def to_config_path(cfgfile, log):
    candidates = [cfgfile + e for e in ['_cfg.py', '.py', '']]
    if os.sep in cfgfile:  # specified as full path
        file = Path(cfgfile) if Path(cfgfile).exists() else None
    else:
        for file in [Path(d) / candidate
                     for d in generalConfig.confdir
                     for candidate in candidates]:
            if file.exists():
                break
        else:
            file = None
    if file is None:
        raise ConfigError(f"Couldn't find cfg file {cfgfile!r} in {generalConfig.confdir}")
    if not file.name.endswith('_cfg.py'):
        log.warning("Config files should end in '_cfg.py': %s", file.name)
    log.debug('Using config file %s for %s', file, cfgfile)
    return file


def load_config(cfgfiles, log):
    """Load config files.

    Only the node-section of the first config file will be returned.
    The others will be discarded.
    Arguments
    - cfgfiles : list
        List of config file paths
    - log : frappy.logging.Mainlogger
        Logger aquired from frappy.logging
    Returns
    - config: Config
        merged configuration
    """
    config = None
    for cfgfile in cfgfiles:
        filename = to_config_path(str(cfgfile), log)
        log.debug('Parsing config file %s...', filename)
        cfg = process_file(filename, log)
        if config:
            config.merge_modules(cfg)
        else:
            config = cfg

    if config.ambiguous:
        log.warning('ambiguous sections in %s: %r',
                    cfgfiles, list(config.ambiguous))
    return config
