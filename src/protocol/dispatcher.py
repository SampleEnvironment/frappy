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

"""Dispatcher for SECoP Messages

Interface to the service offering part:

 - 'handle_request(connectionobj, data)' handles incoming request
   will call 'queue_request(data)' on connectionobj before returning
 - 'add_connection(connectionobj)' registers new connection
 - 'remove_connection(connectionobj)' removes now longer functional connection
 - may at any time call 'queue_async_request(connobj, data)' on the connobj

Interface to the devices:
 - add_device(devname, devobj, export=True) registers a new device under the
   given name, may also register it for exporting (making accessible)
 - get_device(devname) returns the requested device or None
 - remove_device(devname_or_obj): removes the device (during shutdown)

internal stuff which may be called
 - get_devices(): return a list of devices + descriptive data as dict
 - get_device_params():
   return a list of paramnames for this device + descriptive data
"""

import threading

from messages import *


class Dispatcher(object):
    def __init__(self, logger, options):
        self.log = logger
        # XXX: move framing and encoding to interface!
        self.framing = options.pop('framing')
        self.encoding = options.pop('encoding')
        # map ALL devname -> devobj
        self._dispatcher_devices = {}
        # list of EXPORTED devices
        self._dispatcher_export = []
        # list all connections
        self._dispatcher_connections = []
        # map eventname -> list of subscribed connections
        self._dispatcher_subscriptions = {}
        self._dispatcher_lock = threading.RLock()

    def handle_request(self, conn, data):
        """handles incoming request

        will call 'queue.request(data)' on conn to send reply before returning
        """
        self.log.debug('Dispatcher: handling data: %r' % data)
        # play thread safe !
        with self._dispatcher_lock:
            # de-frame data
            frames = self.framing.decode(data)
            self.log.debug('Dispatcher: frames=%r' % frames)
            for frame in frames:
                reply = None
                # decode frame
                msg = self.encoding.decode(frame)
                self.log.debug('Dispatcher: msg=%r' % msg)
                # act upon requestobj
                msgtype = msg.TYPE
                msgname = msg.NAME
                msgargs = msg
                # generate reply (coded and framed)
                if msgtype != 'request':
                    reply = ProtocolErrorReply(msg)
                else:
                    self.log.debug('Looking for handle_%s' % msgname)
                    handler = getattr(self, 'handle_%s' % msgname, None)
                    if handler:
                        reply = handler(msgargs)
                    else:
                        self.log.debug('Can not handle msg %r' % msg)
                        reply = self.unhandled(msgname, msgargs)
                if reply:
                    conn.queue_reply(self._format_reply(reply))
            # queue reply viy conn.queue_reply(data)

    def _format_reply(self, reply):
        msg = self.encoding.encode(reply)
        frame = self.framing.encode(msg)
        return frame

    def announce_update(self, device, pname, value):
        """called by devices param setters to notify subscribers of new values
        """
        eventname = '%s/%s' % (self.get_device(device).name, pname)
        subscriber = self._dispatcher_subscriptions.get(eventname, None)
        if subscriber:
            reply = AsyncDataUnit(device=self.get_device(device).name,
                                  param=pname,
                                  value=str(value),
                                  timestamp=time.time(),
                                  )
            data = self._format_reply(reply)
            for conn in subscriber:
                conn.queue_async_reply(data)

    def subscribe(self, conn, device, pname):
        eventname = '%s/%s' % (self.get_device(device).name, pname)
        self._dispatcher_subscriptions.getdefault(eventname, set()).add(conn)

    def add_connection(self, conn):
        """registers new connection"""
        self._dispatcher_connections.append(conn)

    def remove_connection(self, conn):
        """removes now longer functional connection"""
        if conn in self._dispatcher_connections:
            self._dispatcher_connections.remove(conn)
        # XXX: also clean _dispatcher_subscriptions !

    def register_device(self, devobj, devname, export=True):
        self._dispatcher_devices[devname] = devobj
        if export:
            self._dispatcher_export.append(devname)

    def get_device(self, devname):
        dev = self._dispatcher_devices.get(devname, None)
        self.log.debug('get_device(%r) -> %r' % (devname, dev))
        return dev

    def remove_device(self, devname_or_obj):
        devobj = self.get_device(devname_or_obj) or devname_or_obj
        devname = devobj.name
        if devname in self._dispatcher_export:
            self._dispatcher_export.remove(devname)
        self._dispatcher_devices.pop(devname)
        # XXX: also clean _dispatcher_subscriptions

    def list_device_names(self):
        # return a copy of our list
        return self._dispatcher_export[:]

    def list_devices(self):
        dn = []
        dd = {}
        for devname in self._dispatcher_export:
            dn.append(devname)
            dev = self.get_device(devname)
            descriptive_data = {
                'class': dev.__class__,
                #'bases': dev.__bases__,
                'parameters': dev.PARAMS.keys(),
                'commands': dev.CMDS.keys(),
                # XXX: what else?
            }
            dd[devname] = descriptive_data
        return dn, dd

    def list_device_params(self, devname):
        if devname in self._dispatcher_export:
            # XXX: omit export=False params!
            return self.get_device(devname).PARAMS
        return {}

    # now the (defined) handlers for the different requests
    def handle_Help(self, msg):
        return HelpReply()

    def handle_ListDevices(self, msgargs):
        # XXX: choose!
        #return ListDevicesReply(self.list_device_names())
        return ListDevicesReply(*self.list_devices())

    def handle_ListDeviceParams(self, msgargs):
        devobj = self.get_device(msgargs.device)
        if devobj:
            return ListDeviceParamsReply(msgargs.device,
                                         self.get_device_params(devobj))
        else:
            return NoSuchDeviceErrorReply(msgargs.device)

    def handle_ReadValue(self, msgargs):
        devobj = self.get_device(msgargs.device)
        if devobj:
            return ReadValueReply(msgargs.device, devobj.read_value(),
                                  timestamp=time.time())
        else:
            return NoSuchDeviceErrorReply(msgargs.device)

    def handle_ReadParam(self, msgargs):
        devobj = self.get_device(msgargs.device)
        if devobj:
            readfunc = getattr(devobj, 'read_%s' % msgargs.param, None)
            if readfunc:
                return ReadParamReply(msgargs.device, msgargs.param,
                                      readfunc(), timestamp=time.time())
            else:
                return NoSuchParamErrorReply(msgargs.device, msgargs.param)
        else:
            return NoSuchDeviceErrorReply(msgargs.device)

    def handle_WriteParam(self, msgargs):
        devobj = self.get_device(msgargs.device)
        if devobj:
            writefunc = getattr(devobj, 'write_%s' % msgargs.param, None)
            if writefunc:
                readbackvalue = writefunc(msgargs.value) or msgargs.value
                # trigger async updates
                setattr(devobj, msgargs.param, readbackvalue)
                return WriteParamReply(msgargs.device, msgargs.param,
                                       readbackvalue,
                                       timestamp=time.time())
            else:
                if getattr(devobj, 'read_%s' % msgargs.param, None):
                    return ParamReadonlyErrorReply(msgargs.device,
                                                   msgargs.param)
                else:
                    return NoSuchParamErrorReply(msgargs.device,
                                                 msgargs.param)
        else:
            return NoSuchDeviceErrorReply(msgargs.device)

    def handle_RequestAsyncData(self, msgargs):
        return ErrorReply('AsyncData is not (yet) supported')

    def handle_ListOfFeatures(self, msgargs):
        # no features supported (yet)
        return ListOfFeaturesReply([])

    def handle_ActivateFeature(self, msgargs):
        return ErrorReply('Features are not (yet) supported')

    def unhandled(self, msgname, msgargs):
        """handler for unhandled Messages

        (no handle_<messagename> method was defined)
        """
        self.log.error('IGN: got unhandled request %s' % msgname)
        return ErrorReply('Got Unhandled Request')

    def parse_message(self, message):
        # parses a message and returns
        # msgtype, msgname and parameters of message (as dict)
        msgtype = 'unknown'
        msgname = 'unknown'
        if isinstance(message, ErrorReply):
            msgtype = message.TYPE
            msgname = message.__class__.__name__[:-len('Reply')]
        elif isinstance(message, Request):
            msgtype = message.TYPE
            msgname = message.__class__.__name__[:-len('Request')]
        elif isinstance(message, Reply):
            msgtype = message.TYPE
            msgname = message.__class__.__name__[:-len('Reply')]
        return msgtype, msgname, \
            attrdict([(k, getattr(message, k)) for k in message.ARGS])
