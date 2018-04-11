# pylint: disable=unused-import
from __future__ import print_function

try:
    from PyQt5 import uic
    from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QFont, QTextCursor, QFontMetrics
    from PyQt5.QtWidgets import QLabel, QWidget, QDialog, QLineEdit, QCheckBox, QPushButton, \
        QSizePolicy, QMainWindow, QMessageBox, QInputDialog, QTreeWidgetItem, QApplication, \
        QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton, QVBoxLayout, QHBoxLayout, \
        QGridLayout, QScrollArea, QFrame

    from xml.sax.saxutils import escape as toHtmlEscaped

except ImportError:
    from PyQt4 import uic
    from PyQt4.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
    from PyQt4.QtGui import QFont, QTextCursor, QFontMetrics, \
        QLabel, QWidget, QDialog, QLineEdit, QCheckBox, QPushButton, \
        QSizePolicy, QMainWindow, QMessageBox, QInputDialog, QTreeWidgetItem, QApplication, \
        QGroupBox, QSpinBox, QDoubleSpinBox, QComboBox, QRadioButton, QVBoxLayout, QHBoxLayout, \
        QGridLayout, QScrollArea, QFrame

    def toHtmlEscaped(s):
        return Qt.escape(s)
