from __future__ import annotations

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


def main() -> None:
    root = Path(__file__).resolve().parent
    server = ThreadingHTTPServer(("127.0.0.1", 8000), NoCacheHandler)
    print(f"Serving {root} at http://127.0.0.1:8000")
    print("Open index.html in your browser, or use the URL above.")
    server.serve_forever()


if __name__ == "__main__":
    main()
