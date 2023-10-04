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

from frappy.client import SecopClient, decode_msg, encode_msg_frame
from frappy.datatypes import StringType
from frappy.errors import BadValueError, CommunicationFailedError, ConfigError
from frappy.lib import get_class
from frappy.modules import Drivable, Module, Readable, Writable
from frappy.params import Command, Parameter
from frappy.properties import Property
from frappy.io import HasIO


class ProxyModule(HasIO, Module):
    module = Property('remote module name', datatype=StringType(), default='')
    status = Parameter('connection status', Readable.status.datatype)  # add status even when not a Readable

    _consistency_check_done = False
    _secnode = None
    enablePoll = False

    def ioClass(self, name, logger, opts, srv):
        opts['description'] = f"secnode {opts.get('module', name)} on {opts['uri']}"
        return SecNode(name, logger, opts, srv)

    def updateEvent(self, module, parameter, value, timestamp, readerror):
        if parameter not in self.parameters:
            return  # ignore unknown parameters
        # should be done here: deal with clock differences
        self.announceUpdate(parameter, value, readerror, timestamp)

    def initModule(self):
        if not self.module:
            self.module = self.name
        self._secnode = self.io.secnode
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
                if pobj.export:
                    self.log.warning('remote parameter %s:%s does not exist', self.module, pname)
                continue
            dt = props['datatype']
            try:
                if pobj.readonly:
                    dt.compatible(pobj.datatype)
                else:
                    if props['readonly']:
                        self.log.warning('remote parameter %s:%s is read only', self.module, pname)
                    pobj.datatype.compatible(dt)
                    try:
                        dt.compatible(pobj.datatype)
                    except Exception:
                        self.log.warning('remote parameter %s:%s is not fully compatible: %r != %r',
                                         self.module, pname, pobj.datatype, dt)
            except Exception:
                self.log.warning('remote parameter %s:%s has an incompatible datatype: %r != %r',
                                 self.module, pname, pobj.datatype, dt)
        while cmds:
            cname, cobj = cmds.popitem()
            props = remotecmds.get(cname)
            if props is None:
                self.log.warning('remote command %s:%s does not exist', self.module, cname)
                continue
            dt = props['datatype']
            try:
                cobj.datatype.compatible(dt)
            except BadValueError:
                self.log.warning('remote command %s:%s is not compatible: %r != %r',
                                 self.module, cname, cobj.datatype, dt)
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

    def checkProperties(self):
        pass  # skip


class ProxyReadable(ProxyModule, Readable):
    pass


class ProxyWritable(ProxyModule, Writable):
    pass


class ProxyDrivable(ProxyModule, Drivable):
    pass


PROXY_CLASSES = [ProxyDrivable, ProxyWritable, ProxyReadable, ProxyModule]


class SecNode(Module):
    uri = Property('uri of a SEC node', datatype=StringType())

    def earlyInit(self):
        super().earlyInit()
        self.secnode = SecopClient(self.uri, self.log)

    def startModule(self, start_events):
        super().startModule(start_events)
        self.secnode.spawn_connect(start_events.get_trigger())

    @Command(StringType(), result=StringType())
    def request(self, msg):
        """send a request, for debugging purposes"""
        reply = self.secnode.request(*decode_msg(msg.encode('utf-8')))
        # pylint: disable=not-an-iterable
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
        raise ConfigError(f'{remote_class!r} is no SECoP module class')

    attrs = rcls.propertyDict.copy()

    for aname, aobj in rcls.accessibles.items():
        if isinstance(aobj, Parameter):
            pobj = aobj.copy()
            # we have to set own properties of pobj to the inherited ones
            # this matters for the ProxyModule.status datatype, which should be
            # overidden by the remote class status datatype
            pobj.ownProperties = pobj.propertyValues
            pobj.merge({'needscfg': False})
            attrs[aname] = pobj

            def rfunc(self, pname=aname):
                value, _, readerror = self._secnode.getParameter(self.name, pname, True)
                if readerror:
                    raise readerror
                return value

            attrs['read_' + aname] = rfunc

            if not pobj.readonly:

                def wfunc(self, value, pname=aname):
                    value, _, readerror = self._secnode.setParameter(self.name, pname, value)
                    if readerror:
                        raise readerror
                    return value

                attrs['write_' + aname] = wfunc

        elif isinstance(aobj, Command):
            cobj = aobj.copy()

            def cfunc(self, arg=None, cname=aname):
                return self._secnode.execCommand(self.name, cname, arg)[0]

            attrs[aname] = cobj(cfunc)

        else:
            raise ConfigError(f'do not now about {aobj!r} in {remote_class}.accessibles')

    return type(name+"_", (proxycls,), attrs)


def Proxy(name, logger, cfgdict, srv):
    """create a Proxy object based on remote_class

    title cased as it acts like a class
    """
    remote_class = cfgdict.pop('remote_class')
    if isinstance(remote_class, dict):
        remote_class = remote_class['value']

    if 'description' not in cfgdict:
        cfgdict['description'] = f"remote module {cfgdict.get('module', name)} on {cfgdict.get('io', {'value:': '?'})['value']}"

    return proxy_class(remote_class)(name, logger, cfgdict, srv)
