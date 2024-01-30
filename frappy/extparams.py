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
from frappy.datatypes import DataType, ValueType, EnumType, \
    StringType, FloatRange, DataTypeType
from frappy.errors import ProgrammingError


# TODO: insert StructParam here


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

    def finish(self, modobj=None):
        """register callbacks for consistency"""
        super().finish(modobj)
        if modobj:
            # trigger setter of float parameter on change of enum parameter
            def cb(value, modobj=modobj, name=self.name):
                setattr(modobj, name, getattr(modobj, name))

            modobj.valueCallbacks[self.idx_name].append(cb)
