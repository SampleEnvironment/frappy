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

import time

from frappy.gui.qt import QLabel, Qt, QVBoxLayout, QWidget, pyqtSignal

from frappy.gui.util import Colors

try:
    import numpy as np
    import pyqtgraph as pg
except ImportError:
    pg = None
    np = None


def getPlotWidget(parent):
    if pg:
        pg.setConfigOption('background', Colors.colors['plot-bg'])
        pg.setConfigOption('foreground', Colors.colors['plot-fg'])

    if pg is None:
        window = PlotPlaceHolderWidget(parent)
    else:
        window = PlotWidget(parent)
    window.setWindowFlags(Qt.WindowType.Window)
    return window


class PlotPlaceHolderWidget(QWidget):
    closed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout()
        label = QLabel("pyqtgraph is not installed!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        name = f'{module}:{param}'
        unit = paramData.get('unit', '')
        if unit:
            unit = '/' + unit
        curve = self.plot.plot(name=f'{name}{unit}')
        if 'min' in paramData and 'max' in paramData:
            curve.setXRange(paramData['min'], paramData['max'])

        curve.setDownsampling(method='peak')
        self.data[name] = (np.array([]),np.array([]))
        self.curves[name] = curve
        node.newData.connect(self.update)

    def setCurveColor(self, module, param, color):
        curve = self.curves[f'{module}:{param}']
        curve.setPen(color)

    def scrollUpdate(self):
        for cname, curve in self.curves.items():
            x,y = self.data[cname]
            x = np.append(x, time.time())
            y = np.append(y, y[-1])
            curve.setData(x,y)

    def update(self, module, param, value):
        name = f'{module}:{param}'
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
