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

import frappy.version
from frappy.gui.qt import QInputDialog, QMainWindow, QMessageBox, \
        QTreeWidgetItem, pyqtSignal, pyqtSlot, QWidget, QSettings, QAction, \
        QShortcut, QKeySequence
from frappy.gui.util import Colors, loadUi
from frappy.gui.logwindow import LogWindow
from frappy.gui.tabwidget import TearOffTabWidget
from frappy.gui.nodewidget import NodeWidget
from frappy.gui.connection import QSECNode

ITEM_TYPE_NODE = QTreeWidgetItem.UserType + 1
ITEM_TYPE_GROUP = QTreeWidgetItem.UserType + 2
ITEM_TYPE_MODULE = QTreeWidgetItem.UserType + 3
ITEM_TYPE_PARAMETER = QTreeWidgetItem.UserType + 4


class Greeter(QWidget):
    recentClearBtn = pyqtSignal()
    addnodes = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(self, 'greeter.ui')
        self.loadRecent()

    def loadRecent(self):
        self.recentNodes.clear()
        settings = QSettings()
        recent = settings.value('recent', [])
        for host in recent:
            self.recentNodes.addItem(host)

    @pyqtSlot()
    def on_ClearButton_clicked(self):
        self.recentClearBtn.emit()

    @pyqtSlot()
    def on_connectRecentButton_clicked(self):
        selected = self.recentNodes.selectedItems()
        hosts = [item.text() for item in selected]
        self.addnodes.emit(hosts)

    @pyqtSlot()
    def on_AddSECNodeButton_clicked(self):
        self.addnodes.emit([self.secnodeEdit.text()
                            or self.secnodeEdit.placeholderText()])


class MainWindow(QMainWindow):
    recentNodesChanged = pyqtSignal()

    def __init__(self, hosts, logger, parent=None):
        super().__init__(parent)

        self.log = logger
        self.logwin = LogWindow(logger, self)
        self.logwin.hide()

        loadUi(self, 'mainwin.ui')
        Colors._setPalette(self.palette())

        self.toolBar.hide()
        self.buildRecentNodeMenu()
        self.recentNodesChanged.connect(self.buildRecentNodeMenu)

        # what is which?
        self.tab = TearOffTabWidget(self, self, self, self)
        self.tab.setTabsClosable(True)
        self.tab.tabCloseRequested.connect(self._handleTabClose)
        self.shortcut = QShortcut(QKeySequence("Ctrl+W"), self,
                                  self.tab.close_current)
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
                self.log.error('error in addNode: %r', e)

        if not self._nodes:
            greeter = Greeter(self)
            greeter.addnodes.connect(self._addNodes)
            greeter.recentClearBtn.connect(self.on_actionClear_triggered)
            self.recentNodesChanged.connect(greeter.loadRecent)
            self.tab.addPanel(greeter, 'Welcome')

    @pyqtSlot()
    def on_actionAbout_triggered(self):
        try:
            ver = frappy.version.get_version()
        except Exception:
            ver = 'unknown'

        QMessageBox.about(
            self, 'About Frappy GUI',
            f'''
            <h2>About Frappy GUI</h2>
            <p>A graphical client for the SECoP protocol.</p>
            <p>© 2017-2023 Frappy contributors:</p>
            <ul>
              <li><a href="mailto:markus.zolliker@psi.ch">Markus Zolliker</a></li>
              <li><a href="mailto:enrico.faulhaber@frm2.tum.de">Enrico Faulhaber</a></li>
              <li><a href="mailto:a.zaft@fz-juelich.de">Alexander Zaft</a></li>
              <li><a href="mailto:g.brandl@fz-juelich.de">Georg Brandl</a></li>
            </ul>
            <p>Frappy is available under the
              <a href="http://www.gnu.org/licenses/gpl.html">GNU General
              Public License</a> version 2.0 or later.</p>
            <p style="font-weight: bold">Version: v{ver}</p>
            ''')

    @pyqtSlot()
    def on_actionAdd_SEC_node_triggered(self):
        host, ok = QInputDialog.getText(
            self, 'Add SEC node',
            'Enter SEC node URI (or just hostname:port):')

        if not ok:
            return

        try:
            self._addNode(host)
        except Exception as e:
            QMessageBox.critical(self.parent(),
                                 'Connecting to %s failed!' % host, str(e))

    @pyqtSlot()
    def on_actionReconnect_triggered(self):
        self.tab.currentWidget().getSecNode().reconnect()

    def on_actionDetailed_View_toggled(self, toggled):
        self._rebuildAdvanced(toggled)

    def on_actionShow_Logs_toggled(self, active):
        self.logwin.setHidden(not active)

    # def on_validateCheckBox_toggled(self, state):
    #     print('validateCheckBox_toggled', state)

    # def on_visibilityComboBox_activated(self, level):
    #     if level in ['user', 'admin', 'expert']:
    #         print('visibility Level now:', level)

    def _addNodes(self, hosts):
        for host in hosts:
            try:
                self.log.info('Trying to connect to %s', host)
                self._addNode(host)
            except Exception as e:
                self.log.error('error in addNode: %r', e)
                QMessageBox.critical(self.parent(),
                                     'Connecting to %s failed!' % host, str(e))

    def _addNode(self, host):
        # create client
        node = QSECNode(host, self.log, parent=self)
        nodename = node.nodename
        self._nodes[nodename] = node

        nodeWidget = NodeWidget(node, self)
        self.tab.addTab(nodeWidget, node.equipmentId)
        self._nodeWidgets[nodename] = nodeWidget
        self.tab.setCurrentWidget(nodeWidget)

        # add to recent nodes
        settings = QSettings()
        recent = settings.value('recent', [])
        if host in recent:
            recent.remove(host)
        recent.insert(0, host)
        settings.setValue('recent', recent)
        self.recentNodesChanged.emit()
        return nodename

    def buildRecentNodeMenu(self):
        settings = QSettings()
        recent = settings.value('recent', [])
        menu = self.menuRecent_SECNodes
        for action in list(menu.actions()):
            if action.isSeparator():
                break
            menu.removeAction(action)
        # save reference so they are not deleted
        self.recentNodeActions = []
        for host in recent:
            a = QAction(host)
            a.triggered.connect(lambda _t, h=host: self._addNode(h))
            self.recentNodeActions.append(a)
        menu.insertActions(action, self.recentNodeActions)

    def on_actionClear_triggered(self):
        """clears recent SECNode menu"""
        settings = QSettings()
        settings.remove('recent')
        self.recentNodesChanged.emit()

    def _handleTabClose(self, index):
        try:
            node = self.tab.widget(index).getSecNode()
            # disconnect node from all events
            self._nodes.pop(node.nodename)
            self.log.debug("Closing tab with node %s" % node.nodename)
        except AttributeError:
            # Closing the greeter
            self.log.debug("Greeter Tab closed")
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
