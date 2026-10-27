"""Public pages must work without invoking the Python API router or database."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from vercel_rewrite import StaticOutputHandler, destination

ROOT = Path(__file__).resolve().parents[1]


class StaticOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, 'scripts/build_static.py'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)

    def test_public_output_has_no_private_source(self):
        root = ROOT / 'public-site'
        files = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()]
        self.assertEqual(len(files), 30)
        self.assertFalse(any(n.endswith(('.py', '.sql', '.sqlite3')) or n.startswith(('templates/', 'private/')) for n in files))
        self.assertIn('index.html', files)
        self.assertIn('video.js', files)
        for path in root.glob('*.html'):
            self.assertIn('<meta name="stratevo-api" content="/api/index.py">', path.read_text())

    def test_direct_function_url_is_not_rewritten(self):
        path = '/api/index.py?__stratevo_path=%2Fapi%2Fsuppliers%2Fpublic&q=steel'
        self.assertEqual(destination(path), path)
        self.assertTrue(destination('/api/suppliers').startswith('/api/index.py?'))
        self.assertEqual(destination('/'), '/')

    def test_static_pages_do_not_call_api_router(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), StaticOutputHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch('app.server.Handler.do_GET', side_effect=AssertionError('Public page invoked API router')):
                for path in ('/', '/supplier', '/marketplace', '/supplier/account', '/admin', '/site.css', '/ui.js'):
                    with self.subTest(path=path), urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port)+path) as response:
                        self.assertEqual(response.status, 200)
                        self.assertTrue(response.read())
        finally:
            server.shutdown();server.server_close();thread.join()
