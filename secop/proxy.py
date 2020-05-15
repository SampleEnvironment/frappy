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
"""SECoP proxy modules"""

from secop.params import Parameter, Command
from secop.modules import Module, Writable, Readable, Drivable
from secop.datatypes import StringType
from secop.properties import Property
from secop.stringio import HasIodev
from secop.lib import get_class
from secop.client import SecopClient, decode_msg, encode_msg_frame
from secop.errors import ConfigError, make_secop_error, CommunicationFailedError


class ProxyModule(HasIodev, Module):
    properties = {
        'module':
            Property('remote module name', datatype=StringType(), default=''),
    }

    pollerClass = None
    _consistency_check_done = False
    _secnode = None

    def iodevClass(self, name, logger, opts, srv):
        opts['description'] = 'secnode %s on %s' % (opts.get('module', name), opts['uri'])
        return SecNode(name, logger, opts, srv)

    def updateEvent(self, module, parameter, value, timestamp, readerror):
        if parameter not in self.parameters:
            return  # ignore unknown parameters
        # should be done here: deal with clock differences
        if readerror:
            readerror = make_secop_error(*readerror)
        self.announceUpdate(parameter, value, readerror, timestamp)

    def initModule(self):
        if not self.module:
            self.properties['module'] = self.name
        self._secnode = self._iodev.secnode
        self._secnode.register_callback(self.module, self.updateEvent,
                                        self.descriptiveDataChange, self.nodeStateChange)
        super().initModule()

    def descriptiveDataChange(self, module, moddesc):
        if module is None:
            return  # do not care about the node for now
        self._check_descriptive_data()

    def _check_descriptive_data(self):
        params = self.parameters.copy()
        cmds = self.commands.copy()
        moddesc = self._secnode.modules[self.module]
        remoteparams = moddesc['parameters'].copy()
        remotecmds = moddesc['commands'].copy()
        while params:
            pname, pobj = params.popitem()
            props = remoteparams.get(pname, None)
            if props is None:
                self.log.warning('remote parameter %s:%s does not exist' % (self.module, pname))
                continue
            dt = props['datatype']
            try:
                if pobj.readonly:
                    dt.compatible(pobj.datatype)
                else:
                    if props['readonly']:
                        self.log.warning('remote parameter %s:%s is read only' % (self.module, pname))
                    pobj.datatype.compatible(dt)
                    try:
                        dt.compatible(pobj.datatype)
                    except Exception:
                        self.log.warning('remote parameter %s:%s is not fully compatible: %r != %r'
                                           % (self.module, pname, pobj.datatype, dt))
            except Exception:
                self.log.warning('remote parameter %s:%s has an incompatible datatype: %r != %r'
                                   % (self.module, pname, pobj.datatype, dt))
        while cmds:
            cname, cobj = cmds.popitem()
            props = remotecmds.get(cname)
            if props is None:
                self.log.warning('remote command %s:%s does not exist' % (self.module, cname))
                continue
            dt = props['datatype']
            try:
                cobj.datatype.compatible(dt)
            except Exception:
                self.log.warning('remote command %s:%s is not compatible: %r != %r'
                                 % (self.module, pname, pobj.datatype, dt))
        # what to do if descriptive data does not match?
        # we might raise an exception, but this would lead to a reconnection,
        # which might not help.
        # for now, the error message must be enough

    def nodeStateChange(self, online, state):
        if online:
            if not self._consistency_check_done:
                self._check_descriptive_data()
                self._consistency_check_done = True
        else:
            newstatus = Readable.Status.ERROR, 'disconnected'
            readerror = CommunicationFailedError('disconnected')
            if self.status != newstatus:
                for pname in set(self.parameters) - set(('module', 'status')):
                    self.announceUpdate(pname, None, readerror)
                self.announceUpdate('status', newstatus)


class ProxyReadable(ProxyModule, Readable):
    pass


class ProxyWritable(ProxyModule, Writable):
    pass


class ProxyDrivable(ProxyModule, Drivable):
    pass


PROXY_CLASSES = [ProxyDrivable, ProxyWritable, ProxyReadable, ProxyModule]


class SecNode(Module):
    properties = {
        'uri':
            Property('uri of a SEC node', datatype=StringType()),
    }
    commands = {
        'request':
            Command('send a request', argument=StringType(), result=StringType())
    }

    def earlyInit(self):
        self.secnode = SecopClient(self.uri, self.log)

    def startModule(self, started_callback):
        self.secnode.spawn_connect(started_callback)

    def do_request(self, msg):
        """for test purposes"""
        reply = self.secnode.request(*decode_msg(msg.encode('utf-8')))
        return encode_msg_frame(*reply).decode('utf-8')


def proxy_class(remote_class, name=None):
    """create a proxy class based on the definition of remote class

    remote class is <import path>.<class name> of a class used on the remote node
    if name is not given, 'Proxy' + <class name> is used
    """
    if isinstance(remote_class, type) and issubclass(remote_class, Module):
        rcls = remote_class
        remote_class = rcls.__name__
    else:
        rcls = get_class(remote_class)
    if name is None:
        name = rcls.__name__

    for proxycls in PROXY_CLASSES:
        if issubclass(rcls, proxycls.__bases__[-1]):
            # avoid 'should not be redefined' warning
            proxycls.accessibles = {}
            break
    else:
        raise ConfigError('%r is no SECoP module class' % remote_class)

    parameters = {}
    commands = {}
    attrs = dict(parameters=parameters, commands=commands, properties=rcls.properties)

    for aname, aobj in rcls.accessibles.items():
        if isinstance(aobj, Parameter):
            pobj = aobj.copy()
            parameters[aname] = pobj
            pobj.properties['poll'] = False
            pobj.properties['handler'] = None
            pobj.properties['needscfg'] = False

            def rfunc(self, pname=aname):
                value, _, readerror = self._secnode.getParameter(self.name, pname)
                if readerror:
                    raise readerror
                return value

            attrs['read_' + aname] = rfunc

            if not pobj.readonly:

                def wfunc(self, value, pname=aname):
                    value, _, readerror = self._secnode.setParameter(self.name, pname, value)
                    if readerror:
                        raise make_secop_error(*readerror)
                    return value

                attrs['write_' + aname] = wfunc

        elif isinstance(aobj, Command):
            cobj = aobj.copy()
            commands[aname] = cobj

            def cfunc(self, arg=None, cname=aname):
                return self._secnode.execCommand(self.name, cname, arg)

            attrs['do_' + aname] = cfunc

        else:
            raise ConfigError('do not now about %r in %s.accessibles' % (aobj, remote_class))

    return type(name, (proxycls,), attrs)


def Proxy(name, logger, cfgdict, srv):
    """create a Proxy object based on remote_class

    title cased as it acts like a class
    """
    remote_class = cfgdict.pop('remote_class')
    if 'description' not in cfgdict:
        cfgdict['description'] = 'remote module %s on %s' % (
            cfgdict.get('module', name), cfgdict.get('iodev', '?'))
    return proxy_class(remote_class)(name, logger, cfgdict, srv)
