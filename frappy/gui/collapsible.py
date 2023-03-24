#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2023 by the authors, see LICENSE
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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

from frappy.gui.qt import QFrame, QGridLayout, QSizePolicy, Qt, QToolButton, \
    QVBoxLayout, QWidget


class CollapsibleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.button = QToolButton()
        self.widget = QWidget()
        self.widgetContainer = QWidget()

        self.button.setArrowType(Qt.ArrowType.RightArrow)
        self.button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setStyleSheet("QToolButton { border: none; }")
        self.button.setCheckable(True)
        self.button.toggled.connect(self._collapse)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Maximum)

        l = QVBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        l.addWidget(self.widget)
        self.widgetContainer.setLayout(l)
        self.widgetContainer.setMaximumHeight(0)

        layout = QGridLayout()
        layout.addWidget(self.button, 0, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(line, 0, 1, 1, 1)
        layout.addWidget(self.widgetContainer, 1, 0, -1, -1)
        layout.setContentsMargins(0, 6, 0, 0)
        self.setLayout(layout)

    def _collapse(self, expand):
        if expand:
            self.button.setArrowType(Qt.ArrowType.DownArrow)
            self.widgetContainer.setMaximumHeight(self.widget.maximumHeight())
        else:
            self.button.setArrowType(Qt.ArrowType.RightArrow)
            self.widgetContainer.setMaximumHeight(0)
            self.setMaximumHeight(self.button.maximumHeight())

    def replaceWidget(self, widget):
        layout = self.widgetContainer.layout()
        layout.removeWidget(self.widget)
        self.widget = widget
        layout.addWidget(self.widget)

    def setTitle(self, title):
        self.button.setText(title)

    def getWidget(self):
        return self.widget
