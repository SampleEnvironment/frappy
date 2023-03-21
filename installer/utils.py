#  -*- coding: utf-8 -*-

import os
import subprocess
import sys
from os import path

rootdir = path.abspath('..')
guidirs = [path.join('frappy', 'gui')]

# Make sure to generate the version file.
os.environ['PYTHONPATH'] = os.environ.get('PYTHONPATH', '') + path.pathsep + rootdir
subprocess.check_call([sys.executable,
                       path.join(rootdir, 'frappy', 'version.py')])


# Include all .ui files for the main GUI module.
def find_uis():
    res = []
    for guidir in guidirs:
        for root, _dirs, files in os.walk(path.join(rootdir, guidir)):
            if any(uifile for uifile in files if uifile.endswith('.ui')):
                res.append((path.join(root, '*.ui'),
                            path.join(guidir,
                                      root[len(path.join(rootdir, guidir)) + 1:])))
    return res


# Include all modules found in a certain package -- they may not be
# automatically found because of dynamic importing via the guiconfig file
# and custom widgets in .ui files.
def find_modules(*modules):
    res = []
    startdir = path.join(rootdir, *modules)
    startmod = '.'.join(modules) + '.'
    for root, _dirs, files in os.walk(startdir):
        modpath = root[len(startdir) + 1:].replace(path.sep, '.')
        if modpath:
            modpath += '.'
        for mod in files:
            if mod.endswith('.py'):
                res.append(startmod + modpath + mod[:-3])
    return res
