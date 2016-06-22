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

"""Define basic SECoP DeviceServer"""

import time

from protocol.messages import parse, ListDevicesRequest, ListDeviceParamsRequest, \
    ReadParamRequest, ErrorReply, MessageHandler



class DeviceServer(MessageHandler):
    def __init__(self, logger, serveropts):
        self._devices = {}
        self.log = logger
        # XXX: check serveropts and raise if problems exist
        # mandatory serveropts: interface=tcpip, encoder=pickle, frame=eol
        # XXX: remaining opts are checked by the corresponding interface server

    def serve_forever(self):
        self.log.error("Serving not yet implemented!")

    def register_device(self, deviceobj, devicename):
    # make the server export a deviceobj under a given name.
    # all exportet properties are taken from the device
        if devicename in self._devices:
            self.log.error('IGN: Device %r already registered' % devicename)
        else:
            self._devices[devicename] = deviceobj
            deviceobj.name = devicename

    def unregister_device(self, device_obj_or_name):
        if not device_obj_or_name in self._devices:
            self.log.error('IGN: Device %r not registered!' %
                           device_obj_or_name)
        else:
            del self._devices[device_obj_or_name]
            # may need to do more

    def get_device(self, devname):
        """returns the requested deviceObj or None"""
        devobj = self._devices.get(devname, None)
        return devobj

    def list_devices(self):
        return list(self._devices.keys())

    def handle(self, msg):
        # server got a message, handle it
        msgtype, msgname, msgargs = parse(msg)
        if msgtype != 'request':
            self.log.error('IGN: Server only handles request, but got %s/%s!' %
                           (msgtype, msgname))
            return
        try:
            self.log.info('handling message %s with %r' % (msgname, msgargs))
            handler = getattr(self, 'handle_%s' * msgname, None)
            if handler is None:
                handler = self.unhandled
            res = handler(msgargs)
            self.log.info('replying with %r' % res)
            return res
        except Exception as err:
            res = ErrorReply('Exception:\n%r' % err)
            self.log.info('replying with %r' % res)
            return res


if __name__ == '__main__':
    from devices.core import Driveable
    from protocol import status
    class TestDevice(Driveable):
        name = 'Unset'
        unit = 'Oinks'
        def read_status(self):
            return status.OK
        def read_value(self):
            """The devices main value"""
            return 3.1415
        def read_testpar1(self):
            return 2.718
        def read_fail(self):
            raise KeyError()
        def read_none(self):
            pass
        def read_NotImplemented(self):
            raise NotImplementedError('funny errors should be transported')
        def do_wait(self):
            time.sleep(3)
        def do_stop(self):
            pass
        def do_count(self):
            print "counting:"
            for d in range(10-1, -1, -1):
                print '%d',
                time.sleep(1)
            print
        def do_add_args(self, arg1, arg2):
            return arg1 + arg2
        def do_return_stuff(self):
            return [{'a':1}, (2, 3)]

    print "minimal testing: server"
    srv = DeviceServer()
    srv.register_device(TestDevice(), 'dev1')
    srv.register_device(TestDevice(), 'dev2')
    devices = parse(srv.handle(ListDevicesRequest()))[2]['list_of_devices']
    print 'Srv exports these devices:', devices
    for dev in sorted(devices):
        print '___ testing device %s ___' % dev
        params = parse(srv.handle(ListDeviceParamsRequest(dev)))[2]['params']
        print '-has params: ', sorted(params.keys())
        for p in sorted(params.keys()):
            pinfo = params[p]
            if pinfo.readonly:
                print ' - param %r is readonly' % p
            if pinfo.description:
                print ' - param %r\'s description is: %r' % (p,
                                                             pinfo.description)
            else:
                print ' - param %r has no description' % p
            replytype, replyname, rv = parse(srv.handle(ReadParamRequest(dev,
                                                                         p)))
            if replytype == 'error':
                print ' - reading param %r resulted in error/%s' % (p,
                                                                    replyname)
            else:
                print ' - param %r current value is %r' % (p, rv.value)
                print ' - param %r current unit is %r' % (p, rv.unit)

