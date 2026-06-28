# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 将 ADB GUI 打包为独立 .exe"""

import sys
from pathlib import Path

# 项目根目录 (PyInstaller 用 SPECPATH)
PROJ_ROOT = Path(SPECPATH)

a = Analysis(
    ['adb/gui.py'],
    pathex=[str(PROJ_ROOT)],
    binaries=[],
    datas=[
        # 打包模板文件
        (str(PROJ_ROOT / 'adb' / 'templates' / 'config_template.yaml'), 'adb/templates'),
    ],
    hiddenimports=[
        'adb', 'adb.cli', 'adb.gui', 'adb.parsers', 'adb.parsers.inp_parser',
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
    name='ADB_GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
