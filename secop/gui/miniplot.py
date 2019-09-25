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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************



from os import path

from secop.gui.qt import QBrush, QColor, QPainter, QPen, \
    QPointF, QPolygonF, QRectF, QSize, Qt, QWidget

_magenta = QBrush(QColor('#A12F86'))
_yellow = QBrush(QColor('yellow'))
_white = QBrush(QColor('white'))
_lightgrey = QBrush(QColor('lightgrey'))
_grey = QBrush(QColor('grey'))
_darkgrey = QBrush(QColor('#404040'))
_black = QBrush(QColor('black'))
_blue = QBrush(QColor('blue'))
_green = QBrush(QColor('green'))
_red = QBrush(QColor('red'))
_olive = QBrush(QColor('olive'))
_orange = QBrush(QColor('#ffa500'))


my_uipath = path.dirname(__file__)

class MiniPlotCurve(object):
    # placeholder for data
    linecolor = _black
    linewidth = 0  # set to 0 to disable lines
    symbolcolors = (_black, _white)  # line, fill
    symbolsize = 3  # both symbol linewidth and symbolsize, set to 0 to disable
    errorbarcolor = _darkgrey
    errorbarwidth = 3 # set to 0 to disable errorbar

    def __init__(self):
        self.data = []  # tripels of x, y, err  (err may be None)

    @property
    def xvalues(self):
        return [p[0] for p in self.data] if self.data else [0]

    @property
    def yvalues(self):
        return [p[1] for p in self.data] if self.data else [0]

    @property
    def errvalues(self):
        return [p[2] or 0.0 for p in self.data] if self.data else [0]

    @property
    def xmin(self):
        return min(self.xvalues)

    @property
    def xmax(self):
        return max(self.xvalues)

    @property
    def ymin(self):
        return min(self.yvalues)

    @property
    def ymax(self):
        return max(self.yvalues)

    @property
    def yemin(self):
        return min(y-(e or 0) for _, y, e in self.data) if self.data else 0

    @property
    def yemax(self):
        return max(y+(e or 0) for _, y, e in self.data) if self.data else 0


    def paint(self, scale, painter):
        # note: scale returns a screen-XY tuple for data XY
        # draw errorbars, lines and symbols in that order
        if self.errorbarwidth > 0:
            pen = QPen()
            pen.setBrush(self.errorbarcolor)
            pen.setWidth(self.errorbarwidth)
            painter.setPen(pen)
            for _x,_y,_e in self.data:
                if _e is None:
                    continue
                x, y = scale(_x,_y)
                e = scale(_x,_y + _e)[1] - y
                painter.drawLine(x, y-e, x, y+e)
                painter.fillRect(x - self.errorbarwidth / 2., y - e,
                                 self.errorbarwidth, 2 * e, self.errorbarcolor)

        points = [QPointF(*scale(p[0], p[1])) for p in self.data]
        if self.linewidth > 0:
            pen = QPen()
            pen.setBrush(self.linecolor)
            pen.setWidth(self.linewidth)
            painter.setPen(pen)
            painter.drawPolyline(QPolygonF(points))

        if self.symbolsize > 0:
            pen = QPen()
            pen.setBrush(self.symbolcolors[0])  # linecolor
            pen.setWidth(self.symbolsize) # linewidth
            painter.setPen(pen)
            painter.setBrush(self.symbolcolors[1]) # fill color
            if self.symbolsize > 0:
                for p in points:
                    painter.drawEllipse(p, 2*self.symbolsize, 2*self.symbolsize)

    def preparepainting(self, scale, xmin, xmax):
        pass  # nothing to do


class MiniPlotFitCurve(MiniPlotCurve):

    # do not influence scaling of plotting window
    @property
    def xmin(self):
        return float('inf')

    @property
    def xmax(self):
        return float('-inf')

    @property
    def ymin(self):
        return float('inf')

    @property
    def ymax(self):
        return float('-inf')

    @property
    def yemin(self):
        return float('inf')

    @property
    def yemax(self):
        return float('-inf')

    def __init__(self, formula, params):
        super(MiniPlotFitCurve, self).__init__()
        self.formula = formula
        self.params = params

    linecolor = _blue
    linewidth = 5  # set to 0 to disable lines
    symbolsize = 0  # both symbol linewidth and symbolsize, set to 0 to disable
    errorbarwidth = 0 # set to 0 to disable errorbar

    def preparepainting(self, scale, xmin, xmax):
        # recalculate data
        points = int(scale(xmax) - scale(xmin))
        self.data = []
        for idx in range(points+1):
            x = xmin + idx * (xmax-xmin) / points
            y = self.formula(x, *self.params)
            self.data.append((x,y,None))


