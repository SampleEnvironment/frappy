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
from frappy.gui.qt import QInputDialog, QMainWindow, QMessageBox, QObject, \
        QTreeWidgetItem, pyqtSignal, pyqtSlot
from frappy.gui.util import Value, Colors, loadUi
from frappy.lib import formatExtendedTraceback
from frappy.gui.logwindow import LogWindow
from frappy.gui.tabwidget import TearOffTabWidget
from frappy.gui.nodewidget import NodeWidget

ITEM_TYPE_NODE = QTreeWidgetItem.UserType + 1
ITEM_TYPE_GROUP = QTreeWidgetItem.UserType + 2
ITEM_TYPE_MODULE = QTreeWidgetItem.UserType + 3
ITEM_TYPE_PARAMETER = QTreeWidgetItem.UserType + 4


class QSECNode(QObject):
    newData = pyqtSignal(str, str, object)  # module, parameter, data
    stateChange = pyqtSignal(str, bool, str)  # node name, online, connection state
    unhandledMsg = pyqtSignal(str)  # message
    logEntry = pyqtSignal(str)

    def __init__(self, uri, parent_logger, parent=None):
        super().__init__(parent)
        self.log = parent_logger.getChild(uri)
        self.conn = conn = frappy.client.SecopClient(uri, self.log)
        conn.validate_data = True
        self.contactPoint = conn.uri
        conn.connect()
        self.equipmentId = conn.properties['equipment_id']
        self.log.info('Switching to logger %s', self.equipmentId)
        self.log.name = '.'.join((parent_logger.name, self.equipmentId))
        self.nodename = '%s (%s)' % (self.equipmentId, conn.uri)
        self.modules = conn.modules
        self.properties = self.conn.properties
        self.protocolVersion = conn.secop_version
        self.log.debug('SECoP Version: %s', conn.secop_version)
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
        #print(module, parameter, self.modules[module]['parameters'])
        return self.modules[module]['parameters'][parameter]

    def updateEvent(self, module, parameter, value, timestamp, readerror):
        self.newData.emit(module, parameter, Value(value, timestamp, readerror))

    def nodeStateChange(self, online, state):
        self.stateChange.emit(self.nodename, online, state)

    def unhandledMessage(self, action, specifier, data):
        self.unhandledMsg.emit('%s %s %r' % (action, specifier, data))


class MainWindow(QMainWindow):
    def __init__(self, hosts, logger, parent=None):
        super().__init__(parent)

        self.log = logger
        self.logwin = LogWindow(logger, self)
        self.logwin.hide()

        loadUi(self, 'mainwin.ui')
        Colors._setPalette(self.palette())

        self.toolBar.hide()

        # what is which?
        self.tab = TearOffTabWidget(self, self, self, self)
        self.tab.setTabsClosable(True)
        self.tab.tabCloseRequested.connect(self._handleTabClose)
        self.setCentralWidget(self.tab)

        self._nodes = {}
        self._nodeWidgets = {}

        # add localhost (if available) and SEC nodes given as arguments
        for host in hosts:
            try:
                self.log.info('Trying to connect to %s', host)
                self._addNode(host)
            except Exception as e:
                # TODO: make this nicer than dumping to console
                print(formatExtendedTraceback())
                self.log.error('error in addNode: %r', e)

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

    def on_actionDetailed_View_toggled(self, toggled):
        self._rebuildAdvanced(toggled)

    def on_actionShow_Logs_toggled(self, active):
        self.logwin.setHidden(not active)

    # def on_validateCheckBox_toggled(self, state):
    #     print('validateCheckBox_toggled', state)

    # def on_visibilityComboBox_activated(self, level):
    #     if level in ['user', 'admin', 'expert']:
    #         print('visibility Level now:', level)

    def _addNode(self, host):

        # create client
        node = QSECNode(host, self.log, parent=self)
        nodename = node.nodename
        self._nodes[nodename] = node

        nodeWidget = NodeWidget(node, self)
        self.tab.addTab(nodeWidget, node.equipmentId)
        self._nodeWidgets[nodename] = nodeWidget
        self.tab.setCurrentWidget(nodeWidget)
        return nodename

    def _handleTabClose(self, index):
        node = self.tab.widget(index).getSecNode()
        # disconnect node from all events
        self._nodes.pop(node.nodename)
        self.tab.removeTab(index)

    def _rebuildAdvanced(self, advanced):
        if advanced:
            pass
        else:
            pass
        for widget in self._nodeWidgets.values():
            widget._rebuildAdvanced(advanced)

    def _onQuit(self):
        for node in self._nodes.values():
            # this is only qt signals deconnecting!
            # TODO: terminate node.conn explicitly?
            node.disconnect()
        self.logwin.onClose()
