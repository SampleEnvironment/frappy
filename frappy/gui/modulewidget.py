from frappy.gui.qt import QColor, QDialog, QHBoxLayout, QIcon, QLabel, \
    QLineEdit, QMessageBox, QPropertyAnimation, QPushButton, Qt, QToolButton, \
    QWidget, pyqtProperty, pyqtSignal, pyqtSlot

from frappy.gui.util import Colors, loadUi
from frappy.gui.valuewidgets import get_widget


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

    def exec(self):
        if super().exec():
            return self.get_value()
        return None


def showCommandResultDialog(command, args, result, extras=''):
    m = QMessageBox()
    args = '' if args is None else repr(args)
    m.setText('calling: %s(%s)\nyielded: %r\nqualifiers: %s' %
              (command, args, result, extras))
    m.exec()


def showErrorDialog(command, args, error):
    m = QMessageBox()
    args = '' if args is None else repr(args)
    m.setText('calling: %s(%s)\nraised %r' % (command, args, error))
    m.exec()


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
            args = dlg.exec()
            if args:  # not 'Cancel' clicked
                self._cb(self._cmdname, args[1])
        else:
            # no need for arguments
            self._cb(self._cmdname, None)
        #self.setEnabled(True)


class AnimatedLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.backgroundColor = self.palette().color(self.backgroundRole())
        self.animation = QPropertyAnimation(self, b"bgColor", self)
        self.animation.setDuration(350)
        self.animation.setStartValue(Colors.colors['yellow'])
        self.animation.setEndValue(self.backgroundColor)

    @pyqtProperty(QColor)
    def bgColor(self):
        return self.palette().color(self.backgroundRole())

    @bgColor.setter
    def bgColor(self, color):
        p = self.palette()
        p.setColor(self.backgroundRole(), color)
        self.setPalette(p)

    def triggerAnimation(self):
        self.animation.start()


class AnimatedLabelHandthrough(QWidget):
    """This class is a crutch for the failings of the current grouping
    implementation. TODO: It has to be removed in the grouping rework """
    def __init__(self, label, btn, parent=None):
        super().__init__(parent)
        self.label = label
        box = QHBoxLayout()
        box.addWidget(label)
        box.addWidget(btn)
        self.setLayout(box)

    def triggerAnimation(self):
        self.label.triggerAnimation()


