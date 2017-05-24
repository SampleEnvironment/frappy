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

from PyQt4.QtGui import QWidget, QTextCursor, QFont, QFontMetrics
from PyQt4.QtCore import pyqtSignature as qtsig, Qt

from secop.gui.util import loadUi
from secop.protocol.errors import SECOPError


class NodeCtrl(QWidget):

    def __init__(self, node, parent=None):
        super(NodeCtrl, self).__init__(parent)
        loadUi(self, 'nodectrl.ui')

        self._node = node

        self.contactPointLabel.setText(self._node.contactPoint)
        self.equipmentIdLabel.setText(self._node.equipmentId)
        self.protocolVersionLabel.setText(self._node.protocolVersion)
        self._clearLog()

    @qtsig('')
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

    @qtsig('')
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
                msg = '<div style="color:#FF0000"><b><pre>%s</pre></b></div>' % Qt.escape(
                    str(msg)).replace('\n', '<br />')
            else:
                msg = '<pre>%s</pre>' % Qt.escape(str(msg)).replace('\n',
                                                                    '<br />')

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
