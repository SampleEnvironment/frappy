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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

from __future__ import division, print_function

from secop.gui.params import ParameterView
from secop.gui.qt import QCheckBox, QDialog, QLabel, QMessageBox, QPushButton, \
    QSizePolicy, QWidget
from secop.gui.util import loadUi
from secop.gui.valuewidgets import get_widget

try:
    # py2
    unicode(u'')
except NameError:
    # py3
    unicode = str  # pylint: disable=redefined-builtin



#from secop.datatypes import ...





class CommandDialog(QDialog):
    def __init__(self, cmdname, argument, parent=None):
        super(CommandDialog, self).__init__(parent)
        loadUi(self, 'cmddialog.ui')

        self.setWindowTitle('Arguments for %s' % cmdname)
        #row = 0

        self._labels = []
        self.widgets = []
        # improve! recursive?
        dtype = argument
        l = QLabel(repr(dtype))
        l.setWordWrap(True)
        w = get_widget(dtype, readonly=False)
        self.gridLayout.addWidget(l, 0, 0)
        self.gridLayout.addWidget(w, 0, 1)
        self._labels.append(l)
        self.widgets.append(w)

        self.gridLayout.setRowStretch(1, 1)
        self.setModal(True)
        self.resize(self.sizeHint())

    def get_value(self):
        return True, self.widgets[0].get_value()

    def exec_(self):
        if super(CommandDialog, self).exec_():
            return self.get_value()
        return None


def showCommandResultDialog(command, args, result, extras=''):
    m = QMessageBox()
    if not args:
        args = ''
    m.setText('calling: %s(%s)\nyielded: %r\nqualifiers: %s' %
              (command, args, result, extras))
    m.exec_()


def showErrorDialog(error):
    m = QMessageBox()
    m.setText('Error %r' % error)
    m.exec_()


class ParameterGroup(QWidget):

    def __init__(self, groupname, parent=None):
        super(ParameterGroup, self).__init__(parent)
        loadUi(self, 'paramgroup.ui')

        self._groupname = groupname

        self._row = 0
        self._widgets = []

        self.paramGroupBox.setTitle('Group: ' + unicode(groupname))
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
        if self.paramGroupBox.isChecked():
            for w in self._widgets:
                w.show()
        else:
            for w in self._widgets:
                w.hide()


