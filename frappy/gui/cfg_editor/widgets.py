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


import os

from frappy.gui.qt import QComboBox, QDialog, QDialogButtonBox, QLabel, \
    QLineEdit, QMenu, QPoint, QSize, QStandardItem, QStandardItemModel, Qt, \
    QTabBar, QTextEdit, QTreeView, QTreeWidget, pyqtSignal

from frappy.gui.cfg_editor.config_file import read_config, write_config
from frappy.gui.cfg_editor.tree_widget_item import TreeWidgetItem
from frappy.gui.cfg_editor.utils import get_all_items, get_file_paths, \
    get_interface_class_from_name, get_interfaces, \
    get_module_class_from_name, get_modules, get_params, get_props, loadUi, \
    set_name_edit_style, setActionIcon

NODE = 'node'
MODULE = 'module'
INTERFACE = 'interface'
PARAMETER = 'parameter'
PROPERTY = 'property'
COMMENT = 'comment'


class TreeWidget(QTreeWidget):

    save_status_changed = pyqtSignal(bool)
    add_canceled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = None
        self.setIconSize(QSize(24, 24))
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.context_pos = QPoint(0, 0)
        self.menu = QMenu()
        self.context_actions = []
        self.invalid_context_actions = {}
        self.setup_context_actions()
        self.customContextMenuRequested.connect(self.on_context_menu_requested)

    def setup_context_actions(self):
        edit = self.menu.addAction('Rename')
        a_m = self.menu.addAction('Add module')
        a_i = self.menu.addAction('Add interface')
        a_pa = self.menu.addAction('Add parameter')
        a_pr = self.menu.addAction('Add property')
        a_c = self.menu.addAction('Add comment')
        dup = self.menu.addAction('Duplicate')
        dele = self.menu.addAction('Delete')
        self.context_actions = [edit, a_m, a_i, a_pa, a_pr, a_c, dup, dele]
        setActionIcon(edit, 'edit.png')
        setActionIcon(a_m, 'add_module.png')
        setActionIcon(a_i, 'add_interface.png')
        setActionIcon(a_pa, 'add_parameter.png')
        setActionIcon(a_pr, 'add_property.png')
        setActionIcon(a_c, 'add_comment.png')
        setActionIcon(dup, 'duplicate.png')
        setActionIcon(dele, 'delete.png')
        self.invalid_context_actions = {NODE: [a_pa, dup, dele],
                                        MODULE: [],
                                        INTERFACE: [a_pa],
                                        PARAMETER: [edit, a_pa, dup],
                                        PROPERTY: [edit, a_pa, a_pr, dup],
                                        COMMENT: [edit, a_pa, a_pr, a_c, dup],
                                        None: [edit, a_pa, a_pr, a_c, dup,
                                               dele]}
        edit.triggered.connect(self.change_name_via_context)
        a_m.triggered.connect(self.add_module)
        a_i.triggered.connect(self.add_interface)
        a_pa.triggered.connect(self.add_parameter)
        a_pr.triggered.connect(self.add_property)
        a_c.triggered.connect(self.add_comment)
        dup.triggered.connect(self.duplicate)
        dele.triggered.connect(self.delete)

    def emit_save_status_changed(self, status):
        self.save_status_changed.emit(status)

    def set_file(self, file_path):
        self.file_path = file_path
        if self.file_path:
            if os.path.isfile(file_path):
                self.set_tree(read_config(self.file_path))
                self.emit_save_status_changed(True)
                return True
            self.file_path = None
        return self.new_tree()

    def new_tree(self):
        dialog = AddDialog(NODE)
        values = dialog.get_values()
        if values:
            sec_node = self.get_tree_widget_item(NODE, values[0], values[1],
                                                 None)
            self.addTopLevelItem(sec_node)
            sec_node.setExpanded(True)
            self.mods = self.get_tree_widget_item(name='Modules')
            self.ifs = self.get_tree_widget_item(name='Interfaces')
            sec_node.addChild(self.ifs)
            sec_node.addChild(self.mods)
            self.emit_save_status_changed(False)
            self.setCurrentItem(sec_node)
            return True
        return False

    def set_tree(self, tree_items):
        self.clear()
        self.addTopLevelItem(tree_items[0])
        self.ifs = tree_items[1]
        self.mods = tree_items[2]
        self.expandAll()
        self.setCurrentItem(tree_items[0])
        for item in get_all_items(self):
            item.widget.save_status_changed.connect(self.emit_save_status_changed)

    def add_module(self):
        dialog = AddDialog(MODULE, get_modules(),
                           self.mods.get_children_names())
        values = dialog.get_values()
        if values:
            module_class = get_module_class_from_name(values[1])
            params = get_params(module_class)
            props = get_props(module_class)
            mod = self.get_tree_widget_item(MODULE, values[0], values[1],
                                            module_class, params, props)
            self.mods.addChild(mod)

            # add all mandatory properties
            for pr, pr_o in props.items():
                # TODO: mandatory to must_be_configured
                if pr_o.mandatory is True:
                    pr_i = self.get_tree_widget_item(PROPERTY, pr,
                                                     pr_o.default, pr_o)
                    mod.addChild(pr_i)
            # add all mandatory properties of parameter
            for pa, pa_o in params.items():
                pa_i = None
                for pr, pr_o in pa_o[1].items():
                    # TODO: mandatory to must_be_configured
                    if pr_o.mandatory is True:
                        pr_i = self.get_tree_widget_item(PROPERTY, pr,
                                                         pr_o.default, pr_o)
                        if not pa_i:
                            pa_i = self.get_tree_widget_item(PARAMETER, pa,
                                                             class_object=pa_o[0],
                                                             properties=pa_o[1])
                            mod.addChild(pa_i)
                        pa_i.addChild(pr_i)

            self.setCurrentItem(mod)
            self.emit_save_status_changed(False)

    def add_interface(self):
        dialog = AddDialog(INTERFACE, get_interfaces(),
                           self.ifs.get_children_names())
        values = dialog.get_values()
        if values:
            interface_class = get_interface_class_from_name(values[1])
            props = get_props(interface_class)
            interface = self.get_tree_widget_item(INTERFACE, values[0],
                                                  values[1], interface_class,
                                                  properties=props)
            self.ifs.addChild(interface)
            # add all mandatory properties
            for pr, pr_o in props.items():
                # TODO: mandatory to must_be_configured
                if pr_o.mandatory is True:
                    pr_i = self.get_tree_widget_item(PROPERTY, pr,
                                                     pr_o.default, pr_o)
                    interface.addChild(pr_i)
            self.setCurrentItem(interface)
            self.emit_save_status_changed(False)

    def add_parameter(self):
        selected_item = self.get_selected_item()
        if not selected_item or self.is_heading(selected_item) or \
                self.is_not_extendable(selected_item) or \
                selected_item.kind in [PARAMETER, INTERFACE]:
            return
        params = selected_item.parameters
        if params:
            dialog = AddDialog(PARAMETER, params.keys())
            values = dialog.get_values()
            current_children = selected_item.get_children_names()
            if values:
                if values[0] in current_children:
                    self.setCurrentItem(selected_item.child(current_children.index(
                        values[0])))
                else:
                    param = self.get_tree_widget_item(PARAMETER, values[0],
                                                      class_object=params[values[0]][0],
                                                      properties=params[values[0]][1])
                    selected_item.insertChild(0, param)
                    self.setCurrentItem(param)
                    self.emit_save_status_changed(False)
        else:
            # TODO: warning
            pass

    def add_property(self):
        selected_item = self.get_selected_item()
        if not selected_item or self.is_heading(selected_item) or \
                self.is_not_extendable(selected_item):
            return
        props = selected_item.properties
        if props:
            dialog = AddDialog(PROPERTY, props.keys())
            values = dialog.get_values()
            current_children = selected_item.get_children_names()
            if values:
                if values[0] in current_children:
                    self.setCurrentItem(selected_item.child(current_children.index(
                        values[0])))
                else:
                    prop = self.get_tree_widget_item(PROPERTY, values[0],
                                                     props[values[0]].default,
                                                     props[values[0]])
                    selected_item.insertChild(0, prop)
                    self.setCurrentItem(prop)
                    self.emit_save_status_changed(False)
        else:
            # TODO: warning
            pass

    def add_comment(self):
        selected_item = self.get_selected_item()
        if not selected_item or self.is_heading(selected_item) or \
                selected_item.kind == COMMENT:
            return
        dialog = AddDialog(COMMENT)
        values = dialog.get_values()
        if values:
            comm = self.get_tree_widget_item(COMMENT, '#', values[0])
            selected_item.insertChild(0, comm)
            self.setCurrentItem(comm)
            self.emit_save_status_changed(False)

    def duplicate(self):
        selected_item = self.get_selected_item()
        if not selected_item or selected_item.kind not in [MODULE, INTERFACE]:
            return
        selected_item.duplicate()
        # TODO set duplicated selected
        self.emit_save_status_changed(False)

    def delete(self):
        selected_item = self.get_selected_item()
        if not selected_item or self.is_heading(selected_item) \
                or selected_item == NODE:
            return
        selected_item.parent().removeChild(selected_item)
        self.emit_save_status_changed(False)

    def save(self, save_as=False):
        file_name = self.file_path
        if not self.file_path or save_as:
            file_name = get_file_paths(self, False)[-1]
        if file_name[-4:] == '.cfg':
            self.file_path = file_name
            write_config(self.file_path, self)
            self.emit_save_status_changed(True)
            return True
        return False

    def is_heading(self, item):
        return item is self.ifs or item is self.mods

    def is_not_extendable(self, item):
        return item.kind in [PROPERTY, COMMENT]

    def get_selected_item(self):
        selected_item = self.selectedItems()
        if not selected_item:
            return None
        return selected_item[-1]

    def is_valid_name(self, name, kind):
        if kind == MODULE:
            if name in self.mods.get_children_names():
                return False
        elif kind == INTERFACE:
            if name in self.ifs.get_children_names():
                return False
        else:
            selected_item = self.get_selected_item()
            if not selected_item:
                return False
            if name in selected_item.get_children_names():
                return False
        return True

    def get_tree_widget_item(self, kind=None, name='', value=None,
                             class_object=None, parameters=None, properties=None):
        item = TreeWidgetItem(kind, name, value, class_object, parameters or {}, properties or {})
        item.widget.save_status_changed.connect(self.emit_save_status_changed)
        return item

    def change_name_via_context(self):
        self.itemAt(self.context_pos).change_name()

    def on_context_menu_requested(self, pos):
        self.context_pos = pos
        self.menu.move(self.mapToGlobal(pos))
        self.menu.show()
        for action in self.context_actions:
            action.setEnabled(True)
        for action in self.invalid_context_actions[self.itemAt(self.context_pos).kind]:
            action.setEnabled(False)


