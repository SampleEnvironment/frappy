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

import time
import threading

from messages import *
from errors import *
from secop.lib.parsing import format_time
from secop.lib import formatExtendedStack, formatException


class Dispatcher(object):

    def __init__(self, logger, options):
        self.equipment_id = options.pop('equipment_id')
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

    def handle_request(self, conn, msg):
        """handles incoming request

        will call 'queue.request(data)' on conn to send reply before returning
        """
        self.log.debug('Dispatcher: handling msg: %r' % msg)
        # play thread safe !
        with self._lock:
            reply = None
            # generate reply (coded and framed)
            msgname = msg.__class__.__name__
            if msgname.endswith('Request'):
                msgname = msgname[:-len('Request')]
            if msgname.endswith('Message'):
                msgname = msgname[:-len('Message')]
            self.log.debug('Looking for handle_%s' % msgname)
            handler = getattr(self, 'handle_%s' % msgname, None)
            if handler:
                try:
                    reply = handler(conn, msg)
                except SECOPError as err:
                    self.log.exception(err)
                    reply = msg.get_error(
                        errorclass=err.__class__.__name__,
                        errorinfo=[repr(err), str(msg)])
                except (ValueError, TypeError) as err:
                    self.log.exception(err)
                    reply = msg.get_error(
                        errorclass='BadValue',
                        errorinfo=[repr(err), str(msg)])
                except Exception as err:
                    self.log.exception(err)
                    reply = msg.get_error(
                        errorclass='InternalError',
                        errorinfo=[formatException(), str(msg), formatExtendedStack()])
            else:
                self.log.debug('Can not handle msg %r' % msg)
                reply = self.unhandled(conn, msg)
            if reply:
                conn.queue_reply(reply)

    def broadcast_event(self, msg, reallyall=False):
        """broadcasts a msg to all active connections"""
        if reallyall:
            listeners = self._connections
        else:
            if getattr(msg, 'command', None) is None:
                eventname = '%s:%s' % (msg.module, msg.parameter
                                       if msg.parameter else 'value')
            else:
                eventname = '%s:%s()' % (msg.module, msg.command)
            listeners = self._subscriptions.get(eventname, [])
            listeners += list(self._active_connections)
        for conn in listeners:
            conn.queue_async_reply(msg)

    def announce_update(self, moduleobj, pname, pobj):
        """called by modules param setters to notify subscribers of new values
        """
        msg = Value(
            moduleobj.name,
            parameter=pname,
            value=pobj.value,
            t=pobj.timestamp)
        self.broadcast_event(msg)

    def subscribe(self, conn, modulename, pname='value'):
        eventname = '%s:%s' % (modulename, pname)
        self._subscriptions.setdefault(eventname, set()).add(conn)

    def unsubscribe(self, conn, modulename, pname='value'):
        eventname = '%s:%s' % (modulename, pname)
        if eventname in self._subscriptions:
            self._subscriptions.remove(conn)

    def add_connection(self, conn):
        """registers new connection"""
        self._connections.append(conn)

    def remove_connection(self, conn):
        """removes now longer functional connection"""
        if conn in self._connections:
            self._connections.remove(conn)
        for _evt, conns in self._subscriptions.items():
            conns.discard(conn)

    def activate_connection(self, conn):
        self._active_connections.add(conn)

    def deactivate_connection(self, conn):
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
        elif modulename in self._modules.values():
            return modulename
        raise NoSuchModuleError(module=str(modulename))

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

    def list_module_params(self, modulename, only_static=False):
        self.log.debug('list_module_params(%r)' % modulename)
        if modulename in self._export:
            # omit export=False params!
            res = {}
            for paramname, param in self.get_module(modulename).PARAMS.items():
                if param.export:
                    res[paramname] = param.as_dict(only_static)
            self.log.debug('list params for module %s -> %r' %
                           (modulename, res))
            return res
        self.log.debug('-> module is not to be exported!')
        return {}

    def list_module_cmds(self, modulename):
        self.log.debug('list_module_cmds(%r)' % modulename)
        if modulename in self._export:
            # omit export=False params!
            res = {}
            for cmdname, cmdobj in self.get_module(modulename).CMDS.items():
                res[cmdname] = cmdobj.as_dict()
            self.log.debug('list cmds for module %s -> %r' % (modulename, res))
            return res
        self.log.debug('-> module is not to be exported!')
        return {}

    def get_descriptive_data(self):
        """returns a python object which upon serialisation results in the descriptive data"""
        # XXX: be lazy and cache this?
        # format: {[{[{[, specific entries first
        result = {'modules': []}
        for modulename in self._export:
            module = self.get_module(modulename)
            # some of these need rework !
            mod_desc = {'parameters':[], 'commands':[]}
            for pname, param in self.list_module_params(modulename, only_static=True).items():
                mod_desc['parameters'].extend([pname, param])
            for cname, cmd in self.list_module_cmds(modulename).items():
                mod_desc['commands'].extend([cname, cmd])
            for propname, prop in module.PROPERTIES.items():
                mod_desc[propname] = prop
            result['modules'].extend([modulename, mod_desc])
        result['equipment_id'] = self.equipment_id
        result['firmware'] = 'The SECoP playground'
        result['version'] = "2017.07"
        # XXX: what else?
        return result

    def get_descriptive_data_old(self):
        # XXX: be lazy and cache this?
        result = {'modules': {}}
        for modulename in self._export:
            module = self.get_module(modulename)
            # some of these need rework !
            dd = {
                'parameters': self.list_module_params(modulename, only_static=True),
                'commands': self.list_module_cmds(modulename),
                'properties': module.PROPERTIES,
            }
            result['modules'][modulename] = dd
        result['equipment_id'] = self.equipment_id
        result['firmware'] = 'The SECoP playground'
        result['version'] = "2017.01"
        # XXX: what else?
        return result

    def _execute_command(self, modulename, command, arguments=None):
        if arguments is None:
            arguments = []

        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(module=modulename)

        cmdspec = moduleobj.CMDS.get(command, None)
        if cmdspec is None:
            raise NoSuchCommandError(module=modulename, command=command)
        if len(cmdspec.arguments) != len(arguments):
            raise BadValueError(
                module=modulename,
                command=command,
                reason='Wrong number of arguments!')

        # now call func and wrap result as value
        # note: exceptions are handled in handle_request, not here!
        func = getattr(moduleobj, 'do' + command)
        res = func(*arguments)
        res = CommandReply(
            module=modulename,
            command=command,
            result=res,
            qualifiers=dict(t=time.time()))
        # res = Value(modulename, command=command, value=func(*arguments), t=time.time())
        return res

    def _setParamValue(self, modulename, pname, value):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(module=modulename)

        pobj = moduleobj.PARAMS.get(pname, None)
        if pobj is None:
            raise NoSuchParamError(module=modulename, parameter=pname)
        if pobj.readonly:
            raise ReadonlyError(module=modulename, parameter=pname)

        writefunc = getattr(moduleobj, 'write_%s' % pname, None)
        # note: exceptions are handled in handle_request, not here!
        if writefunc:
            value = writefunc(value)
        else:
            setattr(moduleobj, pname, value)
        if pobj.timestamp:
            return WriteReply(
                module=modulename,
                parameter=pname,
                value=[pobj.value, dict(t=format_time(pobj.timestamp))])
        return WriteReply(
            module=modulename, parameter=pname, value=[pobj.value, {}])

    def _getParamValue(self, modulename, pname):
        moduleobj = self.get_module(modulename)
        if moduleobj is None:
            raise NoSuchModuleError(module=modulename)

        pobj = moduleobj.PARAMS.get(pname, None)
        if pobj is None:
            raise NoSuchParamError(module=modulename, parameter=pname)

        readfunc = getattr(moduleobj, 'read_%s' % pname, None)
        if readfunc:
            # should also update the pobj (via the setter from the metaclass)
            # note: exceptions are handled in handle_request, not here!
            readfunc()
        if pobj.timestamp:
            return Value(
                modulename,
                parameter=pname,
                value=pobj.value,
                t=pobj.timestamp)
        return Value(modulename, parameter=pname, value=pobj.value)

    # now the (defined) handlers for the different requests
    def handle_Help(self, conn, msg):
        return HelpMessage()

    def handle_Identify(self, conn, msg):
        return IdentifyReply(version_string='currently,is,ignored,here')

    def handle_Describe(self, conn, msg):
        # XXX:collect descriptive data
        return DescribeReply(
            equipment_id=self.equipment_id,
            description=self.get_descriptive_data())

    def handle_Poll(self, conn, msg):
        # XXX: trigger polling and force sending event
        res = self._getParamValue(msg.module, msg.parameter or 'value')
        # self.broadcast_event(res)
        if conn in self._active_connections:
            return None  # already send to myself
        return res  # send reply to inactive conns

    def handle_Write(self, conn, msg):
        # notify all by sending WriteReply
        #msg1 = WriteReply(**msg.as_dict())
        # self.broadcast_event(msg1)
        # try to actually write  XXX: should this be done asyncron? we could
        # just return the reply in that case
        if msg.parameter:
            res = self._setParamValue(msg.module, msg.parameter, msg.value)
        else:
            # first check if module has a target
            if 'target' not in self.get_module(msg.module).PARAMS:
                raise ReadonlyError(module=msg.module, parameter=None)
            res = self._setParamValue(msg.module, 'target', msg.value)
            res.parameter = 'target'
        # self.broadcast_event(res)
        # if conn in self._active_connections:
        #    return None  # already send to myself
        return res

    def handle_Command(self, conn, msg):
        # notify all by sending CommandReply
        #msg1 = CommandReply(**msg.as_dict())
        # self.broadcast_event(msg1)
        # XXX: should this be done asyncron? we could just return the reply in
        # that case

        # try to actually execute command
        res = self._execute_command(msg.module, msg.command, msg.arguments)
        # self.broadcast_event(res)
        # if conn in self._active_connections:
        #    return None  # already send to myself
        return res  # send reply to inactive conns

    def handle_Heartbeat(self, conn, msg):
        return HeartbeatReply(**msg.as_dict())

    def handle_Activate(self, conn, msg):
        self.activate_connection(conn)
        # easy approach: poll all values...
        for modulename, moduleobj in self._modules.items():
            for pname, pobj in moduleobj.PARAMS.items():
                # WARNING: THIS READS ALL PARAMS FROM HW!
                # XXX: should we send the cached values instead? (pbj.value)
                # also: ignore errors here.
                try:
                    res = self._getParamValue(modulename, pname)
                except SECOPError as e:
                    self.log.error('decide what to do here!')
                    self.log.exception(e)
                    res = Value(
                        module=modulename,
                        parameter=pname,
                        value=pobj.value,
                        t=pobj.timestamp,
                        unit=pobj.unit)
                if res.value != Ellipsis:  # means we do not have a value at all so skip this
                    self.broadcast_event(res)
        conn.queue_async_reply(ActivateReply(**msg.as_dict()))
        return None

    def handle_Deactivate(self, conn, msg):
        self.deactivate_connection(conn)
        conn.queue_async_reply(DeactivateReply(**msg.as_dict()))
        return None

    def handle_Error(self, conn, msg):
        return msg

    def unhandled(self, conn, msg):
        """handler for unhandled Messages

        (no handle_<messagename> method was defined)
        """
        self.log.error('IGN: got unhandled request %s' % msg)
        return msg.get_error(
            errorclass="InternalError", errorinfo="Unhandled Request")
