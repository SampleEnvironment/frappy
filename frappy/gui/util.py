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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************


from pathlib import Path

from frappy.gui.qt import QColor, uic

uipath = Path(__file__).parent


def loadUi(widget, uiname, subdir='ui'):
    uic.loadUi(uipath / subdir / uiname, widget)


def is_light_theme(palette):
    background = palette.window().color().lightness()
    foreground = palette.windowText().color().lightness()
    return background > foreground


class Colors:
    @classmethod
    def _setPalette(cls, palette):
        if hasattr(cls, 'palette'):
            return
        cls.palette = palette
        if is_light_theme(palette): # light
            cls.colors = {
                          'gray' : QColor('#696969'),
                          'red' : QColor('#FF0000'),
                          'orange': QColor('#FA6800'),
                          'yellow': QColor('#FCFFa4'),
                          'plot-fg': QColor('black'),
                          'plot-bg': QColor('white'),
                          0: QColor('black'),
                          1: QColor('blue'),
                          2: QColor('#FA6800'),
                          3: QColor('green'),
                          4: QColor('red'),
                          5: QColor('purple'),
                          }
        else: # dark
            cls.colors = {
                          'gray' : QColor('#AAAAAA'),
                          'red' : QColor('#FF0000'),
                          'orange': QColor('#FA6800'),
                          'yellow': QColor('#FEFE22'),
                          'plot-fg': QColor('white'),
                          'plot-bg': QColor('black'),
                          0: QColor('white'),
                          1: QColor('#72ADD4'),
                          2: QColor('#FA6800'),
                          3: QColor('olive'),
                          4: QColor('red'),
                          5: QColor('purple'),
                          }
