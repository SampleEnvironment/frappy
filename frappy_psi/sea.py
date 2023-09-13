# *****************************************************************************
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
#   Markus Zolliker <markus.zolliker@psi.ch>
# *****************************************************************************
"""generic SEA driver

a object or subobject in sea may be assigned to a SECoP module

Examples:

SECoP       SEA          hipadaba path   mod.obj  mod.sub  par.sub   mod.path
-------------------------------------------------------------------------------
tt:maxwait  tt           /tt/maxwait     tt                maxwait   /tt
tt:ramp     tt set/ramp  /tt/set/ramp    tt                set/ramp  /tt
t1:raw      tt t1/raw    /tt/t1/raw      tt       t1       raw       /tt/t1
rx:bla      rx bla       /some/rx_a/bla  rx                bla       /some/rx_a
"""

import json
import threading
import time
import os
from os.path import expanduser, join, exists

from frappy.client import ProxyClient
from frappy.datatypes import ArrayOf, BoolType, \
    EnumType, FloatRange, IntRange, StringType
from frappy.errors import ConfigError, HardwareError, secop_error, CommunicationFailedError
from frappy.lib import generalConfig, mkthread
from frappy.lib.asynconn import AsynConn, ConnectionClosed
from frappy.modules import Attached, Command, Done, Drivable, \
    Module, Parameter, Property, Readable, Writable
from frappy.protocol.dispatcher import make_update


CFG_HEADER = """Node('%(config)s.sea.psi.ch',
    '''%(nodedescr)s''',
)
Mod(%(seaconn)r,
    'frappy_psi.sea.SeaClient',
    '%(service)s sea connection for %(config)s',
    config = %(config)r,
    service = %(service)r,
)
"""

CFG_MODULE = """Mod(%(module)r,
    'frappy_psi.sea.%(modcls)s', '',
    io = %(seaconn)r,
    sea_object = %(module)r,
)
"""

SERVICE_NAMES = {
    'config': 'main',
    'stick': 'stick',
    'addon': 'addons',
}

SEA_DIR = expanduser('~/sea')
seaconfdir = os.environ.get('FRAPPY_SEA_DIR')
if not exists(seaconfdir):
    for confdir in generalConfig.confdir.split(os.pathsep):
        seaconfdir = join(confdir, 'sea')
        if exists(seaconfdir):
            break


def get_sea_port(instance):
    for filename in ('sea_%s.tcl' % instance, 'sea.tcl'):
        try:
            with open(join(SEA_DIR, filename), encoding='utf-8') as f:
                for line in f:
                    linesplit = line.split()
                    if len(linesplit) == 3:
                        _, var, value = line.split()
                        if var == 'serverport':
                            return value
        except FileNotFoundError:
            pass
    return None


