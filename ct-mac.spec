# -*- mode: python ; coding: utf-8 -*-
#
# Build (macOS example):
#   uv run pyinstaller ComicTranslate.spec
#
# Notes:
# - macOS prefers `.icns` for both app + document icons. This spec uses your existing
#   `resources/icon.ico` for now (it will still build; Finder may not show it as a doc icon).
#

from __future__ import annotations

import os
from PyInstaller.utils.hooks import collect_all


block_cipher = None

here = os.path.abspath(globals().get("SPECPATH", os.getcwd()))

app_name = "Comic Translate"
entrypoint = os.path.join(here, "comic.py")

bundle_identifier = "com.comiclabs.comictranslate"
project_uti = "com.comiclabs.comictranslate.ctpr"
project_ext = "ctpr"

resources_dir = os.path.join(here, "resources")
icon_path = os.path.join(resources_dir, "icons", "icon.icns")
file_icon_path = os.path.join(resources_dir, "icons", "file_icon.icns")

psd_datas, psd_binaries, psd_hiddenimports = collect_all("photoshopapi")
np_datas, np_binaries, np_hiddenimports = collect_all("numpy")

a = Analysis(
    [entrypoint],
    pathex=[here],
    binaries=psd_binaries + np_binaries,
    datas=[
        # Mirrors: --add-data "resources:resources"
        (resources_dir, "resources"),
        # Also place the icon at bundle Resources root so Info.plist can reference it.
        (file_icon_path, "."),
    ] + psd_datas + np_datas,
    hiddenimports=sorted(set(
        psd_hiddenimports
        + np_hiddenimports
        + [
            # Mirrors: --hidden-import=requests
            "requests",
            "numpy.core.multiarray",
            "numpy.core._multiarray_umath",
            "numpy.core.umath",
        ]
    )),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(here, "pyinstaller_rth_numpy_compat.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, 
    disable_windowed_traceback=True,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)

app = BUNDLE(
    coll,
    name=f"{app_name}.app",
    icon=icon_path,
    bundle_identifier=bundle_identifier,
    argv_emulation=True,
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        
        # File association for `.ctpr`
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Comic Translate Project",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "LSItemContentTypes": [project_uti],
                # Document icon file name in Contents/Resources
                "CFBundleTypeIconFile": os.path.basename(file_icon_path),
            }
        ],
        # Declare our custom type (UTI) and map it to the `.ctpr` extension.
        "UTExportedTypeDeclarations": [
            {
                "UTTypeIdentifier": project_uti,
                "UTTypeDescription": "Comic Translate Project",
                "UTTypeConformsTo": ["public.data"],
                "UTTypeTagSpecification": {
                    "public.filename-extension": [project_ext],
                },
                "UTTypeIconFile": os.path.basename(file_icon_path),
            }
        ],
    },
)

