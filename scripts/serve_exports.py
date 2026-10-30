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


STYLE = ('<style>body{background:#000;color:#fff;font:15px/1.55 system-ui,sans-serif;'
         'margin:0;padding:28px 32px}h1{font-size:26px;letter-spacing:-.03em;margin:0 0 6px}'
         'h1 span{color:#4ADE80}.lede{color:#8a8a8a;max-width:760px;margin:0 0 26px}'
         'h2.section{font-size:13px;letter-spacing:.14em;text-transform:uppercase;'
         'color:#8a8a8a;border-top:1px solid #1c1c1c;padding-top:22px;margin:34px 0 16px}'
         '.grid{display:flex;flex-wrap:wrap;gap:18px}'
         'article{border:1px solid #262626;border-radius:14px;padding:14px;width:360px;'
         'background:#0b0b0b}'
         'h3{font-size:15px;margin:0 0 8px;color:#4ADE80}'
         'h3 em{font-style:normal;color:#fff;font-weight:700}'
         'video{width:100%;border-radius:10px;background:#000;display:block}'
         'p{color:#a7f3d0;margin:8px 0 0;font-size:13px}'
         'p.quote{color:#fff;font-size:13px}p small{color:#8a8a8a}'
         'a{color:#fff}</style>')

LAYOUT_NAMES = {'A': 'audit dashboard + radar + checklist',
                'B': 'wire transfer + cost bars + defect maths',
                'C': 'supplier alert + missing docs + verify list',
                'D': 'kinetic card + cards + chat'}


def _records(folder):
    manifest = ROOT / folder / 'manifest.json'
    if not manifest.exists():
        return []
    return json.loads(manifest.read_text(encoding='utf-8'))['episodes']


def _card(item, folder, badge=''):
    name = Path(item['file']).name
    layout = (item.get('layout') or '').upper()
    title = ('%s · %s' % (badge or '%02d' % item['episode'],
                          html.escape(LAYOUT_NAMES.get(layout, 'kinetic'))))
    hook = html.escape(item.get('hook') or '')
    return ('<article><h3>%s</h3>'
            '<video controls preload="metadata" playsinline src="/%s/%s"></video>'
            '<p class="quote">%s</p>'
            '<p>%s s · %dx%d · %.1f MB · <small>%s</small></p>'
            '<p><a href="/%s/%s" download>Download MP4</a></p></article>'
            % (title, folder, name, hook, item['seconds'], item['width'],
               item['height'], item['bytes'] / 1e6,
               html.escape(item.get('voice') or 'silent'), folder, name))


def gallery():
    preview = _records('preview')
    videos = _records('videos')
    sections = []
    if preview:
        badges = {'A': 'LAYOUT A', 'B': 'LAYOUT B', 'C': 'LAYOUT C', 'D': 'LAYOUT D'}
        sections.append('<h2 class="section">Review build · one clip per layout · '
                        'music + foley, no narration yet</h2><div class="grid">%s</div>'
                        % '\n'.join(_card(item, 'preview',
                                           badges.get((item.get('layout') or '').upper(),
                                                      '%02d' % item['episode']))
                                     for item in preview))
    if videos:
        sections.append('<h2 class="section">Delivered masters · 19 episodes · '
                        'replaced once a neural voice is configured</h2><div class="grid">%s</div>'
                        % '\n'.join(_card(item, 'videos') for item in videos))
    if not sections:
        sections.append('<p>Nothing rendered yet. Run '
                        '<code>python scripts/render_kinetic_series.py</code>.</p>')
    return ('<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>StratEvo · kinetic series</title>' + STYLE +
            '<h1>StratEvo<span>.</span> kinetic series</h1>'
            '<p class="lede">1080×1920 · 30 fps · 20.60 s. Find. Vet. Verify. → '
            'stratevo.online</p>' + ''.join(sections)).encode('utf-8')


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
        mime = {'.mp4': 'video/mp4', '.png': 'image/png', '.json': 'application/json',
                '.txt': 'text/plain; charset=utf-8'}.get(target.suffix,
                                                        'application/octet-stream')
        self.send_header('Content-Type', mime)
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