class SeaClient(ProxyClient, Module):
    """connection to SEA"""

    uri = Parameter('hostname:portnumber', datatype=StringType(), default='localhost:5000')
    timeout = Parameter('timeout', datatype=FloatRange(0), default=10)
    config = Property("""needed SEA configuration, space separated

                      Example: "ori4.config ori4.stick"
                      """, StringType(), default='')
    service = Property("main/stick/addons", StringType(), default='')
    visibility = 'expert'
    default_json_file = {}
    _connect_thread = None
    _service_manager = None
    _instance = None
    _last_connect = 0

    def __init__(self, name, log, opts, srv):
        nodename = srv.node_cfg.get('name') or srv.node_cfg.get('equipment_id')
        instance = nodename.rsplit('_', 1)[0]
        if 'uri' not in opts:
            self._instance = instance
            port = get_sea_port(instance)
            if port is None:
                raise ConfigError('missing sea port for %s' % instance)
            opts['uri'] = {'value': 'tcp://localhost:%s' % port}
        self.objects = set()
        self.shutdown = False
        self.path2param = {}
        self._write_lock = threading.Lock()
        config = opts.get('config')
        if isinstance(config, dict):
            config = config['value']
        if config:
            self.default_json_file[name] = config.split()[0] + '.json'
        self.syncio = None
        self.asynio = None
        ProxyClient.__init__(self)
        Module.__init__(self, name, log, opts, srv)

    def doPoll(self):
        if not self.asynio and time.time() > self._last_connect + 10:
            with self._write_lock:
                # make sure no more connect thread is running
                if self._connect_thread and self._connect_thread.isAlive():
                    return
                if not self._last_connect:
                    self.log.info('reconnect to SEA %s', self.service)
                self._connect_thread = mkthread(self._connect, None)

    def register_obj(self, module, obj):
        self.objects.add(obj)
        for k, v in module.path2param.items():
            self.path2param.setdefault(k, []).extend(v)
        self.register_callback(module.name, module.updateEvent)

    def _connect(self, started_callback):
        self.asynio = None
        if self.syncio:
            # trigger syncio reconnect in self.request()
            try:
                self.syncio.disconnect()
            except Exception:
                pass
        self.syncio = None
        self._last_connect = time.time()
        if self._instance:
            if not self._service_manager:
                if self._service_manager is None:
                    try:
                        from servicemanager import SeaManager  # pylint: disable=import-outside-toplevel
                        self._service_manager = SeaManager()
                    except ImportError:
                        self._service_manager = False
            if self._service_manager:
                self._service_manager.do_start(self._instance)
        if '//' not in self.uri:
            self.uri = 'tcp://' + self.uri
        self.asynio = AsynConn(self.uri)
        reply = self.asynio.readline()
        if reply != b'OK':
            raise CommunicationFailedError('reply %r should be "OK"' % reply)
        for _ in range(2):
            self.asynio.writeline(b'Spy 007')
            reply = self.asynio.readline()
            if reply == b'Login OK':
                break
        else:
            raise CommunicationFailedError('reply %r should be "Login OK"' % reply)
        result = self.request('frappy_config %s %s' % (self.service, self.config))
        if result not in {'0', '1'}:
            raise CommunicationFailedError(f'reply from frappy_config: {result}')
        # frappy_async_client switches to the json protocol (better for updates)
        self.asynio.writeline(b'frappy_async_client')
        self.asynio.writeline(('get_all_param ' + ' '.join(self.objects)).encode())
        self._connect_thread = None
        mkthread(self._rxthread, started_callback)

    def request(self, command, quiet=False):
        """send a request and wait for reply"""
        with self._write_lock:
            if not self.syncio or not self.syncio.connection:
                if not self.asynio or not self.asynio.connection:
                    try:
                        self._connect_thread.join()
                    except AttributeError:
                        pass
                    # let doPoll do the reconnect
                    self.pollInfo.trigger(True)
                    raise ConnectionClosed('disconnected - reconnect later')
                self.syncio = AsynConn(self.uri)
                assert self.syncio.readline() == b'OK'
                self.syncio.writeline(b'seauser seaser')
                assert self.syncio.readline() == b'Login OK'
                self.log.info('connected to %s', self.uri)
            try:
                self.syncio.flush_recv()
                ft = 'fulltransAct' if quiet else 'fulltransact'
                self.syncio.writeline(('%s %s' % (ft, command)).encode())
                result = None
                deadline = time.time() + 10
                while time.time() < deadline:
                    reply = self.syncio.readline()
                    if reply is None:
                        continue
                    reply = reply.decode()
                    if reply.startswith('TRANSACTIONSTART'):
                        result = []
                        continue
                    if reply == 'TRANSACTIONFINISHED':
                        if result is None:
                            self.log.info('missing TRANSACTIONSTART on: %s', command)
                            return ''
                        if not result:
                            return ''
                        return '\n'.join(result)
                    if result is None:
                        self.log.info('swallow: %s', reply)
                        continue
                    if not result:
                        result = [reply.split('=', 1)[-1]]
                    else:
                        result.append(reply)
            except ConnectionClosed:
                try:
                    self.syncio.disconnect()
                except Exception:
                    pass
                self.syncio = None
                raise
        raise TimeoutError('no response within 10s')

    def _rxthread(self, started_callback):
        recheck = None
        while not self.shutdown:
            if recheck and time.time() > recheck:
                # try to collect device changes within 1 sec
                recheck = None
                result = self.request('check_config %s %s' % (self.service, self.config))
                if result == '1':
                    self.asynio.writeline(('get_all_param ' + ' '.join(self.objects)).encode())
                else:
                    self.DISPATCHER.shutdown()
            try:
                reply = self.asynio.readline()
                if reply is None:
                    continue
            except ConnectionClosed:
                try:
                    self.asynio.disconnect()
                except Exception:
                    pass
                self.asynio = None
                break
            try:
                msg = json.loads(reply)
            except Exception as e:
                self.log.warn('bad reply %r %r', e, reply)
                continue
            if isinstance(msg, str):
                if msg.startswith('_E '):
                    try:
                        _, path, readerror = msg.split(None, 2)
                    except ValueError:
                        continue
                else:
                    continue
                data = {'%s.geterror' % path: readerror.replace('ERROR: ', '')}
                obj = None
                flag = 'hdbevent'
            else:
                obj = msg['object']
                flag = msg['flag']
                data = msg['data']
            if flag == 'finish' and obj == 'get_all_param':
                # first updates have finished
                if started_callback:
                    started_callback()
                    started_callback = None
                continue
            if flag != 'hdbevent':
                if obj not in ('frappy_async_client', 'get_all_param'):
                    self.log.debug('skip %r', msg)
                continue
            if not data:
                continue
            if not isinstance(data, dict):
                self.log.debug('what means %r', msg)
                continue
            now = time.time()
            for path, value in data.items():
                readerror = None
                if path.endswith('.geterror'):
                    if value:
                        readerror = HardwareError(value)
                    path = path.rsplit('.', 1)[0]
                    value = None
                mplist = self.path2param.get(path)
                if mplist is None:
                    if path.startswith('/device'):
                        if path == '/device/changetime':
                            recheck = time.time() + 1
                        elif path.startswith('/device/frappy_%s' % self.service) and value == '':
                            self.DISPATCHER.shutdown()
                else:
                    for module, param in mplist:
                        oldv, oldt, oldr = self.cache.get((module, param), [None, None, None])
                        if value is None:
                            value = oldv
                        if value != oldv or str(readerror) != str(oldr) or abs(now - oldt) > 60:
                            # do not update unchanged values within 60 sec
                            self.updateValue(module, param, value, now, readerror)

    @Command(StringType(), result=StringType())
    def communicate(self, command):
        """send a command to SEA"""
        reply = self.request(command)
        return reply

    @Command(StringType(), result=StringType())
    def query(self, cmd, quiet=False):
        """a request checking for errors and accepting 0 or 1 line as result"""
        errors = []
        reply = None
        for line in self.request(cmd, quiet).split('\n'):
            if line.strip().startswith('ERROR:'):
                errors.append(line[6:].strip())
            elif reply is None:
                reply = line.strip()
            else:
                self.log.info('SEA: superfluous reply %r to %r', reply, cmd)
        if errors:
            raise HardwareError('; '.join(errors))
        return reply


