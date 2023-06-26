from frappy.gui.qt import QCheckBox, QComboBox, QLineEdit, pyqtSignal

from frappy.datatypes import BoolType, EnumType

# ArrayOf, BLOBType, FloatRange, IntRange, StringType, StructOf, TextType, TupleOf


def get_input_widget(datatype, parent=None):
    return {
        EnumType: EnumInput,
        BoolType: BoolInput,
    }.get(datatype.__class__, GenericInput)(datatype, parent)


class GenericInput(QLineEdit):
    submitted = pyqtSignal()
    def __init__(self, datatype, parent=None):
        super().__init__(parent)
        self.datatype = datatype
        self.setPlaceholderText('new value')
        self.returnPressed.connect(self.submit)

    def get_input(self):
        return self.datatype.from_string(self.text())

    def submit(self):
        self.submitted.emit()


class EnumInput(QComboBox):
    submitted = pyqtSignal()
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

    def submit(self):
        self.submitted.emit()


class BoolInput(QCheckBox):
    submitted = pyqtSignal()
    def __init__(self, datatype, parent=None):
        super().__init__(parent)
        self.datatype = datatype

    def get_input(self):
        return self.isChecked()

    def submit(self):
        self.submitted.emit()