class CommandButton(QPushButton):

    def __init__(self, cmdname, cmdinfo, cb, parent=None):
        super(CommandButton, self).__init__(parent)

        self._cmdname = cmdname
        self._argintype = cmdinfo['datatype'].argtype   # single datatype
        self.resulttype = cmdinfo['datatype'].resulttype
        self._cb = cb  # callback function for exection

        self.setText(cmdname)
        if cmdinfo['description']:
            self.setToolTip(cmdinfo['description'])
        self.pressed.connect(self.on_pushButton_pressed)

    def on_pushButton_pressed(self):
        self.setEnabled(False)
        if self._argintype:
            dlg = CommandDialog(self._cmdname, self._argintype)
            args = dlg.exec_()
            if args:  # not 'Cancel' clicked
                self._cb(self._cmdname, args[1])
        else:
            # no need for arguments
            self._cb(self._cmdname, None)
        self.setEnabled(True)


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

    def _execCommand(self, command, args=None):
        if not args:
            args = tuple()
        try:
            result, qualifiers = self._node.execCommand(
                self._module, command, args)
        except TypeError:
            result = None
            qualifiers = {}
            # XXX: flag missing data report as error
        showCommandResultDialog(command, args, result, qualifiers)

    def _initModuleWidgets(self):
        initValues = self._node.queryCache(self._module)
        row = 0

        # ignore groupings for commands (for now)
        commands = self._node.getCommands(self._module)
        # keep a reference or the widgets are destroyed to soon.
        self.cmdWidgets = cmdWidgets = {}
        # create and insert widgets into our QGridLayout
        for command in sorted(commands):
            #  XXX: fetch and use correct datatypes here!
            w = CommandButton(command, commands[command], self._execCommand)
            cmdWidgets[command] = w
            self.commandGroupBox.layout().addWidget(w, 0, row)
            row += 1

        row = 0
        # collect grouping information
        paramsByGroup = {}  # groupname -> [paramnames]
        allGroups = set()
        params = self._node.getParameters(self._module)
        for param in params:
            props = self._node.getProperties(self._module, param)
            group = props.get('group', '')
            if group:
                allGroups.add(group)
                paramsByGroup.setdefault(group, []).append(param)
            # enforce reading initial value if not already in cache
            if param not in initValues:
                self._node.getParameter(self._module, param)

        # groupname -> CheckBoxWidget for (un)folding
        self._groupWidgets = groupWidgets = {}

        # create and insert widgets into our QGridLayout
        # iterate over a union of all groups and all params
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
                    datatype = self._node.getProperties(
                        self._module, group).get(
                        'datatype', None)
                    # yes: create a widget for this as well
                    labelstr, buttons = self._makeEntry(
                        group, initValues[param].value, datatype=datatype, nolabel=True, checkbox=checkbox, invert=True)
                    checkbox.setText(labelstr)

                    # add to Layout (yes: ignore the label!)
                    self.paramGroupBox.layout().addWidget(checkbox, row, 0)
                    self.paramGroupBox.layout().addWidget(buttons, row, 1)
                else:
                    self.paramGroupBox.layout().addWidget(checkbox, row, 0, 1, 2)  # or .. 1, 2) ??
                row += 1

                # loop over all params and insert and connect
                for param_ in paramsByGroup[param]:
                    if param_ == group:
                        continue
                    if param_ not in initValues:
                        initval = None
                        print("Warning: %r not in initValues!" % param_)
                    else:
                        initval = initValues[param_].value
                    datatype = self._node.getProperties(
                        self._module, param_).get(
                        'datatype', None)
                    label, buttons = self._makeEntry(
                        param_, initval, datatype=datatype, checkbox=checkbox, invert=False)

                    # add to Layout
                    self.paramGroupBox.layout().addWidget(label, row, 0)
                    self.paramGroupBox.layout().addWidget(buttons, row, 1)
                    row += 1

            else:
                # param is a 'normal' param: create a widget if it has no group
                # or is named after a group (otherwise its created above)
                props = self._node.getProperties(self._module, param)
                if (props.get('group', '') or param) == param:
                    datatype = self._node.getProperties(
                        self._module, param).get(
                        'datatype', None)
                    label, buttons = self._makeEntry(
                        param, initValues[param].value, datatype=datatype)

                    # add to Layout
                    self.paramGroupBox.layout().addWidget(label, row, 0)
                    self.paramGroupBox.layout().addWidget(buttons, row, 1)
                    row += 1

        # also populate properties
        self._propWidgets = {}
        props = self._node.getModuleProperties(self._module)
        row = 0
        for prop in sorted(props):
            label = QLabel(prop + ':')
            label.setFont(self._labelfont)
            label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

            # make 'display' label
            view = QLabel(unicode(props[prop]))
            view.setFont(self.font())
            view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            view.setWordWrap(True)

            self.propertyGroupBox.layout().addWidget(label, row, 0)
            self.propertyGroupBox.layout().addWidget(view, row, 1)
            row += 1

            self._propWidgets[prop] = (label, view)

    def _makeEntry(
            self,
            param,
            initvalue,
            datatype=None,
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

        buttons = ParameterView(
            self._module,
            param,
            datatype=datatype,
            initvalue=initvalue,
            readonly=props['readonly'])
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
        try:
            self._node.setParameter(module, parameter, target)
        except Exception as e:
            QMessageBox.warning(self.parent(), 'Operation failed', unicode(e))

    def _updateValue(self, module, parameter, value):
        if module != self._module:
            return
        # value is [data, qualifiers]
        # note: update subwidgets with the data portion only
        # note: paramwidgets[..][1] is a ParameterView from secop.gui.params
        self._paramWidgets[parameter][1].updateValue(value[0])