class SeaConfigCreator(SeaClient):
    def startModule(self, start_events):
        """save objects (and sub-objects) description and exit"""
        self._connect(None)
        reply = self.request('describe_all')
        reply = ''.join('' if line.startswith('WARNING') else line for line in reply.split('\n'))
        description, reply = json.loads(reply)
        modules = {}
        modcls = {}
        for filename, obj, descr in reply:
            if filename not in modules:
                modules[filename] = {}
            if descr['params'][0].get('cmd', '').startswith('run '):
                modcls[obj] = 'SeaDrivable'
            elif not descr['params'][0].get('readonly', True):
                modcls[obj] = 'SeaWritable'
            else:
                modcls[obj] = 'SeaReadable'
            modules.setdefault(filename, {})[obj] = descr

        result = []
        for filename, descr in modules.items():
            stripped, _, ext = filename.rpartition('.')
            service = SERVICE_NAMES[ext]
            seaconn = 'sea_' + service
            cfgfile = join(seaconfdir, stripped + '_cfg.py')
            with open(cfgfile, 'w', encoding='utf-8') as fp:
                fp.write(CFG_HEADER % {'config': filename, 'seaconn': seaconn, 'service': service,
                                       'nodedescr': description.get(filename, filename)})
                for obj in descr:
                    fp.write(CFG_MODULE % {'modcls': modcls[obj], 'module': obj, 'seaconn': seaconn})
            content = json.dumps(descr).replace('}, {', '},\n{').replace('[{', '[\n{').replace('}]}, ', '}]},\n\n')
            result.append('%s\n' % cfgfile)
            with open(join(seaconfdir, filename + '.json'), 'w', encoding='utf-8') as fp:
                fp.write(content + '\n')
            result.append('%s: %s' % (filename, ','.join(n for n in descr)))
        raise SystemExit('; '.join(result))

    @Command(StringType(), result=StringType())
    def query(self, cmd, quiet=False):
        """a request checking for errors and accepting 0 or 1 line as result"""
        errors = []
        reply = None
        for line in self.request(cmd).split('\n'):
            if line.strip().startswith('ERROR:'):
                errors.append(line[6:].strip())
            elif reply is None:
                reply = line.strip()
            else:
                self.log.info('SEA: superfluous reply %r to %r', reply, cmd)
        if errors:
            raise HardwareError('; '.join(errors))
        return reply


