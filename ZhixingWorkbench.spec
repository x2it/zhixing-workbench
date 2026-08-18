# -*- mode: python ; coding: utf-8 -*-
# 知行工作台 v3.2 PyInstaller 配置（onedir + tkinterdnd2 拖拽支持）

block_cipher = None

_a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app_icon.ico", "."),
        ("version_info.txt", "."),
        (r"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\lib\site-packages\tkinterdnd2\tkdnd\win-x64", "tkdnd/win-x64"),
        (r"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\lib\site-packages\tkinterdnd2\tkdnd", "tkdnd"),
    ],
    hiddenimports=[
        "PIL._tkinter_finder",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "customtkinter",
        "customtkinter.windows.widgets",
        "tkinter.ttk",
        "tkinterdnd2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "pytest",
        "black",
        "flake8",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(_a.pure, _a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    _a.scripts,
    [],
    exclude_binaries=True,
    name="知行工作台",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app_icon.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    _a.binaries,
    _a.zipfiles,
    _a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="知行工作台",
)
