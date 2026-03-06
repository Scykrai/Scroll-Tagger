# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for scroll-tagger.
# Produces a single self-contained executable: dist/scroll-tagger
#
# Build with:
#   pyinstaller scroll_tagger.spec
# or:
#   make build

from PyInstaller.building.build_main import Analysis, PYZ, EXE

a = Analysis(
    ["scroll_tagger/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "scroll_tagger",
        "scroll_tagger.extract_tags",
        "scroll_tagger.tagger_client",
        "scroll_tagger.scryfall_client",
        "scroll_tagger.output_writer",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 'cryptography' is a system-compiled extension that can fail inside
    # PyInstaller's isolation on some Linux distros. requests uses Python's
    # built-in ssl module and does not need the cryptography package at runtime.
    excludes=["cryptography", "_pytest", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="scroll-tagger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
)
