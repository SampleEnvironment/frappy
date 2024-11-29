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
"""extended parameters

special parameter classes with some automatic functionality
"""

import re
from frappy.core import Parameter, Property
from frappy.datatypes import BoolType, DataType, DataTypeType, EnumType, \
    FloatRange, StringType, StructOf, ValueType
from frappy.errors import ProgrammingError


class StructParam(Parameter):
    """convenience class to create a struct Parameter together with individual params

    Usage:

        class Controller(Drivable):

            ...

            ctrlpars = StructParam('ctrlpars struct', {
                'p': Parameter('control parameter p', FloatRange()),
                'i': Parameter('control parameter i', FloatRange()),
                'd': Parameter('control parameter d', FloatRange()),
            }, prefix='pid_', readonly=False)
            ...

        then implement either read_ctrlpars and write_ctrlpars or
        read_pid_p, read_pid_i, read_pid_d, write_pid_p, write_pid_i and write_pid_d

        the methods not implemented will be created automatically
    """

    # use properties, as simple attributes are not considered on copy()
    paramdict = Property('dict <parametername> of Parameter(...)', ValueType())
    hasStructRW = Property('has a read_<struct param> or write_<struct param> method',
                           BoolType(), default=False)

    insideRW = 0  # counter for avoiding multiple superfluous updates

    def __init__(self, description=None, paramdict=None, prefix='', *, datatype=None, readonly=False, **kwds):
        """create a struct parameter together with individual parameters

        in addition to normal Parameter arguments:

        :param paramdict: dict <member name> of Parameter(...)
        :param prefix: a prefix for the parameter name to add to the member name
        """
        if isinstance(paramdict, DataType):
            raise ProgrammingError('second argument must be a dict of Param')
        if datatype is None and paramdict is not None:  # omit the following on Parameter.copy()
            for membername, param in paramdict.items():
                param.name = prefix + membername
            datatype = StructOf(**{m: p.datatype for m, p in paramdict.items()})
            kwds['influences'] = [p.name for p in paramdict.values()]
        self.updateEnable = {}
        if paramdict:
            kwds['paramdict'] = paramdict
        super().__init__(description, datatype, readonly=readonly, **kwds)

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

                modobj.addCallback(self.name, cb)
            else:
                for membername, param in self.paramdict.items():
                    def cb(value, modobj=modobj, structparam=self, membername=membername):
                        if not structparam.insideRW:
                            prev = dict(getattr(modobj, structparam.name))
                            prev[membername] = value
                            setattr(modobj, structparam.name, prev)

                    modobj.addCallback(param.name, cb)


class FloatEnumParam(Parameter):
    """combine enum and float parameter

    Example Usage:

    vrange = FloatEnumParam('sensor range', ['500uV', '20mV', '1V'], 'V')

    The following will be created automatically:

    - the parameter vrange will get a datatype FloatRange(5e-4, 1, unit='V')
    - an additional parameter `vrange_idx` will be created with an enum type
      {'500uV': 0, '20mV': 1, '1V': 2}
    - the method `write_vrange` will be created automatically

    However, the methods `write_vrange_idx` and `read_vrange_idx`, if needed,
    have to implemented by the programmer.

    Writing to the float parameter involves 'rounding' to the closest allowed value.

    Customization:

    The individual labels might be customized by defining them as a tuple
    (<index>, <label>, <float value>) where either the index or the float value
    may be omitted.

    When the index is omitted, the element will be the previous index + 1 or
    0 when it is the first element.

    Omitted values will be determined from the label, assuming that they use
    one of the predefined unit prefixes together with the given unit.

    The name of the index parameter is by default '<name>_idx' but might be
    changed with the idx_name argument.
    """
    # use properties, as simple attributes are not considered on copy()
    idx_name = Property('name of attached index parameter', StringType(), default='')
    valuedict = Property('dict <index> of <value>', ValueType(dict))
    enumtype = Property('dict <label> of <index', DataTypeType())

    # TODO: factor out unit handling, at the latest when needed elsewhere
    PREFIXES = {'q': -30, 'r': -27, 'y': -24, 'z': -21, 'a': -18, 'f': -15,
                'p': -12, 'n': -9, 'u': -6, 'µ': -6, 'm': -3,
                '': 0, 'k': 3, 'M': 6, 'G': 9, 'T': 12,
                'P': 15, 'E': 18, 'Z': 21, 'Y': 24, 'R': 25, 'Q': 30}

    def __init__(self, description=None, labels=None, unit='',
                 *, datatype=None, readonly=False, **kwds):
        if labels is None:
            # called on Parameter.copy()
            super().__init__(description, datatype, readonly=readonly, **kwds)
            return
        if isinstance(labels, DataType):
            raise ProgrammingError('second argument must be a list of labels, not a datatype')
        nextidx = 0
        try:
            edict = {}
            vdict = {}
            for elem in labels:
                if isinstance(elem, str):
                    idx, label = [nextidx, elem]
                else:
                    if isinstance(elem[0], str):
                        elem = [nextidx] + list(elem)
                    idx, label, *tail = elem
                    if tail:
                        vdict[idx], = tail
                edict[label] = idx
                nextidx = idx + 1
        except (ValueError, TypeError) as e:
            raise ProgrammingError('labels must be a list of labels or tuples '
                                   '([index], label, [value])') from e
        pat = re.compile(rf'([+-]?\d*\.?\d*) *({"|".join(self.PREFIXES)}){unit}$')
        try:
            # determine missing values from labels
            for label, idx in edict.items():
                if idx not in vdict:
                    value, prefix = pat.match(label).groups()
                    vdict[idx] = float(f'{value}e{self.PREFIXES[prefix]}')
        except (AttributeError, ValueError) as e:
            raise ProgrammingError(f"{label!r} has not the form '<float><prefix>{unit}'") from e
        try:
            enumtype = EnumType(**edict)
        except TypeError as e:
            raise ProgrammingError(str(e)) from e
        datatype = FloatRange(min(vdict.values()), max(vdict.values()), unit=unit)
        super().__init__(description, datatype, enumtype=enumtype, valuedict=vdict,
                         readonly=readonly, **kwds)

    def __set_name__(self, owner, name):
        super().__set_name__(owner, name)
        if not self.idx_name:
            self.idx_name = name + '_idx'
        iname = self.idx_name
        idx_param = Parameter(f'index of {name}', self.enumtype,
                              readonly=self.readonly, influences={name})
        idx_param.init({})
        setattr(owner, iname, idx_param)
        idx_param.__set_name__(owner, iname)

        self.setProperty('influences', {iname})

        if not hasattr(owner, f'write_{name}'):

            # customization (like rounding up or down) might be
            # achieved by adding write_<name>. if not, the default
            # is rounding to the closest value

            def wfunc(mobj, value, vdict=self.valuedict, fname=name, wfunc_iname=f'write_{iname}'):
                getattr(mobj, wfunc_iname)(
                    min(vdict, key=lambda i: abs(vdict[i] - value)))
                return getattr(mobj, fname)

            setattr(owner, f'write_{name}', wfunc)

    def __get__(self, instance, owner):
        """getter for value"""
        if instance is None:
            return self
        return self.valuedict[instance.parameters[self.idx_name].value]

    def trigger_setter(self, modobj, _):
        # trigger update of float parameter on change of enum parameter
        modobj.announceUpdate(self.name, getattr(modobj, self.name))

    def finish(self, modobj=None):
        """register callbacks for consistency"""
        super().finish(modobj)
        if modobj:
            modobj.addCallback(self.idx_name, self.trigger_setter, modobj)
