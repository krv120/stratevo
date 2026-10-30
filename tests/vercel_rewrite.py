"""Local configured routing/static-output harness; not Vercel infrastructure."""
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit
from api.index import handler

ROOT = Path(__file__).resolve().parents[1]


def destination(path):
    request = urlsplit(path)
    for rule in json.loads((ROOT / 'vercel.json').read_text())['rewrites']:
        match = re.fullmatch(rule['source'], request.path)
        if not match:
            continue
        target = rule['destination']
        for index, value in enumerate(match.groups(), 1):
            target = target.replace('$'+str(index), quote(value, safe='/'))
        return target + (('&' if '?' in target else '?') + request.query if request.query else '')
    return path


class RewrittenHandler(handler):
    def do_GET(self):
        # HTML rewrite destinations are a filesystem operation on Vercel.
        # Keep original page paths for tests of the dynamic local server.
        if self.path.startswith('/api/'):
            self.path = destination(self.path)
        super().do_GET()

    def do_POST(self):
        self.path = destination(self.path)
        super().do_POST()


class StaticOutputHandler(RewrittenHandler):
    def do_GET(self):
        import mimetypes
        request = urlsplit(self.path)
        if request.path.startswith('/api/'):
            return super().do_GET()
        config = json.loads((ROOT / 'vercel.json').read_text())
        for rule in config.get('redirects', []):
            if request.path == rule['source']:
                return self.send(308, b'', headers={'Location': rule['destination']})
        path = urlsplit(destination(self.path)).path
        name = 'index.html' if path == '/' else path.lstrip('/')
        if '.' not in Path(name).name:
            name += '.html'
        root = (ROOT / config['outputDirectory']).resolve()
        file = (root / name).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            return self.send(404, (root / '404.html').read_bytes(), 'text/html; charset=utf-8')
        mime = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        return self.send(200, file.read_bytes(), mime)
