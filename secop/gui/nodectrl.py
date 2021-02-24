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


import json
import pprint
from time import sleep

import mlzlog

import secop.lib
from secop.datatypes import EnumType, StringType
from secop.errors import SECoPError
from secop.gui.qt import QFont, QFontMetrics, QLabel, \
    QMessageBox, QTextCursor, QWidget, pyqtSlot, toHtmlEscaped
from secop.gui.util import Value, loadUi


class NodeCtrl(QWidget):

    def __init__(self, node, parent=None):
        super(NodeCtrl, self).__init__(parent)
        loadUi(self, 'nodectrl.ui')

        self._node = node

        self.contactPointLabel.setText(self._node.contactPoint)
        self.equipmentIdLabel.setText(self._node.equipmentId)
        self.protocolVersionLabel.setText(self._node.protocolVersion)
        self.nodeDescriptionLabel.setText(self._node.properties.get('description',
                                                                    'no description available'))
        self._clearLog()

        # now populate modules tab
        self._init_modules_tab()

        node.logEntry.connect(self._addLogEntry)

    @pyqtSlot()
    def on_sendPushButton_clicked(self):
        msg = self.msgLineEdit.text().strip()

        if not msg:
            return

        self._addLogEntry(
            '<span style="font-weight:bold">Request:</span> '
            '%s:' % msg,
            raw=True)
        #        msg = msg.split(' ', 2)
        try:
            reply = self._node.syncCommunicate(*self._node.decode_message(msg))
            if msg == 'describe':
                _, eid, stuff = self._node.decode_message(reply)
                reply = '%s %s %s' % (_, eid, json.dumps(
                    stuff, indent=2, separators=(',', ':'), sort_keys=True))
                self._addLogEntry(reply, newline=True, pretty=False)
            else:
                self._addLogEntry(reply, newline=True, pretty=False)
        except SECoPError as e:
            einfo = e.args[0] if len(e.args) == 1 else json.dumps(e.args)
            self._addLogEntry(
                '%s: %s' % (e.name, einfo),
                newline=True,
                pretty=False,
                error=True)
        except Exception as e:
            self._addLogEntry(
                'error when sending %r: %r' % (msg, e),
                newline=True,
                pretty=False,
                error=True)

    @pyqtSlot()
    def on_clearPushButton_clicked(self):
        self._clearLog()

    def _clearLog(self):
        self.logTextBrowser.clear()

        self._addLogEntry('SECoP Communication Shell')
        self._addLogEntry('=========================')
        self._addLogEntry('', newline=True)

    def _addLogEntry(self,
                     msg,
                     newline=False,
                     pretty=False,
                     raw=False,
                     error=False):
        if pretty:
            msg = pprint.pformat(msg, width=self._getLogWidth())
            msg = msg[1:-1]

        if not raw:
            if error:
                msg = '<div style="color:#FF0000"><b><pre>%s</pre></b></div>' % toHtmlEscaped(
                    str(msg)).replace('\n', '<br />')
            else:
                msg = '<pre>%s</pre>' % toHtmlEscaped(
                    str(msg)).replace('\n', '<br />')

        content = ''
        if self.logTextBrowser.toPlainText():
            content = self.logTextBrowser.toHtml()
        content += msg

        if newline:
            content += '<br />'

        self.logTextBrowser.setHtml(content)
        self.logTextBrowser.moveCursor(QTextCursor.End)

    def _getLogWidth(self):
        fontMetrics = QFontMetrics(QFont('Monospace'))
        # calculate max avail characters by using an m (which is possible
        # due to monospace)
        result = self.logTextBrowser.width() / fontMetrics.width('m')
        return result

    def _init_modules_tab(self):
        self._moduleWidgets = []
        layout = self.scrollAreaWidgetContents.layout()
        labelfont = self.font()
        labelfont.setBold(True)
        row = 0
        for modname in sorted(self._node.modules):
            modprops = self._node.getModuleProperties(modname)
            interfaces = modprops.get('interface_classes', '')
            description = modprops.get('description', '!!! missing description !!!')

            # fallback: allow (now) invalid 'Driveable'
            unit = ''
            try:
                if 'Drivable' in interfaces or 'Driveable' in interfaces:
                    widget = DrivableWidget(self._node, modname, self)
                    unit = self._node.getProperties(modname, 'value').get('unit', '')
                elif 'Writable' in interfaces or 'Writeable' in interfaces:
                    # XXX !!!
                    widget = DrivableWidget(self._node, modname, self)
                    unit = self._node.getProperties(modname, 'value').get('unit', '')
                elif 'Readable' in interfaces:
                    widget = ReadableWidget(self._node, modname, self)
                    unit = self._node.getProperties(modname, 'value').get('unit', '')
                else:
                    widget = QLabel('Unsupported Interfaceclass %r' % interfaces)
            except Exception as e:
                print(secop.lib.formatExtendedTraceback())
                widget = QLabel('Bad configured Module %s! (%s)' % (modname, e))


            if unit:
                labelstr = '%s (%s):' % (modname, unit)
            else:
                labelstr = '%s:' % (modname,)
            label = QLabel(labelstr)
            label.setFont(labelfont)

            if description:
                widget.setToolTip(description)

            layout.addWidget(label, row, 0)
            layout.addWidget(widget, row, 1)

            row += 1
            self._moduleWidgets.extend((label, widget))
        layout.setRowStretch(row, 1)


