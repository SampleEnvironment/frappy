#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2023 by the authors, see LICENSE
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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

from frappy.datatypes import StatusType
from frappy.gui.qt import QIcon, Qt, QTreeWidget, QTreeWidgetItem, pyqtSignal


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
        if 'status' not in parameters:
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
            if value.readerror:
                self.setIcon(self.display[parameter], ModuleItem.statusIcon(StatusType.ERROR))
                self.setText(self.display['status/text'], str(value.readerror))
            else:
                self.setIcon(self.display[parameter], ModuleItem.statusIcon(value.value[0].value))
                self.setText(self.display['status/text'], value.value[1])
        else:
            self.setText(self.display[parameter], value.formatted())

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
    # current module/param, prev module/param
    itemChanged = pyqtSignal(str, str)
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self._node = node
        self._modules = {}

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
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # self.customContextMenuRequested.connect(self._contextMenu)

        self._node.newData.connect(self._updateValue)
        self.currentItemChanged.connect(self.handleCurrentItemChanged)
        #self.itemDoubleClicked.connect(self.handleDoubleClick)

    # def handleDoubleClick(self, item, column):
    #     if item.hasTarget() and column == 2:
    #         self.editItem(item, column)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.itemAt(event.pos()) is None:
                self.clearTreeSelection()
        return super().mouseReleaseEvent(event)

    def handleCurrentItemChanged(self, current, previous):
        self.itemChanged.emit(current.module, current.param or '')

    def setToDisconnected(self):
        for module in self._modules.values():
            module.disconnected()

    def setToReconnected(self):
        """set status after connection is reestablished.

        If the node-description has changed during the reconnection, the nodewidget
        this overview is a part of gets replaced. However, the reconnect-event
        gets through before the descriptionChanged-event. So if a module is no
        longer present we return early in order to avoid KeyErrors on node.modules
        For the case of additional modules or changed module contents we do not care.
        """
        nodemods = self._node.modules.keys()
        for mname, module in self._modules.items():
            if mname not in nodemods:
                return # description changed and we will be replaced, return early
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
        selected = self.selectedItems()
        if not selected:
            return
        self.clearSelection()
        self.itemChanged.emit('', '')
        self.last_was_clear = True
