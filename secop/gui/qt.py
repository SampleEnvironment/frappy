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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************
"""Import needed stuff from PyQt4/PyQt5"""

# pylint: disable=unused-import
from __future__ import division, print_function

import sys

try:
    # Do not abort on exceptions in signal handlers.
    # pylint: disable=unnecessary-lambda
    sys.excepthook = lambda *args: sys.__excepthook__(*args)

    from PyQt5 import uic
    from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QSize, QPointF, \
        QRectF
    from PyQt5.QtGui import QFont, QTextCursor, QFontMetrics, QColor, QBrush, \
        QPainter, QPolygonF, QPen
    from PyQt5.QtWidgets import QLabel, QWidget, QDialog, QLineEdit, QCheckBox, \
        QPushButton, QSizePolicy, QMainWindow, QMessageBox, QInputDialog, \
        QTreeWidgetItem, QApplication, QGroupBox, QSpinBox, QDoubleSpinBox, \
        QComboBox, QRadioButton, QVBoxLayout, QHBoxLayout, QGridLayout, \
        QScrollArea, QFrame

    from xml.sax.saxutils import escape as toHtmlEscaped

except ImportError:
    from PyQt4 import uic
    from PyQt4.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QSize, QPointF, QRectF
    from PyQt4.QtGui import QFont, QTextCursor, QFontMetrics, \
        QLabel, QWidget, QDialog, QLineEdit, QCheckBox, QPushButton, \
        QSizePolicy, QMainWindow, QMessageBox, QInputDialog, QTreeWidgetItem, QApplication, \
        QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton, QVBoxLayout, QHBoxLayout, \
        QGridLayout, QScrollArea, QFrame, QColor, QBrush, QPainter, QPolygonF, QPen

    def toHtmlEscaped(s):
        return Qt.escape(s)
