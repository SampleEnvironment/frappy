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
# Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
import os
import re

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
            raise ConfigError('Not a valid SECoP Module name: "%s". '
                              'Does it only contain letters, numbers and underscores?'
                              % (name))
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
        for name, mod in other.items():
            if name == 'node':
                continue
            if name not in self.module_names:
                self.module_names.add(name)
                self.modules.append(mod)


def process_file(config_text):
    node = NodeCollector()
    mods = Collector(Mod)
    ns = {'Node': node.add, 'Mod': mods.add, 'Param': Param, 'Command': Param, 'Group': Group}

    # pylint: disable=exec-used
    exec(config_text, ns)
    return Config(node, mods)


def to_config_path(cfgfile, log):
    candidates = [cfgfile + e for e in ['_cfg.py', '.py', '']]
    if os.sep in cfgfile:  # specified as full path
        filename = cfgfile if os.path.exists(cfgfile) else None
    else:
        for filename in [os.path.join(d, candidate)
                         for d in generalConfig.confdir.split(os.pathsep)
                         for candidate in candidates]:
            if os.path.exists(filename):
                break
        else:
            filename = None

    if filename is None:
        raise ConfigError("Couldn't find cfg file %r in %s"
                          % (cfgfile, generalConfig.confdir))
    if not filename.endswith('_cfg.py'):
        log.warning("Config files should end in '_cfg.py': %s", os.path.basename(filename))
    log.debug('Using config file %s for %s', filename, cfgfile)
    return filename


def load_config(cfgfiles, log):
    """Load config files.

    Only the node-section of the first config file will be returned.
    The others will be discarded.
    Arguments
    - cfgfiles : str
        Comma separated list of config-files
    - log : frappy.logging.Mainlogger
        Logger aquired from frappy.logging
    Returns
    - config: Config
        merged configuration
    """
    config = None
    for cfgfile in cfgfiles.split(','):
        filename = to_config_path(cfgfile, log)
        log.debug('Parsing config file %s...', filename)
        with open(filename, 'rb') as f:
            config_text = f.read()
        cfg = process_file(config_text)
        if config:
            config.merge_modules(cfg)
        else:
            config = cfg

    if config.ambiguous:
        log.warning('ambiguous sections in %s: %r',
                    cfgfiles, list(config.ambiguous))
    return config
