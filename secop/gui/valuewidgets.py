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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************

from __future__ import division, print_function

from secop.datatypes import ArrayOf, BLOBType, BoolType, EnumType, \
    FloatRange, IntRange, StringType, StructOf, TupleOf, TextType
from secop.gui.qt import QCheckBox, QComboBox, QDialog, QDoubleSpinBox, \
    QFrame, QGridLayout, QGroupBox, QLabel, QLineEdit, QSpinBox, QVBoxLayout, \
    QTextEdit
from secop.gui.util import loadUi

# XXX: implement live validators !!!!
# XXX: signals upon change of value
# XXX: honor readonly in all cases!

class StringWidget(QLineEdit):
    def __init__(self, datatype, readonly=False, parent=None):
        super(StringWidget, self).__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)

    def get_value(self):
        res = self.text()
        return self.datatype(res)

    def set_value(self, value):
        self.setText(value)


class TextWidget(QTextEdit):
    def __init__(self, datatype, readonly=False, parent=None):
        super(TextWidget, self).__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)

    def get_value(self):
        res = self.text()
        return self.datatype(res)

    def set_value(self, value):
        self.setPlainText(value)


class BlobWidget(StringWidget):
    #  XXX: make an editable hex-table ?
    pass


# or derive from widget and switch between combobox and radiobuttons?
class EnumWidget(QComboBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super(EnumWidget, self).__init__(parent)
        self.datatype = datatype

        self._map = {}
        self._revmap = {}
        for idx, member in enumerate(datatype._enum.members):
            self._map[idx] = member
            self._revmap[member.name] = idx
            self._revmap[member.value] = idx
            self.addItem(member.name, member.value)

    def get_value(self):
        return self._map[self.currentIndex()].value

    def set_value(self, value):
        self.setCurrentIndex(self._revmap[value])


class BoolWidget(QCheckBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super(BoolWidget, self).__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)

    def get_value(self):
        return self.isChecked()

    def set_value(self, value):
        self.setChecked(bool(value))


class IntWidget(QSpinBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super(IntWidget, self).__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)
        self.setMaximum(datatype.max)
        self.setMinimum(datatype.min)

    def get_value(self):
        return int(self.value())

    def set_value(self, value):
        self.setValue(int(value))


class FloatWidget(QDoubleSpinBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super(FloatWidget, self).__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)
        self.setMaximum(datatype.max or 1e6)  # XXX!
        self.setMinimum(datatype.min or 0)  # XXX!
        self.setDecimals(12)

    def get_value(self):
        return float(self.value())

    def set_value(self, value):
        self.setValue(float(value))


class TupleWidget(QFrame):
    def __init__(self, datatype, readonly=False, parent=None):
        super(TupleWidget, self).__init__(parent)

        self.datatypes = datatype.members

        self.layout = QVBoxLayout()
        self.subwidgets = []
        for t in self.datatypes:
            w = get_widget(t, readonly=readonly, parent=self)
            w.show()
            self.layout.addWidget(w)
            self.subwidgets.append(w)
        self.setLayout(self.layout)
        self.show()
        self.update()

    def get_value(self):
        return [v(w.get_value()) for w, v in zip(self.subwidgets, self.datatypes)]

    def set_value(self, value):
        for w, _ in zip(self.subwidgets, value):
            w.set_value(value)


class StructWidget(QGroupBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super(StructWidget, self).__init__(parent)

        self.layout = QGridLayout()
        self.subwidgets = {}
        self.datatypes = []
        self._labels = []
        for idx, name in enumerate(sorted(datatype.members)):
            dt = datatype.members[name]
            w = get_widget(dt, readonly=readonly, parent=self)
            l = QLabel(name)
            self.layout.addWidget(l, idx, 0)
            self.layout.addWidget(w, idx, 1)
            self._labels.append(l)
            self.subwidgets[name] = (w, dt)
            self.datatypes.append(dt)
        self.setLayout(self.layout)

    def get_value(self):
        res = {}
        for name, entry in self.subwidgets.items():
            w, dt = entry
            res[name] = dt(w.get_value())
        return res

    def set_value(self, value):
        for k, v in value.items():
            entry = self.subwidgets[k]
            w, dt = entry
            w.set_value(dt(v))


class ArrayWidget(QGroupBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super(ArrayWidget, self).__init__(parent)
        self.datatype = datatype.members

        self.layout = QVBoxLayout()
        self.subwidgets = []
        for _ in range(datatype.maxsize):
            w = get_widget(self.datatype, readonly=readonly, parent=self)
            self.layout.addWidget(w)
            self.subwidgets.append(w)
        self.setLayout(self.layout)

    def get_value(self):
        return [self.datatype(w.get_value()) for w in self.subwidgets]

    def set_value(self, values):
        for w, v in zip(self.subwidgets, values):
            w.set_value(v)



def get_widget(datatype, readonly=False, parent=None):
    return {FloatRange: FloatWidget,
     IntRange: IntWidget,
     StringType: StringWidget,
     TextType: TextWidget,
     BLOBType: BlobWidget,
     EnumType: EnumWidget,
     BoolType: BoolWidget,
     TupleOf: TupleWidget,
     StructOf: StructWidget,
     ArrayOf: ArrayWidget,
    }.get(datatype.__class__)(datatype, readonly, parent)


class msg(QDialog):
    def __init__(self, stuff, parent=None):
        super(msg, self).__init__(parent)
        loadUi(self, 'cmddialog.ui')
        print(dir(self))
        self.setWindowTitle('Please enter the arguments for calling command "blubb()"')
        row = 0

        self.gridLayout.addWidget(QLabel('struct'), row, 0)
        dt = StructOf(i=IntRange(0, 10), f=FloatRange(), b=BoolType())
        w = StructWidget(dt)
        self.gridLayout.addWidget(w, row, 1)
        row+=1

        self.gridLayout.addWidget(QLabel('stuff'), row, 0, 1, 0)
        row += 1  # at pos (0,0) span 2 cols, 1 row
        self.gridLayout.setRowStretch(row, 1)
        self.setModal(True)

    def accept(self):
        print('accepted')
        super(msg, self).accept()

    def reject(self):
        print('rejected')
        super(msg, self).reject()

    def done(self, how):
        print('done(%r)' % how)
        return super(msg, self).done(how)
