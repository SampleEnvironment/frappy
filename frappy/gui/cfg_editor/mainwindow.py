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

from frappy.gui.qt import QMainWindow, QMessageBox

from frappy.gui.cfg_editor.node_display import NodeDisplay
from frappy.gui.cfg_editor.utils import get_file_paths, loadUi
from frappy.gui.cfg_editor.widgets import TabBar

# TODO move frappy mainwindow to gui/client and all specific stuff
NODE = 'node'
MODULE = 'module'
INTERFACE = 'interface'
PARAMETER = 'parameter'
PROPERTY = 'property'
COMMENT = 'comment'


class MainWindow(QMainWindow):

    def __init__(self, file_path=None, log=None, parent=None):
        super().__init__(parent)
        loadUi(self, 'mainwindow.ui')
        self.log = log
        self.tabWidget.currentChanged.connect(self.tab_relevant_btns_disable)
        if file_path is None:
            self.tab_relevant_btns_disable(-1)
        else:
            self.duplicate_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        self.tabWidget.setTabBar(TabBar())
        self.tabWidget.tabBar().tabCloseRequested.connect(self.close_tab)
        self.open_file(file_path)
        self.new_files = 0

    def on_actionNew(self):
        name = f'unnamed_{self.new_files}.cfg' if self.new_files else \
            'unnamed.cfg'
        self.new_node(name)
        self.new_files += 1

    def on_actionOpen(self):
        file_paths = get_file_paths(self)
        for file_path in file_paths:
            self.open_file(file_path)

    def on_actionSave(self):
        self.save_tab(self.tabWidget.currentIndex())

    def on_actionSave_as(self):
        self.save_tab(self.tabWidget.currentIndex(), True)

    def on_action_Close(self):
        self.close_tab(self.tabWidget.currentIndex())

    def on_actionQuit(self):
        self.close()

    def on_actionAbout(self):
        QMessageBox.about(
            self, 'About cfg-editor',
            '''
            <h2>About cfg-editor</h2>
            <p style="font-style: italic">
              (C) 2019 MLZ instrument control
            </p>
            <p>
              cfg-editor is a graphical interface for editing
              FRAPPY-configuration-files.
            </p>
            <h3>Author:</h3>
            <ul>
              <li>Copyright (C) 2019
                <a href="mailto:sandra.seger@frm2.tum.de">Sandra Seger</a>
                </li>
            </ul>
            <p>
              cfg-editor is published under the
              <a href="http://www.gnu.org/licenses/gpl.html">GPL
                (GNU General Public License)</a>
            </p>
            ''')

    def on_add_module(self):
        self.tabWidget.currentWidget().tree_widget.add_module()

    def on_add_interface(self):
        self.tabWidget.currentWidget().tree_widget.add_interface()

    def on_add_parameter(self):
        self.tabWidget.currentWidget().tree_widget.add_parameter()

    def on_add_property(self):
        self.tabWidget.currentWidget().tree_widget.add_property()

    def on_add_comment(self):
        self.tabWidget.currentWidget().tree_widget.add_comment()

    def on_duplicate(self):
        self.tabWidget.currentWidget().tree_widget.duplicate()

    def on_delete(self):
        self.tabWidget.currentWidget().tree_widget.delete()

    def open_file(self, file_path):
        for i in range(0, self.tabWidget.count()):
            if self.tabWidget.widget(i).tree_widget.file_path == file_path:
                self.tabWidget.setCurrentIndex(i)
                return
        if file_path:
            self.new_node(os.path.basename(file_path), file_path)

    def close_tab(self, index):
        if self.tabWidget.widget(index).saved:
            reply = QMessageBox.StandardButton.Close
        else:
            reply = self.show_save_message(self.tabWidget.tabText(index))
        if reply == QMessageBox.StandardButton.Cancel:
            return
        if reply == QMessageBox.StandardButton.Save:
            self.save_tab(index)
        self.tabWidget.removeTab(index)

    def save_tab(self, index, save_as=False):
        widget = self.tabWidget.widget(index)
        if widget.tree_widget.save(save_as):
            self.tabWidget.setTabText(index, os.path.basename(
                widget.tree_widget.file_path))

    def closeEvent(self, event):
        if self.tabWidget.count():
            reply = None
            for i in range(0, self.tabWidget.count()):
                if not self.tabWidget.widget(i).saved:
                    reply = self.show_save_message()
                    break
            if not reply:
                reply = QMessageBox.StandardButton.Close
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Save:
                for i in range(0, self.tabWidget.count()):
                    self.save_tab(i)
        event.accept()

    def show_save_message(self, file_name=''):
        if file_name:
            file_name = f' in "{file_name}"'
        return QMessageBox.question(self, 'Save file?', f'''
                                <h2>Do you want to save changes{file_name}?</h2>
                                <p>
                                Your changes will be lost if you don't save them!
                                </p>
                                ''',
                                    QMessageBox.StandardButton.Cancel |
                                    QMessageBox.StandardButton.Close |
                                    QMessageBox.StandardButton.Save,
                                    QMessageBox.StandardButton.Save)

    def new_node(self, name, file_path=None):
        node = NodeDisplay(file_path, self.log)
        if node.created:
            node.tree_widget.currentItemChanged.connect(self.disable_btns)
            self.tabWidget.setCurrentIndex(self.tabWidget.addTab(node, name))

    def disable_btns(self, current, previous):
        cur_kind = current.kind if current else None
        self.add_parameter_btn.setEnabled(True)
        self.add_property_btn.setEnabled(True)
        self.add_comment_btn.setEnabled(True)
        self.duplicate_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        if cur_kind is None:
            self.add_parameter_btn.setEnabled(False)
            self.add_property_btn.setEnabled(False)
            self.add_comment_btn.setEnabled(False)
            self.duplicate_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        elif cur_kind not in [MODULE, INTERFACE]:
            self.duplicate_btn.setEnabled(False)
        if cur_kind == NODE:
            self.duplicate_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
        elif cur_kind == INTERFACE:
            self.add_parameter_btn.setEnabled(False)
        elif cur_kind == PARAMETER:
            self.add_parameter_btn.setEnabled(False)
        elif cur_kind == PROPERTY:
            self.add_parameter_btn.setEnabled(False)
            self.add_property_btn.setEnabled(False)
        elif cur_kind == COMMENT:
            self.add_parameter_btn.setEnabled(False)
            self.add_property_btn.setEnabled(False)
            self.add_comment_btn.setEnabled(False)

    def tab_relevant_btns_disable(self, index):
        if index == -1:
            enable = False
            self.duplicate_btn.setEnabled(enable)
            self.delete_btn.setEnabled(enable)
        else:
            enable = True
        self.save_btn.setEnabled(enable)
        self.add_module_btn.setEnabled(enable)
        self.add_interface_btn.setEnabled(enable)
        self.add_parameter_btn.setEnabled(enable)
        self.add_property_btn.setEnabled(enable)
        self.add_comment_btn.setEnabled(enable)