class AddDialog(QDialog):
    def __init__(self, kind, possible_values=None, invalid_names=None,
                 parent=None):
        """Notes:
            self.get_value: is mapped to the specific method for getting
                            the value from self.value"""
        super().__init__(parent)
        loadUi(self, 'add_dialog.ui')
        self.setWindowTitle('Add %s' % kind)
        self.kind = kind
        self.invalid_names = invalid_names
        if self.invalid_names:
            for i, name in enumerate(self.invalid_names):
                self.invalid_names[i] = name.lower()
        if kind in [NODE, MODULE, INTERFACE]:
            self.button_box.button(
                QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            self.name = QLineEdit()
            # TODO: input mask
            self.name.textChanged.connect(self.check_input)
            self.add_layout.addWidget(QLabel('Name:'), 0, 0)
            self.add_layout.addWidget(self.name, 0, 1)
            if kind == NODE:
                label_text = 'Description:'
                self.value = QTextEdit()
                self.get_value = self.value.toPlainText
                self.value.text = self.value.toPlainText
            else:
                label_text = 'Kind:'
                self.value = QComboBox()
                self.get_value = self.value.currentText
                if type(possible_values) == dict:
                    # TODO disable OK Button if TreeComboBox is empty
                    self.value = TreeComboBox(possible_values)
                    self.get_value = self.value.get_value
                else:
                    self.value.addItems(possible_values)
                    self.value.setCurrentIndex(len(possible_values)-1)
            self.add_layout.addWidget(QLabel(label_text), 1, 0)
            self.add_layout.addWidget(self.value, 1, 1)
            self.name.setFocus()
        else:
            if kind in [PARAMETER, PROPERTY]:
                label_text = 'Kind:'
                self.value = QComboBox()
                self.get_value = self.value.currentText
                self.value.addItems(possible_values)
            else:
                label_text = 'Comment:'
                self.value = QTextEdit()
                self.get_value = self.value.toPlainText
            self.add_layout.addWidget(QLabel(label_text), 0, 0)
            self.add_layout.addWidget(self.value, 0, 1)
            self.value.setFocus()
        if self.add_layout.rowCount() == 2:
            self.setTabOrder(self.name, self.value)
        self.setTabOrder(self.value, self.button_box.button(
                             QDialogButtonBox.StandardButton.Ok))
        self.setTabOrder(self.button_box.button(
                             QDialogButtonBox.StandardButton.Ok),
                         self.button_box.button(
                             QDialogButtonBox.StandardButton.Cancel))

    def get_values(self):
        if self.exec() == QDialog.DialogCode.Accepted:
            if self.kind in [NODE, MODULE, INTERFACE]:
                return [self.name.text(), self.get_value()]
            if self.kind in [PARAMETER, PROPERTY, COMMENT]:
                return [self.get_value()]
        return None

    def check_input(self, name):
        set_name_edit_style((self.kind in [MODULE, INTERFACE] and
                            name.lower() in self.invalid_names) or name == '',
                            self.name, self.button_box)


class TabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.context_pos = QPoint(0, 0)
        self.menu = QMenu()
        close = self.menu.addAction('&Close')
        close_all = self.menu.addAction('&Close all')
        close.triggered.connect(self.close_tab_via_context)
        close_all.triggered.connect(self.close_all)
        self.customContextMenuRequested.connect(self.on_context_menu_requested)
        self.setMovable(True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MidButton:
            self.close_tab_at_pos(event.pos())
        QTabBar.mouseReleaseEvent(self, event)

    def on_context_menu_requested(self, pos):
        self.context_pos = pos
        self.menu.move(self.mapToGlobal(pos))
        self.menu.show()

    def close_tab_via_context(self):
        self.close_tab_at_pos(self.context_pos)

    def close_all(self):
        for i in range(self.count()-1, -1, -1):
            self.tabCloseRequested.emit(i)

    def close_tab_at_pos(self, pos):
        self.tabCloseRequested.emit(self.tabAt(pos))


class TreeComboBox(QComboBox):
    def __init__(self, value_dict, parent=None):
        super().__init__(parent)
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.expanded.connect(self.resize_length)
        self.tree_view.collapsed.connect(self.resize_length)
        self.model = QStandardItemModel()
        self.insert_dict(value_dict)
        self.setModel(self.model)
        self.setView(self.tree_view)
        self.setStyleSheet('QTreeView::item:has-children{color: black;'
                           'font: bold;}')

    def insert_dict(self, value_dict, parent=None):
        for not_selectable in value_dict:
            act_item = QStandardItem(not_selectable)
            act_item.setEnabled(False)
            font = act_item.font()
            font.setBold(True)
            act_item.setFont(font)
            if parent:
                parent.appendRow([act_item])
            else:
                self.model.appendRow([act_item])
            if type(value_dict[not_selectable]) == dict:
                self.insert_dict(value_dict[not_selectable], act_item)
            else:
                for item in value_dict[not_selectable]:
                    act_item.appendRow([QStandardItem(item)])

    def get_value(self):
        value = ''
        act_index = self.tree_view.selectedIndexes()[0]
        act_item = act_index.model().itemFromIndex(act_index)
        value += act_item.text()
        while act_item.parent():
            value = '%s.%s' % (act_item.parent().text(), value)
            act_item = act_item.parent()
        return value

    def resize_length(self):
        self.showPopup()
