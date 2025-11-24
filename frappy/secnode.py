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

import time
from collections import OrderedDict

from frappy.dynamic import Pinata
from frappy.errors import NoSuchModuleError, NoSuchParameterError, SECoPError, \
    ConfigError, ProgrammingError
from frappy.lib import get_class, generalConfig
from frappy.version import get_version
from frappy.modules import Module


class SecNode:
    """Managing the modules.

    Interface to the modules:
     - add_module(module, modulename)
     - get_module(modulename) returns the requested module or None if there is
       no suitable configuration on the server
    """
    def __init__(self, name, logger, options, srv):
        self.equipment_id = options.pop('equipment_id', name)
        self.nodeprops = {}
        # map ALL modulename -> moduleobj
        self.modules = {}
        self.log = logger
        self.srv = srv
        self.error_count = 0  # count catchable errors during initialization
        self.name = name

    def add_secnode_property(self, prop, value):
        """Add SECNode property. If starting with an underscore, it is exported
        in the description."""
        self.nodeprops[prop] = value

    def logError(self, error):
        """log error or raise, depending on generalConfig settings

        :param error: an exception or a str (considered as ConfigError)

        to be used during startup
        """
        if generalConfig.raise_config_errors:
            raise ConfigError(error) if isinstance(error, str) else error
        self.log.error(str(error))
        self.error_count += 1

    def get_secnode_property(self, prop):
        """Get SECNode property.

        Returns None if not present.
        """
        return self.nodeprops.get(prop)

    def get_module(self, modulename):
        """ Returns a fully initialized module. Or None, if something went
        wrong during instatiating/initializing the module."""
        modobj = self.get_module_instance(modulename)
        if modobj is None:
            return None
        if modobj._isinitialized:
            return modobj

        # also call earlyInit on the modules
        self.log.debug('initializing module %r', modulename)
        modobj.earlyInit()
        if not modobj.earlyInitDone:
            self.logError(ProgrammingError(
                f'module {modulename}: '
                'Module.earlyInit was not called, probably missing super call'))
            modobj.earlyInitDone = True
        modobj.initModule()
        if not modobj.initModuleDone:
            self.logError(ProgrammingError(
                f'module {modulename}: '
                'Module.initModule was not called, probably missing super call'))
            modobj.initModuleDone = True
        modobj._isinitialized = True
        self.log.debug('initialized module %r', modulename)
        return modobj

    def get_module_instance(self, modulename):
        """ Returns the module in its current initialization state or creates a
        new uninitialized module to return.

        When creating a new module, srv.module_config is accessed to get the
        modules configuration.
        """
        if modulename in self.modules:
            return self.modules[modulename]
        if modulename in list(self.modules.values()):
            # it's actually already the module object
            return modulename

        # create module from srv.module_cfg, store and return
        self.log.debug('attempting to create module %r', modulename)

        opts = self.srv.module_cfg.get(modulename, None)
        if opts is None:
            raise NoSuchModuleError(f'Module {modulename!r} does not exist on '
                                    f'this SEC-Node!')
        opts = dict(opts)
        classname = opts.pop('cls')
        try:
            if isinstance(classname, str):
                cls = get_class(classname)
            else:
                cls = classname
            if not issubclass(cls, Module):
                self.logError(f'{cls.__name__} is not a Module')
                return None
        except AttributeError as e:
            if str(e) == 'no such class':
                self.logError(f'{classname} not found')
                return None
            raise
        modobj = cls(modulename, self.log.parent.getChild(modulename),
                     opts, self.srv)
        return modobj

    def create_modules(self):
        self.modules = OrderedDict()

        # create and initialize modules
        todos = list(self.srv.module_cfg.items())
        while todos:
            modname, options = todos.pop(0)
            if modname in self.modules:
                # already created via Attached
                continue
            # For Pinata modules: we need to access this in Self.get_module
            self.srv.module_cfg[modname] = options
            modobj = self.get_module_instance(modname)  # lazy
            if modobj is None:
                self.log.debug('Module %s returned None', modname)
                continue
            self.modules[modname] = modobj
            if isinstance(modobj, Pinata):
                # scan for dynamic devices
                pinata = self.get_module(modname)
                pinata_modules = list(pinata.scanModules())
                for name, _cfg in pinata_modules:
                    if name in self.srv.module_cfg:
                        self.log.error('Module %s, from pinata %s, already '
                                       'exists in config file!', name, modname)
                self.log.info('Pinata %s found %d modules',
                              modname, len(pinata_modules))
                todos.extend(pinata_modules)
        # initialize all modules
        for modname in self.modules:
            modobj = self.get_module(modname)
            # check attached modules for existence
            # normal properties are retrieved too, but this does not harm
            for prop in modobj.propertyDict:
                try:
                    getattr(modobj, prop)
                except SECoPError as e:
                    if generalConfig.raise_config_errors:
                        raise
                    self.error_count += 1
                    modobj.logError(e)

    def export_accessibles(self, modobj):
        self.log.debug('export_accessibles(%r)', modobj.name)
        # omit export=False params!
        res = OrderedDict()
        for aobj in modobj.accessibles.values():
            if aobj.export:
                res[aobj.export] = aobj.for_export()
        self.log.debug('list accessibles for module %s -> %r',
                       modobj.name, res)
        return res

    def build_descriptive_data(self):
        modules = {}
        result = {'modules': modules}
        for modulename in self.modules:
            modobj = self.get_module(modulename)
            if not modobj.export:
                continue
            # some of these need rework !
            mod_desc = {'accessibles': self.export_accessibles(modobj)}
            mod_desc.update(modobj.exportProperties())
            mod_desc.pop('export', None)
            modules[modulename] = mod_desc
        result['equipment_id'] = self.equipment_id
        result['firmware'] = 'FRAPPY ' + get_version()
        result['description'] = self.nodeprops['description']
        for prop, propvalue in self.nodeprops.items():
            if prop.startswith('_'):
                result[prop] = propvalue
        self.descriptive_data = result

    def get_descriptive_data(self, specifier):
        """returns a python object which upon serialisation results in the
        descriptive data"""
        specifier = specifier or ''
        modname, _, pname = specifier.partition(':')
        modules = self.descriptive_data['modules']
        if modname in modules:  # extension to SECoP standard: description of a single module
            result = modules[modname]
            if pname in result['accessibles']:  # extension to SECoP standard: description of a single accessible
                # command is also accepted
                return result['accessibles'][pname]
            if pname:
                raise NoSuchParameterError(f'Module {modname!r} '
                                           f'has no parameter {pname!r}')
            return result
        if not modname or modname == '.':
            return self.descriptive_data
        raise NoSuchModuleError(f'Module {modname!r} does not exist')

    def get_exported_modules(self):
        return [m for m, o in self.modules.items() if o.export]

    def add_module(self, module, modulename):
        """Adds a named module object to this SecNode."""
        self.modules[modulename] = module

    # def remove_module(self, modulename_or_obj):
    #     moduleobj = self.get_module(modulename_or_obj)
    #     modulename = moduleobj.name
    #     if modulename in self.export:
    #         self.export.remove(modulename)
    #     self.modules.pop(modulename)
    #     self._subscriptions.pop(modulename, None)
    #     for k in [kk for kk in self._subscriptions if kk.startswith(f'{modulename}:')]:
    #         self._subscriptions.pop(k, None)

    def shutdown_modules(self):
        """Call 'shutdownModule' for all modules."""
        # stop pollers
        for mod in self.modules.values():
            mod.stopPollThread()
            # do not yet join here, as we want to wait in parallel
        now = time.time()
        deadline = now + 0.5  # should be long enough for most read functions to finish
        for mod in self.modules.values():
            mod.joinPollThread(max(0.0, deadline - now))
            now = time.time()
        for name in self._getSortedModules():
            self.modules[name].shutdownModule()

    def _getSortedModules(self):
        """Sort modules topologically by inverse dependency.

        Example: if there is an IO device A and module B depends on it, then
        the result will be [B, A].
        Right now, if the dependency graph is not a DAG, we give up and return
        the unvisited nodes to be dismantled at the end.
        Taken from Introduction to Algorithms [CLRS].
        """
        def go(name):
            if name in done:  # visiting a node
                return True
            if name in visited:
                visited.add(name)
                return False  # cycle in dependencies -> fail
            visited.add(name)
            if name in unmarked:
                unmarked.remove(name)
            for module in self.modules[name].attachedModules.values():
                res = go(module.name)
                if not res:
                    return False
            visited.remove(name)
            done.add(name)
            l.append(name)
            return True

        unmarked = set(self.modules.keys())  # unvisited nodes
        visited = set()  # visited in DFS, but not completed
        done = set()
        l = []  # list of sorted modules

        while unmarked:
            if not go(unmarked.pop()):
                self.log.error('cyclical dependency between modules!')
                return l[::-1] + list(visited) + list(unmarked)
        return l[::-1]
