"""Development only: serves the UI on http://127.0.0.1:<port> for a normal browser.

window.pywebview.api is replaced by a fetch() shim that calls the same Api methods over HTTP.
"""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .api import Api
from .app import STATIC

SHIM = """<script>
window.pywebview = { api: new Proxy({}, { get: (_, name) => (...args) =>
  fetch('/api/' + name, { method: 'POST', body: JSON.stringify(args) }).then(r => r.json()) }) };
addEventListener('DOMContentLoaded', () => dispatchEvent(new Event('pywebviewready')));
</script>"""


def serve(port: int = 8765) -> None:
    api = Api()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            super().__init__(*args, directory=str(STATIC), **kwargs)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text(encoding="utf-8").replace("<script src", SHIM + "<script src", 1)
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            else:
                super().do_GET()

        def do_POST(self) -> None:
            name = self.path.removeprefix("/api/")
            args = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"[]")
            if name.startswith("_") or not hasattr(api, name):
                self.send_error(404)
                return
            body = json.dumps(getattr(api, name)(*args)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    print(f"http://127.0.0.1:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
