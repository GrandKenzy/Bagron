# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


portable_python_root = Path('build/portable-python')
if not portable_python_root.is_dir():
    raise SystemExit(
        'Falta build/portable-python; ejecuta tools/prepare_portable_python.py antes de PyInstaller.'
    )
portable_python = [
    (
        str(path),
        str(Path('portable-python') / path.relative_to(portable_python_root).parent),
    )
    for path in portable_python_root.rglob('*')
    if path.is_file()
]
if not portable_python:
    raise SystemExit('build/portable-python no contiene archivos para embebir.')


a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=portable_python,
    hiddenimports=[],
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
    name='bagron-installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
