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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""Define helpers"""

import ast
import configparser
import os
import sys
import traceback
from collections import OrderedDict

from frappy.errors import ConfigError, SECoPError
from frappy.lib import formatException, get_class, generalConfig
from frappy.lib.multievent import MultiEvent
from frappy.params import PREDEFINED_ACCESSIBLES
from frappy.modules import Attached

try:
    from daemon import DaemonContext
    try:
        from daemon import pidlockfile
    except ImportError:
        import daemon.pidfile as pidlockfile
except ImportError:
    DaemonContext = None

try:
    import systemd.daemon
except ImportError:
    systemd = None


class Server:
    INTERFACES = {
        'tcp': 'protocol.interface.tcp.TCPServer',
    }
    _restart = True

    def __init__(self, name, parent_logger, cfgfiles=None, interface=None, testonly=False):
        """initialize server

        Arguments:
        - name:  the node name
        - parent_logger: the logger to inherit from
        - cfgfiles: if not given, defaults to name
            may be a comma separated list of cfg files
            items ending with .cfg are taken as paths, else .cfg is appended and
            files are looked up in the config path retrieved from the general config
        - interface: an uri of the from tcp://<port> or a bare port number for tcp
            if not given, the interface is taken from the config file. In case of
            multiple cfg files, the interface is taken from the first cfg file
        - testonly: test mode. tries to build all modules, but the server is not started

        Format of cfg file (for now, both forms are accepted):
        old form:                  new form:

        [node <equipment id>]      [NODE]
        description=<descr>        id=<equipment id>
                                   description=<descr>

        [interface tcp]            [INTERFACE]
        bindport=10769             uri=tcp://10769
        bindto=0.0.0.0

        [module temp]              [temp]
        ramp=12                    ramp=12
        ...
        """
        self._testonly = testonly

        if not cfgfiles:
            cfgfiles = name
        # sanitize name (in case it is a cfgfile)
        name = os.path.splitext(os.path.basename(name))[0]
        self.log = parent_logger.getChild(name, True)
        merged_cfg = OrderedDict()
        ambiguous_sections = set()
        for cfgfile in cfgfiles.split(','):
            cfgdict = self.loadCfgFile(cfgfile)
            ambiguous_sections |= set(merged_cfg) & set(cfgdict)
            merged_cfg.update(cfgdict)
        self.node_cfg = merged_cfg.pop('NODE', {})
        self.interface_cfg = merged_cfg.pop('INTERFACE', {})
        self.module_cfg = merged_cfg
        if interface:
            ambiguous_sections.discard('interface')
            ambiguous_sections.discard('node')
            self.node_cfg['name'] = name
            self.node_cfg['id'] = cfgfiles
            self.interface_cfg['uri'] = str(interface)
        elif 'uri' not in self.interface_cfg:
            raise ConfigError('missing interface uri')
        if ambiguous_sections:
            self.log.warning('ambiguous sections in %s: %r' % (cfgfiles, tuple(ambiguous_sections)))
        self._cfgfiles = cfgfiles
        self._pidfile = os.path.join(generalConfig.piddir, name + '.pid')

    def loadCfgFile(self, cfgfile):
        if not cfgfile.endswith('.cfg'):
            cfgfile += '.cfg'
        if os.sep in cfgfile:  # specified as full path
            filename = cfgfile if os.path.exists(cfgfile) else None
        else:
            for filename in [os.path.join(d, cfgfile) for d in generalConfig.confdir.split(os.pathsep)]:
                if os.path.exists(filename):
                    break
            else:
                filename = None
        if filename is None:
            raise ConfigError("Couldn't find cfg file %r in %s" % (cfgfile, generalConfig.confdir))
        self.log.debug('Parse config file %s ...' % filename)
        result = OrderedDict()
        parser = configparser.ConfigParser()
        parser.optionxform = str
        if not parser.read([filename]):
            raise ConfigError("Couldn't read cfg file %r" % filename)
        for section, options in parser.items():
            if section == 'DEFAULT':
                continue
            opts = {}
            for k, v in options.items():
                # is the following really needed? - ConfigParser supports multiple lines!
                while '\n.\n' in v:
                    v = v.replace('\n.\n', '\n\n')
                try:
                    opts[k] = ast.literal_eval(v)
                except Exception:
                    opts[k] = v
            # convert old form
            name, _, arg = section.partition(' ')
            if arg:
                if name == 'node':
                    name = 'NODE'
                    opts['id'] = arg
                elif name == 'interface':
                    name = 'INTERFACE'
                    if 'bindport' in opts:
                        opts.pop('bindto', None)
                        opts['uri'] = '%s://%s' % (opts.pop('type', arg), opts.pop('bindport'))
                elif name == 'module':
                    name = arg
            result[name] = opts
        return result

    def start(self):
        if not DaemonContext:
            raise ConfigError('can not daemonize, as python-daemon is not installed')
        piddir = os.path.dirname(self._pidfile)
        if not os.path.isdir(piddir):
            os.makedirs(piddir)
        pidfile = pidlockfile.TimeoutPIDLockFile(self._pidfile)

        if pidfile.is_locked():
            self.log.error('Pidfile already exists. Exiting')

        with DaemonContext(
                pidfile=pidfile,
                files_preserve=self.log.getLogfileStreams()):
            self.run()

    def unknown_options(self, cls, options):
        return ("%s class don't know how to handle option(s): %s" %
                (cls.__name__, ', '.join(options)))

    def run(self):
        while self._restart:
            self._restart = False
            try:
                if systemd:
                    systemd.daemon.notify("STATUS=initializing")
                self._processCfg()
                if self._testonly:
                    return
            except Exception:
                print(formatException(verbose=True))
                raise

            opts = dict(self.interface_cfg)
            scheme, _, _ = opts['uri'].rpartition('://')
            scheme = scheme or 'tcp'
            cls = get_class(self.INTERFACES[scheme])
            with cls(scheme, self.log.getChild(scheme), opts, self) as self.interface:
                if opts:
                    raise ConfigError(self.unknown_options(cls, opts))
                self.log.info('startup done, handling transport messages')
                if systemd:
                    systemd.daemon.notify("READY=1\nSTATUS=accepting requests")
                self.interface.serve_forever()
                self.interface.server_close()
            if self._restart:
                self.restart_hook()
                self.log.info('restart')
            else:
                self.log.info('shut down')

    def restart(self):
        if not self._restart:
            self._restart = True
            self.interface.shutdown()

    def shutdown(self):
        self._restart = False
        self.interface.shutdown()

    def _processCfg(self):
        errors = []
        opts = dict(self.node_cfg)
        cls = get_class(opts.pop('class', 'protocol.dispatcher.Dispatcher'))
        self.dispatcher = cls(opts.pop('name', self._cfgfiles), self.log.getChild('dispatcher'), opts, self)
        if opts:
            errors.append(self.unknown_options(cls, opts))
        self.modules = OrderedDict()
        failure_traceback = None  # traceback for the first error
        failed = set()  # python modules failed to load
        self.lastError = None
        for modname, options in self.module_cfg.items():
            opts = dict(options)
            pymodule = None
            try:
                classname = opts.pop('class')
                pymodule = classname.rpartition('.')[0]
                if pymodule in failed:
                    continue
                cls = get_class(classname)
            except Exception as e:
                if str(e) == 'no such class':
                    errors.append('%s not found' % classname)
                else:
                    failed.add(pymodule)
                    if failure_traceback is None:
                        failure_traceback = traceback.format_exc()
                    errors.append('error importing %s' % classname)
            else:
                try:
                    modobj = cls(modname, self.log.getChild(modname), opts, self)
                    # all used args should be popped from opts!
                    if opts:
                        errors.append(self.unknown_options(cls, opts))
                    self.modules[modname] = modobj
                except ConfigError as e:
                    errors.append('error creating module %s:' % modname)
                    for errtxt in e.args[0] if isinstance(e.args[0], list) else [e.args[0]]:
                        errors.append('  ' + errtxt)
                except Exception:
                    if failure_traceback is None:
                        failure_traceback = traceback.format_exc()
                    errors.append('error creating %s' % modname)

        missing_super = set()
        # all objs created, now start them up and interconnect
        for modname, modobj in self.modules.items():
            self.log.info('registering module %r' % modname)
            self.dispatcher.register_module(modobj, modname, modobj.export)
            # also call earlyInit on the modules
            modobj.earlyInit()
            if not modobj.earlyInitDone:
                missing_super.add('%s was not called, probably missing super call'
                                  % modobj.earlyInit.__qualname__)

        # handle attached modules
        for modname, modobj in self.modules.items():
            attached_modules = {}
            for propname, propobj in modobj.propertyDict.items():
                if isinstance(propobj, Attached):
                    try:
                        attname = getattr(modobj, propname)
                        if attname:  # attached module specified in cfg file
                            attobj = self.dispatcher.get_module(attname)
                            if isinstance(attobj, propobj.basecls):
                                attached_modules[propname] = attobj
                            else:
                                errors.append('attached module %s=%r must inherit from %r'
                                              % (propname, attname, propobj.basecls.__qualname__))
                    except SECoPError as e:
                        errors.append('module %s, attached %s: %s' % (modname, propname, str(e)))
            modobj.attachedModules = attached_modules

        # call init on each module after registering all
        for modname, modobj in self.modules.items():
            try:
                modobj.initModule()
                if not modobj.initModuleDone:
                    missing_super.add('%s was not called, probably missing super call'
                                      % modobj.initModule.__qualname__)
            except Exception as e:
                if failure_traceback is None:
                    failure_traceback = traceback.format_exc()
                errors.append('error initializing %s: %r' % (modname, e))

        if not self._testonly:
            start_events = MultiEvent(default_timeout=30)
            for modname, modobj in self.modules.items():
                # startModule must return either a timeout value or None (default 30 sec)
                start_events.name = 'module %s' % modname
                modobj.startModule(start_events)
                if not modobj.startModuleDone:
                    missing_super.add('%s was not called, probably missing super call'
                                      % modobj.startModule.__qualname__)
            errors.extend(missing_super)

        if errors:
            for errtxt in errors:
                for line in errtxt.split('\n'):
                    self.log.error(line)
            # print a list of config errors to stderr
            sys.stderr.write('\n'.join(errors))
            sys.stderr.write('\n')
            if failure_traceback:
                sys.stderr.write(failure_traceback)
            sys.exit(1)

        if self._testonly:
            return
        self.log.info('waiting for modules being started')
        start_events.name = None
        if not start_events.wait():
            # some timeout happened
            for name in start_events.waiting_for():
                self.log.warning('timeout when starting %s' % name)
        self.log.info('all modules started')
        history_path = os.environ.get('FRAPPY_HISTORY')
        if history_path:
            from frappy_psi.historywriter import FrappyHistoryWriter  # pylint: disable=import-outside-toplevel
            writer = FrappyHistoryWriter(history_path, PREDEFINED_ACCESSIBLES.keys(), self.dispatcher)
            # treat writer as a connection
            self.dispatcher.add_connection(writer)
            writer.init(self.dispatcher.handle_describe(writer, None, None))
        # TODO: if ever somebody wants to implement an other history writer:
        # - a general config file /etc/secp/frappy.conf or <frappy repo>/etc/frappy.conf
        #   might be introduced, which contains the log, pid and cfg directory path and
        #   the class path implementing the history
        # - or we just add here an other if statement:
        #   history_path = os.environ.get('ALTERNATIVE_HISTORY')
        #   if history_path:
        #       from frappy_<xx>.historywriter import ... etc.
