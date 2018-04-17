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

import pprint
import json
from time import sleep

from secop.gui.qt import QWidget, QTextCursor, QFont, QFontMetrics, QLabel, \
    QMessageBox, pyqtSlot, toHtmlEscaped

from secop.gui.util import loadUi
from secop.protocol.errors import SECOPError
from secop.datatypes import StringType, EnumType


class NodeCtrl(QWidget):

    def __init__(self, node, parent=None):
        super(NodeCtrl, self).__init__(parent)
        loadUi(self, 'nodectrl.ui')

        self._node = node

        self.contactPointLabel.setText(self._node.contactPoint)
        self.equipmentIdLabel.setText(self._node.equipmentId)
        self.protocolVersionLabel.setText(self._node.protocolVersion)
        self.nodeDescriptionLabel.setText(self._node.describingData['properties'].get(
            'description', 'no description available'))
        self._clearLog()

        # now populate modules tab
        self._init_modules_tab()

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
                self._addLogEntry(reply, newline=True, pretty=True)
        except SECOPError as e:
            self._addLogEntry(
                'error %s %s' % (e.name, json.dumps(e.args)),
                newline=True,
                pretty=True,
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
        # calculate max avail characters by using an a (which is possible
        # due to monospace)
        result = self.logTextBrowser.width() / fontMetrics.width('a')
        return result

    def _init_modules_tab(self):
        self._moduleWidgets = []
        layout = self.scrollAreaWidgetContents.layout()
        labelfont = self.font()
        labelfont.setBold(True)
        row = 0
        for modname in sorted(self._node.modules):
            modprops = self._node.getModuleProperties(modname)
            if 'interface_class' in modprops:
                interfaces = modprops['interface_class']
            else:
                interfaces = modprops['interfaces']
            description = modprops['description']

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
            if 'status' in self._node.describing_data['modules'][module]['parameters']:
                break
            sleep(0.01*i)

        self._status_type = self._node.getProperties(
            self._module, 'status').get('datatype')

        params = self._node.getProperties(self._module, 'value')
        datatype = params.get('datatype', StringType())
        self._is_enum = isinstance(datatype, EnumType)

        loadUi(self, 'modulebuttons.ui')

        # populate comboBox, keeping a mapping of Qt-index to EnumValue
        if self._is_enum:
            self._map = {}  # maps QT-idx to name/value
            self._revmap = {}  # maps value/name to QT-idx
            for idx, (val, name) in enumerate(
                    sorted(datatype.entries.items())):
                self._map[idx] = (name, val)
                self._revmap[name] = idx
                self._revmap[val] = idx
                self.targetComboBox.addItem(name, val)

        self._init_status_widgets()
        self._init_current_widgets()
        self._init_target_widgets()

        self._node.newData.connect(self._updateValue)

    def _get(self, pname, fallback=Ellipsis):
        params = self._node.queryCache(self._module)
        if pname in params:
            return params[pname].value
        try:
            # if queried, we get the qualifiers as well, but don't want them
            # here
            import mlzlog
            mlzlog.getLogger('cached values').warn(
                'no cached value for %s:%s' % (self._module, pname))
            val = self._node.getParameter(self._module, pname)[0]
            return val
        except Exception:
            self._node.log.exception()
            if fallback is not Ellipsis:
                return fallback
            raise

    def _init_status_widgets(self):
        self.update_status(self._get('status', (999, '<not supported>')), {})
        # XXX: also connect update_status signal to LineEdit ??

    def update_status(self, status, qualifiers=None):
        display_string = self._status_type.subtypes[0].entries.get(status[0])
        if status[1]:
            display_string += ':' + status[1]
        self.statusLineEdit.setText(display_string)
        # may change meaning of cmdPushButton

    def _init_current_widgets(self):
        self.update_current(self._get('value', ''), {})

    def update_current(self, value, qualifiers=None):
        self.currentLineEdit.setText(str(value))

    def _init_target_widgets(self):
        #  Readable has no target: disable widgets
        self.targetLineEdit.setHidden(True)
        self.targetComboBox.setHidden(True)
        self.cmdPushButton.setHidden(True)

    def update_target(self, target, qualifiers=None):
        pass

    def _updateValue(self, module, parameter, value):
        if module != self._module:
            return
        if parameter == 'status':
            self.update_status(*value)
        elif parameter == 'value':
            self.update_current(*value)
        elif parameter == 'target':
            self.update_target(*value)


class DrivableWidget(ReadableWidget):

    def _init_target_widgets(self):
        if self._is_enum:
            # EnumType: disable Linedit
            self.targetLineEdit.setHidden(True)
        else:
            # normal types: disable Combobox
            self.targetComboBox.setHidden(True)
            target = self._get('target', None)
            if target:
                if isinstance(target, list) and isinstance(target[1], dict):
                    self.update_target(target[0])
                else:
                    self.update_target(target)

    def update_current(self, value, qualifiers=None):
        if self._is_enum:
            self.currentLineEdit.setText(self._map[self._revmap[value]][0])
        else:
            self.currentLineEdit.setText(str(value))

    def update_target(self, target, qualifiers=None):
        if self._is_enum:
            # update selected item
            if target in self._revmap:
                self.targetComboBox.setCurrentIndex(self._revmap[target])
            else:
                print(
                    "%s: Got invalid target value %r!" %
                    (self._module, target))
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

    @pyqtSlot(unicode)
    def on_targetComboBox_activated(self, stuff):
        self.target_go(stuff)
