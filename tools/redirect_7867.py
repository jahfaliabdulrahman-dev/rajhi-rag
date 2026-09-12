#!/usr/bin/env python3
"""Redirect the template port to the real app.

History: the owner opened :7867 (the HTML template scaffold) three times and
read its DEMO rows ("مثال ١ / مثال ٢") as an app failure. The template is a dev
artifact; the real app lives on :7860. This redirect makes any stale bookmark
self-heal: whatever hits :7867 lands on the real app.

Run via launchd: com.jahfali.rajhi-redirect (KeepAlive).

Dev note: :7867 is now permanently reserved for this redirect — run any future
template preview on another port (7868+).
"""
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

SOURCE_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7867
TARGET = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:7860"


class Redirector(BaseHTTPRequestHandler):
    def _go(self):
        self.send_response(302)
        self.send_header("Location", TARGET)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        self._go()

    def do_HEAD(self):  # noqa: N802
        self._go()

    def log_message(self, format, *args):  # noqa: A002 — keep the log quiet
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", SOURCE_PORT), Redirector).serve_forever()
