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
"""Secop Router

this is a replacement for the standard dispatcher, with the
additional functionality of routing message from/to several other SEC nodes

simplifications:
- module wise activation not supported
- on connection, the description from all nodes are cached and all nodes are activated
- on 'describe' and on 'activate', cached values are returned
- ping is not forwarded
- what to do on a change of descriptive data is not yet implemented
"""

import time

import frappy.client
import frappy.errors
import frappy.protocol.dispatcher
from frappy.lib.multievent import MultiEvent
from frappy.protocol.messages import COMMANDREQUEST, DESCRIPTIONREPLY, \
    ENABLEEVENTSREPLY, ERRORPREFIX, EVENTREPLY, READREQUEST, WRITEREQUEST


class SecopClient(frappy.client.SecopClient):
    disconnectedExc = frappy.errors.CommunicationFailedError('remote SEC node disconnected')
    disconnectedError = (disconnectedExc.name, str(disconnectedExc))

    def __init__(self, uri, log, dispatcher):
        self.dispatcher = dispatcher
        super().__init__(uri, log)

    def internalize_name(self, name):
        """do not modify names"""
        return name

    def updateEvent(self, module, parameter, value, timestamp, readerror):
        specifier = '%s:%s' % (module, parameter)
        if readerror:
            msg = ERRORPREFIX + EVENTREPLY, specifier, (readerror.name, str(readerror), dict(t=timestamp))
        else:
            msg = EVENTREPLY, specifier, (value, dict(t=timestamp))
        self.dispatcher.broadcast_event(msg)

    def nodeStateChange(self, online, state):
        t = time.time()
        if not online:
            for key, (value, _, readerror) in self.cache.items():
                if not readerror:
                    self.cache[key] = value, t, self.disconnectedExc
                    self.updateEvent(*key, *self.cache[key])

    def descriptiveDataChange(self, module, data):
        if module is None:
            self.dispatcher.restart()
            self._shutdown = True
            raise frappy.errors.SECoPError('descriptive data for node %r has changed' % self.nodename)


class Router(frappy.protocol.dispatcher.Dispatcher):
    singlenode = None

    def __init__(self, name, logger, options, srv):
        """initialize router

        Use the option node = <uri> for a single node or
        nodes = ["<uri1>", "<uri2>" ...] for multiple nodes.
        If a single node is given, the node properties are forwarded transparently,
        else the description property is a merge from all client node properties.
        """
        uri = options.pop('node', None)
        uris = options.pop('nodes', None)
        if uri and uris:
            raise frappy.errors.ConfigError('can not specify node _and_ nodes')
        super().__init__(name, logger, options, srv)
        if uri:
            self.nodes = [SecopClient(uri, logger.getChild('routed'), self)]
            self.singlenode = self.nodes[0]
        else:
            self.nodes = [SecopClient(uri, logger.getChild('routed%d' % i), self) for i, uri in enumerate(uris)]
        # register callbacks
        for node in self.nodes:
            node.register_callback(None, node.updateEvent, node.descriptiveDataChange, node.nodeStateChange)

        self.restart = srv.restart
        self.node_by_module = {}
        multievent = MultiEvent()
        for node in self.nodes:
            node.spawn_connect(multievent.new().set)
        multievent.wait(10)  # wait for all nodes started
        nodes = []
        for node in self.nodes:
            if node.online:
                for module in node.modules:
                    self.node_by_module[module] = node
                nodes.append(node)
            else:

                def nodeStateChange(online, state, self=self, node=node):
                    if online:
                        for module in node.modules:
                            self.node_by_module[module] = node
                        self.nodes.append(node)
                        self.restart()
                        return frappy.client.UNREGISTER
                    return None

                node.register_callback(None, nodeStateChange)
                logger.warning('can not connect to node %r', node.nodename)

    def handle_describe(self, conn, specifier, data):
        if self.singlenode:
            return DESCRIPTIONREPLY, specifier, self.singlenode.descriptive_data
        reply = super().handle_describe(conn, specifier, data)
        result = reply[2]
        allmodules = result.get('modules', {})
        node_description = [result['description']]
        for node in self.nodes:
            data = node.descriptive_data.copy()
            modules = data.pop('modules')
            equipment_id = data.pop('equipment_id', 'unknown')
            node_description.append('--- %s ---\n%s' % (equipment_id, data.pop('description', '')))
            node_description.append('\n'.join('%s: %r' % kv for kv in data.items()))
            for modname, moddesc in modules.items():
                if modname in allmodules:
                    self.log.info('module %r is already present', modname)
                else:
                    allmodules[modname] = moddesc
        result['modules'] = allmodules
        result['description'] = '\n\n'.join(node_description)
        return DESCRIPTIONREPLY, specifier, result

    def handle_activate(self, conn, specifier, data):
        super().handle_activate(conn, specifier, data)
        for node in self.nodes:
            for (module, parameter), (value, t, readerror) in node.cache.items():
                spec = '%s:%s' % (module, parameter)
                if readerror:
                    reply = ERRORPREFIX + EVENTREPLY, spec, (readerror.name, str(readerror), dict(t=t))
                else:
                    datatype = node.modules[module]['parameters'][parameter]['datatype']
                    reply = EVENTREPLY, spec, [datatype.export_value(value), dict(t=t)]
                self.broadcast_event(reply)
        return ENABLEEVENTSREPLY, None, None

    def handle_deactivate(self, conn, specifier, data):
        if specifier:
            raise frappy.errors.NotImplementedError('module wise activation not implemented')
        super().handle_deactivate(conn, specifier, data)

    def handle_read(self, conn, specifier, data):
        module = specifier.split(':')[0]
        if module in self._modules:
            return super().handle_read(conn, specifier, data)
        node = self.node_by_module[module]
        if node.online:
            return node.request(READREQUEST, specifier, data)
        return ERRORPREFIX + READREQUEST, specifier, SecopClient.disconnectedError + (dict(t=node.disconnect_time),)

    def handle_change(self, conn, specifier, data):
        module = specifier.split(':')[0]
        if module in self._modules:
            return super().handle_change(conn, specifier, data)
        return self.node_by_module[module].request(WRITEREQUEST, specifier, data)

    def handle_do(self, conn, specifier, data):
        module = specifier.split(':')[0]
        if module in self._modules:
            return super().handle_do(conn, specifier, data)
        return self.node_by_module[module].request(COMMANDREQUEST, specifier, data)
