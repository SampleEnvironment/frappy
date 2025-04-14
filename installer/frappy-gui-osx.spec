# -*- mode: python -*-

import sys
from os import path

sys.path.insert(0, path.abspath('.'))

from utils import find_modules, find_uis, rootdir

binscript = path.join(rootdir, 'bin', 'frappy-gui')

a = Analysis(
    [binscript],
    pathex=[rootdir],
    binaries=[],
    datas=find_uis() +
          [(path.join(rootdir, 'frappy', 'RELEASE-VERSION'), 'frappy')],
    hiddenimports=find_modules('frappy', 'gui'),
    hookspath=[],
    excludes=['matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None
)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None
)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='frappy-gui',
    strip=False,
    debug=False,
    upx=False,
    console=False
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='frappy-gui',
)
app = BUNDLE(
    coll,
    name='frappy-gui.app',
    bundle_identifier=None,
)
