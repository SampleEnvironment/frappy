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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""simple interactive python client"""

import sys
import time
import re
import code
import signal
import os
import traceback
import threading
import logging
from os.path import expanduser
from frappy.lib import delayed_import
from frappy.client import SecopClient, UnregisterCallback
from frappy.errors import SECoPError
from frappy.datatypes import get_datatype, StatusType

readline = delayed_import('readline')


USAGE = """
Usage:
{client_assign}
# for all SECoP modules objects are created in the main namespace

<module>                     # list all parameters
<module>.<param> = <value>   # change parameter
<module>(<target>)           # set target and wait until not busy
                             # 'status' and 'value' changes are shown every 1 sec
{client_name}.mininterval = 0.2        # change minimal update interval to 0.2 s (default is 1 s)

watch(T)                     # watch changes of T.status and T.value (stop with ctrl-C)
watch(T='status target')     # watch status and target parameters
watch(io, T=True)            # watch io and all parameters of T
{tail}"""


LOG_LEVELS = {
    'debug': logging.DEBUG,
    'comlog':  logging.DEBUG+1,
    'info': logging.INFO,
    'warning': logging.WARN,
    'error': logging.ERROR,
    'off': logging.ERROR+1}
CLR = '\r\x1b[K'  # code to move to the left and clear current line


class Handler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        if clientenv.sigwinch:
            # SIGWINCH: 'window size has changed' -> triggers a refresh of the input line
            os.kill(os.getpid(), signal.SIGWINCH)


class Logger(logging.Logger):
    show_time = False
    _minute = None

    def __init__(self, name, loglevel='info'):
        super().__init__(name, LOG_LEVELS.get(loglevel, logging.INFO))
        handler = Handler()
        handler.formatter = logging.Formatter('%(asctime)s%(message)s')
        handler.formatter.formatTime = self.format_time
        self.addHandler(handler)

    def format_time(self, record, datefmt=None):
        if self.show_time:
            now = record.created
            tm = time.localtime(now)
            sec = f'{now % 60.0:6.3f}'.replace(' ', '0')
            if tm.tm_min == self._minute:
                return f'{CLR}{sec} '
            self._minute = tm.tm_min
            return f"{CLR}{time.strftime('--- %H:%M:%S ---', tm)}\n{sec} "
        return ''


class PrettyFloat(float):
    """float with a nicer repr:

    - numbers which are close to a fractional decimal number do not have
      additional annoying digits
    - always display a decimal point
    """
    def __repr__(self):
        result = f'{self:.12g}'
        if '.' in result or 'e' in result:
            return result
        return result + '.'


class Module:
    _log_pattern = re.compile('.*')

    def __init__(self, name, secnode):
        self._name = name
        self._secnode = secnode
        self._parameters = list(secnode.modules[name]['parameters'])
        self._commands = list(secnode.modules[name]['commands'])
        if 'communicate' in self._commands:
            self._watched_params = {}
            self._log_level = 'comlog'
        else:
            self._watched_params = {'value', 'status'}
            self._log_level = 'info'
        self._is_driving = False
        self._driving_event = threading.Event()
        self._status = None
        props = secnode.modules[name]['properties']
        self._title = f"# {props.get('implementation', '')} ({(props.get('interface_classes') or ['Module'])[0]})"

    def _one_line(self, pname, minwid=0):
        """return <module>.<param> = <value> truncated to one line"""
        param = getattr(type(self), pname)
        result = param.formatted(self)
        pname = pname.ljust(minwid)
        vallen = 113 - len(self._name) - len(pname)
        if len(result) > vallen:
            result = result[:vallen - 4] + ' ...'
        return f'{self._name}.{pname} = {result}'

    def _isBusy(self):
        return self.status[0] // 100 == StatusType.BUSY // 100

    def _status_update(self, m, p, status, t, e):
        if self._is_driving and not self._isBusy():
            self._is_driving = False
        self._driving_event.set()

    def _watch_parameter(self, m, pname, *args, forced=False, mininterval=0):
        """show parameter update"""
        pobj = getattr(type(self), pname)
        if not args:
            args = self._secnode.cache[self._name, pname]
        value = args[0]
        now = time.time()
        if (value != pobj.prev and now >= pobj.prev_time + mininterval) or forced:
            self._secnode.log.info('%s', self._one_line(pname))
            pobj.prev = value
            pobj.prev_time = now

    def _set_watching(self, watch_list=None):
        """set parameters for watching and log levels

        :param watch_list: items to be watched
             True or 1: watch all parameters
             a string from LOG_LEVELS: change the log level
             any other string: convert space separated string to a list of strings
             a list of string: parameters to be watched or log_level to be set
        """
        if isinstance(watch_list, str):
            if watch_list in LOG_LEVELS:
                self._log_level = watch_list
                watch_list = None
            else:
                # accept also space separated list instead of list of strings
                watch_list = watch_list.split()
        elif isinstance(watch_list, int):  # includes also True
            watch_list = self._parameters if watch_list else ()
        if watch_list is not None:
            params = []
            for item in watch_list:
                if item in self._parameters:
                    params.append(item)
                elif item in LOG_LEVELS:
                    self._log_level = item
                else:
                    self._secnode.log.error('can not set %r on module %s', item, self._name)
            self._watched_params = params
        print(f"--- {self._name}:\nlog: {self._log_level}, watch: {' '.join(self._watched_params)}")

    def _start_watching(self):
        for pname in self._watched_params:
            self._watch_parameter(self, pname, forced=True)
            self._secnode.register_callback((self._name, pname), updateEvent=self._watch_parameter)
        self._secnode.request('logging', self._name, self._log_level)
        self._secnode.register_callback(None, nodeStateChange=self._set_log_level)

    def _stop_watching(self):
        for pname in self._watched_params:
            self._secnode.unregister_callback((self._name, pname), updateEvent=self._watch_parameter)
        self._secnode.unregister_callback(None, nodeStateChange=self._set_log_level)
        self._secnode.request('logging', self._name, 'off')

    def _set_log_level(self, online, state):
        if online and state == 'connected':
            self._secnode.request('logging', self._name, self._log_level)

    def read(self, pname='value'):
        value, _, error = self._secnode.readParameter(self._name, pname)
        if error:
            clientenv.raise_with_short_traceback(error)
        return value

    def __call__(self, target=None):
        if target is None:
            return self.read()
        watch_params = ['value', 'status']
        for pname in watch_params:
            self._secnode.register_callback((self._name, pname),
                                            updateEvent=self._watch_parameter,
                                            callimmediately=False)

        self.target = target  # this sets self._is_driving

        def loop():
            while self._is_driving:
                self._driving_event.wait()
                self._driving_event.clear()
        try:
            loop()
        except KeyboardInterrupt as e:
            self._secnode.log.info('-- interrupted --')
            self.stop()
            try:
                loop()  # wait for stopping to be finished
            except KeyboardInterrupt:
                # interrupted again while stopping -> definitely quit
                pass
            clientenv.raise_with_short_traceback(e)
        finally:
            self._secnode.readParameter(self._name, 'value')
            for pname in watch_params:
                self._secnode.unregister_callback((self._name, pname),
                                                  updateEvent=self._watch_parameter)
        return self.value

    def __repr__(self):
        return f'<module {self._name}>'

    def showAll(self):
        wid = max((len(k) for k in self._parameters), default=0)
        return '%s\n%s%s' % (
            self._title,
            '\n'.join(self._one_line(k, wid) for k in self._parameters),
            '\nCommands: %s' % ', '.join(k + '()' for k in self._commands) if self._commands else '')

    def log_filter(self, pattern='.*'):
        self._log_pattern = re.compile(pattern)

    def handle_log_message_(self, loglevel, data):
        if self._log_pattern.match(data):
            if loglevel == 'comlog':
                self._secnode.log.info('%s%s', self._name, data)
            else:
                self._secnode.log.info('%s %s: %s', self._name, loglevel, data)


class Param:
    def __init__(self, name, datainfo):
        self.name = name
        self.prev = None
        self.prev_time = 0
        self.datatype = get_datatype(datainfo)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        value, _, error = obj._secnode.cache[obj._name, self.name]
        if error:
            clientenv.raise_with_short_traceback(error)
        return value

    def formatted(self, obj):
        return obj._secnode.cache[obj._name, self.name].formatted()

    def __set__(self, obj, value):
        try:
            obj._secnode.setParameter(obj._name, self.name, value)
            if self.name == 'target':
                obj._is_driving = obj._isBusy()
            return
        except SECoPError as e:
            clientenv.raise_with_short_traceback(e)
            obj._secnode.log.error(repr(e))


class Command:
    def __init__(self, name, modname, secnode):
        self.name = name
        self.modname = modname
        self.exec = secnode.execCommand

    def call(self, *args, **kwds):
        if kwds:
            if args:
                raise TypeError('mixed arguments forbidden')
            result, _ = self.exec(self.modname, self.name, kwds)
        elif len(args) == 1:
            result, _ = self.exec(self.modname, self.name, *args)
        else:
            result, _ = self.exec(self.modname, self.name, args or None)
        return result

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return self.call


def show_parameter(modname, pname, *args, forced=False, mininterval=0):
    """show parameter update"""
    mobj = clientenv.namespace[modname]
    mobj._watch_parameter(modname, pname, *args)


def watch(*args, **kwds):
    modules = []
    for mobj in args:
        if isinstance(mobj, Module):
            if mobj._name not in kwds:
                modules.append(mobj)
                mobj._set_watching()
        else:
            print(f'do not know {mobj!r}')
    for key, arg in kwds.items():
        mobj = clientenv.namespace.get(key)
        if mobj is None:
            print(f'do not know {key!r}')
        else:
            modules.append(mobj)
            mobj._set_watching(arg)
    print('---')
    try:
        nodes = set()
        for mobj in modules:
            nodes.add(mobj._secnode)
            mobj._start_watching()

        close_event = threading.Event()

        def close_node(online, state):
            if online and state != 'shutdown':
                return None
            close_event.set()
            return UnregisterCallback

        def handle_error(*_):
            close_event.set()
            return UnregisterCallback

        for node in nodes:
            node.register_callback(None, nodeStateChange=close_node, handleError=handle_error)

        close_event.wait()

    except KeyboardInterrupt as e:
        clientenv.raise_with_short_traceback(e)
    finally:
        for mobj in modules:
            mobj._stop_watching()
    print()


class Client(SecopClient):
    activate = True
    secnodes = {}
    mininterval = 1

    def __init__(self, uri, loglevel='info', name=''):
        if clientenv.namespace is None:
            #  called from a simple python interpeter
            clientenv.init(sys.modules['__main__'].__dict__)
        # remove previous client:
        prev = self.secnodes.pop(uri, None)
        log = Logger(name, loglevel)
        removed_modules = []
        if prev:
            log.info('remove previous client to %s', uri)
            for modname in prev.modules:
                prevnode = getattr(clientenv.namespace.get(modname), '_secnode', None)
                if prevnode == prev:
                    removed_modules.append(modname)
                    clientenv.namespace.pop(modname)
            prev.disconnect()
        self.secnodes[uri] = self
        if name:
            log.info('\n>>> %s = Client(%r)', name, uri)
        super().__init__(uri, log)
        self.connect()
        created_modules = []
        skipped_modules = []
        for modname, moddesc in self.modules.items():
            prev = clientenv.namespace.get(modname)
            if prev is None:
                created_modules.append(modname)
            else:
                if getattr(prev, '_secnode', None) is None:
                    skipped_modules.append(modname)
                    continue
                removed_modules.append(modname)
                created_modules.append(modname)
            attrs = {}
            for pname, pinfo in moddesc['parameters'].items():
                attrs[pname] = Param(pname, pinfo['datainfo'])
            for cname in moddesc['commands']:
                attrs[cname] = Command(cname, modname, self)
            mobj = type(f'M_{modname}', (Module,), attrs)(modname, self)
            if 'status' in mobj._parameters:
                self.register_callback((modname, 'status'), updateEvent=mobj._status_update)
            clientenv.namespace[modname] = mobj
        if removed_modules:
            self.log.info('removed modules: %s', ' '.join(removed_modules))
        if skipped_modules:
            self.log.info('skipped modules overwriting globals: %s', ' '.join(skipped_modules))
        if created_modules:
            self.log.info('created modules: %s', ' '.join(created_modules))
        self.register_callback(None, self.unhandledMessage)
        log.show_time = True

    def unhandledMessage(self, action, ident, data):
        """handle logging messages"""
        if action == 'log':
            modname, loglevel = ident.split(':')
            modobj = clientenv.namespace.get(modname)
            if modobj:
                modobj.handle_log_message_(loglevel, data)
                return
            self.log.info('module %s not found', modname)
        self.log.info('unhandled: %s %s %r', action, ident, data)

    def __repr__(self):
        return f'Client({self.uri!r})'


def run(filepath):
    clientenv.namespace.update({
        "__file__": filepath,
        "__name__": "__main__",
    })
    with filepath.open('rb') as file:
        # pylint: disable=exec-used
        exec(compile(file.read(), filepath, 'exec'), clientenv.namespace, None)


class ClientEnvironment:
    namespace = None
    last_frames = 0
    sigwinch = False

    def init(self, namespace=None):
        self.nodes = []
        self.namespace = namespace or {}
        self.namespace.update(run=run, watch=watch, Client=Client)

    def raise_with_short_traceback(self, exc):
        # count number of lines of internal irrelevant stack (for remote errors)
        self.last_frames = len(traceback.format_exception(*sys.exc_info()))
        raise exc

    def short_traceback(self):
        """cleanup traceback from irrelevant lines"""
        lines = traceback.format_exception(*sys.exc_info())
        # line 0: Traceback header
        # skip line 1+2 (contains unspecific console line and exec code)
        lines[1:3] = []
        if '  exec(' in lines[1]:
            # replace additional irrelevant exec line if needed with run command
            lines[1:2] = []
        # skip lines of client code not relevant for remote errors
        lines[-self.last_frames-1:-1] = []
        self.last_frames = 0
        if len(lines) <= 2:  # traceback contains only console line
            lines = lines[-1:]
        return ''.join(lines)


clientenv = ClientEnvironment()


class Console(code.InteractiveConsole):
    def __init__(self, name='cli', namespace=None):
        if namespace:
            clientenv.namespace = namespace
        super().__init__(clientenv.namespace)
        history = None
        if readline:
            try:
                history = expanduser(f'~/.frappy-{name}-history')
                readline.read_history_file(history)
            except FileNotFoundError:
                pass
        try:
            self.interact('', '')
        finally:
            if history:
                readline.write_history_file(history)

    def raw_input(self, prompt=""):
        clientenv.sigwinch = bool(readline)  # activate refresh signal
        line = input(prompt)
        clientenv.sigwinch = False
        if line.startswith('/'):
            line = f"run('{line[1:].strip()}')"
        module = clientenv.namespace.get(line.strip())
        if isinstance(module, Module):
            print(module.showAll())
            line = ''
        return line

    def showtraceback(self):
        self.write(clientenv.short_traceback())


def init(*nodes):
    clientenv.init()
    success = not nodes
    for idx, node in enumerate(nodes):
        client_name = '_c%d' % idx
        try:
            node = clientenv.namespace[client_name] = Client(node, name=client_name)
            clientenv.nodes.append(node)
            success = True
        except Exception as e:
            print(repr(e))
    return success


def interact(usage_tail=''):
    empty = '_c0' not in clientenv.namespace
    print(USAGE.format(
        client_name='cli' if empty else '_c0',
        client_assign="\ncli = Client('localhost:5000')\n" if empty else '',
        tail=usage_tail))
    Console()
