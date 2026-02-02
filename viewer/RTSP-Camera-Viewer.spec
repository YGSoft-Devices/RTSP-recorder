# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\sn8k\\Documents\\gitHub\\RTSP-Full\\RTSP-recorder\\viewer\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\sn8k\\Documents\\gitHub\\RTSP-Full\\RTSP-recorder\\viewer\\README.md', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RTSP-Camera-Viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
