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
from __future__ import division, print_function

import ast
import os
import threading
import time
from collections import OrderedDict

from daemon import DaemonContext

from secop.errors import ConfigError
from secop.lib import formatException, get_class, getGeneralConfig

try:
    import configparser  # py3
except ImportError:
    import ConfigParser as configparser  # py2

try:
    import daemon.pidlockfile as pidlockfile
except ImportError:
    import daemon.pidfile as pidlockfile




class Server(object):
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
            self._pidfile = os.path.join(cfg[u'piddir'],
                                         name[:-4].replace(os.path.sep, u'_') + u'.pid')
            name = os.path.basename(name[:-4])
        else:
            self._cfgfile = os.path.join(cfg[u'confdir'], name + u'.cfg')
            self._pidfile = os.path.join(cfg[u'piddir'], name + u'.pid')

        self._name = name

        self.log = parent_logger.getChild(name, True)

        self._dispatcher = None
        self._interface = None

    def start(self):
        piddir = os.path.dirname(self._pidfile)
        if not os.path.isdir(piddir):
            os.makedirs(piddir)
        pidfile = pidlockfile.TimeoutPIDLockFile(self._pidfile)

        if pidfile.is_locked():
            self.log.error(u'Pidfile already exists. Exiting')

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

        self.log.info(u'startup done, handling transport messages')
        self._threads = set()
        for ifname, ifobj in self.interfaces.items():
            self.log.debug(u'starting thread for interface %r' % ifname)
            t = threading.Thread(target=ifobj.serve_forever)
            t.daemon = True
            t.start()
            self._threads.add(t)
        while self._threads:
            time.sleep(1)
            for t in self._threads:
                if not t.is_alive():
                    self.log.debug(u'thread %r died (%d still running)' %
                                   (t, len(self._threads)))
                    t.join()
                    self._threads.discard(t)

    def _processCfg(self):
        self.log.debug(u'Parse config file %s ...' % self._cfgfile)

        parser = configparser.SafeConfigParser()
        parser.optionxform = str

        if not parser.read([self._cfgfile]):
            self.log.error(u'Couldn\'t read cfg file !')
            raise ConfigError(u'Couldn\'t read cfg file %r' % self._cfgfile)



        for kind, devtype, classmapping in self.CFGSECTIONS:
            kinds = u'%ss' % kind
            objs = OrderedDict()
            self.__dict__[kinds] = objs
            for section in parser.sections():
                prefix = u'%s ' % kind
                if section.lower().startswith(prefix):
                    name = section[len(prefix):]
                    opts = dict(item for item in parser.items(section))
                    if u'class' in opts:
                        cls = opts.pop(u'class')
                    else:
                        if not classmapping:
                            self.log.error(u'%s %s needs a class option!' % (kind.title(), name))
                            raise ConfigError(u'cfgfile %r: %s %s needs a class option!' %
                                              (self._cfgfile, kind.title(), name))
                        type_ = opts.pop(u'type', devtype)
                        cls = classmapping.get(type_, None)
                        if not cls:
                            self.log.error(u'%s %s needs a type option (select one of %s)!' %
                                           (kind.title(), name, ', '.join(repr(r) for r in classmapping)))
                            raise ConfigError(u'cfgfile %r: %s %s needs a type option (select one of %s)!' %
                                      (self._cfgfile, kind.title(), name, ', '.join(repr(r) for r in classmapping)))
                    # MAGIC: transform \n.\n into \n\n which are normally stripped
                    # by the ini parser
                    for k in opts:
                        v = opts[k]
                        while u'\n.\n' in v:
                            v = v.replace(u'\n.\n', u'\n\n')
                        try:
                            opts[k] = ast.literal_eval(v)
                        except Exception:
                            opts[k] = v

                    # try to import the class, raise if this fails
                    self.log.debug(u'Creating %s %s ...' % (kind.title(), name))
                    # cls.__init__ should pop all used args from options!
                    logname = u'dispatcher' if kind == u'node' else u'%s_%s' % (kind, name.lower())
                    obj = get_class(cls)(name, self.log.getChild(logname), opts, self)
                    if opts:
                        raise ConfigError(u'%s %s: class %s: don\'t know how to handle option(s): %s' %
                                          (kind, name, cls, u', '.join(opts)))

                    # all went well so far
                    objs[name] = obj

            # following line is the reason for 'node' beeing the first entry in CFGSECTIONS
            if len(self.nodes) != 1:
                raise ConfigError(u'cfgfile %r: needs exactly one node section!' % self._cfgfile)
            self.dispatcher, = tuple(self.nodes.values())

        pollTable = dict()
        # all objs created, now start them up and interconnect
        for modname, modobj in self.modules.items():
            self.log.info(u'registering module %r' % modname)
            self.dispatcher.register_module(modobj, modname, modobj.properties['export'])
            try:
                modobj.pollerClass.add_to_table(pollTable, modobj)
            except AttributeError:
                pass
            # also call earlyInit on the modules
            modobj.earlyInit()

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
        self.log.info(u'waiting for modules and pollers being started')
        for deadline, name, event in sorted(start_events):
            if not event.wait(timeout=max(0, deadline - time.time())):
                self.log.info('WARNING: timeout when starting %s' % name)
        self.log.info(u'all modules and pollers started')
