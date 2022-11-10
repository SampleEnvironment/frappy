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
"""simple interactive python client"""

import sys
import time
import re
from queue import Queue
from frappy.client import SecopClient
from frappy.errors import SECoPError
from frappy.datatypes import get_datatype

USAGE = """
Usage:

from frappy.client.interactive import Client

client = Client('localhost:5000')  # start client.
# this connects and creates objects for all SECoP modules in the main namespace

<module>                            # list all parameters
<module>.<param> = <value>          # change parameter
<module>(<target>)                  # set target and wait until not busy
                                    # 'status' and 'value' changes are shown every 1 sec
client.mininterval = 0.2            # change minimal update interval to 0.2 sec (default is 1 second)

<module>.watch(1)                   # watch changes of all parameters of a module
<module>.watch(0)                   # remove all watching
<module>.watch(status=1, value=1)   # add 'status' and 'value' to watched parameters
<module>.watch(value=0)             # remove 'value' from watched parameters
"""

main = sys.modules['__main__']


class Logger:
    def __init__(self, loglevel='info'):
        func = self.noop
        for lev in 'debug', 'info', 'warning', 'error':
            if lev == loglevel:
                func = self.emit
            setattr(self, lev, func)
        self._minute = 0

    def emit(self, fmt, *args, **kwds):
        now = time.time()
        minute = now // 60
        if minute != self._minute:
            self._minute = minute
            print(time.strftime('--- %H:%M:%S ---', time.localtime(now)))
        print('%6.3f' % (now % 60.0), str(fmt) % args)

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
        self._running = None
        self._status = None
        props = secnode.modules[name]['properties']
        self._title = '# %s (%s)' % (props.get('implementation', ''), props.get('interface_classes', [''])[0])

    def _one_line(self, pname, minwid=0):
        """return <module>.<param> = <value> truncated to one line"""
        param = getattr(type(self), pname)
        try:
            value = getattr(self, pname)
            r = param.format(value)
        except Exception as e:
            r = repr(e)
        pname = pname.ljust(minwid)
        vallen = 113 - len(self._name) - len(pname)
        if len(r) > vallen:
            r = r[:vallen - 4] + ' ...'
        return '%s.%s = %s' % (self._name, pname, r)

    def _isBusy(self):
        return 300 <= self.status[0] < 400

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

    def watch(self, *args, **kwds):
        enabled = {}
        for arg in args:
            if arg == 1:  # or True
                enabled.update({k: True for k in self._parameters})
            elif arg == 0:  # or False
                enabled.update({k: False for k in self._parameters})
            else:
                enabled.update(arg)
        enabled.update(kwds)
        for pname, enable in enabled.items():
            self._secnode.unregister_callback((self._name, pname), updateEvent=self._watch_parameter)
            if enable:
                self._secnode.register_callback((self._name, pname), updateEvent=self._watch_parameter)

    def read(self, pname='value'):
        value, _, error = self._secnode.readParameter(self._name, pname)
        if error:
            raise error
        return value

    def __call__(self, target=None):
        if target is None:
            return self.read()
        self.target = target  # this sets self._running
        type(self).value.prev = None  # show at least one value
        show_final_value = True
        try:
            while self._running.get():
                self._watch_parameter(self._name, 'value', mininterval=self._secnode.mininterval)
                self._watch_parameter(self._name, 'status')
        except KeyboardInterrupt:
            self._secnode.log.info('-- interrupted --')
        self._running = None
        self._watch_parameter(self._name, 'status')
        self._secnode.readParameter(self._name, 'value')
        self._watch_parameter(self._name, 'value', forced=show_final_value)
        return self.value

    def __repr__(self):
        wid = max(len(k) for k in self._parameters)
        return '%s\n%s\nCommands: %s' % (
            self._title,
            '\n'.join(self._one_line(k, wid) for k in self._parameters),
            ', '.join(k + '()' for k in self._commands))

    def logging(self, level='comlog', pattern='.*'):
        self._log_pattern = re.compile(pattern)
        self._secnode.request('logging', self._name, level)

    def handle_log_message_(self, data):
        if self._log_pattern.match(data):
            self._secnode.log.info('%s: %r', self._name, data)


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
            raise error
        return value

    def __set__(self, obj, value):
        if self.name == 'target':
            obj._running = Queue()
        try:
            obj._secnode.setParameter(obj._name, self.name, value)
        except SECoPError as e:
            obj._secnode.log.error(repr(e))

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


class Client(SecopClient):
    activate = True
    secnodes = {}
    mininterval = 1

    def __init__(self, uri, loglevel='info'):
        # remove previous client:
        prev = self.secnodes.pop(uri, None)
        if prev:
            prev.log.info('remove previous client to %s', uri)
            for modname in prev.modules:
                prevnode = getattr(getattr(main, modname, None), '_secnode', None)
                if prevnode == prev:
                    prev.log.info('remove previous module %s', modname)
                    delattr(main, modname)
            prev.disconnect()
        self.secnodes[uri] = self
        super().__init__(uri, Logger(loglevel))
        self.connect()
        for modname, moddesc in self.modules.items():
            prev = getattr(main, modname, None)
            if prev is None:
                self.log.info('create module %s', modname)
            else:
                if getattr(prev, '_secnode', None) is None:
                    self.log.error('skip module %s overwriting a global variable' % modname)
                    continue
                self.log.info('overwrite module %s', modname)
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
        self.register_callback(None, self.unhandledMessage)
        self.log.info('%s', USAGE)

    def unhandledMessage(self, action, ident, data):
        """handle logging messages"""
        if action == 'log':
            modname = ident.split(':')[0]
            modobj = getattr(main, modname, None)
            if modobj:
                modobj.handle_log_message_(data)
                return
            self.log.info('module %s not found', modname)
        self.log.info('unhandled: %s %s %r', action, ident, data)
