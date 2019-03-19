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

from secop.gui.qt import QWidget, Qt, QHBoxLayout, QSpacerItem, QSizePolicy
from secop.gui.cfg_editor.utils import loadUi


class NodeDisplay(QWidget):
    def __init__(self, file_path=None, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'node_display.ui')
        self.saved = True if file_path else False
        self.created = self.tree_widget.set_file(file_path)
        self.tree_widget.save_status_changed.connect(self.change_save_status)
        self.tree_widget.currentItemChanged.connect(self.set_scroll_area)
        self.scroll_area_layout.setAlignment(Qt.AlignTop)
        self.set_scroll_area(self.tree_widget.get_selected_item(), None)
        self.splitter.setSizes([1, 1])

    def change_save_status(self, saved):
        self.saved = saved

    def set_scroll_area(self, current, previous):
        self.remove_all_from_scroll_area(self.scroll_area_layout)
        self.scroll_area_layout.addWidget(current.widget)
        for index in range(0, current.childCount()):
            child_layout = QHBoxLayout()
            spacer = QSpacerItem(30, 0, QSizePolicy.Fixed,
                                 QSizePolicy.Minimum)
            child_layout.addSpacerItem(spacer)
            child_layout.addWidget(current.child(index).widget)
            self.scroll_area_layout.addLayout(child_layout)
            for sub_index in range(0, current.child(index).childCount()):
                sub_child_layout = QHBoxLayout()
                sub_spacer = QSpacerItem(60, 0, QSizePolicy.Fixed,
                                         QSizePolicy.Minimum)
                sub_child_layout.addSpacerItem(sub_spacer)
                sub_child_layout.addWidget(
                    current.child(index).child(sub_index).widget)
                self.scroll_area_layout.addLayout(sub_child_layout)

    def remove_all_from_scroll_area(self, layout):
        for index in range(layout.count()-1, -1, -1):
            item = layout.itemAt(index)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self.remove_all_from_scroll_area(item.layout())
