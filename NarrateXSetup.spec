# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Oliver\\Development\\NarrateX\\installer\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Oliver\\Development\\NarrateX\\installer\\payload\\payload.zip', 'installer/payload'), ('C:\\Users\\Oliver\\Development\\NarrateX\\installer\\payload\\manifest.json', 'installer/payload'), ('C:\\Users\\Oliver\\Development\\NarrateX\\LICENSE', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\LGPL3-LICENSE', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex.ico', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_16.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_32.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_48.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_64.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_128.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_256.png', '.'), ('C:\\Users\\Oliver\\Development\\NarrateX\\narratex_512.png', '.')],
    hiddenimports=['installer.ui.worker'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NarrateXSetup',
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
    icon=['C:\\Users\\Oliver\\Development\\NarrateX\\narratex.ico'],
)
