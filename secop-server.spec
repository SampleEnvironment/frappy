# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['bin\\secop-server'],
             pathex=['.'],
             binaries=[],
             datas=[],
             hiddenimports=['secop.protocol', 'secop.protocol.dispatcher', 'secop.protocol.interface', 'secop.protocol.interface.tcp', 
                            'secop_psi.ppmssim', 'secop_psi.ppmswindows', 'secop_psi.ppms'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='secop-server',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='secop-server')