SEA_TO_SECOPTYPE = {
    'float': FloatRange(),
    'text': StringType(),
    'int': IntRange(-1 << 63, 1 << 63 - 1),
    'bool': BoolType(),
    'none': None,
    'floatvarar': ArrayOf(FloatRange(), 0, 400),  # 400 is the current limit for proper notify events in SEA
}


class SeaEnum(EnumType):
    """some sea enum nodes have text type -> accept '<integer>' also"""
    def copy(self):
        return SeaEnum(self._enum)

    def __call__(self, value):
        try:
            value = int(value)
        except TypeError:
            pass
        return super().__call__(value)


def get_datatype(paramdesc):
    typ = paramdesc['type']
    result = SEA_TO_SECOPTYPE.get(typ, False)
    if result is not False:  # general case
        return result
    # special cases
    if typ == 'enum':
        return SeaEnum(paramdesc['enum'])
    raise ValueError('unknown SEA type %r' % typ)


class SeaModule(Module):
    io = Attached()

    path2param = None
    sea_object = None
    hdbpath = None  # hdbpath for main writable

    # pylint: disable=too-many-statements,arguments-differ,too-many-branches
    def __new__(cls, name, logger, cfgdict, srv):
        if hasattr(srv, 'extra_sea_modules'):
            extra_modules = srv.extra_sea_modules
        else:
            extra_modules = {}
            srv.extra_sea_modules = extra_modules
        for k, v in cfgdict.items():
            try:
                cfgdict[k] = v['value']
            except (KeyError, TypeError):
                pass
        json_file = cfgdict.pop('json_file', None) or SeaClient.default_json_file[cfgdict['io']]
        visibility_level = cfgdict.pop('visibility_level', 2)

        single_module = cfgdict.pop('single_module', None)
        if single_module:
            sea_object, base, paramdesc = extra_modules[single_module]
            params = [paramdesc]
            paramdesc['key'] = 'value'
            if issubclass(cls, SeaWritable):
                if paramdesc.get('readonly', True):
                    raise ConfigError(f"{sea_object}/{paramdesc['path']} is not writable")
                params.insert(0, paramdesc.copy())  # copy value
                paramdesc['key'] = 'target'
                paramdesc['readonly'] = False
            extra_module_set = ()
            if 'description' not in cfgdict:
                cfgdict['description'] = f'{single_module}@{json_file}'
        else:
            sea_object = cfgdict.pop('sea_object')
            rel_paths = cfgdict.pop('rel_paths', '.')
            if 'description' not in cfgdict:
                cfgdict['description'] = '%s@%s%s' % (
                    name, json_file, '' if rel_paths == '.' else f' (rel_paths={rel_paths})')

            with open(join(seaconfdir, json_file), encoding='utf-8') as fp:
                content = json.load(fp)
                descr = content[sea_object]
            if rel_paths == '*' or not rel_paths:
                # take all
                main = descr['params'][0]
                if issubclass(cls, Readable):
                    # assert main['path'] == ''  # TODO: check cases where this fails
                    main['key'] = 'value'
                else:
                    descr['params'].pop(0)
            else:
                # filter by relative paths
                result = []
                is_running = None
                for rpath in rel_paths:
                    include = True
                    for paramdesc in descr['params']:
                        path = paramdesc['path']
                        if path.endswith('is_running') and issubclass(cls, Drivable):
                            # take this independent of visibility
                            is_running = paramdesc
                            continue
                        if paramdesc.get('visibility', 1) > visibility_level:
                            continue
                        sub = path.split('/', 1)
                        if rpath == '.':  # take all except subpaths with readonly node at top
                            if len(sub) == 1:
                                include = paramdesc.get('kids', 0) == 0 or not paramdesc.get('readonly', True)
                            if include or path == '':
                                result.append(paramdesc)
                        elif sub[0] == rpath:
                            result.append(paramdesc)
                if is_running:  # take this at end
                    result.append(is_running)
                descr['params'] = result
                rel0 = '' if rel_paths[0] == '.' else rel_paths[0]
                if result[0]['path'] == rel0:
                    if issubclass(cls, Readable):
                        result[0]['key'] = 'value'
                    else:
                        result.pop(0)
                else:
                    logger.error('%s: no value found', name)
            base = descr['base']
            params = descr['params']
            if issubclass(cls, SeaWritable):
                paramdesc = params[0]
                assert paramdesc['key'] == 'value'
                params.append(paramdesc.copy())  # copy value?
                if paramdesc.get('readonly', True):
                    raise ConfigError(f"{sea_object}/{paramdesc['path']} is not writable")
                paramdesc['key'] = 'target'
                paramdesc['readonly'] = False
            extra_module_set = set(cfgdict.pop('extra_modules', ()))
        path2param = {}
        attributes = {'sea_object': sea_object, 'path2param': path2param}

        # some guesses about visibility (may be overriden in *_cfg.py):
        if sea_object in ('table', 'cc'):
            attributes['visibility'] = 2
        elif base.count('/') > 1:
            attributes['visibility'] = 2
        for paramdesc in params:
            path = paramdesc['path']
            readonly = paramdesc.get('readonly', True)
            dt = get_datatype(paramdesc)
            kwds = {'description': paramdesc.get('description', path),
                    'datatype': dt,
                    'visibility': paramdesc.get('visibility', 1),
                    'needscfg': False, 'readonly': readonly}
            if kwds['datatype'] is None:
                kwds.update(visibility=3, default='', datatype=StringType())
            pathlist = path.split('/') if path else []
            key = paramdesc.get('key')  # None, 'value' or 'target'
            if key is None:
                if len(pathlist) > 0:
                    if len(pathlist) == 1:
                        if issubclass(cls, Readable):
                            kwds['group'] = 'more'
                    else:
                        kwds['group'] = pathlist[-2]
                # flatten path to parameter name
                for i in reversed(range(len(pathlist))):
                    key = '_'.join(pathlist[i:])
                    if not key in cls.accessibles:
                        break
                if key == 'is_running':
                    kwds['export'] = False
            if key == 'target' and kwds.get('group') == 'more':
                kwds.pop('group')
            if key in cls.accessibles:
                if key == 'target':
                    kwds['readonly'] = False
                prev = cls.accessibles[key]
                if key == 'status':
                    # special case: status from sea is a string, not the status tuple
                    pobj = prev.copy()
                else:
                    pobj = Parameter(**kwds)
                    merged_properties = prev.propertyValues.copy()
                    pobj.updateProperties(merged_properties)
                    pobj.merge(merged_properties)
            else:
                pobj = Parameter(**kwds)
            datatype = pobj.datatype
            if issubclass(cls, SeaWritable) and key == 'target':
                kwds['readonly'] = False
                attributes['value'] = Parameter(**kwds)

            hdbpath = '/'.join([base] + pathlist)
            if key in extra_module_set:
                extra_modules[name + '.' + key] = sea_object, base, paramdesc
                continue  # skip this parameter
            path2param.setdefault(hdbpath, []).append((name, key))
            attributes[key] = pobj

            def rfunc(self, cmd=f'hval {base}/{path}'):
                reply = self.io.query(cmd, True)
                try:
                    reply = float(reply)
                except ValueError:
                    pass
                # an updateEvent will be handled before above returns
                return reply

            rfunc.poll = False
            attributes['read_' + key] = rfunc

            if not readonly:

                def wfunc(self, value, datatype=datatype, command=paramdesc['cmd']):
                    value = datatype.export_value(value)
                    if isinstance(value, bool):
                        value = int(value)
                        # TODO: check if more has to be done for valid tcl data (strings?)
                    cmd = f'{command} {value}'
                    self.io.query(cmd)
                    return Done

                attributes['write_' + key] = wfunc

        # create standard parameters like value and status, if not yet there
        for pname, pobj in cls.accessibles.items():
            if pname == 'pollinterval':
                pobj.export = False
                attributes[pname] = pobj
                pobj.__set_name__(cls, pname)
            elif pname not in attributes and isinstance(pobj, Parameter):
                pobj.needscfg = False
                attributes[pname] = pobj
                pobj.__set_name__(cls, pname)

        classname = f'{cls.__name__}_{name}'
        newcls = type(classname, (cls,), attributes)
        result = Module.__new__(newcls)
        return result

    def updateEvent(self, module, parameter, value, timestamp, readerror):
        upd = getattr(self, 'update_' + parameter, None)
        if upd:
            upd(value, timestamp, readerror)
            return
        try:
            pobj = self.parameters[parameter]
        except KeyError:
            self.log.error('do not know %s:%s', self.name, parameter)
            raise
        pobj.timestamp = timestamp
        # should be done here: deal with clock differences
        if not readerror:
            try:
                pobj.value = value  # store the value even in case of a validation error
                pobj.value = pobj.datatype(value)
            except Exception as e:
                readerror = secop_error(e)
        pobj.readerror = readerror
        if pobj.export:
            self.DISPATCHER.broadcast_event(make_update(self.name, pobj))

    def initModule(self):
        self.io.register_obj(self, self.sea_object)
        super().initModule()

    def doPoll(self):
        pass


