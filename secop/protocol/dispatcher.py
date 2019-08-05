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
   it returns the (sync) reply, and it may call 'queue_async_reply(data)'
   on the connectionobj
 - 'add_connection(connectionobj)' registers new connection
 - 'remove_connection(connectionobj)' removes now longer functional connection

Interface to the modules:
 - add_module(modulename, moduleobj, export=True) registers a new module under the
   given name, may also register it for exporting (making accessible)
 - get_module(modulename) returns the requested module or None
 - remove_module(modulename_or_obj): removes the module (during shutdown)

"""
from __future__ import division, print_function

import threading
from time import time as currenttime

from secop.errors import SECoPServerError as InternalError
from secop.errors import BadValueError, NoSuchCommandError, NoSuchModuleError, \
    NoSuchParameterError, ProtocolError, ReadOnlyError, SECoPError
from secop.params import Parameter
from secop.protocol.messages import COMMANDREPLY, DESCRIPTIONREPLY, \
    DISABLEEVENTSREPLY, ENABLEEVENTSREPLY, ERRORPREFIX, EVENTREPLY, \
    HEARTBEATREPLY, IDENTREPLY, IDENTREQUEST, READREPLY, WRITEREPLY

try:
    unicode
except NameError:
    # no unicode on py3
    unicode = str  # pylint: disable=redefined-builtin


class Dispatcher(object):

    def __init__(self, name, logger, options, srv):
        # to avoid errors, we want to eat all options here
        self.equipment_id = name
        self.nodeprops = {}
        for k in list(options):
            self.nodeprops[k] = options.pop(k)

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
        # eventname is <modulename> or <modulename>:<parametername>
        self._subscriptions = {}
        self._lock = threading.RLock()

    def broadcast_event(self, msg, reallyall=False):
        """broadcasts a msg to all active connections

        used from the dispatcher"""
        if reallyall:
            listeners = self._connections
        else:
            # all subscribers to module:param
            listeners = self._subscriptions.get(msg[1], set()).copy()
            # all subscribers to module
            module = msg[1].split(':', 1)[0]
            listeners.update(self._subscriptions.get(module, set()))
            # all generic subscribers
            listeners.update(self._active_connections)
        for conn in listeners:
            conn.queue_async_reply(msg)

    def announce_update(self, moduleobj, pname, pobj):
        """called by modules param setters to notify subscribers of new values
        """
        # argument pname is no longer used here - should we remove it?
        msg = (EVENTREPLY, u'%s:%s' % (moduleobj.name, pobj.export),
               [pobj.export_value(), dict(t=pobj.timestamp)])
        self.broadcast_event(msg)

    def announce_update_error(self, moduleobj, pname, pobj, err):
        """called by modules param setters/getters to notify subscribers

        of problems
        """
        # argument pname is no longer used here - should we remove it?
        if not isinstance(err, SECoPError):
            err = InternalError(err)
        msg = (ERRORPREFIX + EVENTREPLY, u'%s:%s' % (moduleobj.name, pobj.export),
               # error-report !
               [err.name, repr(err), dict(t=currenttime())])
        self.broadcast_event(msg)

    def subscribe(self, conn, eventname):
        self._subscriptions.setdefault(eventname, set()).add(conn)

    def unsubscribe(self, conn, eventname):
        if not ':' in eventname:
            # also remove 'more specific' subscriptions
            for k, v in self._subscriptions.items():
                if k.startswith(u'%s:' % eventname):
                    v.discard(conn)
        if eventname in self._subscriptions:
            self._subscriptions[eventname].discard(conn)

    def add_connection(self, conn):
        """registers new connection"""
        self._connections.append(conn)

    def remove_connection(self, conn):
        """removes now longer functional connection"""
        if conn in self._connections:
            self._connections.remove(conn)
        for _evt, conns in list(self._subscriptions.items()):
            conns.discard(conn)
        self._active_connections.discard(conn)

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
        raise NoSuchModuleError(u'Module does not exist on this SEC-Node!')

    def remove_module(self, modulename_or_obj):
        moduleobj = self.get_module(modulename_or_obj)
        modulename = moduleobj.name
        if modulename in self._export:
            self._export.remove(modulename)
        self._modules.pop(modulename)
        self._subscriptions.pop(modulename, None)
        for k in [k for k in self._subscriptions if k.startswith(u'%s:' % modulename)]:
            self._subscriptions.pop(k, None)

    def list_module_names(self):
        # return a copy of our list
        return self._export[:]

    def export_accessibles(self, modulename):
        self.log.debug(u'export_accessibles(%r)' % modulename)
        if modulename in self._export:
            # omit export=False params!
            res = []
            for aobj in self.get_module(modulename).accessibles.values():
                if aobj.export:
                    res.append([aobj.export, aobj.for_export()])
            self.log.debug(u'list accessibles for module %s -> %r' %
                           (modulename, res))
            return res
        self.log.debug(u'-> module is not to be exported!')
        return []

    def get_descriptive_data(self):
        """returns a python object which upon serialisation results in the descriptive data"""
        # XXX: be lazy and cache this?
        # format: {[{[{[, specific entries first
        result = {u'modules': []}
        for modulename in self._export:
            module = self.get_module(modulename)
            if not module.properties.get('export', False):
                continue
            # some of these need rework !
            mod_desc = {u'accessibles': self.export_accessibles(modulename)}
            mod_desc.update(module.exportProperties())
            mod_desc.pop('export', False)
            result[u'modules'].append([modulename, mod_desc])
        result[u'equipment_id'] = self.equipment_id
        result[u'firmware'] = u'FRAPPY - The Python Framework for SECoP'
        result[u'version'] = u'2019.05'
        result.update(self.nodeprops)
        return result

    def _execute_command(self, modulename, exportedname, argument=None):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(u'Module does not exist on this SEC-Node!')

        cmdname = moduleobj.commands.exported.get(exportedname, None)
        if cmdname is None:
            raise NoSuchCommandError(u'Module has no command %r on this SEC-Node!' % exportedname)
        cmdspec = moduleobj.commands[cmdname]
        if argument is None and cmdspec.datatype.argument is not None:
            raise BadValueError(u'Command needs an argument!')

        if argument is not None and cmdspec.datatype.argument is None:
            raise BadValueError(u'Command takes no argument!')

        if cmdspec.datatype.argument:
            # validate!
            argument = cmdspec.datatype(argument)

        # now call func
        # note: exceptions are handled in handle_request, not here!
        func = getattr(moduleobj, u'do_' + cmdname)
        res = func(argument) if argument else func()

        # pipe through cmdspec.datatype.result
        if cmdspec.datatype.result:
            res = cmdspec.datatype.result(res)

        return res, dict(t=currenttime())

    def _setParameterValue(self, modulename, exportedname, value):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(u'Module does not exist on this SEC-Node!')

        pname = moduleobj.parameters.exported.get(exportedname, None)
        if pname is None:
            raise NoSuchParameterError(u'Module has no parameter %r on this SEC-Node!' % exportedname)
        pobj = moduleobj.parameters[pname]
        if pobj.constant is not None:
            raise ReadOnlyError(u'This parameter is constant and can not be accessed remotely.')
        if pobj.readonly:
            raise ReadOnlyError(u'This parameter can not be changed remotely.')

        # validate!
        value = pobj.datatype(value)
        writefunc = getattr(moduleobj, u'write_%s' % pname, None)
        # note: exceptions are handled in handle_request, not here!
        if writefunc:
            # return value is ignored here, as it is automatically set on the pobj and broadcast
            writefunc(value)
        else:
            setattr(moduleobj, pname, value)
        return pobj.export_value(), dict(t=pobj.timestamp) if pobj.timestamp else {}

    def _getParameterValue(self, modulename, exportedname):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(u'Module does not exist on this SEC-Node!')

        pname = moduleobj.parameters.exported.get(exportedname, None)
        if pname is None:
            raise NoSuchParameterError(u'Module has no parameter %r on this SEC-Node!' % exportedname)
        pobj = moduleobj.parameters[pname]
        if pobj.constant is not None:
            # really needed? we could just construct a readreply instead....
            #raise ReadOnlyError(u'This parameter is constant and can not be accessed remotely.')
            return pobj.datatype.export_value(pobj.constant)

        readfunc = getattr(moduleobj, u'read_%s' % pname, None)
        if readfunc:
            # should also update the pobj (via the setter from the metaclass)
            # note: exceptions are handled in handle_request, not here!
            readfunc()
        return pobj.export_value(), dict(t=pobj.timestamp) if pobj.timestamp else {}

    #
    # api to be called from the 'interface'
    # any method above has no idea about 'messages', this is handled here
    #
    def handle_request(self, conn, msg):
        """handles incoming request

        will call 'queue_async_reply(data)' on conn or return reply
        """
        self.log.debug(u'Dispatcher: handling msg: %s' % repr(msg))

        # play thread safe !
        # XXX: ONLY ONE REQUEST (per dispatcher) AT A TIME
        with self._lock:
            action, specifier, data = msg
            # special case for *IDN?
            if action == IDENTREQUEST:
                action, specifier, data = '_ident', None, None

            self.log.debug(u'Looking for handle_%s' % action)
            handler = getattr(self, u'handle_%s' % action, None)

            if handler:
                return handler(conn, specifier, data)
            else:
                raise InternalError('unhandled message!')

    # now the (defined) handlers for the different requests
    def handle_help(self, conn, specifier, data):
        self.log.error('should have been handled in the interface!')

    def handle__ident(self, conn, specifier, data):
        return (IDENTREPLY, None, None)

    def handle_describe(self, conn, specifier, data):
        return (DESCRIPTIONREPLY, '.', self.get_descriptive_data())

    def handle_read(self, conn, specifier, data):
        if data:
            raise ProtocolError('read requests don\'t take data!')
        modulename, pname = specifier, u'value'
        if ':' in specifier:
            modulename, pname = specifier.split(':', 1)
        # XXX: trigger polling and force sending event ???
        return (READREPLY, specifier, list(self._getParameterValue(modulename, pname)))

    def handle_change(self, conn, specifier, data):
        modulename, pname = specifier, u'value'
        if ':' in specifier:
            modulename, pname = specifier.split(u':', 1)
        return (WRITEREPLY, specifier, list(self._setParameterValue(modulename, pname, data)))

    def handle_do(self, conn, specifier, data):
        # XXX: should this be done asyncron? we could just return the reply in
        # that case
        modulename, cmd = specifier.split(u':', 1)
        return (COMMANDREPLY, specifier, list(self._execute_command(modulename, cmd, data)))

    def handle_ping(self, conn, specifier, data):
        if data:
            raise ProtocolError('ping requests don\'t take data!')
        return (HEARTBEATREPLY, specifier, [None, {u't':currenttime()}])

    def handle_activate(self, conn, specifier, data):
        if data:
            raise ProtocolError('activate requests don\'t take data!')
        if specifier:
            modulename, exportedname = specifier, None
            if ':' in specifier:
                modulename, exportedname = specifier.split(u':', 1)
            if modulename not in self._export:
                raise NoSuchModuleError('Module does not exist on this SEC-Node!')
            moduleobj = self.get_module(modulename)
            if exportedname is not None:
                pname = moduleobj.accessiblename2attr.get(exportedname, True)
                if pname and pname not in moduleobj.accessibles:
                    # what if we try to subscribe a command here ???
                    raise NoSuchParameterError('Module has no such parameter on this SEC-Node!')
                modules = [(modulename, pname)]
            else:
                modules = [(modulename, None)]
            # activate only ONE item (module or module:parameter)
            self.subscribe(conn, specifier)
        else:
            # activate all modules
            self._active_connections.add(conn)
            modules = [(m, None) for m in self._export]

        # send updates for all subscribed values.
        # note: The initial poll already happend before the server is active
        for modulename, pname in modules:
            moduleobj = self._modules.get(modulename, None)
            if pname:
                pobj = moduleobj.accessibles[pname]
                updmsg = (EVENTREPLY, u'%s:%s' % (modulename, pobj.export),
                          [pobj.export_value(), dict(t=pobj.timestamp)])
                conn.queue_async_reply(updmsg)
                continue
            for pobj in moduleobj.accessibles.values():
                if not isinstance(pobj, Parameter):
                    continue
                if not pobj.export:
                    continue
                # can not use announce_update here, as this will send to all clients
                updmsg = (EVENTREPLY, u'%s:%s' % (modulename, pobj.export),
                          [pobj.export_value(), dict(t=pobj.timestamp)])
                conn.queue_async_reply(updmsg)
        return (ENABLEEVENTSREPLY, specifier, None) if specifier else (ENABLEEVENTSREPLY, None, None)

    def handle_deactivate(self, conn, specifier, data):
        if data:
            raise ProtocolError('deactivate requests don\'t take data!')
        if specifier:
            self.unsubscribe(conn, specifier)
        else:
            self._active_connections.discard(conn)
            # XXX: also check all entries in self._subscriptions?
        return (DISABLEEVENTSREPLY, None, None)
