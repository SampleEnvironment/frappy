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
from secop.lib import formatException, get_class, getGeneralConfig, mkthread
from secop.modules import Attached

try:
    import systemd.daemon
except ImportError:
    systemd = None



class Server:
    # list allowed section prefixes
    # if mapped dict does not exist -> section need a 'class' option
    # otherwise a 'type' option is evaluated and the class from the mapping dict used
    #
    # IMPORTANT: keep the order! (node MUST be first, as the others are referencing it!)
    CFGSECTIONS = [
        # section_prefix, default type, mapping of selectable classes
        ('node', 'std', {'std': "protocol.dispatcher.Dispatcher",
                         'router': 'protocol.router.Router'}),
        ('module', None, None),
        ('interface', "tcp", {"tcp": "protocol.interface.tcp.TCPServer"}),
    ]
    _restart = True

    def __init__(self, name, parent_logger=None, cfgfiles=None, interface=None, testonly=False):
        """initialize server

        the configuration is taken either from <name>.cfg or from cfgfiles
        if cfgfiles is given, also the serverport has to be given.
        interface is either an uri or a bare serverport number (with tcp as default)
        """
        self._testonly = testonly
        cfg = getGeneralConfig()

        self.log = parent_logger.getChild(name, True)
        configuration = {k: OrderedDict() for k, _, _ in self.CFGSECTIONS}
        if interface:
            try:
                typ, interface = str(interface).split('://', 1)
            except ValueError:
                typ = 'tcp'
            try:
                host, port = interface.split(':', 1)
            except ValueError:
                host, port = '0.0.0.0', interface
            options = {'type': typ, 'bindto': host, 'bindport': port}
            configuration['interface %s' % options['type']] = options
        if not cfgfiles:
            cfgfiles = name
        for cfgfile in cfgfiles.split(','):
            if cfgfile.endswith('.cfg') and os.path.exists(cfgfile):
                filename = cfgfile
            else:
                filename = os.path.join(cfg['confdir'], cfgfile + '.cfg')
            self.mergeCfgFile(configuration, filename)
        if len(configuration['node']) > 1:
            description = ['merged node\n']
            for section, opt in configuration['node']:
                description.append("--- %s:\n%s\n" % (section[5:], opt['description']))
            configuration['node'] = {cfgfiles: {'description': '\n'.join(description)}}
        self._configuration = configuration
        self._cfgfile = cfgfiles  # used for reference in error messages only
        self._pidfile = os.path.join(cfg['piddir'], name + '.pid')

    def mergeCfgFile(self, configuration, filename):
        self.log.debug('Parse config file %s ...' % filename)
        parser = configparser.ConfigParser()
        parser.optionxform = str
        if not parser.read([filename]):
            self.log.error("Couldn't read cfg file %r!" % filename)
            raise ConfigError("Couldn't read cfg file %r" % filename)
        for section, options in parser.items():
            try:
                kind, name = section.split(' ', 1)
                kind = kind.lower()
                cfgdict = configuration[kind]
            except (ValueError, KeyError):
                if section != 'DEFAULT':
                    self.log.warning('skip unknown section %s' % section)
                continue
            opt = dict(options)
            if name in cfgdict:
                if kind == 'interface':
                    opt = dict(type='tcp', bindto='0.0.0.0')
                    opt.update(options)
                if opt != cfgdict[name]:
                    self.log.warning('omit conflicting section %r in %s' % (section, filename))
            else:
                cfgdict[name] = dict(options)

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

            self.log.info('startup done, handling transport messages')
            threads = []
            for ifname, ifobj in self.interfaces.items():
                self.log.debug('starting thread for interface %r' % ifname)
                threads.append((ifname, mkthread(ifobj.serve_forever)))
            if systemd:
                systemd.daemon.notify("READY=1\nSTATUS=accepting requests")
            for ifname, t in threads:
                t.join()
                self.log.debug('thread for %r died' % ifname)

    def restart(self):
        if not self._restart:
            self._restart = True
            for ifobj in self.interfaces.values():
                ifobj.shutdown()
                ifobj.server_close()

    def _processCfg(self):
        self.log.debug('Parse config file %s ...' % self._cfgfile)

        for kind, default_type, classmapping in self.CFGSECTIONS:
            objs = OrderedDict()
            self.__dict__['%ss' % kind] = objs
            for name, options in self._configuration[kind].items():
                opts = dict(options)
                if 'class' in opts:
                    cls = opts.pop('class')
                else:
                    if not classmapping:
                        self.log.error('%s %s needs a class option!' % (kind.title(), name))
                        raise ConfigError('cfgfile %r: %s %s needs a class option!' %
                                          (self._cfgfile, kind.title(), name))
                    type_ = opts.pop('type', default_type)
                    cls = classmapping.get(type_, None)
                    if not cls:
                        self.log.error('%s %s needs a type option (select one of %s)!' %
                                       (kind.title(), name, ', '.join(repr(r) for r in classmapping)))
                        raise ConfigError('cfgfile %r: %s %s needs a type option (select one of %s)!' %
                                  (self._cfgfile, kind.title(), name, ', '.join(repr(r) for r in classmapping)))
                # MAGIC: transform \n.\n into \n\n which are normally stripped
                # by the ini parser
                for k in opts:
                    v = opts[k]
                    while '\n.\n' in v:
                        v = v.replace('\n.\n', '\n\n')
                    try:
                        opts[k] = ast.literal_eval(v)
                    except Exception:
                        opts[k] = v

                # try to import the class, raise if this fails
                self.log.debug('Creating %s %s ...' % (kind.title(), name))
                # cls.__init__ should pop all used args from options!
                logname = 'dispatcher' if kind == 'node' else '%s_%s' % (kind, name.lower())
                obj = get_class(cls)(name, self.log.getChild(logname), opts, self)
                if opts:
                    raise ConfigError('%s %s: class %s: don\'t know how to handle option(s): %s' %
                                      (kind, name, cls, ', '.join(opts)))

                # all went well so far
                objs[name] = obj

            # following line is the reason for 'node' beeing the first entry in CFGSECTIONS
            if len(self.nodes) != 1:
                raise ConfigError('cfgfile %r: needs exactly one node section!' % self._cfgfile)
            self.dispatcher, = tuple(self.nodes.values())

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
