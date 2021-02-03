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

import os
import ast
import time
import threading
import configparser
from collections import OrderedDict
try:
    from daemon import DaemonContext
    try:
        import daemon.pidlockfile as pidlockfile
    except ImportError:
        import daemon.pidfile as pidlockfile
except ImportError:
    DaemonContext = None

from secop.errors import ConfigError
from secop.lib import formatException, get_class, getGeneralConfig
from secop.modules import Attached

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
        cfg = getGeneralConfig()

        self.log = parent_logger.getChild(name, True)
        if not cfgfiles:
            cfgfiles = name
        merged_cfg = OrderedDict()
        ambiguous_sections = set()
        for cfgfile in cfgfiles.split(','):
            if cfgfile.endswith('.cfg') and os.path.exists(cfgfile):
                filename = cfgfile
            else:
                filename = os.path.join(cfg['confdir'], cfgfile + '.cfg')
            cfgdict = self.loadCfgFile(filename)
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
        self._pidfile = os.path.join(cfg['piddir'], name + '.pid')

    def loadCfgFile(self, filename):
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
        raise ConfigError("%s class don't know how to handle option(s): %s" %
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
                    self.unknown_options(cls, opts)
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

    def _processCfg(self):
        opts = dict(self.node_cfg)
        cls = get_class(opts.pop('class', 'protocol.dispatcher.Dispatcher'))
        self.dispatcher = cls(opts.pop('name', self._cfgfiles), self.log.getChild('dispatcher'), opts, self)
        if opts:
            self.unknown_options(cls, opts)
        self.modules = OrderedDict()
        for modname, options in self.module_cfg.items():
            opts = dict(options)
            cls = get_class(opts.pop('class'))
            modobj = cls(modname, self.log.getChild(modname), opts, self)
            # all used args should be popped from opts!
            if opts:
                self.unknown_options(cls, opts)
            self.modules[modname] = modobj

        poll_table = dict()
        # all objs created, now start them up and interconnect
        for modname, modobj in self.modules.items():
            self.log.info('registering module %r' % modname)
            self.dispatcher.register_module(modobj, modname, modobj.properties['export'])
            if modobj.pollerClass is not None:
                # a module might be explicitly excluded from polling by setting pollerClass to None
                modobj.pollerClass.add_to_table(poll_table, modobj)
            # also call earlyInit on the modules
            modobj.earlyInit()

        # handle attached modules
        for modname, modobj in self.modules.items():
            for propname, propobj in modobj.__class__.properties.items():
                if isinstance(propobj, Attached):
                    setattr(modobj, propobj.attrname or '_' + propname,
                            self.dispatcher.get_module(modobj.properties[propname]))
        # call init on each module after registering all
        for modname, modobj in self.modules.items():
            modobj.initModule()

        if self._testonly:
            return
        start_events = []
        for modname, modobj in self.modules.items():
            event = threading.Event()
            # startModule must return either a timeout value or None (default 30 sec)
            timeout = modobj.startModule(started_callback=event.set) or 30
            start_events.append((time.time() + timeout, 'module %s' % modname, event))
        for poller in poll_table.values():
            event = threading.Event()
            # poller.start must return either a timeout value or None (default 30 sec)
            timeout = poller.start(started_callback=event.set) or 30
            start_events.append((time.time() + timeout, repr(poller), event))
        self.log.info('waiting for modules and pollers being started')
        for deadline, name, event in sorted(start_events):
            if not event.wait(timeout=max(0, deadline - time.time())):
                self.log.info('WARNING: timeout when starting %s' % name)
        self.log.info('all modules and pollers started')
