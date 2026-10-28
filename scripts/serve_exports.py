"""Serve the rendered episodes for preview and download.

Python's `http.server` does not answer Range requests, which makes an MP4 stall
or refuse to seek in a browser. This is a ~100-line replacement: a gallery page
listing every clip, byte-range support so the player can seek, and the zip.

    python scripts/serve_exports.py --port 8000
"""
import argparse
import html
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'exports'
CHUNK = 1024 * 256
RANGE = re.compile(r'bytes=(\d*)-(\d*)')


def gallery():
    manifest = ROOT / 'videos' / 'manifest.json'
    records = []
    if manifest.exists():
        records = json.loads(manifest.read_text(encoding='utf-8'))['episodes']
    cards = '\n'.join(
        '<article><h2>%02d · %s</h2>'
        '<video controls preload="metadata" src="/videos/%s"></video>'
        '<p>%s s · %dx%d · %.1f MB · %s</p>'
        '<p><a href="/videos/%s" download>Download MP4</a></p></article>'
        % (item['episode'], html.escape(item['hook']), Path(item['file']).name,
           item['seconds'], item['width'], item['height'], item['bytes'] / 1e6,
           html.escape(item.get('voice') or 'silent'),
           Path(item['file']).name) for item in records)
    zip_link = ''
    if (ROOT / 'StratEvo_19_Videos.zip').exists():
        zip_link = '<p><a href="/StratEvo_19_Videos.zip" download>Download all 19 (zip)</a></p>'
    return ('<!doctype html><meta charset="utf-8"><title>StratEvo · 19 kinetic episodes</title>'
            '<style>body{background:#000;color:#fff;font:16px/1.5 system-ui,sans-serif;'
            'margin:0;padding:32px}h1{font-size:28px;letter-spacing:-.03em}'
            'article{border:1px solid #262626;border-radius:14px;padding:16px;margin:0 0 20px}'
            'h2{font-size:17px;margin:0 0 10px;color:#4ADE80}'
            'video{width:100%;max-width:340px;border-radius:10px;background:#0D0D0D}'
            'p{color:#A7F3D0;margin:8px 0}'
            'a{color:#fff}</style><h1>StratEvo · 19 kinetic episodes (20.60 s)</h1>'
            + zip_link + cards).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    server_version = 'StratevoExports/1'

    def log_message(self, fmt, *args):
        pass

    def do_HEAD(self):
        self.respond(body_only=True)

    def do_GET(self):
        self.respond()

    def resolve(self):
        path = self.path.split('?')[0].lstrip('/')
        if path in ('', 'index.html'):
            return None
        candidate = (ROOT / path).resolve()
        if ROOT.resolve() not in candidate.parents or not candidate.is_file():
            return False
        return candidate

    def respond(self, body_only=False):
        target = self.resolve()
        if target is None:
            payload = gallery()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            if not body_only:
                self.wfile.write(payload)
            return
        if target is False:
            self.send_error(404)
            return
        size = target.stat().st_size
        start, end = 0, size - 1
        status = 200
        header = self.headers.get('Range')
        if header:
            match = RANGE.match(header)
            if match:
                start = int(match.group(1) or 0)
                end = int(match.group(2)) if match.group(2) else size - 1
                end = min(end, size - 1)
                if start > end:
                    self.send_error(416)
                    return
                status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header('Content-Type', 'video/mp4' if target.suffix == '.mp4' else 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'public, max-age=3600')
        if status == 206:
            self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        self.end_headers()
        if body_only:
            return
        with target.open('rb') as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8000')))
    parser.add_argument('--host', default='0.0.0.0')
    arguments = parser.parse_args()
    server = ThreadingHTTPServer((arguments.host, arguments.port), Handler)
    print('Serving %s on http://%s:%d' % (ROOT, arguments.host, arguments.port), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
