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

from __future__ import print_function

import sys

from secop.gui.qt import QMainWindow, QInputDialog, QTreeWidgetItem, QMessageBox, \
    pyqtSlot, QObject, pyqtSignal

from secop.gui.util import loadUi
from secop.gui.nodectrl import NodeCtrl
from secop.gui.modulectrl import ModuleCtrl
from secop.gui.paramview import ParameterView
from secop.client.baseclient import Client as SECNode


ITEM_TYPE_NODE = QTreeWidgetItem.UserType + 1
ITEM_TYPE_GROUP = QTreeWidgetItem.UserType + 2
ITEM_TYPE_MODULE = QTreeWidgetItem.UserType + 3
ITEM_TYPE_PARAMETER = QTreeWidgetItem.UserType + 4


class QSECNode(SECNode, QObject):
    newData = pyqtSignal(str, str, object)  # module, parameter, data

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

        self.toolBar.hide()

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 70)
        self.splitter.setSizes([50, 500])

        self._nodes = {}
        self._nodeCtrls = {}
        self._moduleCtrls = {}
        self._paramCtrls = {}
        self._topItems = {}
        self._currentWidget = self.splitter.widget(1).layout().takeAt(0)

        # add localhost (if available) and SEC nodes given as arguments
        args = sys.argv[1:]
        if '-d' in args:
            args.remove('-d')
        if not args:
            args = ['localhost']
        for host in args:
            try:
                self._addNode(host)
            except Exception as e:
                print(e)

    @pyqtSlot()
    def on_actionAdd_SEC_node_triggered(self):
        host, ok = QInputDialog.getText(self, 'Add SEC node',
                                        'Enter SEC node hostname:')

        if not ok:
            return

        try:
            self._addNode(host)
        except Exception as e:
            QMessageBox.critical(self.parent(),
                                 'Connecting to %s failed!' % host, str(e))

    def on_validateCheckBox_toggled(self, state):
        print("validateCheckBox_toggled", state)

    def on_visibilityComboBox_activated(self, level):
        if level in ['user', 'admin', 'expert']:
            print("visibility Level now:", level)

    def on_treeWidget_currentItemChanged(self, current, previous):
        if current.type() == ITEM_TYPE_NODE:
            self._displayNode(current.text(0))
        elif current.type() == ITEM_TYPE_GROUP:
            self._displayGroup(current.parent().text(0), current.text(0))
        elif current.type() == ITEM_TYPE_MODULE:
            self._displayModule(current.parent().text(0), current.text(0))
        elif current.type() == ITEM_TYPE_PARAMETER:
            self._displayParameter(current.parent().parent().text(0),
                                   current.parent().text(0), current.text(0))

    def _removeSubTree(self, toplevel_item):
        #....
        pass

    def _nodeDisconnected_callback(self, host):
        node = self._nodes[host]
        topItem = self._topItems[node]
        self._removeSubTree(topItem)
        node.quit()
        QMessageBox(self.parent(), repr(host))

    def _addNode(self, host):

        # create client
        port = 10767
        if ':' in host:
            host, port = host.split(':', 1)
            port = int(port)
        node = QSECNode({'connectto': host, 'port': port}, parent=self)
        host = '%s:%d' % (host, port)

        host = '%s (%s)' % (node.equipment_id, host)
        self._nodes[host] = node
        node.register_shutdown_callback(self._nodeDisconnected_callback, host)

        # fill tree
        nodeItem = QTreeWidgetItem(None, [host], ITEM_TYPE_NODE)

        for module in sorted(node.modules):
            moduleItem = QTreeWidgetItem(nodeItem, [module], ITEM_TYPE_MODULE)
            for param in sorted(node.getParameters(module)):
                paramItem = QTreeWidgetItem(moduleItem, [param],
                                            ITEM_TYPE_PARAMETER)
                paramItem.setDisabled(False)

        self.treeWidget.addTopLevelItem(nodeItem)
        self._topItems[node] = nodeItem

    def _displayNode(self, node):
        ctrl = self._nodeCtrls.get(node, None)
        if ctrl is None:
            ctrl = self._nodeCtrls[node] = NodeCtrl(self._nodes[node])

        self._replaceCtrlWidget(ctrl)

    def _displayModule(self, node, module):
        ctrl = self._moduleCtrls.get((node, module), None)
        if ctrl is None:
            ctrl = self._moduleCtrls[(node, module)] = ModuleCtrl(self._nodes[node], module)

        self._replaceCtrlWidget(ctrl)

    def _displayParameter(self, node, module, parameter):
        ctrl = self._paramCtrls.get((node, module, parameter), None)
        if ctrl is None:
            ctrl = ParameterView(self._nodes[node], module, parameter)
            self._paramCtrls[(node, module, parameter)] = ctrl

        self._replaceCtrlWidget(ctrl)

    def _replaceCtrlWidget(self, new):
        old = self.splitter.widget(1).layout().takeAt(0)
        if old:
            old.widget().hide()
        self.splitter.widget(1).layout().addWidget(new)
        new.show()
        self._currentWidget = new
