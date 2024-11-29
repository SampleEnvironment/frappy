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

"""drivers for CCU4, the cryostat control unit at SINQ"""
# the most common Frappy classes can be imported from frappy.core
from frappy.core import EnumType, FloatRange, \
    HasIO, Parameter, Readable, StringIO, StatusType


class CCU4IO(StringIO):
    """communication with CCU4"""
    # for completeness: (not needed, as it is the default)
    end_of_line = '\n'
    # on connect, we send 'cid' and expect a reply starting with 'CCU4'
    identification = [('cid', r'CCU4.*')]


# inheriting HasIO allows us to use the communicate method for talking with the hardware
# Readable as a base class defines the value and status parameters
class HeLevel(HasIO, Readable):
    """He Level channel of CCU4"""

    # define the communication class to create the IO module
    ioClass = CCU4IO

    # define or alter the parameters
    # as Readable.value exists already, we give only the modified property 'unit'
    value = Parameter(unit='%')
    empty_length = Parameter('warm length when empty', FloatRange(0, 2000, unit='mm'),
                             readonly=False)
    full_length = Parameter('warm length when full', FloatRange(0, 2000, unit='mm'),
                            readonly=False)
    sample_rate = Parameter('sample rate', EnumType(slow=0, fast=1), readonly=False)

    status = Parameter(datatype=StatusType(Readable, 'DISABLED'))

    # conversion of the code from the CCU4 parameter 'hsf'
    STATUS_MAP = {
        0: (StatusType.IDLE, 'sensor ok'),
        1: (StatusType.ERROR, 'sensor warm'),
        2: (StatusType.ERROR, 'no sensor'),
        3: (StatusType.ERROR, 'timeout'),
        4: (StatusType.ERROR, 'not yet read'),
        5: (StatusType.DISABLED, 'disabled'),
    }

    def query(self, cmd):
        """send a query and get the response

        :param cmd: the name of the parameter to query or '<parameter>=<value'
                    for changing a parameter
        :returns: the (new) value of the parameter
        """
        name, txtvalue = self.communicate(cmd).split('=')
        assert name == cmd.split('=')[0]  # check that we got a reply to our command
        return float(txtvalue)

    def read_value(self):
        return self.query('h')

    def read_status(self):
        return self.STATUS_MAP[int(self.query('hsf'))]

    def read_empty_length(self):
        return self.query('hem')

    def write_empty_length(self, value):
        return self.query(f'hem={value:g}')

    def read_full_length(self):
        return self.query('hfu')

    def write_full_length(self, value):
        return self.query(f'hfu={value:g}')

    def read_sample_rate(self):
        return self.query('hf')

    def write_sample_rate(self, value):
        return self.query(f'hf={int(value)}')
