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

from logging import NOTSET, Handler

from frappy.gui.qt import QMainWindow, QObject, pyqtSignal

from frappy.gui.util import Colors, loadUi


class LogWindowHandler(Handler, QObject):

    logmessage = pyqtSignal(object)

    def __init__(self, level=NOTSET):
        QObject.__init__(self)
        Handler.__init__(self, level)
        self.log = []

    def emit(self, record):
        self.log.append(record)
        self.logmessage.emit(record)

    def getEntries(self, level):
        return [rec for rec in self.log if rec.levelno >= level]

class LogWindow(QMainWindow):
    closed = pyqtSignal()
    levels = {'Debug':10, 'Info':20, 'Warning':30, 'Error':40}

    def __init__(self, handler, parent=None):
        super().__init__(parent)
        loadUi(self, 'logwindow.ui')
        self.timecolor = Colors.colors['gray']
        self.level = self.levels['Info']
        self.messagecolors = {
            10 : Colors.colors['gray'],
            20 : Colors.palette.windowText().color(),
            30 : Colors.colors['orange'],
            40 : Colors.colors['red'],
        }
        self.handler = handler
        self.handler.logmessage.connect(self.newEntry)
        self.setMessages(self.handler.getEntries(self.level))

    def setMessages(self, msgs):
        for msg in msgs:
            self.appendMessage(msg)

    def newEntry(self, record):
        if record.levelno >= self.level:
            self.appendMessage(record)

    def appendMessage(self, record):
        s = record.getMessage()
        time = record.created
        if record.levelno == self.levels['Error']:
            s = '<b>%s</b>' %s
        s='<span style="color:%s">[%s] </span><span style="color:%s">%s: %s</span>' \
            % (self.timecolor.name(), time, \
               self.messagecolors[record.levelno].name(), \
               record.name, s)
        self.logBrowser.append(s)

    def on_logLevel_currentTextChanged(self, level):
        self.level = self.levels[level]
        self.logBrowser.clear()
        self.setMessages(self.handler.getEntries(self.level))

    def on_clear_pressed(self):
        self.logBrowser.clear()

    def closeEvent(self, event):
        self.closed.emit()
        self.deleteLater()