class ReadableWidget(QWidget):

    def __init__(self, node, module, parent=None):
        super(ReadableWidget, self).__init__(parent)
        self._node = node
        self._module = module

        # XXX: avoid a nasty race condition, mainly biting on M$
        for i in range(15):
            if 'status' in self._node.modules[module]['parameters']:
                break
            sleep(0.01*i)

        self._status_type = self._node.getProperties(
            self._module, 'status').get('datatype')

        try:
            props = self._node.getProperties(self._module, 'target')
            datatype = props.get('datatype', StringType())
            self._is_enum = isinstance(datatype, EnumType)
        except KeyError:
            self._is_enum = False

        loadUi(self, 'modulebuttons.ui')

        # populate comboBox, keeping a mapping of Qt-index to EnumValue
        if self._is_enum:
            self._map = {}  # maps QT-idx to name/value
            self._revmap = {}  # maps value/name to QT-idx
            for idx, member in enumerate(datatype._enum.members):
                self._map[idx] = member
                self._revmap[member.name] = idx
                self._revmap[member.value] = idx
                self.targetComboBox.addItem(member.name, member.value)

        self._init_status_widgets()
        self._init_current_widgets()
        self._init_target_widgets()

        self._node.newData.connect(self._updateValue)

    def _get(self, pname, fallback=Ellipsis):
        try:
            return Value(*self._node.getParameter(self._module, pname))
        except Exception as e:
            # happens only, if there is no response form read request
            mlzlog.getLogger('cached values').warn(
                'no cached value for %s:%s %r' % (self._module, pname, e))
            return Value(fallback)

    def _init_status_widgets(self):
        self.update_status(self._get('status', (400, '<not supported>')))
        # XXX: also connect update_status signal to LineEdit ??

    def update_status(self, status):
        self.statusLineEdit.setText(str(status))
        # may change meaning of cmdPushButton

    def _init_current_widgets(self):
        self.update_current(self._get('value', ''))

    def update_current(self, value):
        self.currentLineEdit.setText(str(value))

    def _init_target_widgets(self):
        #  Readable has no target: disable widgets
        self.targetLineEdit.setHidden(True)
        self.targetComboBox.setHidden(True)
        self.cmdPushButton.setHidden(True)

    def update_target(self, target):
        pass

    def _updateValue(self, module, parameter, value):
        if module != self._module:
            return
        if parameter == 'status':
            self.update_status(value)
        elif parameter == 'value':
            self.update_current(value)
        elif parameter == 'target':
            self.update_target(value)


class DrivableWidget(ReadableWidget):

    def _init_target_widgets(self):
        if self._is_enum:
            # EnumType: disable Linedit
            self.targetLineEdit.setHidden(True)
            self.cmdPushButton.setHidden(True)
        else:
            # normal types: disable Combobox
            self.targetComboBox.setHidden(True)
            target = self._get('target', None)
            if target.value is not None:
                if isinstance(target.value, list) and isinstance(target.value[1], dict):
                    self.update_target(Value(target.value[0]))
                else:
                    self.update_target(target)

    def update_current(self, value):
        self.currentLineEdit.setText(str(value))
        #elif self._is_enum:
        #    member = self._map[self._revmap[value.value]]
        #    self.currentLineEdit.setText('%s.%s (%d)' % (member.enum.name, member.name, member.value))

    def update_target(self, target):
        if self._is_enum:
            if target.readerror:
                return
            # update selected item
            value = target.value
            if value in self._revmap:
                self.targetComboBox.setCurrentIndex(self._revmap[value])
            else:
                print(
                    "%s: Got invalid target value %r!" %
                    (self._module, value))
        else:
            self.targetLineEdit.setText(str(target))

    def target_go(self, target):
        try:
            self._node.setParameter(self._module, 'target', target)
        except Exception as e:
            self._node.log.exception(e)
            QMessageBox.warning(self.parent(), 'Operation failed', str(e))

    @pyqtSlot()
    def on_cmdPushButton_clicked(self):
        if self._is_enum:
            self.on_targetComboBox_activated(self.targetComboBox.currentText())
        else:
            self.on_targetLineEdit_returnPressed()

    @pyqtSlot()
    def on_targetLineEdit_returnPressed(self):
        self.target_go(self.targetLineEdit.text())

    @pyqtSlot(str)
    def on_targetComboBox_activated(self, selection):
        self.target_go(selection)
