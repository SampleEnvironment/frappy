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

    from xml.sax.saxutils import escape as toHtmlEscaped

    from PyQt5 import uic
    from PyQt5.QtCore import QByteArray, QEvent, QMimeData, QObject, QPoint, \
        QPointF, QRectF, QSettings, QSize, Qt, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QBrush, QColor, QCursor, QDrag, QFont, \
        QFontMetrics, QIcon, QKeySequence, QMouseEvent, QPainter, QPalette, \
        QPen, QPixmap, QPolygonF, QStandardItem, QStandardItemModel, \
        QTextCursor
    from PyQt5.QtWidgets import QAction, QApplication, QCheckBox, QComboBox, \
        QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFrame, \
        QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, \
        QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, \
        QRadioButton, QScrollArea, QShortcut, QSizePolicy, QSpacerItem, \
        QSpinBox, QStyle, QStyleOptionTab, QStylePainter, QTabBar, \
        QTabWidget, QTextEdit, QToolButton, QTreeView, QTreeWidget, \
        QTreeWidgetItem, QVBoxLayout, QWidget

    import frappy.gui.cfg_editor.icon_rc_qt5

except ImportError:
    from PyQt4 import uic
    from PyQt4.QtCore import QObject, QPoint, QPointF, QRectF, QSize, Qt, \
        pyqtSignal, pyqtSlot
    from PyQt4.QtGui import QAbstractItemView, QAction, QApplication, QBrush, \
        QCheckBox, QColor, QComboBox, QDialog, QDialogButtonBox, \
        QDoubleSpinBox, QFileDialog, QFont, QFontMetrics, QFrame, \
        QGridLayout, QGroupBox, QHBoxLayout, QIcon, QInputDialog, QLabel, \
        QLineEdit, QMainWindow, QMenu, QMessageBox, QPainter, QPen, \
        QPlainTextEdit, QPolygonF, QPushButton, QRadioButton, QScrollArea, \
        QSizePolicy, QSpacerItem, QSpinBox, QStandardItem, \
        QStandardItemModel, QTabBar, QTextCursor, QTextEdit, QTreeView, \
        QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

    import frappy.gui.cfg_editor.icon_rc_qt4

    def toHtmlEscaped(s):
        return Qt.escape(s)
