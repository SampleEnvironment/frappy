# *****************************************************************************
# Copyright (c) 2015-2024 by the authors, see LICENSE
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


from frappy.gui.qt import QCheckBox, QComboBox, QDoubleSpinBox, \
    QFrame, QGridLayout, QGroupBox, QLabel, QLineEdit, QSpinBox, QTextEdit, \
    QVBoxLayout

from frappy.datatypes import ArrayOf, BLOBType, BoolType, EnumType, \
    FloatRange, IntRange, StringType, StructOf, TextType, TupleOf


# XXX: implement live validators !!!!
# XXX: signals upon change of value
# XXX: honor readonly in all cases!

class StringWidget(QLineEdit):
    def __init__(self, datatype, readonly=False, parent=None):
        super().__init__(parent)
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
        super().__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)

    def get_value(self):
        res = self.toPlainText()
        return self.datatype(res)

    def set_value(self, value):
        self.setPlainText(value)


class BlobWidget(StringWidget):
    #  XXX: make an editable hex-table ?
    pass


# or derive from widget and switch between combobox and radiobuttons?
class EnumWidget(QComboBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super().__init__(parent)
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
        super().__init__(parent)
        self.datatype = datatype
        if readonly:
            self.setEnabled(False)

    def get_value(self):
        return self.isChecked()

    def set_value(self, value):
        self.setChecked(bool(value))


class IntWidget(QSpinBox):
    def __init__(self, datatype, readonly=False, parent=None):
        super().__init__(parent)
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
        super().__init__(parent)
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
        super().__init__(parent)

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
        super().__init__(parent)

        self.layout = QGridLayout()
        self.subwidgets = {}
        self.datatypes = []
        self._labels = []
        for idx, name in enumerate(sorted(datatype.members)):
            dt = datatype.members[name]
            widget = get_widget(dt, readonly=readonly, parent=self)
            label = QLabel(name)
            self.layout.addWidget(label, idx, 0)
            self.layout.addWidget(widget, idx, 1)
            self._labels.append(label)
            self.subwidgets[name] = (widget, dt)
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
        super().__init__(parent)
        self.datatype = datatype.members

        self.layout = QVBoxLayout()
        self.subwidgets = []
        for _ in range(datatype.maxlen):
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
    return {
        FloatRange: FloatWidget,
        IntRange: IntWidget,
        StringType: StringWidget,
        TextType: TextWidget,
        BLOBType: BlobWidget,
        EnumType: EnumWidget,
        BoolType: BoolWidget,
        TupleOf: TupleWidget,
        StructOf: StructWidget,
        ArrayOf: ArrayWidget,
    }.get(datatype.__class__, TextWidget)(datatype, readonly, parent)
# TODO: handle NoneOr
