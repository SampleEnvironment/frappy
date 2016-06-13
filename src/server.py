
import logging
import time

from messages import *
from device import *


class DeviceServer(object):
    def __init__(self):
        self._devices = {}
        self.log = logging
        
        self.log.basicConfig(level=logging.WARNING,
                    format='%(asctime)s %(levelname)s %(message)s')
        
    def registerDevice(self, deviceobj, devicename):
    # make the server export a deviceobj under a given name.
    # all exportet properties are taken from the device
        if devicename in self._devices:
            self.log.error('IGN: Device %r already registered' % devicename)
        else:
            self._devices[devicename] = deviceobj
            deviceobj.name = devicename
    
    def unRegisterDevice(self, device_obj_or_name):
        if not device_obj_or_name in self._devices:
            self.log.error('IGN: Device %r not registered!' % device_obj_or_name)
        else:
            del self._devices[device_obj_or_name]
            # may need to do more
    
    def handle(self, msg):
        # server got a message, handle it
        msgtype, msgname, msgargs = parse(msg)
        if msgtype != 'request':
            self.log.error('IGN: Server only handles request, but got %s/%s!' % (msgtype, msgname))
            return
        try:
            self.log.info('handling message %s with %r' % (msgname, msgargs))
            res = self._handle(msgname, msgargs)
            self.log.info('replying with %r' % res)
            return res
        except Exception as err:
            res = ErrorReply('Exception:\n%r' % err)
            self.log.info('replying with %r' % res)
            return res

    def _handle(self, msgname, msgargs):
        # check all supported Requests, act and return reply
        self.log.debug('handling request %r' % msgname)
        if msgname == 'ListDevices':
            return ListDevicesReply(list(self._devices.keys()))
        elif msgname == 'ListDeviceParams':
            devobj = self._devices.get(msgargs.device, None)
            if devobj:
                return ListDeviceParamsReply(msgargs.device, get_device_pars(devobj))
            else:
                return NoSuchDeviceErrorReply(msgargs.device)
        elif msgname == 'ReadValue':
            devobj = self._devices.get(msgargs.device, None)
            if devobj:
                return ReadValueReply(msgargs.device, devobj.read_value(), timestamp=time.time())
            else:
                return NoSuchDeviceErrorReply(msgargs.device)
        elif msgname == 'ReadParam':
            devobj = self._devices.get(msgargs.device, None)
            if devobj:
                readfunc = getattr(devobj, 'read_%s' % msgargs.param, None)
                if readfunc:
                    return ReadParamReply(msgargs.device, msgargs.param, readfunc(), timestamp=time.time())
                else:
                    return NoSuchParamErrorReply(msgargs.device, msgargs.param)
            else:
                return NoSuchDeviceErrorReply(msgargs.device)
        elif msgname == 'WriteParam':
            devobj = self._devices.get(msgargs.device, None)
            if devobj:
                writefunc = getattr(devobj, 'write_%s' % msgargs.param, None)
                if writefunc:
                    return WriteParamReply(msgargs.device, msgargs.param, writefunc(msgargs.value) or msgargs.value, timestamp=time.time())
                else:
                    if getattr(devobj, 'read_%s' % msgargs.param, None):
                        return ParamReadonlyErrorReply(msgargs.device, msgargs.param)
                    else:
                        return NoSuchParamErrorReply(msgargs.device, msgargs.param)
            else:
                
                return NoSuchDeviceErrorReply(msgargs.device)
        elif msgname == 'RequestAsyncData':
            return ErrorReply('AsyncData is not (yet) supported')
        elif msgname == 'ListOfFeatures':
            return ListOfFeaturesReply([])
        elif msgname == 'ActivateFeature':
            return ErrorReply('Features are not (yet) supported')
        else:
            self.log.error('IGN: got unhandled request %s' % msgname)
            return ErrorReply('Got Unhandled Request')


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
#    def read_NotImplemented(self):
#        raise NotImplemented()
    def do_wait(self):
        time.sleep(3)
    def do_stop(self):
        pass
    def do_count(self):
        print "counting:"
        for d in range(10-1,-1,-1):
            print '%d',
            time.sleep(1)
        print
    def do_add_args(self, arg1, arg2):
        return arg1+arg2
    def do_return_stuff(self):
        return [{a:1},(2,3)]


if __name__ == '__main__':
    print "minimal testing: server"
    srv = DeviceServer()
    srv.registerDevice(TestDevice(), 'dev1')
    srv.registerDevice(TestDevice(), 'dev2')
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
                print ' - param %r\'s description is: %r' % (p, pinfo.description)
            else:
                print ' - param %r has no description' % p
            replytype, replyname, rv = parse(srv.handle(ReadParamRequest(dev, p)))
            if replytype == 'error':
                print ' - reading param %r resulted in error/%s' %(p, replyname)
            else:
                print ' - param %r current value is %r' % (p, rv.value)
                print ' - param %r current unit is %r' % (p, rv.unit)

