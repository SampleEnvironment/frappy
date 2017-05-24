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
#
# *****************************************************************************
"""Define Client side proxies"""

# nothing here yet.

import code


class NameSpace(dict):

    def __init__(self):
        dict.__init__(self)
        self.__const = set()

    def setconst(self, name, value):
        dict.__setitem__(self, name, value)
        self.__const.add(name)

    def __setitem__(self, name, value):
        if name in self.__const:
            raise RuntimeError('%s cannot be assigned' % name)
        dict.__setitem__(self, name, value)

    def __delitem__(self, name):
        if name in self.__const:
            raise RuntimeError('%s cannot be deleted' % name)
        dict.__delitem__(self, name)


import ConfigParser


def getClientOpts(cfgfile):
    parser = ConfigParser.SafeConfigParser()
    if not parser.read([cfgfile + '.cfg']):
        print "Error reading cfg file %r" % cfgfile
        return {}
    if not parser.has_section('client'):
        print "No Server section found!"
    return dict(item for item in parser.items('client'))


from os import path


class ClientConsole(object):

    def __init__(self, cfgname, basepath):
        self.namespace = NameSpace()
        self.namespace.setconst('help', self.helpCmd)

        cfgfile = path.join(basepath, 'etc', cfgname)
        cfg = getClientOpts(cfgfile)
        self.client = Client(cfg)
        self.client.populateNamespace(self.namespace)

    def run(self):
        console = code.InteractiveConsole(self.namespace)
        console.interact("Welcome to the SECoP console")

    def close(self):
        pass

    def helpCmd(self, arg=Ellipsis):
        if arg is Ellipsis:
            print "No help available yet"
        else:
            help(arg)


import socket
import threading
from collections import deque

import mlzlog

from secop.protocol.encoding import ENCODERS
from secop.protocol.framing import FRAMERS
from secop.protocol.messages import *


class TCPConnection(object):

    def __init__(self, connect, port, encoding, framing, **kwds):
        self.log = mlzlog.log.getChild('connection', False)
        self.encoder = ENCODERS[encoding]()
        self.framer = FRAMERS[framing]()
        self.connection = socket.create_connection((connect, port), 3)
        self.queue = deque()
        self._rcvdata = ''
        self.callbacks = set()
        self._thread = threading.Thread(target=self.thread)
        self._thread.daemonize = True
        self._thread.start()

    def send(self, msg):
        self.log.debug("Sending msg %r" % msg)
        frame = self.encoder.encode(msg)
        data = self.framer.encode(frame)
        self.log.debug("raw data: %r" % data)
        self.connection.sendall(data)

    def thread(self):
        while True:
            try:
                self.thread_step()
            except Exception as e:
                self.log.exception("Exception in RCV thread: %r" % e)

    def thread_step(self):
        while True:
            data = self.connection.recv(1024)
            self.log.debug("RCV: got raw data %r" % data)
            if data:
                frames = self.framer.decode(data)
                self.log.debug("RCV: frames %r" % frames)
                for frame in frames:
                    msgs = self.encoder.decode(frame)
                    self.log.debug("RCV: msgs %r" % msgs)
                    for msg in msgs:
                        self.handle(msg)

    def handle(self, msg):
        if isinstance(msg, AsyncDataUnit):
            self.log.info("got Async: %r" % msg)
            for cb in self.callbacks:
                try:
                    cb(msg)
                except Exception as e:
                    self.log.debug(
                        "handle_async: got exception %r" % e, exception=true)
        else:
            self.queue.append(msg)

    def read(self):
        while not len(self.queue):
            pass
        return self.queue.popleft()

    def register_callback(self, callback):
        """registers callback for async data"""
        self.callbacks.add(callback)

    def unregister_callback(self, callback):
        """unregisters callback for async data"""
        self.callbacks.discard(callback)


class Client(object):

    def __init__(self, opts):
        self.log = mlzlog.log.getChild('client', True)
        self._cache = dict()
        self.connection = TCPConnection(**opts)
        self.connection.register_callback(self.handle_async)

    def handle_async(self, msg):
        self.log.info("Got async update %r" % msg)
        device = msg.device
        param = msg.param
        value = msg.value
        self._cache.getdefault(device, {})[param] = value
        # XXX: further notification-callbacks needed ???

    def populateNamespace(self, namespace):
        self.connection.send(ListDevicesRequest())
        #        reply = self.connection.read()
        #        self.log.info("found devices %r" % reply)
        # create proxies, populate cache....
        namespace.setconst('connection', self.connection)
