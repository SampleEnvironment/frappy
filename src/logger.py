#  -*- coding: utf-8 -*-
# *****************************************************************************
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

"""Loggers"""

import logging
from os import path

from paths import log_path


def get_logger(inst='', loglevel=logging.INFO):
    loglevelmap = {'debug': logging.DEBUG,
                   'info': logging.INFO,
                   'warning': logging.WARNING,
                   'error': logging.ERROR,
                   }
    loglevel = loglevelmap.get(loglevel, loglevel)
    logging.basicConfig(level=loglevel,
                        format='#[%(asctime)-15s][%(levelname)s]: %(message)s')

    logger = logging.getLogger(inst)
    logger.setLevel(loglevel)
    fh = logging.FileHandler(path.join(log_path, inst + '.log'))
    fh.setLevel(loglevel)
    logger.addHandler(fh)
    logging.root.addHandler(fh)  # ???
    return logger
