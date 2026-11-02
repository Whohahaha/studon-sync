"""Opens the UI window (system WebView via pywebview: WKWebView on macOS, WebView2 on Windows)."""

from pathlib import Path

import webview

from ..core import settings as settings_mod
from ..i18n import set_language, t
from .api import Api


STATIC = Path(__file__).resolve().parent / "static"  # also valid inside the PyInstaller bundle


def run() -> int:
    set_language(settings_mod.load().language)
    api = Api()
    window = webview.create_window(
        t("app.title"),
        str(STATIC / "index.html"),
        js_api=api,
        width=1020,
        height=720,
        min_size=(820, 560),
    )
    api.attach(window)
    webview.start()
    return 0
