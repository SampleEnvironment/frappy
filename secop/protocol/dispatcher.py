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
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""Dispatcher for SECoP Messages

Interface to the service offering part:

 - 'handle_request(connectionobj, data)' handles incoming request
   it returns the (sync) reply, and it may call 'send_reply(data)'
   on the connectionobj or on activated connections
 - 'add_connection(connectionobj)' registers new connection
 - 'remove_connection(connectionobj)' removes now longer functional connection

Interface to the modules:
 - add_module(modulename, moduleobj, export=True) registers a new module under the
   given name, may also register it for exporting (making accessible)
 - get_module(modulename) returns the requested module or None
 - remove_module(modulename_or_obj): removes the module (during shutdown)

"""

import threading
from collections import OrderedDict
from time import time as currenttime

from secop.errors import BadValueError, NoSuchCommandError, NoSuchModuleError, \
    NoSuchParameterError, ProtocolError, ReadOnlyError, SECoPServerError
from secop.params import Parameter
from secop.protocol.messages import COMMANDREPLY, DESCRIPTIONREPLY, \
    DISABLEEVENTSREPLY, ENABLEEVENTSREPLY, ERRORPREFIX, EVENTREPLY, \
    HEARTBEATREPLY, IDENTREPLY, IDENTREQUEST, READREPLY, WRITEREPLY


def make_update(modulename, pobj):
    if pobj.readerror:
        return (ERRORPREFIX + EVENTREPLY, '%s:%s' % (modulename, pobj.export),
               # error-report !
               [pobj.readerror.name, repr(pobj.readerror), dict(t=pobj.timestamp)])
    return (EVENTREPLY, '%s:%s' % (modulename, pobj.export),
               [pobj.export_value(), dict(t=pobj.timestamp)])


class Dispatcher:

    def __init__(self, name, logger, options, srv):
        # to avoid errors, we want to eat all options here
        self.equipment_id = options.pop('id', name)
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
        self.restart = srv.restart

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
            conn.send_reply(msg)

    def announce_update(self, modulename, pname, pobj):
        """called by modules param setters to notify subscribers of new values
        """
        self.broadcast_event(make_update(modulename, pobj))

    def subscribe(self, conn, eventname):
        self._subscriptions.setdefault(eventname, set()).add(conn)

    def unsubscribe(self, conn, eventname):
        if not ':' in eventname:
            # also remove 'more specific' subscriptions
            for k, v in self._subscriptions.items():
                if k.startswith('%s:' % eventname):
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
        self.log.debug('registering module %r as %s (export=%r)' %
                       (moduleobj, modulename, export))
        self._modules[modulename] = moduleobj
        if export:
            self._export.append(modulename)

    def get_module(self, modulename):
        if modulename in self._modules:
            return self._modules[modulename]
        if modulename in list(self._modules.values()):
            return modulename
        raise NoSuchModuleError('Module %r does not exist on this SEC-Node!' % modulename)

    def remove_module(self, modulename_or_obj):
        moduleobj = self.get_module(modulename_or_obj)
        modulename = moduleobj.name
        if modulename in self._export:
            self._export.remove(modulename)
        self._modules.pop(modulename)
        self._subscriptions.pop(modulename, None)
        for k in [kk for kk in self._subscriptions if kk.startswith('%s:' % modulename)]:
            self._subscriptions.pop(k, None)

    def list_module_names(self):
        # return a copy of our list
        return self._export[:]

    def export_accessibles(self, modulename):
        self.log.debug('export_accessibles(%r)' % modulename)
        if modulename in self._export:
            # omit export=False params!
            res = OrderedDict()
            for aobj in self.get_module(modulename).accessibles.values():
                if aobj.export:
                    res[aobj.export] = aobj.for_export()
            self.log.debug('list accessibles for module %s -> %r' %
                           (modulename, res))
            return res
        self.log.debug('-> module is not to be exported!')
        return OrderedDict()

    def get_descriptive_data(self):
        """returns a python object which upon serialisation results in the descriptive data"""
        # XXX: be lazy and cache this?
        result = {'modules': OrderedDict()}
        for modulename in self._export:
            module = self.get_module(modulename)
            if not module.properties.get('export', False):
                continue
            # some of these need rework !
            mod_desc = {'accessibles': self.export_accessibles(modulename)}
            mod_desc.update(module.exportProperties())
            mod_desc.pop('export', False)
            result['modules'][modulename] = mod_desc
        result['equipment_id'] = self.equipment_id
        result['firmware'] = 'FRAPPY - The Python Framework for SECoP'
        result['version'] = '2019.08'
        result.update(self.nodeprops)
        return result

    def _execute_command(self, modulename, exportedname, argument=None):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError('Module %r does not exist' % modulename)

        cmdname = moduleobj.commands.exported.get(exportedname, None)
        if cmdname is None:
            raise NoSuchCommandError('Module %r has no command %r' % (modulename, exportedname))
        cmdspec = moduleobj.commands[cmdname]
        if argument is None and cmdspec.datatype.argument is not None:
            raise BadValueError("Command '%s:%s' needs an argument" % (modulename, cmdname))

        if argument is not None and cmdspec.datatype.argument is None:
            raise BadValueError("Command '%s:%s' takes no argument" % (modulename, cmdname))

        if cmdspec.datatype.argument:
            # validate!
            argument = cmdspec.datatype(argument)

        # now call func
        # note: exceptions are handled in handle_request, not here!
        func = getattr(moduleobj, 'do_' + cmdname)
        res = func() if argument is None else func(argument)

        # pipe through cmdspec.datatype.result
        if cmdspec.datatype.result:
            res = cmdspec.datatype.result(res)

        return res, dict(t=currenttime())

    def _setParameterValue(self, modulename, exportedname, value):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError('Module %r does not exist' % modulename)

        pname = moduleobj.parameters.exported.get(exportedname, None)
        if pname is None:
            raise NoSuchParameterError('Module %r has no parameter %r' % (modulename, exportedname))
        pobj = moduleobj.parameters[pname]
        if pobj.constant is not None:
            raise ReadOnlyError("Parameter %s:%s is constant and can not be changed remotely"
                                % (modulename, pname))
        if pobj.readonly:
            raise ReadOnlyError("Parameter %s:%s can not be changed remotely"
                                % (modulename, pname))

        # validate!
        value = pobj.datatype(value)
        writefunc = getattr(moduleobj, 'write_%s' % pname, None)
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
            raise NoSuchModuleError('Module %r does not exist' % modulename)

        pname = moduleobj.parameters.exported.get(exportedname, None)
        if pname is None:
            raise NoSuchParameterError('Module %r has no parameter %r' % (modulename, exportedname))
        pobj = moduleobj.parameters[pname]
        if pobj.constant is not None:
            # really needed? we could just construct a readreply instead....
            # raise ReadOnlyError('This parameter is constant and can not be accessed remotely.')
            return pobj.datatype.export_value(pobj.constant)

        readfunc = getattr(moduleobj, 'read_%s' % pname, None)
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

        will return return reply, may send replies to conn or
        activated connections in addition
        """
        self.log.debug('Dispatcher: handling msg: %s' % repr(msg))

        # play thread safe !
        # XXX: ONLY ONE REQUEST (per dispatcher) AT A TIME
        with self._lock:
            action, specifier, data = msg
            # special case for *IDN?
            if action == IDENTREQUEST:
                action, specifier, data = '_ident', None, None

            self.log.debug('Looking for handle_%s' % action)
            handler = getattr(self, 'handle_%s' % action, None)

            if handler:
                return handler(conn, specifier, data)
            raise SECoPServerError('unhandled message: %s' % repr(msg))

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
        modulename, pname = specifier, 'value'
        if ':' in specifier:
            modulename, pname = specifier.split(':', 1)
        # XXX: trigger polling and force sending event ???
        return (READREPLY, specifier, list(self._getParameterValue(modulename, pname)))

    def handle_change(self, conn, specifier, data):
        modulename, pname = specifier, 'target'
        if ':' in specifier:
            modulename, pname = specifier.split(':', 1)
        return (WRITEREPLY, specifier, list(self._setParameterValue(modulename, pname, data)))

    def handle_do(self, conn, specifier, data):
        # XXX: should this be done asyncron? we could just return the reply in
        # that case
        modulename, cmd = specifier.split(':', 1)
        return (COMMANDREPLY, specifier, list(self._execute_command(modulename, cmd, data)))

    def handle_ping(self, conn, specifier, data):
        if data:
            raise ProtocolError('ping requests don\'t take data!')
        return (HEARTBEATREPLY, specifier, [None, {'t':currenttime()}])

    def handle_activate(self, conn, specifier, data):
        if data:
            raise ProtocolError('activate requests don\'t take data!')
        if specifier:
            modulename, exportedname = specifier, None
            if ':' in specifier:
                modulename, exportedname = specifier.split(':', 1)
            if modulename not in self._export:
                raise NoSuchModuleError('Module %r does not exist' % modulename)
            moduleobj = self.get_module(modulename)
            if exportedname is not None:
                pname = moduleobj.accessiblename2attr.get(exportedname, True)
                if pname and pname not in moduleobj.accessibles:
                    # what if we try to subscribe a command here ???
                    raise NoSuchParameterError('Module %r has no parameter %r' % (modulename, pname))
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
                conn.send_reply(make_update(modulename, moduleobj.parameters[pname]))
                continue
            for pobj in moduleobj.accessibles.values():
                if isinstance(pobj, Parameter) and pobj.export:
                    conn.send_reply(make_update(modulename, pobj))
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
