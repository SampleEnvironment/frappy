from frappy.gui.qt import QLabel, QMessageBox, QWidget, QLineEdit, \
        QPushButton, QIcon, pyqtSignal, QToolButton, QDialog
from frappy.gui.util import loadUi
from frappy.gui.valuewidgets import get_widget
import frappy.gui.resources # pylint: disable=unused-import

class CommandDialog(QDialog):
    def __init__(self, cmdname, argument, parent=None):
        super().__init__(parent)
        loadUi(self, 'cmddialog.ui')

        self.setWindowTitle('Arguments for %s' % cmdname)
        # row = 0

        self._labels = []
        self.widgets = []
        # improve! recursive?
        dtype = argument
        label = QLabel(repr(dtype))
        label.setWordWrap(True)
        widget = get_widget(dtype, readonly=False)
        self.gridLayout.addWidget(label, 0, 0)
        self.gridLayout.addWidget(widget, 0, 1)
        self._labels.append(label)
        self.widgets.append(widget)

        self.gridLayout.setRowStretch(1, 1)
        self.setModal(True)
        self.resize(self.sizeHint())

    def get_value(self):
        return True, self.widgets[0].get_value()

    def exec_(self):
        if super().exec_():
            return self.get_value()
        return None


def showCommandResultDialog(command, args, result, extras=''):
    m = QMessageBox()
    args = '' if args is None else repr(args)
    m.setText('calling: %s(%s)\nyielded: %r\nqualifiers: %s' %
              (command, args, result, extras))
    m.exec_()


def showErrorDialog(command, args, error):
    m = QMessageBox()
    args = '' if args is None else repr(args)
    m.setText('calling: %s(%s)\nraised %r' % (command, args, error))
    m.exec_()


class CommandButton(QPushButton):
    def __init__(self, cmdname, cmdinfo, cb, parent=None):
        super().__init__(parent)

        self._cmdname = cmdname
        self._argintype = cmdinfo['datatype'].argument   # single datatype
        self.result = cmdinfo['datatype'].result
        self._cb = cb  # callback function for exection

        self.setText(cmdname)
        if cmdinfo['description']:
            self.setToolTip(cmdinfo['description'])
        self.pressed.connect(self.on_pushButton_pressed)

    def on_pushButton_pressed(self):
        #self.setEnabled(False)
        if self._argintype:
            dlg = CommandDialog(self._cmdname, self._argintype)
            args = dlg.exec_()
            if args:  # not 'Cancel' clicked
                self._cb(self._cmdname, args[1])
        else:
            # no need for arguments
            self._cb(self._cmdname, None)
        #self.setEnabled(True)


