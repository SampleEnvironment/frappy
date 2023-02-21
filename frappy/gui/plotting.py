import time

try:
    import pyqtgraph as pg
    import numpy as np
except ImportError:
    pg = None
    np = None

from frappy.gui.util import Colors
from frappy.gui.qt import QWidget, QVBoxLayout, QLabel, Qt, pyqtSignal
def getPlotWidget():
    if pg:
        pg.setConfigOption('background', Colors.colors['plot-bg'])
        pg.setConfigOption('foreground', Colors.colors['plot-fg'])

    if pg is None:
        return PlotPlaceHolderWidget()
    return PlotWidget()

class PlotPlaceHolderWidget(QWidget):
    closed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout()
        label = QLabel("pyqtgraph is not installed!")
        label.setAlignment(Qt.AlignCenter)
        l.addWidget(label)
        self.setLayout(l)
        self.setMinimumWidth(300)
        self.setMinimumHeight(150)
        self.curves = {}

    def addCurve(self, node, module, param):
        pass

    def setCurveColor(self, module, param, color):
        pass

    def update(self, module, param, value):
        pass

    def closeEvent(self, event):
        self.closed.emit(self)
        event.accept()

# TODO:
# - timer-based updates when receiving no updates from the node
#   in order to make slower updates not jump that much?
# - remove curves again
class PlotWidget(QWidget):
    closed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.win = pg.GraphicsLayoutWidget()
        self.curves = {}
        self.data = {}
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.scrollUpdate)

        # TODO: Shoud this scrolling be done? or with configuration?
        self.timer.start(100)

        self.plot = self.win.addPlot()
        self.plot.addLegend()
        self.plot.setAxisItems({'bottom': pg.DateAxisItem()})
        self.plot.setLabel('bottom', 'Time')
        self.plot.setLabel('left', 'Value')
        l = QVBoxLayout()
        l.addWidget(self.win)
        self.setLayout(l)

    def addCurve(self, node, module, param):
        paramData = node._getDescribingParameterData(module, param)
        name = '%s:%s' % (module, param)
        unit = paramData.get('unit', '')
        if unit:
            unit = '/' + unit
        curve = self.plot.plot(name='%s%s' % (name, unit))
        if 'min' in paramData and 'max' in paramData:
            curve.setXRange(paramData['min'], paramData['max'])

        curve.setDownsampling(method='peak')
        self.data[name] = (np.array([]),np.array([]))
        self.curves[name] = curve
        node.newData.connect(self.update)

    def setCurveColor(self, module, param, color):
        curve = self.curves['%s:%s' % (module, param)]
        curve.setPen(color)

    def scrollUpdate(self):
        for cname, curve in self.curves.items():
            x,y = self.data[cname]
            x = np.append(x, time.time())
            y = np.append(y, y[-1])
            curve.setData(x,y)

    def update(self, module, param, value):
        name = '%s:%s' % (module, param)
        if name not in self.curves:
            return
        curve = self.curves[name]
        x,y = self.data[name]
        x = np.append(x, value.timestamp)
        y = np.append(y, value.value)
        self.data[name] = (x,y)
        curve.setData(x,y)

    def closeEvent(self, event):
        self.closed.emit(self)
        event.accept()
