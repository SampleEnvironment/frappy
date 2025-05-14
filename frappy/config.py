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
# Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************

import os
from pathlib import Path
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

    def override(self, **kwds):
        name = self['name']
        warnings = []
        for key, ovr in kwds.items():
            if isinstance(ovr, Group):
                warnings.append(f'ignore Group when overriding module {name}')
                continue
            param = self.get(key)
            if param is None:
                self[key] = ovr if isinstance(ovr, Param) else Param(ovr)
                continue
            if isinstance(param, Param):
                if isinstance(ovr, Param):
                    param.update(ovr)
                else:
                    param['value'] = ovr
            else:  # description or cls
                self[key] = ovr
        return warnings


class Collector:
    def __init__(self):
        self.modules = {}
        self.warnings = []

    def add(self, *args, **kwds):
        mod = Mod(*args, **kwds)
        name = mod.pop('name')
        if name in self.modules:
            self.warnings.append(f'duplicate module {name} overrides previous')
        self.modules[name] = mod
        return mod

    def override(self, name, **kwds):
        """override properties/parameters of previously configured modules

        this is useful together with 'include'
        """
        mod = self.modules.get(name)
        if mod is None:
            self.warnings.append(f'try to override nonexisting module {name}')
            return
        self.warnings.extend(mod.override(**kwds))


class NodeCollector:
    def __init__(self):
        self.node = None

    def add(self, *args, **kwds):
        if self.node is None:
            self.node = Node(*args, **kwds)
        else:
            raise ConfigError('Only one Node is allowed per file!')

    def override(self, **kwds):
        if self.node is None:
            raise ConfigError('node must be defined before overriding')
        self.node.update(kwds)


class Config(dict):
    def __init__(self, node, modules):
        super().__init__(node=node.node, **modules.modules)
        self.module_names = set(modules.modules)
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


class Include:
    def __init__(self, namespace, log):
        self.namespace = namespace
        self.log = log

    def __call__(self, cfgfile):
        filename = to_config_path(cfgfile, self.log, '')
        # pylint: disable=exec-used
        exec(compile(filename.read_bytes(), filename, 'exec'), self.namespace)


def process_file(filename, log):
    config_text = filename.read_bytes()
    node = NodeCollector()
    mods = Collector()
    ns = {'Node': node.add, 'Mod': mods.add, 'Param': Param, 'Command': Param, 'Group': Group,
          'override': mods.override, 'overrideNode': node.override}
    ns['include'] = Include(ns, log)
    # pylint: disable=exec-used
    exec(compile(config_text, filename, 'exec'), ns)

    if mods.warnings:
        log.warning('warnings in %s', filename)
        for text in mods.warnings:
            log.warning(text)
    return Config(node, mods)


def to_config_path(cfgfile, log, check_end='_cfg.py'):
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
    if not file.name.endswith(check_end):
        log.warning("Config files should end in %r: %s", check_end, file.name)
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
            if config.get('node') is None:
                raise ConfigError(f'missing Node in {filename}')

    if config.ambiguous:
        log.warning('ambiguous sections in %s: %r',
                    cfgfiles, list(config.ambiguous))
    return config
