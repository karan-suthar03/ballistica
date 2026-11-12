#!/usr/bin/env python3
"""Dev server for the web build.

Serves build/web/dist with the cross-origin-isolation headers that
SharedArrayBuffer (wasm threads) needs, and appends anything POSTed to
/log into build/web/browser.log so engine output can be read remotely.

Large files are served pre-compressed when package.sh produced a .br or
.gz sibling and the client accepts that encoding. Every response carries
an ETag with `Cache-Control: no-cache`, so browsers keep the 180 MB data
file and only revalidate it (304) on reload.

usage: web/serve.py [port]   (default 8000)
"""

import email.utils
import http.server
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'build' / 'web' / 'dist'
LOG = ROOT / 'build' / 'web' / 'browser.log'

TYPES = {
    '.wasm': 'application/wasm',
    '.js': 'text/javascript',
    '.data': 'application/octet-stream',
    '.html': 'text/html; charset=utf-8',
    '.webmanifest': 'application/manifest+json',
}
# Preferred first.
ENCODINGS = (('br', '.br'), ('gzip', '.gz'))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        **TYPES,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def _pick(self, path: str):
        """Return (file to send, content-encoding or None)."""
        accepted = self.headers.get('Accept-Encoding', '')
        src_mtime = os.stat(path).st_mtime_ns
        for name, suffix in ENCODINGS:
            # A sibling older than its source is stale (compress.sh still
            # running); never serve it.
            if (
                name in accepted
                and os.path.isfile(path + suffix)
                and os.stat(path + suffix).st_mtime_ns >= src_mtime
            ):
                return path + suffix, name
        return path, None

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, 'index.html')
        if not os.path.isfile(path):
            return super().send_head()
        src, enc = self._pick(path)
        st = os.stat(src)
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}-{enc or "id"}"'
        if self.headers.get('If-None-Match') == etag:
            self.send_response(304)
            self.send_header('ETag', etag)
            self.send_header('Vary', 'Accept-Encoding')
            self.end_headers()
            return None
        f = open(src, 'rb')  # pylint: disable=consider-using-with
        self.send_response(200)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Length', str(st.st_size))
        self.send_header(
            'Last-Modified', email.utils.formatdate(st.st_mtime, usegmt=True)
        )
        self.send_header('ETag', etag)
        self.send_header('Vary', 'Accept-Encoding')
        if enc:
            self.send_header('Content-Encoding', enc)
        self.end_headers()
        return f

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
