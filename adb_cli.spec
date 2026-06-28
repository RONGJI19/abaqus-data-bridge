# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ADB CLI 轻量版 (不含GUI依赖)"""

from pathlib import Path

PROJ_ROOT = Path(SPECPATH)

a = Analysis(
    ['run_cli.py'],
    pathex=[str(PROJ_ROOT)],
    binaries=[],
    datas=[
        (str(PROJ_ROOT / 'adb' / 'templates' / 'config_template.yaml'), 'adb/templates'),
    ],
    hiddenimports=[
        'adb', 'adb.cli', 'adb.parsers', 'adb.parsers.inp_parser',
        'adb.parsers.dat_parser', 'adb.parsers.version_patterns',
        'adb.models', 'adb.models.inp_model', 'adb.models.dat_model',
        'adb.models.extraction_config',
        'adb.core', 'adb.core.engine', 'adb.core.matcher',
        'adb.core.statistics',
        'adb.exporters', 'adb.exporters.csv_exporter',
        'adb.exporters.streaming',
        'adb.utils', 'adb.utils.fortran', 'adb.utils.encoding',
        'adb.utils.progress',
        'yaml', 'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy',
        'notebook', 'jupyter', 'IPython',
        # 排除所有GUI相关
        'PySide6', 'PyQt5', 'PyQt6', 'shiboken6',
        'QtCore', 'QtGui', 'QtWidgets',
        'tkinter', '_tkinter', 'Tkinter',
        'curses', 'readline',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ADB_CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
