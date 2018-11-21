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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

from __future__ import print_function

try:
    # py2
    unicode(u'')
except NameError:
    unicode = str  # pylint: disable=redefined-builtin

from secop.gui.qt import QWidget, QLabel, QPushButton as QButton, QLineEdit, \
    QMessageBox, QCheckBox, QSizePolicy, Qt, pyqtSignal, pyqtSlot

from secop.gui.util import loadUi
from secop.datatypes import EnumType
from secop.lib import formatExtendedStack


class ParameterWidget(QWidget):
    setRequested = pyqtSignal(str, str, object)  # module, parameter, target
    cmdRequested = pyqtSignal(str, str, list)  # module, command, args

    def __init__(self,
                 module,
                 paramcmd,
                 datatype=None,
                 initvalue=None,
                 readonly=True,
                 parent=None):
        super(ParameterWidget, self).__init__(parent)
        self._module = module
        self._paramcmd = paramcmd
        self._datatype = datatype
        self._readonly = readonly

        self._load_ui(initvalue)

    def _load_ui(self, initvalue):
        # load ui file, set initvalue to right widget
        pass

    def updateValue(self, value):
        # async !
        pass


class GenericParameterWidget(ParameterWidget):

    def _load_ui(self, initvalue):
        # using two QLineEdits for current and target value
        loadUi(self, 'parambuttons.ui')

        if self._readonly:
            self.setPushButton.setEnabled(False)
            self.setLineEdit.setEnabled(False)
        else:
            self.setLineEdit.returnPressed.connect(
                self.on_setPushButton_clicked)
        self.updateValue(initvalue)

    @pyqtSlot()
    def on_setPushButton_clicked(self):
        self.setRequested.emit(self._module, self._paramcmd,
                               self.setLineEdit.text())

    def updateValue(self, value):
        if self._datatype:
            value = self._datatype.import_value(value)
        self.currentLineEdit.setText(str(value))


class EnumParameterWidget(GenericParameterWidget):

    def _load_ui(self, initvalue):
        # using two QLineEdits for current and target value
        loadUi(self, 'parambuttons_select.ui')

        # transfer allowed settings from datatype to comboBoxes
        self._map = {}  # maps index to EnumMember
        self._revmap = {}  # maps Enum.name + Enum.value to index
        for index, member in enumerate(self._datatype._enum.members):
            self.setComboBox.addItem(member.name, member.value)
            self._map[index] = member
            self._revmap[member.name] = self._revmap[member.value] = index
        if self._readonly:
            self.setLabel.setEnabled(False)
            self.setComboBox.setEnabled(False)
            self.setLabel.setHidden(True)
            self.setComboBox.setHidden(True)
        else:
            self.setComboBox.activated.connect(self.on_setPushButton_clicked)

        self.updateValue(initvalue)

    @pyqtSlot()
    def on_setPushButton_clicked(self):
        member = self._map[self.setComboBox.currentIndex()]
        self.setRequested.emit(self._module, self._paramcmd, member)

    def updateValue(self, value):
        try:
            member = self._map[self._revmap[int(value)]]
            self.currentLineEdit.setText('%s.%s (%d)' % (member.enum.name, member.name, member.value))
        except Exception:
            self.currentLineEdit.setText('undefined Value: %r' % value)
            print(formatExtendedStack())


class GenericCmdWidget(ParameterWidget):

    def _load_ui(self, initvalue):
        # using two QLineEdits for current and target value
        loadUi(self, 'cmdbuttons.ui')

        self.cmdLineEdit.setText('')
        self.cmdLineEdit.setEnabled(self.datatype.argtype is not None)
        self.cmdLineEdit.returnPressed.connect(
            self.on_cmdPushButton_clicked)

    @pyqtSlot()
    def on_cmdPushButton_clicked(self):
        # wait until command complete before retrying
        # since the command is scheduled async: what if an errot happens?
        # XXX: button stays deactivated upon errors in execution of cmd...
        self.cmdPushButton.setEnabled(False)
        self.cmdRequested.emit(
            self._module,
            self._paramcmd,
            self._datatype.from_string(
                self.cmdLineEdit.text()))

    def updateValue(self, value):
        # open dialog and show value, if any.
        # then re-activate the command button
        self.cmdPushButton.setEnabled(True)


def ParameterView(module,
                  paramcmd,
                  datatype=None,
                  initvalue=None,
                  readonly=True,
                  parent=None):
    # depending on datatype returns an initialized widget fit for display and
    # interaction
    if datatype is not None:
        if datatype.IS_COMMAND:
            return GenericCmdWidget(
                module,
                paramcmd,  # name of command
                datatype,
                initvalue,  # not used for comands
                readonly,  # not used for commands
                parent)
        if isinstance(datatype, EnumType):
            return EnumParameterWidget(
                module,
                paramcmd,  # name of parameter
                datatype,
                initvalue,
                readonly,
                parent)

    return GenericParameterWidget(
        module,
        paramcmd,  # name of parameter
        datatype,
        initvalue,
        readonly,
        parent)
