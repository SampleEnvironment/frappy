# *****************************************************************************
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
# *****************************************************************************

import time
import math
from frappy.core import Parameter, FloatRange, IntRange, Property
from frappy.errors import ProgrammingError


class FrozenParam(Parameter):
    """workaround for lazy hardware

    Some hardware does not react nicely: when a parameter is changed,
    and read back immediately, still the old value is returned.
    This special parameter helps fixing this problem.

    Mechanism:

    - after a call to write_<param> for a short time (<n_polls> * <interval>)
      the hardware is polled until the readback changes before the 'changed'
      message is replied to the client
    - if there is no change yet within short time, the 'changed' message is
      set with the given value and further calls to read_<param> return also
      this given value until the readback value has changed or until
      <timeout> sec have passed.

    For float parameters, the behaviour for small changes is improved
    when the write_<param> method tries to return the (may be rounded) value,
    as if it would be returned by the hardware. If this behaviour is not
    known, or the programmer is too lazy to implement it, write_<param>
    should return None or the given value.
    Also it will help to adjust the datatype properties
    'absolute_resolution' and 'relative_resolution' to reasonable values.
    """
    timeout = Property('timeout for freezing readback value',
                       FloatRange(0, unit='s'), default=30)
    n_polls = Property("""number polls within write method""",
                       IntRange(0), default=1)
    interval = Property("""interval for polls within write method
    
                        the product n_polls * interval should not be more than a fraction of a second
                        in order not to block the connection for too long
                        """,
                        FloatRange(0, unit='s'), default=0.05)
    new_value = None
    previous_value = None
    expire = 0
    is_float = True  # assume float. will be fixed later

    def isclose(self, v1, v2):
        if v1 == v2:
            return True
        if self.is_float:
            dt = self.datatype
            try:
                return math.isclose(v1, v2, abs_tol=dt.absolute_tolerance,
                                    rel_tol=dt.relative_tolerance)
            except AttributeError:
                # fix once for ever when datatype is not a float
                self.is_float = False
        return False

    def __set_name__(self, owner, name):
        try:
            rfunc = getattr(owner, f'read_{name}')
            wfunc = getattr(owner, f'write_{name}')
        except AttributeError:
            raise ProgrammingError(f'FrozenParam: methods read_{name} and write_{name} must exist') from None

        super().__set_name__(owner, name)

        def read_wrapper(self, pname=name, rfunc=rfunc):
            pobj = self.parameters[pname]
            value = rfunc(self)
            if pobj.new_value is None:
                return value
            if not pobj.isclose(value, pobj.new_value):
                if value == pobj.previous_value:
                    if time.time() < pobj.expire:
                        return pobj.new_value
                    self.log.warning('%s readback did not change within %g sec',
                                     pname, pobj.timeout)
                else:
                    # value has changed, but is not matching new value
                    self.log.warning('%s readback changed from %r to %r but %r was given',
                                     pname, pobj.previous_value, value, pobj.new_value)
            # readback value has changed or returned value is roughly equal to the new value
            pobj.new_value = None
            return value

        def write_wrapper(self, value, wfunc=wfunc, rfunc=rfunc, read_wrapper=read_wrapper, pname=name):
            pobj = self.parameters[pname]
            pobj.previous_value = rfunc(self)
            pobj.new_value = wfunc(self, value)
            if pobj.new_value is None:  # as wfunc is the unwrapped write_* method, the return value may be None
                pobj.new_value = value
            pobj.expire = time.time() + pobj.timeout
            for cnt in range(pobj.n_polls):
                if cnt:  # we may be lucky, and the readback value has already changed
                    time.sleep(pobj.interval)
                value = read_wrapper(self)
                if pobj.new_value is None:
                    return value
            return pobj.new_value

        setattr(owner, f'read_{name}', read_wrapper)
        setattr(owner, f'write_{name}', write_wrapper)
