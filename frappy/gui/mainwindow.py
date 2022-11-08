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


import frappy.client
from frappy.gui.modulectrl import ModuleCtrl
from frappy.gui.nodectrl import NodeCtrl
from frappy.gui.paramview import ParameterView
from frappy.gui.qt import QBrush, QColor, QInputDialog, QMainWindow, \
    QMessageBox, QObject, QTreeWidgetItem, pyqtSignal, pyqtSlot
from frappy.gui.util import Value, loadUi
from frappy.lib import formatExtendedTraceback

ITEM_TYPE_NODE = QTreeWidgetItem.UserType + 1
ITEM_TYPE_GROUP = QTreeWidgetItem.UserType + 2
ITEM_TYPE_MODULE = QTreeWidgetItem.UserType + 3
ITEM_TYPE_PARAMETER = QTreeWidgetItem.UserType + 4


class QSECNode(QObject):
    newData = pyqtSignal(str, str, object)  # module, parameter, data
    stateChange = pyqtSignal(str, bool, str)  # node name, online, connection state
    unhandledMsg = pyqtSignal(str)  # message
    logEntry = pyqtSignal(str)

    def __init__(self, uri, parent=None):
        super().__init__(parent)
        self.conn = conn = frappy.client.SecopClient(uri)
        conn.validate_data = True
        self.log = conn.log
        self.contactPoint = conn.uri
        conn.connect()
        self.equipmentId = conn.properties['equipment_id']
        self.nodename = '%s (%s)' % (self.equipmentId, conn.uri)
        self.modules = conn.modules
        self.properties = self.conn.properties
        self.protocolVersion = conn.secop_version
        conn.register_callback(None, self.updateEvent, self.nodeStateChange, self.unhandledMessage)

    # provide methods from old baseclient for making other gui code work

    def getParameters(self, module):
        return self.modules[module]['parameters']

    def getCommands(self, module):
        return self.modules[module]['commands']

    def getModuleProperties(self, module):
        return self.modules[module]['properties']

    def getProperties(self, module, parameter):
        props = self.modules[module]['parameters'][parameter]
        if 'unit' in props['datainfo']:
            props['unit'] = props['datainfo']['unit']
        return self.modules[module]['parameters'][parameter]

    def setParameter(self, module, parameter, value):
        # TODO: change the widgets for complex types to no longer use strings
        datatype = self.conn.modules[module]['parameters'][parameter]['datatype']
        self.conn.setParameter(module, parameter, datatype.from_string(value))

    def getParameter(self, module, parameter):
        return self.conn.getParameter(module, parameter, True)

    def execCommand(self, module, command, argument):
        return self.conn.execCommand(module, command, argument)

    def queryCache(self, module):
        return {k: Value(*self.conn.cache[(module, k)])
                for k in self.modules[module]['parameters']}

    def syncCommunicate(self, action, ident='', data=None):
        reply = self.conn.request(action, ident, data)
        # pylint: disable=not-an-iterable
        return frappy.client.encode_msg_frame(*reply).decode('utf-8')

    def decode_message(self, msg):
        # decode_msg needs bytes as input
        return frappy.client.decode_msg(msg.encode('utf-8'))

    def _getDescribingParameterData(self, module, parameter):
        return self.modules[module]['parameters'][parameter]

    def updateEvent(self, module, parameter, value, timestamp, readerror):
        self.newData.emit(module, parameter, Value(value, timestamp, readerror))

    def nodeStateChange(self, online, state):
        self.stateChange.emit(self.nodename, online, state)

    def unhandledMessage(self, action, specifier, data):
        self.unhandledMsg.emit('%s %s %r' % (action, specifier, data))


class MainWindow(QMainWindow):
    def __init__(self, hosts, parent=None):
        super().__init__(parent)

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
        for host in hosts:
            try:
                self._addNode(host)
            except Exception as e:
                print(formatExtendedTraceback())
                print('error in addNode: %r' % e)

    @pyqtSlot()
    def on_actionAdd_SEC_node_triggered(self):
        host, ok = QInputDialog.getText(self, 'Add SEC node',
                                        'Enter SEC node URI (or just hostname:port):')

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
        self.treeWidget.invisibleRootItem().removeChild(toplevel_item)

    def _set_node_state(self, nodename, online, state):
        node = self._nodes[nodename]
        if online:
            self._topItems[node].setBackground(0, QBrush(QColor('white')))
        else:
            self._topItems[node].setBackground(0, QBrush(QColor('orange')))
        # TODO: make connection state be a separate row
        node.contactPoint = '%s (%s)' % (node.conn.uri, state)
        if nodename in self._nodeCtrls:
            self._nodeCtrls[nodename].contactPointLabel.setText(node.contactPoint)

    def _addNode(self, host):

        # create client
        node = QSECNode(host, parent=self)
        nodename = node.nodename

        self._nodes[nodename] = node

        # fill tree
        nodeItem = QTreeWidgetItem(None, [nodename], ITEM_TYPE_NODE)

        for module in sorted(node.modules):
            moduleItem = QTreeWidgetItem(nodeItem, [module], ITEM_TYPE_MODULE)
            for param in sorted(node.getParameters(module)):
                paramItem = QTreeWidgetItem(moduleItem, [param],
                                            ITEM_TYPE_PARAMETER)
                paramItem.setDisabled(False)

        self.treeWidget.addTopLevelItem(nodeItem)
        self._topItems[node] = nodeItem
        node.stateChange.connect(self._set_node_state)

    def _displayNode(self, node):
        ctrl = self._nodeCtrls.get(node, None)
        if ctrl is None:
            ctrl = self._nodeCtrls[node] = NodeCtrl(self._nodes[node])
            self._nodes[node].unhandledMsg.connect(ctrl._addLogEntry)

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
