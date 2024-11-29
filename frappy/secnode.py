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

import traceback
from collections import OrderedDict

from frappy.dynamic import Pinata
from frappy.errors import ConfigError, NoSuchModuleError, NoSuchParameterError
from frappy.lib import get_class


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
        for k in list(options):
            self.nodeprops[k] = options.pop(k)
        # map ALL modulename -> moduleobj
        self.modules = {}
        # list of EXPORTED modules
        self.export = []
        self.log = logger
        self.srv = srv
        # set of modules that failed creation
        self.failed_modules = set()
        # list of errors that occured during initialization
        self.errors = []
        self.traceback_counter = 0
        self.name = name

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
        try:
            modobj.earlyInit()
            if not modobj.earlyInitDone:
                self.errors.append(f'{modobj.earlyInit.__qualname__} was not '
                                   f'called, probably missing super call')
            modobj.initModule()
            if not modobj.initModuleDone:
                self.errors.append(f'{modobj.initModule.__qualname__} was not '
                                   f'called, probably missing super call')
        except Exception as e:
            if self.traceback_counter == 0:
                self.log.exception(traceback.format_exc())
            self.traceback_counter += 1
            self.errors.append(f'error initializing {modulename}: {e!r}')
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
        pymodule = None
        try:  # pylint: disable=no-else-return
            classname = opts.pop('cls')
            if isinstance(classname, str):
                pymodule = classname.rpartition('.')[0]
                if pymodule in self.failed_modules:
                    # creation has failed already once, do not try again
                    return None
                cls = get_class(classname)
            else:
                pymodule = classname.__module__
                if pymodule in self.failed_modules:
                    # creation has failed already once, do not try again
                    return None
                cls = classname
        except Exception as e:
            if str(e) == 'no such class':
                self.errors.append(f'{classname} not found')
            else:
                self.failed_modules.add(pymodule)
                if self.traceback_counter == 0:
                    self.log.exception(traceback.format_exc())
                self.traceback_counter += 1
                self.errors.append(f'error importing {classname}')
            return None
        else:
            try:
                modobj = cls(modulename, self.log.parent.getChild(modulename),
                             opts, self.srv)
            except ConfigError as e:
                self.errors.append(f'error creating module {modulename}:')
                for errtxt in e.args[0] if isinstance(e.args[0], list) else [e.args[0]]:
                    self.errors.append('  ' + errtxt)
                modobj = None
            except Exception as e:
                if self.traceback_counter == 0:
                    self.log.exception(traceback.format_exc())
                self.traceback_counter += 1
                self.errors.append(f'error creating {modulename}')
                modobj = None
        if modobj:
            self.add_module(modobj, modulename)
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

    def export_accessibles(self, modulename):
        self.log.debug('export_accessibles(%r)', modulename)
        if modulename in self.export:
            # omit export=False params!
            res = OrderedDict()
            for aobj in self.get_module(modulename).accessibles.values():
                if aobj.export:
                    res[aobj.export] = aobj.for_export()
            self.log.debug('list accessibles for module %s -> %r',
                           modulename, res)
            return res
        self.log.debug('-> module is not to be exported!')
        return OrderedDict()

    def get_descriptive_data(self, specifier):
        """returns a python object which upon serialisation results in the
        descriptive data"""
        specifier = specifier or ''
        modules = {}
        result = {'modules': modules}
        for modulename in self.export:
            module = self.get_module(modulename)
            if not module.export:
                continue
            # some of these need rework !
            mod_desc = {'accessibles': self.export_accessibles(modulename)}
            mod_desc.update(module.exportProperties())
            mod_desc.pop('export', False)
            modules[modulename] = mod_desc
        modname, _, pname = specifier.partition(':')
        if modname in modules:  # extension to SECoP standard: description of a single module
            result = modules[modname]
            if pname in result['accessibles']:  # extension to SECoP standard: description of a single accessible
                # command is also accepted
                result = result['accessibles'][pname]
            elif pname:
                raise NoSuchParameterError(f'Module {modname!r} '
                                           f'has no parameter {pname!r}')
        elif not modname or modname == '.':
            result['equipment_id'] = self.equipment_id
            result['firmware'] = 'FRAPPY - The Python Framework for SECoP'
            result['version'] = '2021.02'
            result.update(self.nodeprops)
        else:
            raise NoSuchModuleError(f'Module {modname!r} does not exist')
        return result

    def add_module(self, module, modulename):
        """Adds a named module object to this SecNode."""
        self.modules[modulename] = module
        if module.export:
            self.export.append(modulename)

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
