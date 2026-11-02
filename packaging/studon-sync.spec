# PyInstaller spec: build from packaging/ with
#   ../.venv/bin/pyinstaller --noconfirm --distpath ../dist --workpath ../build studon-sync.spec
# macOS -> dist/StudOn Sync.app ; Windows/Linux -> dist/StudOn Sync/ (onedir)
import sys

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules("PFERD") + collect_submodules("keyring.backends")
if sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
elif sys.platform == "win32":
    hiddenimports += ["webview.platforms.edgechromium", "webview.platforms.winforms"]

datas = copy_metadata("keyring") + copy_metadata("PFERD") + [("../src/studon_sync/ui/static", "studon_sync/ui/static")]

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    hiddenimports=hiddenimports,
    datas=datas,
    # nothing here needs these; keeps the bundle small
    excludes=["tkinter", "PySide6", "PyQt5", "PyQt6", "qtpy", "gi", "unittest", "pydoc_data", "test", "setuptools", "pip"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudOn Sync", console=False, strip=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=True, name="StudOn Sync")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="StudOn Sync.app",
        bundle_identifier="de.fau.studon-sync",
        info_plist={"CFBundleShortVersionString": "0.3.0", "NSHighResolutionCapable": True},
    )
