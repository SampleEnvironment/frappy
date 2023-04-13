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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""simple interactive python client

Usage:

from frappy.client.interactive import Client

client = Client('localhost:5000')  # start client.
# this connects and creates objects for all SECoP modules in the main namespace

<module>                            # list all parameters
<module>.<param> = <value>          # change parameter
<module>(<target>)                  # set target and wait until not busy
                                    # 'status' and 'value' changes are shown every 1 sec
client.mininterval = 0.2            # change minimal update interval to 0.2 sec (default is 1 second)

watch(T)                            # watch changes of T.status and T.value (stop with ctrl-C)
watch(T='status target')            # watch status and target parameters
watch(io, T=True)                   # watch io and all parameters of T
"""

import sys
import time
import re
import code
import signal
import os
from os.path import expanduser
from queue import Queue
from frappy.client import SecopClient
from frappy.errors import SECoPError
from frappy.datatypes import get_datatype, StatusType
try:
    import readline
except ImportError:
    readline = None

main = sys.modules['__main__']

LOG_LEVELS = {'debug', 'comlog', 'info', 'warning', 'error', 'off'}
CLR = '\r\x1b[K'  # code to move to the left and clear current line


class Logger:
    show_time = False
    sigwinch = False

    def __init__(self, loglevel='info'):
        func = self.noop
        for lev in 'debug', 'info', 'warning', 'error':
            if lev == loglevel:
                func = self.emit
            setattr(self, lev, func)
        self._minute = 0

    def emit(self, fmt, *args, **kwds):
        if self.show_time:
            now = time.time()
            tm = time.localtime(now)
            if tm.tm_min != self._minute:
                self._minute = tm.tm_min
                print(CLR + time.strftime('--- %H:%M:%S ---', tm))
            sec = ('%6.3f' % (now % 60.0)).replace(' ', '0')
            print(CLR + sec, str(fmt) % args)
        else:
            print(CLR + (str(fmt) % args))
        if self.sigwinch:
            # SIGWINCH: 'window size has changed' -> triggers a refresh of the input line
            os.kill(os.getpid(), signal.SIGWINCH)

    @staticmethod
    def noop(fmt, *args, **kwds):
        pass


class PrettyFloat(float):
    """float with a nicer repr:

    - numbers which are close to a fractional decimal number do not have
      additional annoying digits
    - always display a decimal point
    """
    def __repr__(self):
        result = '%.12g' % self
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
        self._running = None
        self._status = None
        props = secnode.modules[name]['properties']
        self._title = '# %s (%s)' % (props.get('implementation', ''), props.get('interface_classes', [''])[0])

    def _one_line(self, pname, minwid=0):
        """return <module>.<param> = <value> truncated to one line"""
        param = getattr(type(self), pname)
        result = param.formatted(self)
        pname = pname.ljust(minwid)
        vallen = 113 - len(self._name) - len(pname)
        if len(result) > vallen:
            result = result[:vallen - 4] + ' ...'
        return '%s.%s = %s' % (self._name, pname, result)

    def _isBusy(self):
        return self.status[0] // 100 == StatusType.BUSY // 100

    def _status_value_update(self, m, p, status, t, e):
        if self._running:
            try:
                self._running.put(True)
                if self._running and not self._isBusy():
                    self._running.put(False)
            except TypeError:  # may happen when _running is removed during above lines
                pass

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
        print('--- %s:\nlog: %s, watch: %s' % (self._name, self._log_level, ' '.join(self._watched_params)))

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
            Console.raise_without_traceback(error)
        return value

    def __call__(self, target=None):
        if target is None:
            return self.read()
        self.target = target  # this sets self._running
        type(self).value.prev = None  # show at least one value
        try:
            while self._running.get():
                self._watch_parameter(self._name, 'value', mininterval=self._secnode.mininterval)
                self._watch_parameter(self._name, 'status')
        except KeyboardInterrupt:
            self._secnode.log.info('-- interrupted --')
        self._running = None
        self._watch_parameter(self._name, 'status')
        self._secnode.readParameter(self._name, 'value')
        self._watch_parameter(self._name, 'value', forced=True)
        return self.value

    def __repr__(self):
        wid = max(len(k) for k in self._parameters)
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
            Console.raise_without_traceback(error)
            raise error
        return value

    def formatted(self, obj):
        value, _, error = obj._secnode.cache[obj._name, self.name]
        if error:
            return repr(error)
        return self.format(value)

    def __set__(self, obj, value):
        if self.name == 'target':
            obj._running = Queue()
        try:
            obj._secnode.setParameter(obj._name, self.name, value)
        except SECoPError as e:
            Console.raise_without_traceback(e)
            # obj._secnode.log.error(repr(e))

    def format(self, value):
        return self.datatype.format_value(value)


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
        else:
            result, _ = self.exec(self.modname, self.name, args or None)
        return result

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return self.call


def show_parameter(modname, pname, *args, forced=False, mininterval=0):
    """show parameter update"""
    mobj = getattr(main, modname)
    mobj._watch_parameter(modname, pname, *args)


def watch(*args, **kwds):
    modules = []
    for mobj in args:
        if isinstance(mobj, Module):
            if mobj._name not in kwds:
                modules.append(mobj)
                mobj._set_watching()
        else:
            print('do not know %r' % mobj)
    for key, arg in kwds.items():
        mobj = getattr(main, key, None)
        if mobj is None:
            print('do not know %r' % key)
        else:
            modules.append(mobj)
            mobj._set_watching(arg)
    print('---')
    try:
        for mobj in modules:
            mobj._start_watching()
        time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        for mobj in modules:
            mobj._stop_watching()
    print()


class Client(SecopClient):
    activate = True
    secnodes = {}
    mininterval = 1

    def __init__(self, uri, loglevel='info', name=''):
        # remove previous client:
        prev = self.secnodes.pop(uri, None)
        log = Logger(loglevel)
        removed_modules = []
        if prev:
            log.info('remove previous client to %s', uri)
            for modname in prev.modules:
                prevnode = getattr(getattr(main, modname, None), '_secnode', None)
                if prevnode == prev:
                    removed_modules.append(modname)
                    delattr(main, modname)
            prev.disconnect()
        self.secnodes[uri] = self
        if name:
            log.info('\n>>> %s = Client(%r)', name, uri)
        super().__init__(uri, log)
        self.connect()
        created_modules = []
        skipped_modules = []
        for modname, moddesc in self.modules.items():
            prev = getattr(main, modname, None)
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
            mobj = type('M_%s' % modname, (Module,), attrs)(modname, self)
            if 'status' in mobj._parameters:
                self.register_callback((modname, 'status'), updateEvent=mobj._status_value_update)
                self.register_callback((modname, 'value'), updateEvent=mobj._status_value_update)
            setattr(main, modname, mobj)
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
            modobj = getattr(main, modname, None)
            if modobj:
                modobj.handle_log_message_(loglevel, data)
                return
            self.log.info('module %s not found', modname)
        self.log.info('unhandled: %s %s %r', action, ident, data)

    def __repr__(self):
        return 'Client(%r)' % self.uri


class Console(code.InteractiveConsole):
    def __init__(self, local):
        super().__init__(local)
        history = None
        if readline:
            try:
                history = expanduser('~/.frappy-cli-history')
                readline.read_history_file(history)
            except FileNotFoundError:
                pass
        try:
            self.interact('', '')
        finally:
            if history:
                readline.write_history_file(history)

    def raw_input(self, prompt=""):
        Logger.sigwinch = bool(readline)  # activate refresh signal
        line = input(prompt)
        Logger.sigwinch = False
        return line

    @classmethod
    def raise_without_traceback(cls, exc):
        def omit_traceback_once(cls):
            del Console.showtraceback
        cls.showtraceback = omit_traceback_once
        print('ERROR:', repr(exc))
        raise exc
