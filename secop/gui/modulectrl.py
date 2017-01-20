#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2016 by the authors, see LICENSE
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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

from PyQt4.QtGui import QWidget, QLabel
from PyQt4.QtCore import pyqtSignature as qtsig, Qt, pyqtSignal

from secop.gui.util import loadUi


class ParameterButtons(QWidget):
    setRequested = pyqtSignal(str, str, str)  # module, parameter, target

    def __init__(self, module, parameter, initval='',
                 readonly=True, parent=None):
        super(ParameterButtons, self).__init__(parent)
        loadUi(self, 'parambuttons.ui')

        self._module = module
        self._parameter = parameter

        self.currentLineEdit.setText(str(initval))
        if readonly:
            self.setPushButton.setEnabled(False)
            self.setLineEdit.setEnabled(False)

    def on_setPushButton_clicked(self):
        self.setRequested.emit(self._module, self._parameter,
                               self.setLineEdit.text())


class ModuleCtrl(QWidget):

    def __init__(self, node, module, parent=None):
        super(ModuleCtrl, self).__init__(parent)
        loadUi(self, 'modulectrl.ui')
        self._node = node
        self._module = module

        self._paramWidgets = {}  # widget cache do avoid garbage collection

        self.moduleNameLabel.setText(module)
        self._initModuleWidgets()

        self._node.newData.connect(self._updateValue)

    def _initModuleWidgets(self):
        initValues = self._node.queryCache(self._module)
        row = 0

        font = self.font()
        font.setBold(True)

        for param in sorted(self._node.getParameters(self._module)):
            label = QLabel(param + ':')
            label.setFont(font)

            props = self._node.getProperties(self._module, param)

            buttons = ParameterButtons(self._module, param,
                                       initValues[param].value,
                                       props['readonly'])

            buttons.setRequested.connect(self._node.setParameter)

            self.paramGroupBox.layout().addWidget(label, row, 0)
            self.paramGroupBox.layout().addWidget(buttons, row, 1)

            self._paramWidgets[param] = (label, buttons)

            row += 1

    def _updateValue(self, module, parameter, value):
        if module != self._module:
            return

        self._paramWidgets[parameter][1].currentLineEdit.setText(str(value[0]))
