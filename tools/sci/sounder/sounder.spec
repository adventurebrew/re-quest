# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['sounder.py'],
    pathex=['.'],
    binaries=[],
    datas=[('misc', 'misc')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pil'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# First executable for windowed mode.
exe_w = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sounderw',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='misc\\sounder.ico',
)

# Another executable on for console mode.
exe_c = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sounder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='misc\\sounder.ico',
)
all_exe = [exe_w, exe_c]



coll = COLLECT(
    *all_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='sounder',
)
