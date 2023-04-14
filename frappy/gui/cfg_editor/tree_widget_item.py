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
#   Sandra Seger <sandra.seger@frm2.tum.de>
#
# *****************************************************************************

from frappy.gui.qt import QDialog, QFont, QHBoxLayout, QLabel, QPushButton, \
    QSize, QSizePolicy, QTextEdit, QTreeWidgetItem, QVBoxLayout, QWidget, \
    pyqtSignal

from frappy.gui.cfg_editor.utils import loadUi, set_name_edit_style, setIcon, \
    setTreeIcon
from frappy.gui.valuewidgets import get_widget
from frappy.properties import Property

NODE = 'node'
INTERFACE = 'interface'
MODULE = 'module'
PARAMETER = 'parameter'
PROPERTY = 'property'
COMMENT = 'comment'


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, kind=None, name='', value=None, class_object=None,
                 parameters=None, properties=None, parent=None):
        """object_class: for interfaces and modules = class
                         for parameter and properties = their objects
        the datatype passed onto ValueWidget should be on of frappy.datatypes"""
        # TODO: like stated in docstring the datatype for parameters and
        #  properties must be found out through their object
        super().__init__(parent)
        self.kind = kind
        self.name = name
        self.class_object = class_object
        self.parameters = parameters or {}
        self.properties = properties or {}
        if self.kind and self.kind != 'node':
            setTreeIcon(self, f'{self.kind}.png')
        else:
            setTreeIcon(self, 'empty.png')
            font = QFont()
            font.setWeight(QFont.Weight.Bold)
            self.setFont(0, font)
        self.setText(0, self.name)
        self.duplicates = 0
        datatype = None if type(class_object) != Property else \
            class_object.datatype
        self.widget = ValueWidget(name, value, datatype, kind)
        if kind in [NODE, MODULE, INTERFACE]:
            self.widget.edit_btn.clicked.connect(self.change_name)

    def addChild(self, item):
        QTreeWidgetItem.addChild(self, item)
        item.setExpanded(True)

    def duplicate(self):
        self.duplicates += 1
        duplicate = TreeWidgetItem(self.kind, '%s_%i' % (self.name,
                                   self.duplicates), self.get_value(),
                                   self.class_object)
        self.parent().addChild(duplicate)
        for i in range(self.childCount()):
            child = self.child(i)
            duplicate.addChild(TreeWidgetItem(child.kind,
                               child.name, child.widget.get_value()))
            for k in range(child.childCount()):
                sub_child = child.child(k)
                duplicate.child(i).addChild(TreeWidgetItem(sub_child.kind,
                                            sub_child.name,
                                            sub_child.widget.get_value(),
                                            sub_child.datatype))

    def set_name(self, name):
        self.name = name
        self.setText(0, self.name)
        self.widget.set_name(name)

    def get_value(self):
        return self.widget.get_value()

    def set_value(self, value):
        self.widget.set_value(value)

    def set_class_object(self, class_obj, value=''):
        # TODO: should do stuff here if module or interface class is changed or
        #  datatype
        self.class_object = class_obj
        datatype = None if type(self.class_object) != Property else \
            self.class_object.datatype
        self.widget.set_datatype(datatype, value)

    def get_children_names(self):
        children = []
        for i in range(0, self.childCount()):
            children.append(self.child(i).name)
        return children

    def change_name(self):
        if self.parent():
            invalid_names = self.parent().get_children_names()
            invalid_names.remove(self.name)
        else:
            invalid_names = ['']
        dialog = ChangeNameDialog(self.name, invalid_names)
        new_name = dialog.get_values()
        if new_name:
            self.set_name(new_name)


class ValueWidget(QWidget):

    save_status_changed = pyqtSignal(bool)

    def __init__(self, name='', value='', datatype=None, kind='', parent=None):
        # TODO: implement: change module/interface class
        super().__init__(parent)
        self.datatype = datatype
        self.layout = QVBoxLayout()
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet('font-weight: bold')
        self.kind = kind
        if self.kind in [NODE, MODULE, INTERFACE]:
            self.edit_btn = QPushButton()
            setIcon(self.edit_btn, 'edit.png')
            self.edit_btn.setIconSize(QSize(18, 18))
            self.edit_btn.setSizePolicy(QSizePolicy.Policy.Fixed,
                                        QSizePolicy.Policy.Fixed)
            self.edit_btn.setFlat(True)
            layout = QHBoxLayout()
            layout.addWidget(self.name_label)
            layout.addWidget(self.edit_btn)
            self.layout.addLayout(layout)
        else:
            self.layout.addWidget(self.name_label)
        # TODO value_display.valueChanged.connect(emit_save_status_changed) ->
        #  implement or map a valueChanged signal for all possible
        #  value_displays:
        #  String = QLineEdit = textChanged
        #  Enum = QComboBox = editTextChanged
        #  Bool = QCheckBox = stateChanged
        #  Int, Float = Q(Double)SpinBox = ValueChanged
        #  Struct, Array = QGroupBox = clicked
        #  Tuple = QFrame = ???
        if self.kind == PROPERTY and datatype and name != 'datatype':
            # TODO what to do if property is datatype
            self.value_display = get_widget(datatype)
            self.value_display.set_value(value)
        elif self.kind in [NODE, COMMENT]:
            self.value_display = QTextEdit()
            self.value_display.text = self.value_display.toPlainText
            self.value_display.setText = self.value_display.setPlainText
            self.value_display.textChanged.connect(self.emit_save_status_changed)
            self.set_value(value)
        else:
            self.value_display = QLabel(str(value))
        self.layout.addWidget(self.value_display)
        self.setLayout(self.layout)

    def get_value(self):
        if self.datatype:
            return self.value_display.get_value()
        return self.value_display.text()

    def set_value(self, value):
        # TODO try block
        if self.datatype:
            self.value_display.set_value(value)
        else:
            self.value_display.setText(value)

    def set_name(self, name):
        if name != self.name_label.text():
            self.emit_save_status_changed(False)
            self.name_label.setText(name)

    def set_datatype(self, datatype, value=''):
        if datatype == self.datatype:
            return
        # TODO: remove old value_display
        self.datatype = datatype
        if self.kind == PROPERTY and datatype:
            self.value_display = get_widget(datatype)
            self.value_display.set_value(value)
        else:
            self.value_display = QLabel(value)

    def emit_save_status_changed(self, status=False):
        self.save_status_changed.emit(status)


class ChangeNameDialog(QDialog):
    def __init__(self, current_name='', invalid_names=None, parent=None):
        super().__init__(parent)
        loadUi(self, 'change_name_dialog.ui')
        self.invalid_names = invalid_names
        self.name.setText(current_name)
        self.name.selectAll()
        # TODO: input mask
        self.name.textChanged.connect(self.check_input)

    def get_values(self):
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.name.text()
        return None

    def check_input(self, name):
        set_name_edit_style(name in self.invalid_names or name == '', self.name,
                            self.button_box)
