#!/usr/bin/env python3
# *****************************************************************************
# MLZ Tango client tool
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
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************


from pathlib import Path

from setuptools import find_packages, setup

import frappy.version

# cfg-editor is currently not functional
scripts = [str(script) for script in Path('bin').glob('frappy-*')
           if not str(script).endswith('cfg-editor')]


frappydir = Path(__file__).parent / 'frappy'
uidir = frappydir / 'gui' / 'ui'
uis = [str(f.relative_to(frappydir)) for f in uidir.iterdir()]

setup(
    name='frappy-core',
    version=frappy.version.get_version(),
    license='GPL',
    author='Enrico Faulhaber',
    author_email='enrico.faulhaber@frm2.tum.de',
    description='SECoP Playground core system',
    packages=find_packages(exclude=['test']),
    package_data={'frappy': ['RELEASE-VERSION'] + uis},
    install_requires=[
        "pyserial",
        "mlzlog",
        "psutil",
        "python-daemon",
    ],

    data_files=[
        ('/lib/systemd/system-generators', ['etc/frappy-generator']),
        ('/lib/systemd/system', ['etc/frappy@.service',
                                 'etc/frappy.target',
                                 ]),
        ('/var/log/frappy', []),
    ],
    scripts=scripts,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Scientific/Engineering :: Physics',
    ],
)