class SeaReadable(SeaModule, Readable):

    def update_status(self, value, timestamp, readerror):
        if readerror:
            value = repr(readerror)
        if value == '':
            self.status = (self.Status.IDLE, '')
        else:
            self.status = (self.Status.ERROR, value)

    def read_status(self):
        return self.status


class SeaWritable(SeaModule, Writable):
    def read_value(self):
        return self.target

    def update_target(self, value, timestamp, readerror):
        self.target = value
        if not readerror:
            self.value = value


class SeaDrivable(SeaModule, Drivable):
    _sea_status = ''
    _is_running = 0

    def earlyInit(self):
        super().earlyInit()
        self._run_event = threading.Event()

    def read_status(self):
        return self.status

    # def read_target(self):
    #    return self.target

    def write_target(self, value):
        self._run_event.clear()
        self.io.query(f'run {self.sea_object} {value}')
        if not self._run_event.wait(5):
            self.log.warn('target changed but is_running stays 0')
        return value

    def update_status(self, value, timestamp, readerror):
        if not readerror:
            self._sea_status = value
            self.updateStatus()

    def update_is_running(self, value, timestamp, readerror):
        if not readerror:
            self._is_running = value
            self.updateStatus()
            if value:
                self._run_event.set()

    def updateStatus(self):
        if self._sea_status:
            self.status = (self.Status.ERROR, self._sea_status)
        elif self._is_running:
            self.status = (self.Status.BUSY, 'driving')
        else:
            self.status = (self.Status.IDLE, '')

    def updateTarget(self, module, parameter, value, timestamp, readerror):
        if value is not None:
            self.target = value

    @Command()
    def stop(self):
        """propagate to SEA

        - on stdsct drivables this will call the halt script
        - on EaseDriv this will set the stopped state
        """
        self.io.query(f'{self.sea_object} is_running 0')
