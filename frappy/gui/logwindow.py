from logging import Handler, DEBUG, NOTSET

from frappy.gui.qt import QMainWindow, QObject, pyqtSignal
from frappy.gui.util import loadUi



class LogWindowHandler(Handler, QObject):

    logmessage = pyqtSignal(str, int)

    def __init__(self, level=NOTSET):
        QObject.__init__(self)
        Handler.__init__(self, level)

    def emit(self, record):
        self.logmessage.emit(record.getMessage(), record.levelno)

class LogWindow(QMainWindow):
    levels = {'Debug':10, 'Info':20, 'Warning':30, 'Error':40}
    def __init__(self, logger, parent=None):
        super().__init__(parent)
        loadUi(self, 'logwindow.ui')
        self.log = []
        self.level = self.levels['Info']
        handler = LogWindowHandler(DEBUG)
        handler.logmessage.connect(self.newEntry)
        logger.addHandler(handler)

    def newEntry(self, msg, lvl):
        self.log.append((lvl, msg))
        if lvl >= self.level:
            self.logBrowser.append(msg)

    def on_logLevel_currentTextChanged(self, level):
        self.level = self.levels[level]
        self.logBrowser.clear()
        self.logBrowser.setPlainText('\n'.join(msg for (lvl, msg) in self.log if lvl >= self.level))

    def on_clear_pressed(self):
        self.logBrowser.clear()
        self.log.clear()

    def onClose(self):
        pass
