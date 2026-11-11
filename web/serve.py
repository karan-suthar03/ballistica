#!/usr/bin/env python3
"""Dev server for the web build.

Serves build/web/dist with the cross-origin-isolation headers that
SharedArrayBuffer (wasm threads) needs, and appends anything POSTed to
/log into build/web/browser.log so engine output can be read remotely.

usage: web/serve.py [port]   (default 8000)
"""

import http.server
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'build' / 'web' / 'dist'
LOG = ROOT / 'build' / 'web' / 'browser.log'


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.wasm': 'application/wasm',
        '.js': 'text/javascript',
        '.data': 'application/octet-stream',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        if self.path.rstrip('/').endswith('/log'):
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length).decode('utf-8', 'replace')
            with LOG.open('a', encoding='utf-8') as f:
                f.write(data)
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        if '/log' not in (args[0] if args else ''):
            sys.stderr.write(fmt % args + '\n')


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.makedirs(DIST, exist_ok=True)
    print(f'serving {DIST} on http://0.0.0.0:{port} (log: {LOG})')
    http.server.ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
