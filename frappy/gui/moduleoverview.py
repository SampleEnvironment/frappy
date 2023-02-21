import frappy.gui.resources # pylint: disable=unused-import
from frappy.gui.qt import QTreeWidget, QTreeWidgetItem, pyqtSignal, QIcon, Qt

class ParamItem(QTreeWidgetItem):
    def __init__(self, node, module, param):
        super().__init__()
        self.module = module
        self.param = param
        self.setText(0, param)


class ModuleItem(QTreeWidgetItem):
    display = {'status': 0, 'value': 1, 'target': 2, 'status/text': 3}

    def __init__(self, node, module):
        super().__init__()
        ModuleItem._loadicons()
        self.module = module
        self.param = None
        #self._expanded = False
        #self._params = {}

        parameters = node.getParameters(module)
        self._hasTarget = 'target' in parameters
        #if self._hasTarget:
        #    self.setFlags(self.flags() | Qt.ItemIsEditable)
        if 'value' in parameters:
            props = node.getProperties(self.module, 'value')
            self._unit = props.get('unit', '')
        else:
            self.setIcon(self.display['status'], ModuleItem.icons['clear'])

        self.setText(0, self.module)
        # initial read
        cache = node.queryCache(self.module)
        for param, val in cache.items():
            self.valueChanged(param, val)

        self.params = []
        for param in parameters:
            self.params.append(ParamItem(node, module, param))

    @classmethod
    def _loadicons(cls):
        if hasattr(cls, 'icons'):
            return
        cls.icons = {
            'disabled': QIcon(':/leds/gray'),
            'idle': QIcon(':/leds/green'),
            'warn':QIcon(':/leds/orange'),
            'error': QIcon(':/leds/red'),
            'busy': QIcon(':/leds/yellow'),
            'unknown': QIcon(':/leds/unknown'),
            'clear': QIcon(':/leds/clear'),
        }

    @classmethod
    def statusIcon(cls, statuscode):
        if statuscode == 0:
            return ModuleItem.icons['disabled']
        if statuscode in range(100, 200):
            return ModuleItem.icons['idle']
        if statuscode in range(200, 300):
            return ModuleItem.icons['warn']
        if statuscode in range(300, 400):
            return ModuleItem.icons['busy']
        if statuscode in range(400, 500):
            return ModuleItem.icons['error']
        return ModuleItem.icons['clear']

    def valueChanged(self, parameter, value):
        if parameter not in self.display:
            return
        if parameter == 'status':
            self.setIcon(self.display[parameter], ModuleItem.statusIcon(value.value[0].value))
            self.setText(self.display['status/text'], value.value[1])
        else:
            # TODO: stopgap
            if value.readerror:
                strvalue = str(value)
            else:
                strvalue = ('%g' if isinstance(value.value, float)
                            else '%s') % (value.value,)
            self.setText(self.display[parameter], '%s %s' % (strvalue, self._unit))

    def disconnected(self):
        self.setIcon(self.display['status'], ModuleItem.icons['unknown'])

    def setClearIcon(self):
        self.setIcon(self.display['status'], ModuleItem.icons['clear'])

    def hasTarget(self):
        return self._hasTarget


    def _rebuildAdvanced(self, advanced):
        if advanced:
            self.addChildren(self.params)
        else:
            for p in self.params:
                self.removeChild(p)


class ModuleOverview(QTreeWidget):
    itemChanged = pyqtSignal(str, str, str, str)
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self._node = node
        self._modules = {}
        self.last_was_clear = False

        #self.setHeaderHidden(True)
        #self.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)
        self.setRootIsDecorated(False)
        self.setExpandsOnDoubleClick(False)
        self.setColumnCount(4)
        header = self.headerItem()
        header.setText(0, 'Name')
        header.setText(1, 'Value')
        header.setText(2, 'Target')
        header.setText(3, 'Status')
        for module in sorted(self._node.modules):
            mod = ModuleItem(self._node, module)
            self._modules[module] = mod
            self.addTopLevelItem(mod)
        self._resizeColumns()

        self.itemExpanded.connect(self._resizeColumns)
        self.itemCollapsed.connect(self._resizeColumns)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.customContextMenuRequested.connect(self._contextMenu)

        self._node.newData.connect(self._updateValue)
        self.currentItemChanged.connect(self.handleCurrentItemChanged)
        #self.itemDoubleClicked.connect(self.handleDoubleClick)

   # def handleDoubleClick(self, item, column):
   #     if item.hasTarget() and column == 2:
   #         self.editItem(item, column)

    def handleCurrentItemChanged(self, current, previous):
        if previous is None or self.last_was_clear:
            pmod = ''
            pparam = ''
            self.last_was_clear = False
        else:
            pmod = previous.module
            pparam = previous.param or ''
        cparam = current.param or ''
        self.itemChanged.emit(current.module, cparam, pmod, pparam)

    def setToDisconnected(self):
        for module in self._modules.values():
            module.disconnected()

    def setToReconnected(self):
        for mname, module in self._modules.items():
            cache = self._node.queryCache(mname)
            if not 'status' in cache:
                module.setClearIcon()
                continue
            module.valueChanged('status', cache['status'])

    def _updateValue(self, module, parameter, value):
        self._modules[module].valueChanged(parameter, value)

    def _rebuildAdvanced(self, advanced):
        self.setRootIsDecorated(advanced)
        for module in self._modules.values():
            module._rebuildAdvanced(advanced)
        self._resizeColumns()

    def _resizeColumns(self):
        for i in range(self.columnCount()):
            self.resizeColumnToContents(i)

    def clearTreeSelection(self):
        prev = self.selectedItems()[0]
        pmod, pparam = prev.module, prev.param
        self.clearSelection()
        self.itemChanged.emit('', '', pmod, pparam)
        self.last_was_clear = True
