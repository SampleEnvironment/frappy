#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ Tango client tool
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
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************

from setuptools import setup, find_packages
from os import path, listdir
from glob import glob

import secop.version


scripts = glob(path.join('bin', 'secop-*'))

uidir = path.join(path.dirname(__file__), 'secop', 'gui', 'ui')
uis = [path.join('gui', 'ui', entry) for entry in listdir(uidir)]

setup(
    name = 'secop-core',
    version = secop.version.get_version(),
    license = 'GPL',
    author = 'Enrico Faulhaber',
    author_email = 'enrico.faulhaber@frm2.tum.de',
    description = 'SECoP Playground core system',
    packages = find_packages(),
    package_data = {'secop': ['RELEASE-VERSION'] + uis},
    scripts = scripts,
    classifiers = [
        'Development Status :: 6 - Mature',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'License :: OSI Approved :: GPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Scientific/Engineering :: Physics',
    ],
)