class ModuleWidget(QWidget):
    plot = pyqtSignal(str)
    plotAdd = pyqtSignal(str)
    def __init__(self, node, name, parent=None):
        super().__init__()
        loadUi(self, 'modulewidget.ui')
        self._node = node
        self._name = name
        self._paramDisplays = {}
        self._paramInputs = {}
        self._addbtns = []
        self._paramWidgets = {}

        self.moduleName.setText(name)
        props = self._node.getModuleProperties(self._name)
        description = props.get('description', '')
        self.moduleDescription.setText(description)

        row = 0
        params = dict(self._node.getParameters(self._name))
        if 'status' in params:
            params.pop('status')
            self._addRParam('status', row)
            row += 1
        if 'value' in params:
            params.pop('value')
            self._addRParam('value', row)
            row += 1
        if 'target' in params:
            params.pop('target')
            self._addRWParam('target', row)
            row += 1
        for param in params:
            paramProps = self._node.getProperties(self._name, param)
            if paramProps['readonly']:
                self._addRParam(param, row)
            else:
                self._addRWParam(param, row)
            row += 1
            self._setParamHidden(param, True)

        self._addCommands(row)

        cache = self._node.queryCache(self._name)
        for param, val in cache.items():
            self._updateValue(self._name, param, val)

        node.newData.connect(self._updateValue)

    def _updateValue(self, mod, param, val):
        if mod != self._name:
            return
        if param in self._paramDisplays:
            # TODO: stopgap
            if val.readerror:
                strvalue = str(val)
            else:
                strvalue = ('%g' if isinstance(val.value, float)
                            else '%s') % (val.value,)
            self._paramDisplays[param].setText(strvalue)

    def _addRParam(self, param, row):
        props = self._node.getProperties(self._name, param)

        nameLabel = QLabel(param)
        unitLabel = QLabel(props.get('unit', ''))
        display = QLineEdit()

        self._paramDisplays[param] = display
        self._paramWidgets[param] = [nameLabel, unitLabel, display]

        l = self.moduleDisplay.layout()
        l.addWidget(nameLabel, row,0,1,1)
        l.addWidget(display, row,1,1,5)
        l.addWidget(unitLabel, row,6)
        self._addPlotButtons(param, row)

    def _addRWParam(self, param, row):
        props = self._node.getProperties(self._name, param)

        nameLabel = QLabel(param)
        unitLabel = QLabel(props.get('unit', ''))
        unitLabel2 = QLabel(props.get('unit', ''))
        display = QLineEdit()
        inputEdit = QLineEdit()
        submitButton = QPushButton('Go')
        submitButton.setIcon(QIcon(':/icons/submit'))

        submitButton.pressed.connect(lambda: self._button_pressed(param))
        inputEdit.returnPressed.connect(lambda: self._button_pressed(param))
        self._paramDisplays[param] = display
        self._paramInputs[param] = inputEdit
        self._paramWidgets[param] = [nameLabel, unitLabel, unitLabel2,
                                     display, inputEdit, submitButton]

        l = self.moduleDisplay.layout()
        l.addWidget(nameLabel, row,0,1,1)
        l.addWidget(display, row,1,1,2)
        l.addWidget(unitLabel, row,3,1,1)
        l.addWidget(inputEdit, row,4,1,2)
        l.addWidget(unitLabel2, row,6,1,1)
        l.addWidget(submitButton, row, 7)
        self._addPlotButtons(param, row)

    def _addPlotButtons(self, param, row):
        if param == 'status':
            return
        plotButton = QToolButton()
        plotButton.setIcon(QIcon(':/icons/plot'))
        plotButton.setToolTip('Plot %s' % param)
        plotAddButton = QToolButton()
        plotAddButton.setIcon(QIcon(':/icons/plot-add'))
        plotAddButton.setToolTip('Plot With...')

        plotButton.clicked.connect(lambda: self.plot.emit(param))
        plotAddButton.clicked.connect(lambda: self.plotAdd.emit(param))

        self._addbtns.append(plotAddButton)
        plotAddButton.setDisabled(True)
        self._paramWidgets[param].append(plotButton)
        self._paramWidgets[param].append(plotAddButton)

        l = self.moduleDisplay.layout()
        l.addWidget(plotButton, row, 8)
        l.addWidget(plotAddButton, row, 9)

    def _addCommands(self, startrow):
        cmdicons = {
            'stop': QIcon(':/icons/stop'),
        }
        cmds = self._node.getCommands(self._name)
        if not cmds:
            return

        l = self.moduleDisplay.layout()
        # max cols in GridLayout, find out programmatically?
        maxcols = 7
        l.addWidget(QLabel('Commands:'))
        for (i, cmd) in enumerate(cmds):
            cmdb = CommandButton(cmd, cmds[cmd], self._execCommand)
            if cmd in cmdicons:
                cmdb.setIcon(cmdicons[cmd])
            row = startrow + i // maxcols
            col = (i % maxcols) + 1
            l.addWidget(cmdb, row, col)


    def _execCommand(self, command, args=None):
        try:
            result, qualifiers = self._node.execCommand(
                self._name, command, args)
        except Exception as e:
            showErrorDialog(command, args, e)
            return
        if result is not None:
            showCommandResultDialog(command, args, result, qualifiers)

    def _setParamHidden(self, param, hidden):
        for w in self._paramWidgets[param]:
            w.setHidden(hidden)

    def _setGroupHidden(self, group):
        pass

    def rebuildAdvanced(self, advanced):
        for param in self._paramWidgets:
            if param in ['value', 'status', 'target']:
                continue
            self._setParamHidden(param, not advanced)

    def _button_pressed(self, param):
        target = self._paramInputs[param].text()
        try:
            self._node.setParameter(self._name, param, target)
        except Exception as e:
            QMessageBox.warning(self.parent(), 'Operation failed', str(e))

    def plotsPresent(self, present):
        for btn in self._addbtns:
            btn.setDisabled(present)
