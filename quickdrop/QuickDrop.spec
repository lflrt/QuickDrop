# -*- mode: python ; coding: utf-8 -*-
"""QuickDrop PyInstaller 打包配置。

单文件（--onefile）GUI 程序。要点：
- tkinterdnd2 带 tkdnd 原生库 → collect_all
- plyer 按平台动态导入通知模块 → collect_all
- zeroconf 子模块较多 → collect_all
- static/ 打进只读资源目录（运行时解到 sys._MEIPASS）
- config.json 不打包：首次运行由 utils.load_config() 在 exe 旁生成（可写）
构建：pyinstaller --noconfirm QuickDrop.spec  →  dist/QuickDrop.exe
"""
from PyInstaller.utils.hooks import collect_all

datas = [("static", "static")]          # 只读资源：前端页面/图标/manifest/sw
binaries = []
hiddenimports = []

for _pkg in ("tkinterdnd2", "plyer", "zeroconf"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    ["server.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "pydoc", "doctest"],
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
    name="QuickDrop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # GUI 程序；诊断走 exe 旁 logs/quickdrop.log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