class MiniPlot(QWidget):
    ticklinecolors = (_grey, _lightgrey)  # ticks, subticks
    ticklinewidth = 1
    bordercolor = _black
    borderwidth = 1
    labelcolor = _black
    xlabel = 'x'
    ylabel = 'y'
    xfmt = '%.1f'
    yfmt = '%g'
    autotickx = True
    autoticky = True

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.xmin = self.xmax = None
        self.ymin = self.ymax = None
        self.curves = []
        self.plotx = 0 # left of this are labels
        self.ploty = self.height() # below this are labels

    def scaleX(self, x):
        if not self.curves:
            return x  # XXX: !!!!
        x =  self.plotx + (self.width() - self.plotx) * (x - self.xmin) / (self.xmax - self.xmin)
#        x = max(min(x, self.width()), self.plotx)
        return x

    def scaleY(self, y):
        if not self.curves:
            return y  # XXX: !!!!
        y = self.ploty * (self.ymax - y) / (self.ymax - self.ymin)
#        y = max(min(y, self.ploty), 0)
        return y

    def scale(self, x, y):
        # scales a plotting xx/y to a screen x/y to be used for painting...
        return self.scaleX(x), self.scaleY(y)

    def removeCurve(self, curve):
        if curve in self.curves:
            self.curves.remove(curve)
        self.updatePlot()

    def addCurve(self, curve):
        if curve is not None and curve not in self.curves:
            # new curve, recalculate all
            self.curves.append(curve)
        self.updatePlot()

    def updatePlot(self):
        xmin,xmax = -1,1
        ymin,ymax = -1,1
        # find limits of known curves
        if self.curves:
            xmin = min(c.xmin for c in self.curves)
            xmax = max(c.xmax for c in self.curves)
            ymin = min(c.yemin for c in self.curves)
            ymax = max(c.yemax for c in self.curves)
        # fallback values for no curve
        while xmin >= xmax:
            xmin, xmax = xmin - 1, xmax + 1
        while ymin >= ymax:
            ymin, ymax = ymin - 1, ymax + 1
        # adjust limits a little
        self.xmin = xmin - 0.05 * (xmax - xmin)
        self.xmax = xmax + 0.05 * (xmax - xmin)
        self.ymin = ymin - 0.05 * (ymax - ymin)
        self.ymax = ymax + 0.05 * (ymax - ymin)

        # (re-)generate x/yticks
        if self.autotickx:
            self.calc_xticks(xmin, xmax)
        if self. autoticky:
            self.calc_yticks(ymin, ymax)
        # redraw
        self.update()

    def calc_xticks(self, xmin, xmax):
        self.xticks = self.calc_ticks(xmin, xmax, self.xfmt)

    def calc_yticks(self, ymin, ymax):
        self.yticks = self.calc_ticks(ymin, ymax, self.yfmt)

    def calc_ticks(self, _min, _max, fmt):
        min_intervals = 2
        diff = _max - _min
        if diff <= 0:
            return [0]
        # find a 'good' step size
        step = abs(diff / min_intervals)
        # split into mantissa and exp.
        expo = 0
        while step >= 10:
            step /= 10.
            expo += 1
        while step < 1:
            step *= 10.
            expo -= 1
        # make step 'latch' into smalle bigger magic number
        subs = 1
        for n, subs in reversed([(1,5.), (1.5,3.), (2,4.), (3,3.), (5,5.), (10,2.)]):
            if step >= n:
                step = n
                break
        # convert back to normal number
        while expo > 0:
            step *= 10.
            expo -= 1
        while expo < 0:
            step /= 10.
            expo += 1
        substep = step / subs
        # round lower
        rounded_min = step * int(_min / step)

        # generate ticks list
        ticks = []
        x = rounded_min
        while x + substep < _min:
            x += substep
        for _ in range(100):
            if x < _max + substep:
                break

            # check if x is a tick or a subtick
            x = substep * int(x / substep)
            if abs(x - step * int(x / step)) <= substep / 2:
                # tick
                ticks.append((x, fmt % x))
            else:
                # subtick
                ticks.append((x, ''))
            x += substep
        return ticks


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # obtain a few properties we need for proper drawing

        painter.setFont(self.font())
        fm = painter.fontMetrics()
        label_height = fm.height()

        self.plotx = 3 + 2 * label_height
        self.ploty = self.height() - 3 - 2 * label_height

        # fill bg of plotting area
        painter.fillRect(self.plotx ,0,self.width()-self.plotx, self.ploty,_white)

        # paint ticklines
        if self.curves and self.ticklinewidth > 0:
            for e in self.xticks:
                try:
                    _x = e[0]  # pylint: disable=unsubscriptable-object
                    _l = e[1]  # pylint: disable=unsubscriptable-object
                except TypeError:
                    _x = e
                    _l = self.xfmt % _x
                x = self.scaleX(_x)
                pen = QPen()
                pen.setBrush(self.ticklinecolors[0 if _l else 1])
                pen.setWidth(self.ticklinewidth)
                painter.setPen(pen)
                painter.drawLine(x, 0, x, self.ploty)
            for e in self.yticks:
                try:
                    _y = e[0]  # pylint: disable=unsubscriptable-object
                    _l = e[1]  # pylint: disable=unsubscriptable-object
                except TypeError:
                    _y = e
                    _l = self.xfmt % _x
                y = self.scaleY(_y)
                pen = QPen()
                pen.setBrush(self.ticklinecolors[0 if _l else 1])
                pen.setWidth(self.ticklinewidth)
                painter.setPen(pen)
                painter.drawLine(self.plotx, y, self.width(), y)

        # paint curves
        painter.setClipRect(QRectF(self.plotx, 0, self.width()-self.plotx, self.ploty))
        for c in self.curves:
            c.preparepainting(self.scaleX, self.xmin, self.xmax)
            c.paint(self.scale, painter)
        painter.setClipping(False)

        # paint frame
        pen = QPen()
        pen.setBrush(self.bordercolor)
        pen.setWidth(self.borderwidth)
        painter.setPen(pen)
        painter.drawPolyline(QPolygonF([
                                        QPointF(self.plotx, 0),
                                        QPointF(self.width()-1, 0),
                                        QPointF(self.width()-1, self.ploty),
                                        QPointF(self.plotx, self.ploty),
                                        QPointF(self.plotx, 0),
                                       ]))

        # draw labels
        painter.setBrush(self.labelcolor)
        h2 = (self.height()-self.ploty)/2.
        # XXX: offset axis labels from axis a little
        painter.drawText(self.plotx, self.ploty + h2,
                         self.width() - self.plotx, h2,
                         Qt.AlignCenter | Qt.AlignVCenter, self.xlabel)
        # rotate ylabel?
        painter.resetTransform()
        painter.translate(0, self.ploty / 2.)
        painter.rotate(-90)
        w = fm.width(self.ylabel)
        painter.drawText(-w, -fm.height() / 2., w * 2, self.plotx,
                         Qt.AlignCenter | Qt.AlignTop, self.ylabel)
        painter.resetTransform()

        if self.curves:
            for e in self.xticks:
                try:
                    _x = e[0]  # pylint: disable=unsubscriptable-object
                    l = e[1]  # pylint: disable=unsubscriptable-object
                except TypeError:
                    _x = e
                    l = self.xfmt % _x
                x = self.scaleX(_x)
                w = fm.width(l)
                painter.drawText(x - w, self.ploty + 2, 2 * w, h2,
                                 Qt.AlignCenter | Qt.AlignVCenter, l)
            for e in self.yticks:
                try:
                    _y = e[0]  # pylint: disable=unsubscriptable-object
                    l = e[1]  # pylint: disable=unsubscriptable-object
                except TypeError:
                    _y = e
                    l = self.yfmt % _y
                y = self.scaleY(_y)
                w = fm.width(l)
                painter.resetTransform()
                painter.translate(self.plotx - fm.height(), y + w)
                painter.rotate(-90)
                painter.drawText(0, -1,
                                 2 * w, fm.height(),
                                 Qt.AlignCenter | Qt.AlignBottom, l)
            painter.resetTransform()

    def sizeHint(self):
        return QSize(320, 240)
