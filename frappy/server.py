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
import signal
import sys
import threading

import mlzlog

from frappy.config import load_config
from frappy.errors import ConfigError
from frappy.lib import formatException, generalConfig, get_class, mkthread
from frappy.lib.multievent import MultiEvent
from frappy.logging import init_remote_logging
from frappy.params import PREDEFINED_ACCESSIBLES
from frappy.secnode import SecNode

try:
    from daemon import DaemonContext
    try:
        from daemon import pidlockfile
    except ImportError:
        import daemon.pidfile as pidlockfile
except ImportError:
    DaemonContext = None

try:
    # pylint: disable=unused-import
    import systemd.daemon
except ImportError:
    systemd = None


class Server:
    INTERFACES = {
        'tcp': 'protocol.interface.tcp.TCPServer',
        'ws': 'protocol.interface.ws.WSServer',
    }
    _restart = True

    def __init__(self, name, parent_logger, *, cfgfiles=None, interface=None, testonly=False):
        """initialize server

        Arguments:
        - name:  the node name
        - parent_logger: the logger to inherit from. a handler is installed by
            the server to provide remote logging
        - cfgfiles: if not given, defaults to name
            may be a comma separated list of cfg files
            items ending with .cfg are taken as paths, else .cfg is appended and
            files are looked up in the config path retrieved from the general config
        - interface: an uri of the from tcp://<port> or a bare port number for tcp
            if not given, the interface is taken from the config file. In case of
            multiple cfg files, the interface is taken from the first cfg file
        - testonly: test mode. tries to build all modules, but the server is not started

        Config file:
        Format:                     Example:
        Node('<equipment_id>',      Node('ex.frappy.demo',
            <description>,              'short description\n\nlong descr.',
            <main interface>,           'tcp://10769',
            secondary=[                 secondary=['ws://10770'],  # optional
              <interfaces>
            ],
        )                               )
        Mod('<module name>',        Mod('temp',
            <param config>              value = Param(unit='K'),
        )                           )
        ...
        """
        self._testonly = testonly

        if not cfgfiles:
            cfgfiles = name
        # sanitize name (in case it is a cfgfile)
        name = os.path.splitext(os.path.basename(name))[0]
        if isinstance(parent_logger, mlzlog.MLZLogger):
            self.log = parent_logger.getChild(name, True)
        else:
            self.log = parent_logger.getChild(name)
        init_remote_logging(self.log)

        merged_cfg = load_config(cfgfiles, self.log)
        self.node_cfg = merged_cfg.pop('node')
        self.module_cfg = merged_cfg
        if interface:
            self.node_cfg['equipment_id'] = name
            self.node_cfg['interface'] = str(interface)
        elif not self.node_cfg.get('interface'):
            raise ConfigError('No interface specified in configuration or arguments!')

        self._cfgfiles = cfgfiles
        self._pidfile = generalConfig.piddir / (name + '.pid')
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, num, frame):
        if hasattr(self, 'interfaces') and self.interfaces:
            self.shutdown()
        else:
            # TODO: we should probably clean up the already initialized modules
            # when getting an interrupt while the server is starting
            signal.default_int_handler(num, frame)

    def start(self):
        if not DaemonContext:
            raise ConfigError('can not daemonize, as python-daemon is not installed')
        piddir = self._pidfile.parent
        if not piddir.is_dir():
            piddir.mkdir(parents=True)
        pidfile = pidlockfile.TimeoutPIDLockFile(self._pidfile)

        if pidfile.is_locked():
            self.log.error('Pidfile already exists. Exiting')

        with DaemonContext(
                pidfile=pidfile,
                files_preserve=self.log.getLogfileStreams()):
            self.run()

    def unknown_options(self, cls, options):
        return f"{cls.__name__} class don't know how to handle option(s): {', '.join(options)}"

    def restart_hook(self):
        """Actions to be done on restart. May be overridden by a subclass."""

    def run(self):
        global systemd  # pylint: disable=global-statement
        while self._restart:
            self._restart = False
            try:
                # TODO: make systemd notifications configurable
                if systemd:
                    systemd.daemon.notify("STATUS=initializing")
            except Exception:
                systemd = None
            try:
                self._processCfg()
                if self._testonly:
                    return
            except Exception:
                print(formatException(verbose=True))
                raise

            self.interfaces = {}
            iface_threads = []
            # default_timeout 12 sec: TCPServer might need up to 10 sec to wait for Address no longer in use
            interfaces_started = MultiEvent(default_timeout=12)
            lock = threading.Lock()
            failed = {}
            interfaces = [self.node_cfg['interface']] + self.node_cfg.get('secondary', [])
            # TODO: check if only one interface of each type is open?
            for interface in interfaces:
                opts = {'uri': interface}
                t = mkthread(
                    self._interfaceThread,
                    opts,
                    lock,
                    failed,
                    interfaces_started.get_trigger(),
                )
                iface_threads.append(t)
            if not interfaces_started.wait():
                for iface in interfaces:
                    if iface not in failed and iface not in self.interfaces:
                        self.log.error('timeout starting interface %s', iface)
            while failed:
                iface, err = failed.popitem()
                self.log.error('starting interface %s failed with %r', iface, err)
            if not self.interfaces:
                self.log.error('no interface started')
                return
            self.log.info('startup done with interface(s) %s' % ', '.join(self.interfaces))
            if systemd:
                systemd.daemon.notify("READY=1\nSTATUS=accepting requests")

            # we wait here on the thread finishing, which means we got a
            # signal to shut down or an exception was raised
            for t in iface_threads:
                t.join()

            while failed:
                iface, err = failed.popitem()
                self.log.error('interface %s failed with %r', iface, err)

            self.log.info('stopped listening, cleaning up %d modules',
                          len(self.secnode.modules))
            # if systemd:
            #     if self._restart:
            #         systemd.daemon.notify('RELOADING=1')
            #     else:
            #         systemd.daemon.notify('STOPPING=1')
            self.secnode.shutdown_modules()
            if self._restart:
                self.restart_hook()
                self.log.info('restarting')
        self.log.info('shut down')

    def restart(self):
        if not self._restart:
            self._restart = True
            for iface in self.interfaces.values():
                iface.shutdown()

    def shutdown(self):
        self._restart = False
        for iface in self.interfaces.values():
            iface.shutdown()

    def _interfaceThread(self, opts, lock, failed, start_cb):
        iface = opts['uri']
        scheme, _, _ = iface.rpartition('://')
        scheme = scheme or 'tcp'
        cls = get_class(self.INTERFACES[scheme])
        try:
            with cls(scheme, self.log.getChild(scheme), opts, self) as interface:
                if opts:
                    raise ConfigError(self.unknown_options(cls, opts))
                with lock:
                    self.interfaces[iface] = interface
                start_cb()
                interface.serve_forever()
                # server_close() called by 'with'
        except Exception as e:
            with lock:
                failed[iface] = e
            start_cb()
            return
        self.log.info(f'stopped {iface}')

    def _processCfg(self):
        """Processes the module configuration.

        All modules specified in the config file and read recursively from
        Pinata class Modules are instantiated, initialized and started by the
        end of this function.
        If there are errors that occur, they will be collected and emitted
        together in the end.
        """
        errors = []
        opts = dict(self.node_cfg)
        cls = get_class(opts.pop('cls'))
        name = opts.pop('name', self._cfgfiles)
        # TODO: opts not in both
        self.secnode = SecNode(name, self.log.getChild('secnode'), opts, self)
        self.dispatcher = cls(name, self.log.getChild('dispatcher'), opts, self)

        if opts:
            self.secnode.errors.append(self.unknown_options(cls, opts))

        self.secnode.create_modules()
        # initialize all modules by getting them with Dispatcher.get_module,
        # which is done in the get_descriptive data
        # TODO: caching, to not make this extra work
        self.secnode.get_descriptive_data('')
        # =========== All modules are initialized ===========

        # all errors from initialization process
        errors = self.secnode.errors

        if not self._testonly:
            start_events = MultiEvent(default_timeout=30)
            for modname, modobj in self.secnode.modules.items():
                # startModule must return either a timeout value or None (default 30 sec)
                start_events.name = f'module {modname}'
                modobj.startModule(start_events)
                if not modobj.startModuleDone:
                    errors.append(f'{modobj.startModule.__qualname__} was not called, probably missing super call')

        if errors:
            for errtxt in errors:
                for line in errtxt.split('\n'):
                    self.log.error(line)
            # print a list of config errors to stderr
            sys.stderr.write('\n'.join(errors))
            sys.stderr.write('\n')
            sys.exit(1)

        if self._testonly:
            return
        self.log.info('waiting for modules being started')
        start_events.name = None
        if not start_events.wait():
            # some timeout happened
            for name in start_events.waiting_for():
                self.log.warning('timeout when starting %s', name)
        self.log.info('all modules started')
        history_path = os.environ.get('FRAPPY_HISTORY')
        if history_path:
            from frappy_psi.historywriter import \
                FrappyHistoryWriter  # pylint: disable=import-outside-toplevel
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
