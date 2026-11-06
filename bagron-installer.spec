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

release_payload_root = Path('build/release-payload')
if not (release_payload_root / 'bagron-prebuilt.json').is_file():
    raise SystemExit(
        'Falta el compilador preconstruido; ejecuta '
        'tools/prepare_release_payload.py antes de PyInstaller.'
    )
release_payload = [
    (
        str(path),
        str(Path('bagron-payload') / path.relative_to(release_payload_root).parent),
    )
    for path in release_payload_root.rglob('*')
    if path.is_file()
]


a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=portable_python + release_payload,
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
