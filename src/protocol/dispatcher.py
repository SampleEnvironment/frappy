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
 - list_devices(): return a list of devices + descriptive data as dict
 - list_device_params():
   return a list of paramnames for this device + descriptive data
"""

import time
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
            if frames is None:
                # not enough data (yet) -> return and come back with more
                return None
            self.log.debug('Dispatcher: frames=%r' % frames)
            if not frames:
                conn.queue_reply(self._format_reply(HelpReply()))
            for frame in frames:
                reply = None
                # decode frame
                msg = self.encoding.decode(frame)
                self.log.debug('Dispatcher: msg=%r' % msg)
                # act upon requestobj
                msgtype = msg.TYPE
                msgname = msg.NAME
                # generate reply (coded and framed)
                if msgtype != 'request':
                    reply = ProtocolError(msg)
                else:
                    self.log.debug('Looking for handle_%s' % msgname)
                    handler = getattr(self, 'handle_%s' % msgname, None)
                    if handler:
                        reply = handler(conn, msg)
                    else:
                        self.log.debug('Can not handle msg %r' % msg)
                        reply = self.unhandled(msgname, msg)
                if reply:
                    conn.queue_reply(self._format_reply(reply))
            # queue reply via conn.queue_reply(data)

    def _format_reply(self, reply):
        self.log.debug('formatting reply %r' % reply)
        msg = self.encoding.encode(reply)
        self.log.debug('encoded is %r' % msg)
        frame = self.framing.encode(msg)
        self.log.debug('frame is %r' % frame)
        return frame

    def announce_update(self, devobj, pname, pobj):
        """called by devices param setters to notify subscribers of new values
        """
        devname = devobj.name
        eventname = '%s/%s' % (devname, pname)
        subscriber = self._dispatcher_subscriptions.get(eventname, None)
        if subscriber:
            reply = AsyncDataUnit(devname=devname,
                                  pname=pname,
                                  value=str(pobj.value),
                                  timestamp=pobj.timestamp,
                                  )
            data = self._format_reply(reply)
            for conn in subscriber:
                conn.queue_async_reply(data)

    def subscribe(self, conn, devname, pname):
        eventname = '%s/%s' % (devname, pname)
        self._dispatcher_subscriptions.setdefault(eventname, set()).add(conn)

    def unsubscribe(self, conn, devname, pname):
        eventname = '%s/%s' % (devname, pname)
        if eventname in self._dispatcher_subscriptions:
            self._dispatcher_subscriptions.remove(conn)

    def add_connection(self, conn):
        """registers new connection"""
        self._dispatcher_connections.append(conn)

    def remove_connection(self, conn):
        """removes now longer functional connection"""
        if conn in self._dispatcher_connections:
            self._dispatcher_connections.remove(conn)
        # XXX: also clean _dispatcher_subscriptions !

    def register_device(self, devobj, devname, export=True):
        self.log.debug('registering Device %r as %s (export=%r)' %
                       (devobj, devname, export))
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
                'class': dev.__class__.__name__,
                #'bases': dev.__bases__,
                'parameters': dev.PARAMS.keys(),
                'commands': dev.CMDS.keys(),
                # XXX: what else?
            }
            dd[devname] = descriptive_data
        return dn, dd

    def list_device_params(self, devname):
        self.log.debug('list_device_params(%r)' % devname)
        if devname in self._dispatcher_export:
            # XXX: omit export=False params!
            res = {}
            for paramname, param in self.get_device(devname).PARAMS.items():
                if param.export == True:
                    res[paramname] = param
            self.log.debug('list params for device %s -> %r' %
                           (devname, res))
            return res
        self.log.debug('-> device is not to be exported!')
        return {}

    # demo stuff
    def _setDeviceValue(self, devobj, value):
        # set the device value. return readback value
        # if return == None -> Ellispis (readonly!)
        if self._getDeviceParam(devobj, 'target') != Ellipsis:
            return self._setDeviceParam(devobj, 'target', value)
        return Ellipsis

    def _getDeviceValue(self, devobj):
        # get the device value
        # if return == None -> Ellipsis
        return self._getDeviceParam(devobj, 'value')

    def _setDeviceParam(self, devobj, pname, value):
        # set the device param. return readback value
        # if return == None -> Ellipsis (readonly!)
        pobj = devobj.PARAMS.get(pname, Ellipsis)
        if pobj == Ellipsis:
            return pobj
        if pobj.readonly:
            return self._getDeviceParam(devobj, pname)
        writefunc = getattr(devobj, 'write_%s' % pname, None)
        validator = pobj.validator
        value = validator(value)

        if writefunc:
            value = writefunc(value) or value
        else:
            setattr(devobj, pname, value)

        return self._getDeviceParam(devobj, pname)

    def _getDeviceParam(self, devobj, pname):
        # get the device value
        # if return == None -> Ellipsis
        readfunc = getattr(devobj, 'read_%s' % pname, None)
        if readfunc:
            # should also update the pobj (via the setter from the metaclass)
            readfunc()
        pobj = devobj.PARAMS.get(pname, None)
        if pobj:
            return (pobj.value, pobj.timestamp)
        return getattr(devobj, pname, Ellipsis)

    def handle_Demo(self, conn, msg):
        novalue = msg.novalue
        devname = msg.devname
        paramname = msg.paramname
        propname = msg.propname
        assign = msg.assign

        res = []
        if novalue in ('+', '-'):
            # XXX: handling of subscriptions: propname is ignored
            if devname is None:
                # list all subscriptions for this connection
                for evname, conns in self._dispatcher_subscriptions.items():
                    if conn in conns:
                        res.append('+%s:%s' % evname.split('/'))
            devices = self._dispatcher_export if devname == '*' else [devname]
            for devname in devices:
                devobj = self.get_device(devname)
                if devname != '*' and devobj is None:
                    return NoSuchDeviceError(devname)
                if paramname is None:
                    pnames = ['value', 'status']
                elif paramname == '*':
                    pnames = devobj.PARAMS.keys()
                else:
                    pnames = [paramname]
                for pname in pnames:
                    pobj = devobj.PARAMS.get(pname, None)
                    if pobj and not pobj.export:
                        continue
                    if paramname != '*' and pobj is None:
                        return NoSuchParamError(devname, paramname)

                    if novalue == '+':
                        # subscribe
                        self.subscribe(conn, devname, pname)
                        res.append('+%s:%s' % (devname, pname))
                    elif novalue == '-':
                        # unsubscribe
                        self.unsubscribe(conn, devname, pname)
                        res.append('-%s:%s' % (devname, pname))
            return DemoReply(res)

        if devname is None:
            return Error('no devname given!')
        devices = self._dispatcher_export if devname == '*' else [devname]
        for devname in devices:
            devobj = self.get_device(devname)
            if devname != '*' and devobj is None:
                return NoSuchDeviceError(devname)
            if paramname is None:
                # Access Devices
                val = self._setDeviceValue(
                    devobj, assign) if assign else self._getDeviceValue(devobj)
                if val == Ellipsis:
                    if assign:
                        return ParamReadonlyError(devname, 'target')
                    return NoSuchDevice(devname)
                formatfunc = lambda x: '' if novalue else ('=%r;t=%r' % x)
                res.append(devname + formatfunc(val))

            else:
                pnames = devobj.PARAMS.keys(
                ) if paramname == '*' else [paramname]
                for pname in pnames:
                    pobj = devobj.PARAMS.get(pname, None)
                    if pobj and not pobj.export:
                        continue
                    if paramname != '*' and pobj is None:
                        return NoSuchParamError(devname, paramname)
                    if propname is None:
                        # access params
                        callfunc = lambda x, y: self._setDeviceParam(x, y, assign) \
                            if assign else self._getDeviceParam(x, y)
                        formatfunc = lambda x: '' if novalue else (
                            '=%r;t=%r' % x)
                        try:
                            res.append(('%s:%s' % (devname, pname)) +
                                       formatfunc(callfunc(devobj, pname)))
                        except TypeError as e:
                            return InternalError(e)
                    else:
                        props = pobj.__dict__.keys(
                        ) if propname == '*' else [propname]
                        for prop in props:
                            # read props
                            try:
                                if novalue:
                                    res.append(
                                        '%s:%s:%s' %
                                        (devname, pname, prop))
                                else:
                                    res.append(
                                        '%s:%s:%s=%r' %
                                        (devname, pname, prop, getattr(
                                            pobj, prop)))
                            except TypeError as e:
                                return InternalError(e)

        # now clean responce a little
        res = [
            e.replace(
                '/v=',
                '=') for e in sorted(
                (e.replace(
                    ':value=',
                    '/v=') for e in res))]
        return DemoReply(res)

    # now the (defined) handlers for the different requests
    def handle_Help(self, conn, msg):
        return HelpReply()

    def handle_ListDevices(self, conn, msg):
        # XXX: What about the descriptive data????
        # XXX: choose!
        return ListDevicesReply(self.list_device_names())
        # return ListDevicesReply(*self.list_devices())

    def handle_ListDeviceParams(self, conn, msg):
        # reply with a list of the parameter names for a given device
        self.log.error('Keep: ListDeviceParams')
        if msg.device in self._dispatcher_export:
            params = self.list_device_params(msg.device)
            return ListDeviceParamsReply(msg.device, params.keys())
        else:
            return NoSuchDeviceError(msg.device)

    def handle_ReadAllDevices(self, conn, msg):
        # reply with a bunch of ReadValueReplies, reading ALL devices
        result = []
        for devname in sorted(self.list_device_names()):
            devobj = self.get_device(devname)
            value = self._getdeviceValue(devobj)
            if value is not Ellipsis:
                result.append(ReadValueReply(devname, value,
                                             timestamp=time.time()))
        return ReadAllDevicesReply(readValueReplies=result)

    def handle_ReadValue(self, conn, msg):
        devname = msg.device
        devobj = self.get_device(devname)
        if devobj is None:
            return NoSuchDeviceError(devname)

        value = self._getdeviceValue(devname)
        if value is not Ellipsis:
            return ReadValueReply(devname, value,
                                  timestamp=time.time())

        return InternalError('undefined device value')

    def handle_WriteValue(self, conn, msg):
        value = msg.value
        devname = msg.device
        devobj = self.get_device(devname)
        if devobj is None:
            return NoSuchDeviceError(devname)

        pobj = getattr(devobj.PARAMS, 'target', None)
        if pobj is None:
            return NoSuchParamError(devname, 'target')

        if pobj.readonly:
            return ParamReadonlyError(devname, 'target')

        validator = pobj.validator
        try:
            value = validator(value)
        except Exception as e:
            return InvalidParamValueError(devname, 'target', value, e)

        value = self._setDeviceValue(devobj, value) or value
        WriteValueReply(devname, value, timestamp=time.time())

    def handle_ReadParam(self, conn, msg):
        devname = msg.device
        pname = msg.param
        devobj = self.get_device(devname)
        if devobj is None:
            return NoSuchDeviceError(devname)

        pobj = getattr(devobj.PARAMS, pname, None)
        if pobj is None:
            return NoSuchParamError(devname, pname)

        value = self._getdeviceParam(devobj, pname)
        if value is not Ellipsis:
            return ReadParamReply(devname, pname, value,
                                  timestamp=time.time())

        return InternalError('undefined device value')

    def handle_WriteParam(self, conn, msg):
        value = msg.value
        pname = msg.param
        devname = msg.device
        devobj = self.get_device(devname)
        if devobj is None:
            return NoSuchDeviceError(devname)

        pobj = getattr(devobj.PARAMS, pname, None)
        if pobj is None:
            return NoSuchParamError(devname, pname)

        if pobj.readonly:
            return ParamReadonlyError(devname, pname)

        validator = pobj.validator
        try:
            value = validator(value)
        except Exception as e:
            return InvalidParamValueError(devname, pname, value, e)

        value = self._setDeviceParam(devobj, pname, value) or value
        WriteParamReply(devname, pname, value, timestamp=time.time())

    # XXX: !!!
    def handle_RequestAsyncData(self, conn, msg):
        return Error('AsyncData is not (yet) supported')

    def handle_ListOfFeatures(self, conn, msg):
        # no features supported (yet)
        return ListOfFeaturesReply([])

    def handle_ActivateFeature(self, conn, msg):
        return Error('Features are not (yet) supported')

    def unhandled(self, msgname, conn, msg):
        """handler for unhandled Messages

        (no handle_<messagename> method was defined)
        """
        self.log.error('IGN: got unhandled request %s' % msgname)
        return Error('Got Unhandled Request')
