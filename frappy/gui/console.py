# *****************************************************************************
# Copyright (c) 2015-2024 by the authors, see LICENSE
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

import json

from frappy.gui.qt import QApplication, QFont, QFontMetrics, QKeyEvent, \
    QLineEdit, QSettings, Qt, QTextCursor, QWidget, pyqtSignal, pyqtSlot, \
    toHtmlEscaped

from frappy.errors import SECoPError
from frappy.gui.util import loadUi


class ConsoleLineEdit(QLineEdit):
    """QLineEdit with history. Based on HistoryLineEdit from NICOS gui"""
    sentText = pyqtSignal(str)
    scrollingKeys = [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp,
                 Qt.Key.Key_PageDown]

    def __init__(self, parent=None):
        super().__init__(parent)
        settings = QSettings()
        self.history = settings.value('consoleHistory', [])
        self.scrollWidget = None
        self._start_text = ''
        self._current = -1

    def keyPressEvent(self, kev):
        key_code = kev.key()

        # if it's a shifted scroll key...
        if kev.modifiers() & Qt.KeyboardModifier.ShiftModifier and \
                self.scrollWidget and \
                key_code in self.scrollingKeys:
            # create a new, unshifted key event and send it to the
            # scrolling widget
            nev = QKeyEvent(kev.type(), kev.key(),
                            Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(self.scrollWidget, nev)
            return

        if key_code == Qt.Key.Key_Escape:
            # abort history search
            self.setText(self._start_text)
            self._current = -1
            QLineEdit.keyPressEvent(self, kev)

        elif key_code == Qt.Key.Key_Up:
            # go earlier
            if self._current == -1:
                self._start_text = self.text()
                self._current = len(self.history)
            self.stepHistory(-1)
        elif key_code == Qt.Key.Key_Down:
            # go later
            if self._current == -1:
                return
            self.stepHistory(1)

        elif key_code == Qt.Key.Key_PageUp:
            # go earlier with prefix
            if self._current == -1:
                self._current = len(self.history)
                self._start_text = self.text()
            prefix = self.text()[:self.cursorPosition()]
            self.stepHistoryUntil(prefix, 'up')

        elif key_code == Qt.Key.Key_PageDown:
            # go later with prefix
            if self._current == -1:
                return
            prefix = self.text()[:self.cursorPosition()]
            self.stepHistoryUntil(prefix, 'down')

        elif key_code in (Qt.Key.Key_Return, key_code == Qt.Key.Key_Enter):
            # accept - add to history and do normal processing
            self._current = -1
            text = self.text()
            if text and (not self.history or self.history[-1] != text):
                # append to history, but only if it isn't equal to the last
                self.history.append(text)
                self.sentText.emit(text)
            QLineEdit.keyPressEvent(self, kev)

        else:
            # process normally
            QLineEdit.keyPressEvent(self, kev)

    def stepHistory(self, num):
        self._current += num
        if self._current <= -1:
            # no further
            self._current = 0
            return
        if self._current >= len(self.history):
            # back to start
            self._current = -1
            self.setText(self._start_text)
            return
        self.setText(self.history[self._current])

    def stepHistoryUntil(self, prefix, direction):
        if direction == 'up':
            lookrange = range(self._current - 1, -1, -1)
        else:
            lookrange = range(self._current + 1, len(self.history))
        for i in lookrange:
            if self.history[i].startswith(prefix):
                self._current = i
                self.setText(self.history[i])
                self.setCursorPosition(len(prefix))
                return
        if direction == 'down':
            # nothing found: go back to start
            self._current = -1
            self.setText(self._start_text)
            self.setCursorPosition(len(prefix))


class Console(QWidget):
    def __init__(self, node, parent=None):
        super().__init__(parent)
        loadUi(self, 'console.ui')
        self._node = node
        self._clearLog()
        self.msgLineEdit.scrollWidget = self.logTextBrowser

    @pyqtSlot()
    def on_sendPushButton_clicked(self):
        msg = self.msgLineEdit.text().strip()

        if not msg:
            return

        self._addLogEntry(
            f'<span style="font-weight:bold">Request:</span> <tt>{toHtmlEscaped(msg)}</tt>',
            raw=True)
        #        msg = msg.split(' ', 2)
        try:
            reply = self._node.syncCommunicate(*self._node.decode_message(msg))
            if msg == 'describe':
                _, eid, stuff = self._node.decode_message(reply)
                reply = f"{_} {eid} {json.dumps(stuff, indent=2, separators=(',', ':'), sort_keys=True)}"
                self._addLogEntry(reply.rstrip('\n'))
            else:
                self._addLogEntry(reply.rstrip('\n'))
        except SECoPError as e:
            einfo = e.args[0] if len(e.args) == 1 else json.dumps(e.args)
            self._addLogEntry(f'{e.name}: {einfo}', error=True)
        except Exception as e:
            self._addLogEntry(f'error when sending {msg!r}: {e!r}',
                              error=True)

        self.msgLineEdit.clear()

    @pyqtSlot()
    def on_clearPushButton_clicked(self):
        self._clearLog()

    def _clearLog(self):
        self.logTextBrowser.clear()

        self._addLogEntry('<div style="font-weight: bold">'
                          'SECoP Communication Shell<br/>'
                          '=========================<br/></div>',
                          raw=True)

    def _addLogEntry(self, msg, raw=False, error=False):
        if not raw:
            if error:
                msg = ('<div style="color:#FF0000"><b><pre>%s</pre></b></div>'
                       % toHtmlEscaped(str(msg)).replace('\n', '<br />'))
            else:
                msg = ('<pre>%s</pre>'
                       % toHtmlEscaped(str(msg)).replace('\n', '<br />'))

        content = ''
        if self.logTextBrowser.toPlainText():
            content = self.logTextBrowser.toHtml()
        content += msg

        self.logTextBrowser.setHtml(content)
        self.logTextBrowser.moveCursor(QTextCursor.MoveOperation.End)

    def _getLogWidth(self):
        fontMetrics = QFontMetrics(QFont('Monospace'))
        # calculate max avail characters by using an m (which is possible
        # due to monospace)
        result = self.logTextBrowser.width() / fontMetrics.width('m')
        return result
