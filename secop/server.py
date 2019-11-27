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



class Server:
    # list allowed section prefixes
    # if mapped dict does not exist -> section need a 'class' option
    # otherwise a 'type' option is evaluatet and the class from the mapping dict used
    #
    # IMPORTANT: keep he order! (node MUST be first, as the others are referencing it!)
    CFGSECTIONS = [
        # section_prefix, default type, mapping of selectable classes
        ('node', None, {None: "protocol.dispatcher.Dispatcher"}),
        ('module', None, None),
        ('interface', "tcp", {"tcp": "protocol.interface.tcp.TCPServer"}),
    ]
    def __init__(self, name, parent_logger=None):
        cfg = getGeneralConfig()

        # also handle absolut paths
        if os.path.abspath(name) == name and os.path.exists(name) and \
            name.endswith('.cfg'):
            self._cfgfile = name
            self._pidfile = os.path.join(cfg['piddir'],
                                         name[:-4].replace(os.path.sep, '_') + '.pid')
            name = os.path.basename(name[:-4])
        else:
            self._cfgfile = os.path.join(cfg['confdir'], name + '.cfg')
            self._pidfile = os.path.join(cfg['piddir'], name + '.pid')

        self._name = name

        self.log = parent_logger.getChild(name, True)

        self._dispatcher = None
        self._interface = None

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
        try:
            self._processCfg()
        except Exception:
            print(formatException(verbose=True))
            raise

        self.log.info('startup done, handling transport messages')
        self._threads = set()
        for ifname, ifobj in self.interfaces.items():
            self.log.debug('starting thread for interface %r' % ifname)
            t = threading.Thread(target=ifobj.serve_forever)
            t.daemon = True
            t.start()
            self._threads.add(t)
        while self._threads:
            time.sleep(1)
            for t in self._threads:
                if not t.is_alive():
                    self.log.debug('thread %r died (%d still running)' %
                                   (t, len(self._threads)))
                    t.join()
                    self._threads.discard(t)

    def _processCfg(self):
        self.log.debug('Parse config file %s ...' % self._cfgfile)

        parser = configparser.SafeConfigParser()
        parser.optionxform = str

        if not parser.read([self._cfgfile]):
            self.log.error('Couldn\'t read cfg file !')
            raise ConfigError('Couldn\'t read cfg file %r' % self._cfgfile)



        for kind, devtype, classmapping in self.CFGSECTIONS:
            kinds = '%ss' % kind
            objs = OrderedDict()
            self.__dict__[kinds] = objs
            for section in parser.sections():
                prefix = '%s ' % kind
                if section.lower().startswith(prefix):
                    name = section[len(prefix):]
                    opts = dict(item for item in parser.items(section))
                    if 'class' in opts:
                        cls = opts.pop('class')
                    else:
                        if not classmapping:
                            self.log.error('%s %s needs a class option!' % (kind.title(), name))
                            raise ConfigError('cfgfile %r: %s %s needs a class option!' %
                                              (self._cfgfile, kind.title(), name))
                        type_ = opts.pop('type', devtype)
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

        pollTable = dict()
        # all objs created, now start them up and interconnect
        for modname, modobj in self.modules.items():
            self.log.info('registering module %r' % modname)
            self.dispatcher.register_module(modobj, modname, modobj.properties['export'])
            modobj.pollerClass.add_to_table(pollTable, modobj)
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
        for poller in pollTable.values():
            event = threading.Event()
            # poller.start must return either a timeout value or None (default 30 sec)
            timeout = poller.start(started_callback=event.set) or 30
            start_events.append((time.time() + timeout, repr(poller), event))
        self.log.info('waiting for modules and pollers being started')
        for deadline, name, event in sorted(start_events):
            if not event.wait(timeout=max(0, deadline - time.time())):
                self.log.info('WARNING: timeout when starting %s' % name)
        self.log.info('all modules and pollers started')
