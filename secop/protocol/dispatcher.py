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

Interface to the modules:
 - add_module(modulename, moduleobj, export=True) registers a new module under the
   given name, may also register it for exporting (making accessible)
 - get_module(modulename) returns the requested module or None
 - remove_module(modulename_or_obj): removes the module (during shutdown)

"""
from __future__ import print_function

from time import time as currenttime
import threading

from secop.protocol.messages import Message, EVENTREPLY, IDENTREQUEST
from secop.protocol.errors import SECOPError, NoSuchModuleError, \
    NoSuchCommandError, NoSuchParamError, BadValueError, ReadonlyError
from secop.lib import formatExtendedStack, formatException

try:
    unicode('a')
except NameError:
    # no unicode on py3
    unicode = str  # pylint: disable=redefined-builtin


class Dispatcher(object):

    def __init__(self, logger, options):
        # to avoid errors, we want to eat all options here
        self.equipment_id = options[u'equipment_id']
        self.nodeopts = {}
        for k in list(options):
            self.nodeopts[k] = options.pop(k)

        self.log = logger
        # map ALL modulename -> moduleobj
        self._modules = {}
        # list of EXPORTED modules
        self._export = []
        # list all connections
        self._connections = []
        # active (i.e. broadcast-receiving) connections
        self._active_connections = set()
        # map eventname -> list of subscribed connections
        self._subscriptions = {}
        self._lock = threading.RLock()

    def broadcast_event(self, msg, reallyall=False):
        """broadcasts a msg to all active connections

        used from the dispatcher"""
        if reallyall:
            listeners = self._connections
        else:
            if getattr(msg, u'command', None) is None:
                eventname = u'%s:%s' % (msg.module, msg.parameter
                                       if msg.parameter else u'value')
            else:
                eventname = u'%s:%s()' % (msg.module, msg.command)
            listeners = self._subscriptions.get(eventname, set()).copy()
            listeners.update(self._subscriptions.get(msg.module, set()))
            listeners.update(self._active_connections)
        for conn in listeners:
            conn.queue_async_reply(msg)

    def announce_update(self, moduleobj, pname, pobj):
        """called by modules param setters to notify subscribers of new values
        """
        msg = Message(EVENTREPLY, module=moduleobj.name, parameter=pname)
        msg.set_result(pobj.export_value(), dict(t=pobj.timestamp))
        self.broadcast_event(msg)

    def subscribe(self, conn, modulename, pname=u'value'):
        eventname = modulename
        if pname:
            eventname = u'%s:%s' % (modulename, pname)
        self._subscriptions.setdefault(eventname, set()).add(conn)

    def unsubscribe(self, conn, modulename, pname=u'value'):
        eventname = modulename
        if pname:
            eventname = u'%s:%s' % (modulename, pname)
        if eventname in self._subscriptions:
            self._subscriptions.setdefault(eventname, set()).discard(conn)

    def add_connection(self, conn):
        """registers new connection"""
        self._connections.append(conn)

    def remove_connection(self, conn):
        """removes now longer functional connection"""
        if conn in self._connections:
            self._connections.remove(conn)
        for _evt, conns in list(self._subscriptions.items()):
            conns.discard(conn)

    def register_module(self, moduleobj, modulename, export=True):
        self.log.debug(u'registering module %r as %s (export=%r)' %
                       (moduleobj, modulename, export))
        self._modules[modulename] = moduleobj
        if export:
            self._export.append(modulename)

    def get_module(self, modulename):
        if modulename in self._modules:
            return self._modules[modulename]
        elif modulename in list(self._modules.values()):
            return modulename
        raise NoSuchModuleError(module=unicode(modulename))

    def remove_module(self, modulename_or_obj):
        moduleobj = self.get_module(modulename_or_obj) or modulename_or_obj
        modulename = moduleobj.name
        if modulename in self._export:
            self._export.remove(modulename)
        self._modules.pop(modulename)
        # XXX: also clean _subscriptions

    def list_module_names(self):
        # return a copy of our list
        return self._export[:]

    def list_module_params(self, modulename):
        self.log.debug(u'list_module_params(%r)' % modulename)
        if modulename in self._export:
            # omit export=False params!
            res = {}
            for paramname, param in list(self.get_module(modulename).parameters.items()):
                if param.export:
                    res[paramname] = param.for_export()
            self.log.debug(u'list params for module %s -> %r' %
                           (modulename, res))
            return res
        self.log.debug(u'-> module is not to be exported!')
        return {}

    def list_module_cmds(self, modulename):
        self.log.debug(u'list_module_cmds(%r)' % modulename)
        if modulename in self._export:
            # omit export=False params!
            res = {}
            for cmdname, cmdobj in list(self.get_module(modulename).commands.items()):
                res[cmdname] = cmdobj.for_export()
            self.log.debug(u'list cmds for module %s -> %r' % (modulename, res))
            return res
        self.log.debug(u'-> module is not to be exported!')
        return {}

    def get_descriptive_data(self):
        """returns a python object which upon serialisation results in the descriptive data"""
        # XXX: be lazy and cache this?
        # format: {[{[{[, specific entries first
        result = {u'modules': []}
        for modulename in self._export:
            module = self.get_module(modulename)
            # some of these need rework !
            mod_desc = {u'parameters': [], u'commands': []}
            for pname, param in list(self.list_module_params(
                    modulename).items()):
                mod_desc[u'parameters'].extend([pname, param])
            for cname, cmd in list(self.list_module_cmds(modulename).items()):
                mod_desc[u'commands'].extend([cname, cmd])
            for propname, prop in list(module.properties.items()):
                mod_desc[propname] = prop
            result[u'modules'].extend([modulename, mod_desc])
        result[u'equipment_id'] = self.equipment_id
        result[u'firmware'] = u'The SECoP playground'
        result[u'version'] = u'2017.07'
        result.update(self.nodeopts)
        # XXX: what else?
        return result

    def _execute_command(self, modulename, command, arguments=None):
        if arguments is None:
            arguments = []

        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(module=modulename)

        cmdspec = moduleobj.commands.get(command, None)
        if cmdspec is None:
            raise NoSuchCommandError(module=modulename, command=command)
        if len(cmdspec.arguments) != len(arguments):
            raise BadValueError(
                module=modulename,
                command=command,
                reason=u'Wrong number of arguments!')

        # now call func and wrap result as value
        # note: exceptions are handled in handle_request, not here!
        func = getattr(moduleobj, u'do_' + command)
        res = func(*arguments)
        return res, dict(t=currenttime())

    def _setParamValue(self, modulename, pname, value):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(module=modulename)

        pobj = moduleobj.parameters.get(pname, None)
        if pobj is None:
            raise NoSuchParamError(module=modulename, parameter=pname)
        if pobj.readonly:
            raise ReadonlyError(module=modulename, parameter=pname)

        writefunc = getattr(moduleobj, u'write_%s' % pname, None)
        # note: exceptions are handled in handle_request, not here!
        if writefunc:
            value = writefunc(value)
        else:
            setattr(moduleobj, pname, value)
        if pobj.timestamp:
            return pobj.export_value(), dict(t=pobj.timestamp)
        return pobj.export_value(), {}

    def _getParamValue(self, modulename, pname):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(module=modulename)

        pobj = moduleobj.parameters.get(pname, None)
        if pobj is None:
            raise NoSuchParamError(module=modulename, parameter=pname)

        readfunc = getattr(moduleobj, u'read_%s' % pname, None)
        if readfunc:
            # should also update the pobj (via the setter from the metaclass)
            # note: exceptions are handled in handle_request, not here!
            readfunc()
        if pobj.timestamp:
            return pobj.export_value(), dict(t=pobj.timestamp)
        return pobj.export_value(), {}

    #
    # api to be called from the 'interface'
    # any method above has no idea about 'messages', this is handled here
    #
    def handle_request(self, conn, msg):
        """handles incoming request

        will call 'queue.request(data)' on conn to send reply before returning
        """
        self.log.debug(u'Dispatcher: handling msg: %r' % msg)
        # if there was an error in the frontend, bounce the resulting
        # error msgObj directly back to the client
        if msg.errorclass:
            return msg

        # play thread safe !
        with self._lock:
            if msg.action == IDENTREQUEST:
                self.log.debug(u'Looking for handle_ident')
                handler = self.handle_ident
            else:
                self.log.debug(u'Looking for handle_%s' % msg.action)
                handler = getattr(self, u'handle_%s' % msg.action, None)
            if handler:
                try:
                    reply = handler(conn, msg)
                    if reply:
                        conn.queue_reply(reply)
                    return None
                except SECOPError as err:
                    self.log.exception(err)
                    msg.set_error(err.name, unicode(err), {})#u'traceback': formatException(),
                                                       #u'extended_stack':formatExtendedStack()})
                    return msg
                except (ValueError, TypeError) as err:
                    self.log.exception(err)
                    msg.set_error(u'BadValue', unicode(err), {u'traceback': formatException()})
                    print(u'--------------------')
                    print(formatExtendedStack())
                    print(u'====================')
                    return msg
                except Exception as err:
                    self.log.exception(err)
                    msg.set_error(u'InternalError', unicode(err), {u'traceback': formatException()})
                    print(u'--------------------')
                    print(formatExtendedStack())
                    print(u'====================')
                    return msg
            else:
                self.log.error(u'Can not handle msg %r' % msg)
                msg.set_error(u'Protocol', u'unhandled msg', {})
                return msg

    # now the (defined) handlers for the different requests
    def handle_help(self, conn, msg):
        msg.mkreply()
        return msg

    def handle_ident(self, conn, msg):
        msg.mkreply()
        return msg

    def handle_describe(self, conn, msg):
        # XXX:collect descriptive data
        msg.setvalue(u'specifier', u'.')
        msg.setvalue(u'data', self.get_descriptive_data())
        msg.mkreply()
        return msg

    def handle_read(self, conn, msg):
        # XXX: trigger polling and force sending event
        if not msg.parameter:
            msg.parameter = u'value'
        msg.set_result(*self._getParamValue(msg.module, msg.parameter))

        #if conn in self._active_connections:
        #    return None  # already send to myself
        #if conn in self._subscriptions.get(msg.module, set()):
        #    return None  # already send to myself
        msg.mkreply()
        return msg  # send reply to inactive conns

    def handle_change(self, conn, msg):
        # try to actually write  XXX: should this be done asyncron? we could
        # just return the reply in that case
        if not msg.parameter:
            msg.parameter = u'target'
        msg.set_result(*self._setParamValue(msg.module, msg.parameter, msg.data))

        #if conn in self._active_connections:
        #    return None  # already send to myself
        #if conn in self._subscriptions.get(msg.module, set()):
        #    return None  # already send to myself
        msg.mkreply()
        return msg  # send reply to inactive conns

    def handle_do(self, conn, msg):
        # XXX: should this be done asyncron? we could just return the reply in
        # that case
        if not msg.args:
            msg.args = []
        # try to actually execute command
        msg.set_result(*self._execute_command(msg.module, msg.command, msg.args))

        #if conn in self._active_connections:
        #    return None  # already send to myself
        #if conn in self._subscriptions.get(msg.module, set()):
        #    return None  # already send to myself
        msg.mkreply()
        return msg  # send reply to inactive conns

    def handle_ping(self, conn, msg):
        msg.setvalue(u'data', {u't':currenttime()})
        msg.mkreply()
        return msg

    def handle_activate(self, conn, msg):
        if msg.module:
            if msg.module not in self._modules:
                raise NoSuchModuleError()
            # activate only ONE module
            self.subscribe(conn, msg.specifier, u'')
            modules = [msg.specifier]
        else:
            # activate all modules
            self._active_connections.add(conn)
            modules = self._modules

        # for initial update poll all values...
        for modulename in modules:
            moduleobj = self._modules.get(modulename, None)
            if moduleobj is None:
                self.log.error(u'activate: can not lookup module %r, skipping it' % modulename)
                continue
            for pname, pobj in moduleobj.parameters.items():
                if not pobj.export:  # XXX: handle export_as cases!
                    continue
                # WARNING: THIS READS ALL parameters FROM HW!
                # XXX: should we send the cached values instead? (pbj.value)
                # also: ignore errors here.
                try:
                    res = self._getParamValue(modulename, pname)
                    if res[0] == Ellipsis:  # means we do not have a value at all so skip this
                        self.log.error(
                                u'activate: got no value for %s:%s!' %
                                (modulename, pname))
                    #else:
                        #rm = Message(EVENTREPLY, u'%s:%s' % (modulename, pname))
                        #rm.set_result(*res)
                        #self.broadcast_event(rm)
                except SECOPError as e:
                    self.log.error(u'decide what to do here! (ignore error and skip update)')
                    self.log.exception(e)
        msg.mkreply()
        conn.queue_async_reply(msg)  # should be sent AFTER all the ^^initial updates
        return None

    def handle_deactivate(self, conn, msg):
        if msg.specifier:
            self.unsubscribe(conn, msg.specifier, u'')
        else:
            self._active_connections.discard(conn)
            # XXX: also check all entries in self._subscriptions?
        msg.mkreply()
        return msg

    def handle_error(self, conn, msg):
        # is already an error-reply (came from interface frontend) -> just send it back
        return msg
