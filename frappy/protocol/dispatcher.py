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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
"""Dispatcher for SECoP Messages

Interface to the service offering part:

 - 'handle_request(connectionobj, data)' handles incoming request
   it returns the (sync) reply, and it may call 'send_reply(data)'
   on the connectionobj or on activated connections
 - 'add_connection(connectionobj)' registers new connection
 - 'remove_connection(connectionobj)' removes now longer functional connection
"""

import threading
from time import time as currenttime

from frappy.errors import NoSuchCommandError, NoSuchModuleError, \
    NoSuchParameterError, ProtocolError, ReadOnlyError
from frappy.params import Parameter
from frappy.protocol.messages import COMMANDREPLY, DESCRIPTIONREPLY, \
    DISABLEEVENTSREPLY, ENABLEEVENTSREPLY, ERRORPREFIX, EVENTREPLY, \
    HEARTBEATREPLY, IDENTREPLY, IDENTREQUEST, LOG_EVENT, LOGGING_REPLY, \
    READREPLY, WRITEREPLY


def make_update(modulename, pobj):
    if pobj.readerror:
        return (ERRORPREFIX + EVENTREPLY, f'{modulename}:{pobj.export}',
                # error-report !
                [pobj.readerror.name, str(pobj.readerror), {'t': pobj.timestamp}])
    return (EVENTREPLY, f'{modulename}:{pobj.export}',
            [pobj.export_value(), {'t': pobj.timestamp}])


