# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

playwright_datas, playwright_binaries, playwright_hidden = collect_all('playwright')
pywinauto_hidden = collect_submodules('pywinauto')

analysis = Analysis(
    ['launcher.py'],
    pathex=['src'],
    binaries=playwright_binaries,
    datas=playwright_datas,
    hiddenimports=playwright_hidden + pywinauto_hidden + ['plibrary.models', 'plibrary.storage', 'plibrary.visual', 'plibrary.windows_viewer', 'plibrary.browser', 'plibrary.providers'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name='PLibrary',
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
