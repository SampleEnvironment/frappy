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

import sys

try:
    # Do not abort on exceptions in signal handlers.
    # pylint: disable=unnecessary-lambda
    sys.excepthook = lambda *args: sys.__excepthook__(*args)

    from PyQt5 import uic
    from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QSize, QPointF, \
        QRectF, QPoint, QByteArray, QEvent, QMimeData, QSettings
    from PyQt5.QtGui import QFont, QTextCursor, QFontMetrics, QColor, QBrush, \
        QPainter, QPolygonF, QPen, QIcon, QStandardItemModel, QStandardItem, \
        QPalette, QCursor, QDrag, QMouseEvent, QPixmap, QKeySequence
    from PyQt5.QtWidgets import QLabel, QWidget, QDialog, QLineEdit, QCheckBox, \
        QPushButton, QSizePolicy, QMainWindow, QMessageBox, QInputDialog, \
        QTreeWidgetItem, QApplication, QGroupBox, QSpinBox, QDoubleSpinBox, \
        QComboBox, QRadioButton, QVBoxLayout, QHBoxLayout, QGridLayout, \
        QScrollArea, QFrame, QTreeWidget, QFileDialog, QTabBar, QAction, QMenu,\
        QDialogButtonBox, QTextEdit, QSpacerItem, QTreeView, QStyle, \
        QStyleOptionTab, QStylePainter, QTabWidget, QToolButton, QShortcut, \
        QPlainTextEdit

    from xml.sax.saxutils import escape as toHtmlEscaped

    import frappy.gui.cfg_editor.icon_rc_qt5

except ImportError:
    from PyQt4 import uic
    from PyQt4.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QSize, QPointF, QRectF, QPoint
    from PyQt4.QtGui import QFont, QTextCursor, QFontMetrics, \
        QLabel, QWidget, QDialog, QLineEdit, QCheckBox, QPushButton, QTextEdit,\
        QSizePolicy, QMainWindow, QMessageBox, QInputDialog, QTreeWidgetItem, QApplication, \
        QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton, QVBoxLayout, QHBoxLayout, \
        QGridLayout, QScrollArea, QFrame, QColor, QBrush, QPainter, QPolygonF, QPen, QIcon, \
        QTreeWidget, QFileDialog, QTabBar, QAction, QMenu, QDialogButtonBox, QAbstractItemView, \
        QSpacerItem, QTreeView, QStandardItemModel, QStandardItem, QPlainTextEdit

    import frappy.gui.cfg_editor.icon_rc_qt4

    def toHtmlEscaped(s):
        return Qt.escape(s)
