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

from PyQt4.QtGui import QWidget, QLabel, QMessageBox, QCheckBox
from PyQt4.QtCore import pyqtSignature as qtsig, Qt, pyqtSignal

from secop.gui.util import loadUi


class ParameterButtons(QWidget):
    setRequested = pyqtSignal(str, str, str)  # module, parameter, target

    def __init__(self,
                 module,
                 parameter,
                 initval='',
                 readonly=True,
                 parent=None):
        super(ParameterButtons, self).__init__(parent)
        loadUi(self, 'parambuttons.ui')

        self._module = module
        self._parameter = parameter

        self.currentLineEdit.setText(str(initval))
        if readonly:
            self.setPushButton.setEnabled(False)
            self.setLineEdit.setEnabled(False)
        else:
            self.setLineEdit.returnPressed.connect(
                self.on_setPushButton_clicked)

    def on_setPushButton_clicked(self):
        self.setRequested.emit(self._module, self._parameter,
                               self.setLineEdit.text())


class ParameterGroup(QWidget):

    def __init__(self, groupname, parent=None):
        super(ParameterGroup, self).__init__(parent)
        loadUi(self, 'paramgroup.ui')

        self._groupname = groupname

        self._row = 0
        self._widgets = []

        self.paramGroupBox.setTitle('Group: ' + str(groupname))
        self.paramGroupBox.toggled.connect(self.on_toggle_clicked)
        self.paramGroupBox.setChecked(False)

    def addWidgets(self, label, widget):
        self._widgets.extend((label, widget))
        self.paramGroupBox.layout().addWidget(label, self._row, 0)
        self.paramGroupBox.layout().addWidget(widget, self._row, 1)
        label.hide()
        widget.hide()
        self._row += 1

    def on_toggle_clicked(self):
        print "ParameterGroup.on_toggle_clicked"
        if self.paramGroupBox.isChecked():
            for w in self._widgets:
                w.show()
        else:
            for w in self._widgets:
                w.hide()


class ModuleCtrl(QWidget):

    def __init__(self, node, module, parent=None):
        super(ModuleCtrl, self).__init__(parent)
        loadUi(self, 'modulectrl.ui')
        self._node = node
        self._module = module
        self._lastclick = None

        self._paramWidgets = {}  # widget cache do avoid garbage collection
        self._groupWidgets = {}  # cache of grouping widgets

        self._labelfont = self.font()
        self._labelfont.setBold(True)

        self.moduleNameLabel.setText(module)
        self._initModuleWidgets()

        self._node.newData.connect(self._updateValue)

    def _initModuleWidgets(self):
        initValues = self._node.queryCache(self._module)
        row = 0

        # collect grouping information
        paramsByGroup = {}  # groupname -> [paramnames]
        allGroups = set()
        params = self._node.getParameters(self._module)
        for param in params:
            props = self._node.getProperties(self._module, param)
            group = props.get('group', None)
            if group is not None:
                allGroups.add(group)
                paramsByGroup.setdefault(group, []).append(param)

        groupWidgets = {}  # groupname -> CheckBoxWidget for (un)folding

        # create and insert widgets into our QGridLayout
        for param in sorted(allGroups.union(set(params))):
            labelstr = param + ':'
            if param in paramsByGroup:
                group = param
                # is the name of a group -> create (un)foldable label
                checkbox = QCheckBox(labelstr)
                checkbox.setFont(self._labelfont)
                groupWidgets[param] = checkbox

                # check if there is a param of the same name too
                if group in params:
                    # yes: create a widget for this as well
                    labelstr, buttons = self._makeEntry(
                        param, initValues[param].value, nolabel=True, checkbox=checkbox, invert=True)
                    checkbox.setText(labelstr)

                    # add to Layout (yes: ignore the label!)
                    self.paramGroupBox.layout().addWidget(checkbox, row, 0)
                    self.paramGroupBox.layout().addWidget(buttons, row, 1)
                else:
                    self.paramGroupBox.layout().addWidget(checkbox, row, 0, 1, 2)  # or .. 1, 2) ??
                row += 1

                # loop over all params and insert and connect
                for param in paramsByGroup[param]:
                    if param == group:
                        continue
                    label, buttons = self._makeEntry(
                        param, initValues[param].value, checkbox=checkbox, invert=False)

                    # add to Layout
                    self.paramGroupBox.layout().addWidget(label, row, 0)
                    self.paramGroupBox.layout().addWidget(buttons, row, 1)
                    row += 1

            else:
                # param is a 'normal' param: create a widget if it has no group
                # or is named after a group (otherwise its created above)
                props = self._node.getProperties(self._module, param)
                if props.get('group', param) == param:
                    label, buttons = self._makeEntry(
                        param, initValues[param].value)

                    # add to Layout
                    self.paramGroupBox.layout().addWidget(label, row, 0)
                    self.paramGroupBox.layout().addWidget(buttons, row, 1)
                    row += 1

    def _makeEntry(
            self,
            param,
            initvalue,
            nolabel=False,
            checkbox=None,
            invert=False):
        props = self._node.getProperties(self._module, param)

        description = props.get('description', '')
        unit = props.get('unit', '')

        if unit:
            labelstr = '%s (%s):' % (param, unit)
        else:
            labelstr = '%s:' % (param,)

        if checkbox and not invert:
            labelstr = '       ' + labelstr

        buttons = ParameterButtons(
            self._module, param, initvalue, props['readonly'])
        buttons.setRequested.connect(self._set_Button_pressed)

        if description:
            buttons.setToolTip(description)

        if nolabel:
            label = labelstr
        else:
            label = QLabel(labelstr)
            label.setFont(self._labelfont)

        if checkbox:
            def stateChanged(
                    newstate,
                    buttons=buttons,
                    label=None if nolabel else label,
                    invert=invert):
                if (newstate and not invert) or (invert and not newstate):
                    buttons.show()
                    if label:
                        label.show()
                else:
                    buttons.hide()
                    if label:
                        label.hide()
            # set initial state
            stateChanged(0)
            # connect
            checkbox.stateChanged.connect(stateChanged)

        self._paramWidgets[param] = (label, buttons)

        return label, buttons

    def _set_Button_pressed(self, module, parameter, target):
        sig = (module, parameter, target)
        if self._lastclick == sig:
            return
        self._lastclick = sig
        try:
            self._node.setParameter(module, parameter, target)
        except Exception as e:
            QMessageBox.warning(self.parent(), 'Operation failed', str(e))

    def _updateValue(self, module, parameter, value):
        if module != self._module:
            return

        self._paramWidgets[parameter][1].currentLineEdit.setText(str(value[0]))
