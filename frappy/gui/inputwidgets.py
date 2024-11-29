import sys

from frappy.gui.qt import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, \
    QSpinBox, pyqtSignal

from frappy.datatypes import BoolType, EnumType, FloatRange, IntRange, \
    StringType, TextType

# ArrayOf, BLOBType, FloatRange, IntRange, StringType, StructOf, TextType, TupleOf


def get_input_widget(datatype, parent=None):
    return {
        EnumType: EnumInput,
        BoolType: BoolInput,
        IntRange: IntInput,
        StringType: StringInput,
        TextType: StringInput,
    }.get(datatype.__class__, GenericInput)(datatype, parent)


class InputBase:
    submitted = pyqtSignal()
    input_feedback = pyqtSignal(str)

    def get_input(self):
        raise NotImplementedError

    def submit(self):
        self.submitted.emit()


class GenericInput(InputBase, QLineEdit):
    def __init__(self, datatype, parent=None):
        super().__init__(parent)
        self.datatype = datatype
        self.setPlaceholderText('new value')
        self.returnPressed.connect(self.submit)

    def get_input(self):
        return self.datatype.from_string(self.text())


class StringInput(GenericInput):
    def __init__(self, datatype, parent=None):
        super().__init__(datatype, parent)


class IntInput(InputBase, QSpinBox):
    def __init__(self, datatype, parent=None):
        super().__init__(parent)
        self.datatype = datatype
        # we dont use setMaximum and setMinimum because it is quite restrictive
        # when typing, so set it as high as possible
        self.setMaximum(2147483647)
        self.setMinimum(-2147483648)

        self.lineEdit().returnPressed.connect(self.submit)

    def get_input(self):
        return self.datatype(self.value())


class EnumInput(InputBase, QComboBox):
    def __init__(self, datatype, parent=None):
        super().__init__(parent)
        self.setPlaceholderText('choose value')
        self.datatype = datatype

        self._map = {}
        self._revmap = {}
        for idx, member in enumerate(datatype._enum.members):
            self._map[idx] = member
            self._revmap[member.name] = idx
            self._revmap[member.value] = idx
            self.addItem(member.name, member.value)

    def get_input(self):
        return self._map[self.currentIndex()].value


class BoolInput(InputBase, QCheckBox):
    def __init__(self, datatype, parent=None):
        super().__init__(parent)
        self.datatype = datatype

    def get_input(self):
        return self.isChecked()
