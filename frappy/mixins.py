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

from frappy.datatypes import BoolType, EnumType, Enum
from frappy.core import Parameter, Writable, Attached


class HasControlledBy(Writable):
    """mixin for modules with controlled_by

    in the :meth:`write_target` the hardware action to switch to own control should be done
    and in addition self.self_controlled() should be called
    """
    controlled_by = Parameter('source of target value', EnumType(members={'self': 0}), default=0)
    inputCallbacks = ()

    def register_input(self, name, deactivate_control):
        """register input

        :param name: the name of the module (for controlled_by enum)
        :param deactivate_control: a method on the input module to switch off control
        """
        if not self.inputCallbacks:
            self.inputCallbacks = {}
        self.inputCallbacks[name] = deactivate_control
        prev_enum = self.parameters['controlled_by'].datatype.export_datatype()['members']
        # add enum member, using autoincrement feature of Enum
        self.parameters['controlled_by'].datatype = EnumType(Enum(prev_enum, **{name: None}))

    def self_controlled(self):
        """method to change controlled_by to self

        to be called from the write_target method
        """
        if self.controlled_by:
            self.controlled_by = 0
            for deactivate_control in self.inputCallbacks.values():
                deactivate_control(self.name)


class HasOutputModule(Writable):
    """mixin for modules having an output module

    in the :meth:`write_target` the hardware action to switch to own control should be done
    and in addition self.activate_output() should be called
    """
    # mandatory=False: it should be possible to configure a module with fixed control
    output_module = Attached(HasControlledBy, mandatory=False)
    control_active = Parameter('control mode', BoolType(), default=False)

    def initModule(self):
        super().initModule()
        if self.output_module:
            self.output_module.register_input(self.name, self.deactivate_control)

    def activate_control(self):
        """method to switch control_active on

        to be called from the write_target method
        """
        out = self.output_module
        if out:
            for name, deactivate_control in out.inputCallbacks.items():
                if name != self.name:
                    deactivate_control(self.name)
            out.controlled_by = self.name
        self.control_active = True

    def deactivate_control(self, switched_by):
        """called when an other module takes over control"""
        if self.control_active:
            self.control_active = False
            self.log.warning(f'switched to manual mode by {switched_by}')