class ModuleWidget(QWidget):
    plot = pyqtSignal(str)
    plotAdd = pyqtSignal(str)
    def __init__(self, node, name, parent=None):
        super().__init__(parent)
        loadUi(self, 'modulewidget.ui')
        self._node = node
        self._name = name
        self.detailed = False
        self._paramDisplays = {}
        self._paramInputs = {}
        self._addbtns = []
        self._paramWidgets = {}
        self._groups = {}
        self._groupStatus = {}
        self.independentParams = []

        self._initModuleInfo()
        self.infoGrid.hide()

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

        allGroups = set()
        for param in params:
            props = self._node.getProperties(self._name, param)
            group = props.get('group', '')
            if group:
                allGroups.add(group)
                self._groups.setdefault(group, []).append(param)
            else:
                self.independentParams.append(param)
        for key in sorted(allGroups.union(set(self.independentParams))):
            if key in allGroups:
                if key in self._groups[key]:
                    # Param with same name as group
                    self._addParam(key, row)
                    name = AnimatedLabel(key)
                    button = QToolButton()
                    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                    button.setText('+')
                    button.pressed.connect(
                        lambda group=key: self._toggleGroupCollapse(group))
                    groupLabel = AnimatedLabelHandthrough(name, button)

                    l = self.moduleDisplay.layout()
                    label = l.itemAtPosition(row, 0).widget()
                    l.replaceWidget(label, groupLabel)
                    row += 1
                    old = self._paramWidgets[key].pop(0)
                    old.setParent(None)
                    self._paramWidgets[key].insert(0, groupLabel)
                    self._setParamHidden(key, True)
                else:
                    name = AnimatedLabel(key)
                    button = QToolButton()
                    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                    button.setText('+')
                    button.pressed.connect(
                        lambda group=key: self._toggleGroupCollapse(group))
                    box = QHBoxLayout()
                    box.addWidget(name)
                    box.addWidget(button)
                    groupLabel = QWidget()
                    groupLabel.setLayout(box)

                    l = self.moduleDisplay.layout()
                    l.addWidget(groupLabel, row, 0)
                    row += 1
                    self._paramWidgets[key] = [groupLabel]
                    self._groups[key].append(key)
                    self._setParamHidden(key, True)
                for p in self._groups[key]:
                    if p == key:
                        continue
                    self._addParam(p, row)
                    row += 1
                    self._setParamHidden(p, True)
            else:
                self._addParam(key, row)
                row += 1
                self._setParamHidden(key, True)

        self._addCommands(row)

        cache = self._node.queryCache(self._name)
        for param, val in cache.items():
            self._updateValue(self._name, param, val)

        node.newData.connect(self._updateValue)

    def _initModuleInfo(self):
        props = dict(self._node.getModuleProperties(self._name))
        self.moduleName.setText(self._name)
        self.moduleDescription.setText(props.get('description',
                                                 'no description provided'))

        self.groupInfo.setText(props.get('group', '-'))
        feats = ','.join(props.get('features', [])) or '-'
        self.featuresInfo.setText(feats)
        self.implementationInfo.setText(props.pop('implementation', 'MISSING'))
        ifaces = ','.join(props.pop('interface_classes', [])) or '-'
        self.interfaceClassesInfo.setText(ifaces)

        # any additional properties are added after the standard ones
        row = 2
        count = 0
        for prop, value in props.items():
            l = QHBoxLayout()
            l.setContentsMargins(0,0,0,0)
            name = QLabel('<b>%s:</b>' % prop.capitalize())
            val = QLabel(str(value))
            val.setWordWrap(True)
            l.addWidget(name)
            l.addWidget(val)
            additional = QWidget()
            additional.setLayout(l)
            self.infoGrid.layout().addWidget(
                additional, row + count // 2, count % 2)
            count += 1

    @pyqtSlot()
    def on_showDetailsBtn_pressed(self):
        self.showDetails(not self.detailed)

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

    def _addParam(self, param, row):
        paramProps = self._node.getProperties(self._name, param)
        if paramProps['readonly']:
            self._addRParam(param, row)
        else:
            self._addRWParam(param, row)

    def _addRParam(self, param, row):
        props = self._node.getProperties(self._name, param)

        nameLabel = AnimatedLabel(param)
        unitLabel = QLabel(props.get('unit', ''))
        display = QLineEdit()

        p = display.palette()
        p.setColor(display.backgroundRole(), Colors.palette.window().color())
        display.setPalette(p)
        self._paramDisplays[param] = display
        self._paramWidgets[param] = [nameLabel, unitLabel, display]

        l = self.moduleDisplay.layout()
        l.addWidget(nameLabel, row,0,1,1)
        l.addWidget(display, row,1,1,5)
        l.addWidget(unitLabel, row,6)
        self._addPlotButtons(param, row)

    def _addRWParam(self, param, row):
        props = self._node.getProperties(self._name, param)

        nameLabel = AnimatedLabel(param)
        unitLabel = QLabel(props.get('unit', ''))
        unitLabel2 = QLabel(props.get('unit', ''))
        display = QLineEdit()
        inputEdit = QLineEdit()
        submitButton = QPushButton('set')
        submitButton.setIcon(QIcon(':/icons/submit'))

        inputEdit.setPlaceholderText('new value')
        p = display.palette()
        p.setColor(display.backgroundRole(), Colors.palette.window().color())
        display.setPalette(p)
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

    def _toggleGroupCollapse(self, group):
        collapsed = not self._groupStatus.get(group, True)
        self._groupStatus[group] = collapsed
        for param in self._groups[group]:
            if param == group: # dont hide the top level
                continue
            self._setParamHidden(param, collapsed)

    def _setGroupHidden(self, group, show):
        for param in self._groups[group]:
            if show and param == group: # dont hide the top level
                self._setParamHidden(param, False)
            elif show and self._groupStatus.get(group, False):
                self._setParamHidden(param, False)
            else:
                self._setParamHidden(param, True)

    def showDetails(self, show):
        self.detailed = show
        self.infoGrid.setHidden(not show)
        for param in self.independentParams:
            if param in ['value', 'status', 'target']:
                continue
            self._setParamHidden(param, not show)
        for group in self._groups:
            self._setGroupHidden(group, show)

    def _button_pressed(self, param):
        target = self._paramInputs[param].text()
        try:
            self._node.setParameter(self._name, param, target)
        except Exception as e:
            QMessageBox.warning(self.parent(), 'Operation failed', str(e))

    def plotsPresent(self, present):
        for btn in self._addbtns:
            btn.setDisabled(present)
