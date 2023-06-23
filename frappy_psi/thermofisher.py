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
#   Oksana Shliakhtun <oksana.shliakhtun@psi.ch>
#   Markus Zolliker <markus.zolliker@psi.ch>
# *****************************************************************************
"""bath thermostat Thermo Scientific™ ARCTIC A10 Refrigerated Circulators"""

from frappy.core import Command, StringIO, Parameter, HasIO, \
    Drivable, FloatRange, IDLE, BUSY, ERROR, WARN, BoolType
from frappy.structparam import StructParam
from frappy_psi.convergence import HasConvergence


class ThermFishIO(StringIO):
    end_of_line = '\r'
    identification = [('RVER', r'.*')]  # Firmware Version


class TemperatureLoopA10(HasConvergence, HasIO, Drivable):
    ioClass = ThermFishIO
    value = Parameter('temperature', unit='degC')
    target = Parameter('setpoint/target', datatype=FloatRange, unit='degC', default=0)
    control_active = Parameter('circilation and control is on', BoolType(), default=False)
    ctrlpars = StructParam('control parameters struct', dict(
        p_heat = Parameter('proportional heat parameter', FloatRange()),
        i_heat = Parameter('integral heat parameter', FloatRange()),
        d_heat = Parameter('derivative heat parameter', FloatRange()),
        p_cool = Parameter('proportional cool parameter', FloatRange()),
        i_cool = Parameter('integral cool parameter', FloatRange()),
        d_cool = Parameter('derivative cool parameter', FloatRange()),
    ), readonly=False)

    status_messages = [
        (ERROR, 'high tempr. cutout fault', 2, 0),
        (ERROR, 'high RA tempr. fault', 2, 1),
        (ERROR, 'high temperature fixed fault', 3, 7),
        (ERROR, 'low temperature fixed fault', 3, 6),
        (ERROR, 'high temperature fault', 3, 5),
        (ERROR, 'low temperature fault', 3, 4),
        (ERROR, 'low level fault', 3, 3),
        (ERROR, 'circulator fault', 4, 5),
        (ERROR, 'high press. cutout', 5, 2),
        (ERROR, 'motor overloaded', 5, 1),
        (ERROR, 'pump speed fault', 5, 0),
        (WARN, 'open internal sensor', 1, 7),
        (WARN, 'shorted internal sensor', 1, 6),
        (WARN, 'high temperature warn', 3, 2),
        (WARN, 'low temperature warn', 3, 1),
        (WARN, 'low level warn', 3, 0),
        (IDLE, 'max. heating', 5, 5),
        (IDLE, 'heating', 5, 6),
        (IDLE, 'cooling', 5, 4),
        (IDLE, 'max cooling', 5, 3),
        (IDLE, '', 4, 3),
    ]

    def get_par(self, cmd):
        """get parameter and convert to float

        :param cmd: hardware command without the leading 'R'

        :return: result converted to float
        """
        new_cmd = 'R' + cmd
        reply = self.communicate(new_cmd).strip()
        while reply[-1].isalpha():
            reply = reply[:-1]
        return float(reply)

    def set_par(self, cmd, value):
        self.communicate(f'S{cmd} {value}')
        return self.get_par(cmd)

    def read_value(self):
        """
        Reading internal temperature sensor value.
        """
        return self.get_par('T')

    def read_status(self):
        """ convert from RUFS Command: Description of Bits

            ======  ========================================================  ===============
            Value    Description
            ======  ========================================================  ===============
            V1       B6: warning, rtd1 (internal temp. sensor) is shorted      B0 --> 1
                     B7: warning, rtd1 is open                                 B1 --> 2
            V2       B0: error, HTC (high temperature cutout) fault            B2 --> 4
                     B1: error, high RA (refrigeration) temperature fault      B3 --> 8
            V3       B0: warning, low level in the bath                        B5 --> 32
                     B1: warning, low temperature                              B6 --> 64
                     B2: warning, high temperature                             B7 --> 128
                     B3: error, low level in the bath
                     B4: error, low temperature fault
                     B5: error, high temperature fault
                     B6: error, low temperature fixed* fault
                     B7: error, high temperature fixed** fault
            V4       B3: idle, circulator** is running
                     B5: error, circulator** fault
            V5       B0: error, pump speed fault
                     B1: error, motor overloaded
                     B2: error, high pressure cutout
                     B3: idle, maximum cooling
                     B4: idle, cooling
                     B5: idle, maximum heating
                     B6: idle, heating
            ======  ========================================================  ===============
        """
        result_str = self.communicate('RUFS')  # read unit fault status
        values_str = result_str.strip().split()
        values_int = [int(val) for val in values_str]

        for status_type, status_msg, vi, bit in self.status_messages:
            if values_int[vi-1] & (1 << bit):
                conv_status = HasConvergence.read_status(self)
                if self.isBusy(conv_status):
                    # use 'inside tolerance' and 'outside tolerance' from HasConvergence,
                    # else our own status
                    return BUSY, conv_status[1] if 'tolerance' in conv_status[1] else status_msg
                return status_type, status_msg
        return WARN, 'circulation off'

    def read_control_active(self):
        return int(self.get_par('O'))

    @Command
    def control_off(self):
        """switch control and circulation off"""
        self.control_active = self.set_par('O', 0)

    def read_target(self):
        return self.get_par('S')

    def write_target(self, target):
        self.control_active = self.set_par('O', 1)
        self.communicate(f'SS {target}')
        self.convergence_start()
        return target

    def read_p_heat(self):
        return self.get_par('PH')

    def write_p_heat(self, value):
        return self.set_par('PH', value)

    def read_i_heat(self):
        return self.get_par('IH')

    def write_i_heat(self, value):
        return self.set_par('IH', value)

    def read_d_heat(self):
        return self.get_par('DH')

    def write_d_heat(self, value):
        return self.set_par('DH', value)

    def read_p_cool(self):
        return self.get_par('PC')

    def write_p_cool(self, value):
        return self.set_par('PC', value)

    def read_i_cool(self):
        return self.get_par('IC')

    def write_i_cool(self, value):
        return self.set_par('IC', value)

    def read_d_cool(self):
        return self.get_par('DC')

    def write_d_cool(self, value):
        return self.set_par('DC', value)