class Dispatcher:
    def __init__(self, name, logger, options, srv):
        # to avoid errors, we want to eat all options here
        self.equipment_id = options.pop('equipment_id', name)
        self.nodeprops = {}
        for k in list(options):
            self.nodeprops[k] = options.pop(k)

        self.log = logger
        self.secnode = srv.secnode
        # list all connections
        self._connections = []
        # active (i.e. broadcast-receiving) connections
        self._active_connections = set()
        # map eventname -> list of subscribed connections
        # eventname is <modulename> or <modulename>:<parametername>
        self._subscriptions = {}
        self._lock = threading.RLock()
        self.name = name
        self.restart = srv.restart
        self.shutdown = srv.shutdown
        # handle to server
        self.srv = srv

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
        if ':' not in eventname:
            # also remove 'more specific' subscriptions
            for k, v in self._subscriptions.items():
                if k.startswith(f'{eventname}:'):
                    v.discard(conn)
        if eventname in self._subscriptions:
            self._subscriptions[eventname].discard(conn)

    def add_connection(self, conn):
        """registers new connection"""
        self._connections.append(conn)

    def reset_connection(self, conn):
        """remove all subscriptions for a connection

        to be called on the identification message
        """
        for _evt, conns in list(self._subscriptions.items()):
            conns.discard(conn)
        self.set_all_log_levels(conn, 'off')
        self._active_connections.discard(conn)

    def remove_connection(self, conn):
        """removes now longer functional connection"""
        if conn in self._connections:
            self._connections.remove(conn)
        self.reset_connection(conn)

    def _execute_command(self, modulename, exportedname, argument=None):
        """ Execute a command. Importing the value is done in 'do' for nicer
        error messages."""
        moduleobj = self.secnode.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(f'Module {modulename!r} does not exist')

        cname = moduleobj.accessiblename2attr.get(exportedname)
        cobj = moduleobj.commands.get(cname)
        if cobj is None:
            raise NoSuchCommandError(f'Module {modulename!r} has no command {cname or exportedname!r}')
        # now call func
        # note: exceptions are handled in handle_request, not here!
        result = cobj.do(moduleobj, argument)
        if cobj.result:
            result = cobj.result.export_value(result)
        return result, {'t': currenttime()}

    def _setParameterValue(self, modulename, exportedname, value):
        moduleobj = self.secnode.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(f'Module {modulename!r} does not exist')

        pname = moduleobj.accessiblename2attr.get(exportedname)
        pobj = moduleobj.parameters.get(pname)
        if pobj is None:
            raise NoSuchParameterError(f'Module {modulename!r} has no parameter {pname or exportedname!r}')
        if pobj.constant is not None:
            raise ReadOnlyError(f"Parameter {modulename}:{pname} is constant and can not be changed remotely")
        if pobj.readonly:
            raise ReadOnlyError(f"Parameter {modulename}:{pname} can not be changed remotely")

        # validate!
        value = pobj.datatype.validate(value, previous=pobj.value)
        # note: exceptions are handled in handle_request, not here!
        getattr(moduleobj, 'write_' + pname)(value)
        # return value is ignored here, as already handled
        return pobj.export_value(), {'t': pobj.timestamp} if pobj.timestamp else {}

    def _getParameterValue(self, modulename, exportedname):
        moduleobj = self.secnode.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(f'Module {modulename!r} does not exist')

        pname = moduleobj.accessiblename2attr.get(exportedname)
        pobj = moduleobj.parameters.get(pname)
        if pobj is None:
            raise NoSuchParameterError(f'Module {modulename!r} has no parameter {pname or exportedname!r}')
        if pobj.constant is not None:
            # really needed? we could just construct a readreply instead....
            # raise ReadOnlyError('This parameter is constant and can not be accessed remotely.')
            return pobj.datatype.export_value(pobj.constant)

        # note: exceptions are handled in handle_request, not here!
        getattr(moduleobj, 'read_' + pname)()
        # return value is ignored here, as already handled
        return pobj.export_value(), {'t': pobj.timestamp} if pobj.timestamp else {}

    #
    # api to be called from the 'interface'
    # any method above has no idea about 'messages', this is handled here
    #
    def handle_request(self, conn, msg):
        """handles incoming request

        will return return reply, may send replies to conn or
        activated connections in addition
        """
        self.log.debug('Dispatcher: handling msg: %s', repr(msg))

        # play thread safe !
        # XXX: ONLY ONE REQUEST (per dispatcher) AT A TIME
        with self._lock:
            action, specifier, data = msg
            # special case for *IDN?
            if action == IDENTREQUEST:
                action, specifier, data = '_ident', None, None

            self.log.debug('Looking for handle_%s', action)
            handler = getattr(self, f'handle_{action}', None)

            if handler:
                return handler(conn, specifier, data)
            raise ProtocolError(f'unhandled message: {repr(msg)}')

    # now the (defined) handlers for the different requests
    def handle_help(self, conn, specifier, data):
        self.log.error('should have been handled in the interface!')

    def handle__ident(self, conn, specifier, data):
        # Remark: the following line is needed due to issue 66.
        self.reset_connection(conn)
        # The other stuff in issue 66 ('error_closed' message), has to be implemented
        # if and when frappy will support serial server connections
        return (IDENTREPLY, None, None)

    def handle_describe(self, conn, specifier, data):
        return (DESCRIPTIONREPLY, specifier or '.', self.secnode.get_descriptive_data(specifier))

    def handle_read(self, conn, specifier, data):
        if data:
            raise ProtocolError('read requests don\'t take data!')
        if not specifier:
            raise ProtocolError('read requests need a specifier!')
        modulename, pname = specifier, 'value'
        if ':' in specifier:
            modulename, pname = specifier.split(':', 1)
        # XXX: trigger polling and force sending event ???
        return (READREPLY, specifier, list(self._getParameterValue(modulename, pname)))

    def handle_change(self, conn, specifier, data):
        if not specifier:
            raise ProtocolError('change requests need a specifier!')
        modulename, pname = specifier, 'target'
        if ':' in specifier:
            modulename, pname = specifier.split(':', 1)
        return (WRITEREPLY, specifier, list(self._setParameterValue(modulename, pname, data)))

    def handle_do(self, conn, specifier, data):
        if not specifier:
            raise ProtocolError('do requests need a specifier!')
        modulename, cmd = specifier.split(':', 1)
        return (COMMANDREPLY, specifier, list(self._execute_command(modulename, cmd, data)))

    def handle_ping(self, conn, specifier, data):
        if data:
            raise ProtocolError('ping requests don\'t take data!')
        return (HEARTBEATREPLY, specifier, [None, {'t': currenttime()}])

    def handle_activate(self, conn, specifier, data):
        if data:
            raise ProtocolError('activate requests don\'t take data!')
        if specifier:
            modulename, exportedname = specifier, None
            if ':' in specifier:
                modulename, exportedname = specifier.split(':', 1)
            if modulename not in self.secnode.export:
                raise NoSuchModuleError(f'Module {modulename!r} does not exist')
            moduleobj = self.secnode.get_module(modulename)
            if exportedname is not None:
                pname = moduleobj.accessiblename2attr.get(exportedname, True)
                if pname and pname not in moduleobj.accessibles:
                    # what if we try to subscribe a command here ???
                    raise NoSuchParameterError(f'Module {modulename!r} has no parameter {pname!r}')
                modules = [(modulename, pname)]
            else:
                modules = [(modulename, None)]
            # activate only ONE item (module or module:parameter)
            self.subscribe(conn, specifier)
        else:
            # activate all modules
            self._active_connections.add(conn)
            modules = [(m, None) for m in self.secnode.export]

        # send updates for all subscribed values.
        # note: The initial poll already happend before the server is active
        for modulename, pname in modules:
            moduleobj = self.secnode.modules.get(modulename, None)
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

    def send_log_msg(self, conn, modname, level, msg):
        """send log message """
        conn.send_reply((LOG_EVENT, f'{modname}:{level}', msg))

    def set_all_log_levels(self, conn, level):
        for modobj in self.secnode.modules.values():
            modobj.setRemoteLogging(conn, level, self.send_log_msg)

    def handle_logging(self, conn, specifier, level):
        if specifier and specifier != '.':
            modobj = self.secnode.modules[specifier]
            modobj.setRemoteLogging(conn, level, self.send_log_msg)
        else:
            self.set_all_log_levels(conn, level)
        return LOGGING_REPLY, specifier, level
