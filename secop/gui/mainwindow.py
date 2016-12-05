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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

from PyQt4.QtGui import QMainWindow, QInputDialog, QTreeWidgetItem
from PyQt4.QtCore import pyqtSignature as qtsig, QObject, pyqtSignal

from secop.gui.util import loadUi
from secop.gui.nodectrl import NodeCtrl
from secop.gui.modulectrl import ModuleCtrl
from secop.client.baseclient import Client as SECNode

ITEM_TYPE_NODE = QTreeWidgetItem.UserType + 1
ITEM_TYPE_MODULE = QTreeWidgetItem.UserType + 2
ITEM_TYPE_PARAMETER = QTreeWidgetItem.UserType + 3


class QSECNode(SECNode, QObject):
    newData = pyqtSignal(str, str, object) # module, parameter, data

    def __init__(self, opts, autoconnect=False, parent=None):
        SECNode.__init__(self, opts, autoconnect)
        QObject.__init__(self, parent)

        self.startup(True)
        self._subscribeCallbacks()

    def _subscribeCallbacks(self):
        for module in self.modules:
            self._subscribeModuleCallback(module)

    def _subscribeModuleCallback(self, module):
        for parameter in self.getParameters(module):
            self._subscribeParameterCallback(module, parameter)

    def _subscribeParameterCallback(self, module, parameter):
        self.register_callback(module, parameter, self._newDataReceived)

    def _newDataReceived(self, module, parameter, data):
        self.newData.emit(module, parameter, data)


class MainWindow(QMainWindow):

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        loadUi(self, 'mainwindow.ui')

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 70)

        self._nodes = {}
        self._nodeCtrls = {}
        self._currentWidget = self.splitter.widget(1).layout().takeAt(0)

        # add localhost if available
        self._addNode('localhost')

    @qtsig('')
    def on_actionAdd_SEC_node_triggered(self):
        host, ok = QInputDialog.getText(self, 'Add SEC node',
                                    'Enter SEC node hostname:')

        if not ok:
            return

        self._addNode(host)

    def on_treeWidget_currentItemChanged(self, current, previous):
        if current.type() == ITEM_TYPE_NODE:
            self._displayNode(current.text(0))
        elif current.type() == ITEM_TYPE_MODULE:
            self._displayModule(current.parent().text(0), current.text(0))

    def _addNode(self, host):

        # create client
        port = 10767
        if ':' in host:
            host, port = host.split(':', 1)
            port = int(port)
        node = QSECNode({'connectto':host, 'port':port}, parent=self)
        host = '%s:%d' % (host, port)

        self._nodes[host] = node

        # fill tree
        nodeItem = QTreeWidgetItem(None, [host], ITEM_TYPE_NODE)

        for module in sorted(node.modules):
            moduleItem = QTreeWidgetItem(nodeItem, [module], ITEM_TYPE_MODULE)
            for param in sorted(node.getParameters(module)):
                paramItem = QTreeWidgetItem(moduleItem, [param],
                                            ITEM_TYPE_PARAMETER)

        self.treeWidget.addTopLevelItem(nodeItem)

    def _displayNode(self, node):

        ctrl = self._nodeCtrls.get(node, None)

        if ctrl is None:
            ctrl = self._nodeCtrls[node] = NodeCtrl(self._nodes[node])

        self._replaceCtrlWidget(ctrl)

    def _displayModule(self, node, module):
        self._replaceCtrlWidget(ModuleCtrl(self._nodes[node], module))

    def _replaceCtrlWidget(self, new):
        old = self.splitter.widget(1).layout().takeAt(0)
        if old:
            old.widget().hide()
        self.splitter.widget(1).layout().addWidget(new)
        new.show()
        self._currentWidget = new
