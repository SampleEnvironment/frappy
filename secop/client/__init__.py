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
import socket
import threading
from collections import deque
from os import path

try:
    import mlzlog
except ImportError:
    pass # has to be fixed in case this file is used again

from secop.protocol.interface import decode_msg, encode_msg_frame, get_msg
from secop.protocol.messages import DESCRIPTIONREQUEST, EVENTREPLY

try:
    import configparser
except ImportError:
    import ConfigParser as configparser



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



def getClientOpts(cfgfile):
    parser = configparser.SafeConfigParser()
    if not parser.read([cfgfile + '.cfg']):
        print("Error reading cfg file %r" % cfgfile)
        return {}
    if not parser.has_section('client'):
        print("No Server section found!")
    return dict(item for item in parser.items('client'))


class ClientConsole:

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
            print("No help available yet")
        else:
            help(arg)


class TCPConnection:

    def __init__(self, connect, port, **kwds):
        self.log = mlzlog.log.getChild('connection', False)
        self.connection = socket.create_connection((connect, port), 3)
        self.queue = deque()
        self._rcvdata = ''
        self.callbacks = set()
        self._thread = threading.Thread(target=self.thread)
        self._thread.daemonize = True
        self._thread.start()

    def send(self, msg):
        self.log.debug("Sending msg %r" % msg)
        data = encode_msg_frame(*msg.serialize())
        self.log.debug("raw data: %r" % data)
        self.connection.sendall(data)

    def thread(self):
        while True:
            try:
                self.thread_step()
            except Exception as e:
                self.log.exception("Exception in RCV thread: %r" % e)

    def thread_step(self):
        data = b''
        while True:
            newdata = self.connection.recv(1024)
            self.log.debug("RCV: got raw data %r" % newdata)
            data = data + newdata
            while True:
                origin, data = get_msg(data)
                if origin is None:
                    break  # no more messages to process
                if not origin:  # empty string
                    continue  # ???
                _ = decode_msg(origin)
                # construct msgObj from msg
                try:
                    #msgObj = Message(*msg)
                    #msgObj.origin = origin.decode('latin-1')
                    #self.handle(msgObj)
                    pass
                except Exception:
                    # ??? what to do here?
                    pass

    def handle(self, msg):
        if msg.action == EVENTREPLY:
            self.log.info("got Async: %r" % msg)
            for cb in self.callbacks:
                try:
                    cb(msg)
                except Exception as e:
                    self.log.debug(
                        "handle_async: got exception %r" % e, exception=True)
        else:
            self.queue.append(msg)

    def read(self):
        while not self.queue:
            pass  # XXX: remove BUSY polling
        return self.queue.popleft()

    def register_callback(self, callback):
        """registers callback for async data"""
        self.callbacks.add(callback)

    def unregister_callback(self, callback):
        """unregisters callback for async data"""
        self.callbacks.discard(callback)


class Client:

    def __init__(self, opts):
        self.log = mlzlog.log.getChild('client', True)
        self._cache = dict()
        self.connection = TCPConnection(**opts)
        self.connection.register_callback(self.handle_async)

    def handle_async(self, msg):
        self.log.info("Got async update %r" % msg)
        module = msg.module
        param = msg.param
        value = msg.value
        self._cache.getdefault(module, {})[param] = value
        # XXX: further notification-callbacks needed ???

    def populateNamespace(self, namespace):
        #self.connection.send(Message(DESCRIPTIONREQUEST))
        #        reply = self.connection.read()
        #        self.log.info("found modules %r" % reply)
        # create proxies, populate cache....
        namespace.setconst('connection', self.connection)
