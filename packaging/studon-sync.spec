# PyInstaller spec: build with `pyinstaller packaging/studon-sync.spec` from the repo root.
# macOS -> dist/StudOn Sync.app ; Windows/Linux -> dist/StudOn Sync/ (onedir)
import sys

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules("PFERD") + collect_submodules("keyring.backends")
datas = copy_metadata("keyring") + copy_metadata("PFERD")

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    hiddenimports=hiddenimports,
    datas=datas,
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudOn Sync", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="StudOn Sync")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="StudOn Sync.app",
        bundle_identifier="de.fau.studon-sync",
        info_plist={"CFBundleShortVersionString": "0.2.0", "NSHighResolutionCapable": True},
    )
