from lib import attrdict

class Status(object):
    OK = 200
    MOVING = 210
    WARN = 220
    UNSTABLE = 230
    ERROR = 240
    UNKNOWN = 999

status = Status()


# XXX: deriving PARS/CMDS should be done in a suitable metaclass....
class Device(object):
    name = None
    def read_status(self):
        raise NotImplemented
    def read_name(self):
        return self.name

class Readable(Device):
    unit = ''
    def read_value(self):
        raise NotImplemented
    def read_unit(self):
        return self.unit

class Writeable(Readable):
    def read_target(self):
        return self.target
    def write_target(self, target):
        self.target = target

class Driveable(Writeable):
    def do_wait(self):
        raise NotImplemented
    def do_stop(self):
        raise NotImplemented


def get_device_pars(dev):
    # returns a mapping of the devices parameter names to some 'description'
    res = {}
    for n in dir(dev):
        if n.startswith('read_'):
            pname = n[5:]
            entry = attrdict(readonly=True, description=getattr(dev,n).__doc__)
            if hasattr(dev, 'write_%s' % pname):
                entry['readonly'] = False
            res[pname] = entry
    return res
    
def get_device_cmds(dev):
    # returns a mapping of the devices commands names to some 'description'
    res = {}
    for n in dir(dev):
        if n.startswith('do_'):
            cname = n[5:]
            func = getattr(dev,n)
            entry = attrdict(description=func.__doc__, args='unknown') # XXX: use inspect!
            res[cname] = entry
    return res
    

