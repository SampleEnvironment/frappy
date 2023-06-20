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
"""convenience class to create a struct Parameter together with indivdual params

Usage:

    class Controller(Drivable):

        ...

        ctrlpars = StructParam('ctrlpars struct', [
            ('pid_p', 'p', Parameter('control parameter p', FloatRange())),
            ('pid_i', 'i', Parameter('control parameter i', FloatRange())),
            ('pid_d', 'd', Parameter('control parameter d', FloatRange())),
        ], readonly=False)

        ...

    then implement either read_ctrlpars and write_ctrlpars or
    read_pid_p, read_pid_i, read_pid_d, write_pid_p, write_pid_i and write_pid_d

    the methods not implemented will be created automatically
"""

from frappy.core import Parameter, Property
from frappy.datatypes import BoolType, DataType, StructOf, ValueType
from frappy.errors import ProgrammingError


class StructParam(Parameter):
    """create a struct parameter together with individual parameters

    in addition to normal Parameter arguments:

    :param paramdict: dict <member name> of Parameter(...)
    :param prefix_or_map: either a prefix for the parameter name to add to the member name
                          or a dict <member name> or <paramerter name>
    """
    # use properties, as simple attributes are not considered on copy()
    paramdict = Property('dict <parametername> of Parameter(...)', ValueType())
    hasStructRW = Property('has a read_<struct param> or write_<struct param> method',
                           BoolType(), default=False)

    insideRW = 0  # counter for avoiding multiple superfluous updates

    def __init__(self, description=None, paramdict=None, prefix_or_map='', *, datatype=None, readonly=False, **kwds):
        if isinstance(paramdict, DataType):
            raise ProgrammingError('second argument must be a dict of Param')
        if datatype is None and paramdict is not None:  # omit the following on Parameter.copy()
            if isinstance(prefix_or_map, str):
                prefix_or_map = {m: prefix_or_map + m for m in paramdict}
            for membername, param in paramdict.items():
                param.name = prefix_or_map[membername]
            datatype = StructOf(**{m: p.datatype for m, p in paramdict.items()})
            kwds['influences'] = [p.name for p in paramdict.values()]
        self.updateEnable = {}
        super().__init__(description, datatype, paramdict=paramdict, readonly=readonly, **kwds)

    def __set_name__(self, owner, name):
        # names of access methods of structed param (e.g. ctrlpars)
        struct_read_name = f'read_{name}'  # e.g. 'read_ctrlpars'
        struct_write_name = f'write_{name}'  # e.h. 'write_ctrlpars'
        self.hasStructRW = hasattr(owner, struct_read_name) or hasattr(owner, struct_write_name)

        for membername, param in self.paramdict.items():
            pname = param.name
            changes = {
                'readonly': self.readonly,
                'influences': set(param.influences) | {name},
            }
            param.ownProperties.update(changes)
            param.init(changes)
            setattr(owner, pname, param)
            param.__set_name__(owner, param.name)

            if self.hasStructRW:
                rname = f'read_{pname}'

                if not hasattr(owner, rname):
                    def rfunc(self, membername=membername, struct_read_name=struct_read_name):
                        return getattr(self, struct_read_name)()[membername]

                    rfunc.poll = False  # read_<struct param> is polled only
                    setattr(owner, rname, rfunc)

                if not self.readonly:
                    wname = f'write_{pname}'
                    if not hasattr(owner, wname):
                        def wfunc(self, value, membername=membername,
                                  name=name, rname=rname, struct_write_name=struct_write_name):
                            valuedict = dict(getattr(self, name))
                            valuedict[membername] = value
                            getattr(self, struct_write_name)(valuedict)
                            return getattr(self, rname)()

                        setattr(owner, wname, wfunc)

        if not self.hasStructRW:
            if not hasattr(owner, struct_read_name):
                def struct_read_func(self, name=name, flist=tuple(
                        (m, f'read_{p.name}') for m, p in self.paramdict.items())):
                    pobj = self.parameters[name]
                    # disable updates generated from the callbacks of individual params
                    pobj.insideRW += 1   # guarded by self.accessLock
                    try:
                        return {m: getattr(self, f)() for m, f in flist}
                    finally:
                        pobj.insideRW -= 1

                setattr(owner, struct_read_name, struct_read_func)

            if not (self.readonly or hasattr(owner, struct_write_name)):

                def struct_write_func(self, value, name=name, funclist=tuple(
                        (m, f'write_{p.name}') for m, p in self.paramdict.items())):
                    pobj = self.parameters[name]
                    pobj.insideRW += 1  # guarded by self.accessLock
                    try:
                        return {m: getattr(self, f)(value[m]) for m, f in funclist}
                    finally:
                        pobj.insideRW -= 1

                setattr(owner, struct_write_name, struct_write_func)

        super().__set_name__(owner, name)

    def finish(self, modobj=None):
        """register callbacks for consistency"""
        super().finish(modobj)
        if modobj:

            if self.hasStructRW:
                def cb(value, modobj=modobj, structparam=self):
                    for membername, param in structparam.paramdict.items():
                        setattr(modobj, param.name, value[membername])

                modobj.valueCallbacks[self.name].append(cb)
            else:
                for membername, param in self.paramdict.items():
                    def cb(value, modobj=modobj, structparam=self, membername=membername):
                        if not structparam.insideRW:
                            prev = dict(getattr(modobj, structparam.name))
                            prev[membername] = value
                            setattr(modobj, structparam.name, prev)

                    modobj.valueCallbacks[param.name].append(cb)
