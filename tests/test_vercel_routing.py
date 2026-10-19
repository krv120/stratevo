"""Repeat current HTTP contracts through configured Vercel destination routing."""
import json
import threading
import unittest
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import suppliers as s
import test_directory as contracts
from vercel_rewrite import RewrittenHandler


class VercelRoutingTests(contracts.DirectoryTests):
    @classmethod
    def setUpClass(cls):
        s.PRIVATE.mkdir(exist_ok=True)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), RewrittenHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    def test_all_public_routes_and_assets_through_rewrite(self):
        for path in ('/','/supplier','/marketplace','/methodology','/assessment','/inquiry',
                     '/privacy','/cookies','/terms','/admin','/supplier/account'):
            with self.subTest(path=path):
                status, body, headers = self.http(path)
                self.assertEqual(status, 200)
                self.assertIn('text/html', headers['Content-Type'])
                self.assertIn(b'STRATEVO', body)
        for path in ('/site.css','/market.js','/ui.js','/navigation.js','/storage.js',
                     '/favicon.svg','/fonts/inter-latin.woff2','/images/stratevo-social.jpg'):
            with self.subTest(path=path):
                status, body, _ = self.http(path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
        self.assertEqual(self.http('/api/health')[0], 200)
        self.assertEqual(self.http('/not-a-page')[0], 404)
        self.assertEqual(self.http('/api/not-an-endpoint')[0], 404)

    def test_head_through_rewrite(self):
        for path in ('/', '/supplier', '/site.css', '/api/health'):
            with self.subTest(path=path):
                request = urllib.request.Request(self.base + path, method='HEAD')
                with urllib.request.urlopen(request, timeout=10) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b'')

    def test_query_filters_survive_rewrite(self):
        self.register()
        status, body, _ = self.http('/api/suppliers/public?q=Precision')
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['suppliers']), 1)
        status, body, _ = self.http('/api/suppliers/public?q=notmatching')
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['suppliers']), 0)


class RoutingEnvelopeTests(unittest.TestCase):
    def restore(self, path):
        from api.index import handler
        instance = handler.__new__(handler)
        instance.path = path
        errors = []
        instance.send = lambda status, body: errors.append(status)
        result = instance.restore_route()
        return result, instance.path, errors

    def test_config_targets_existing_python_function_and_preserves_path(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'vercel.json').read_text())
        self.assertEqual(config['rewrites'], [
            {'source': '/(.*)', 'destination': '/api/index.py?__stratevo_path=/$1'}
        ])
        self.assertTrue((root / 'api/index.py').is_file())
        self.assertIn('api/index.py', config['functions'])
        from vercel_rewrite import destination
        for original in ('/', '/supplier', '/api/health', '/site.css'):
            ok, restored, errors = self.restore(destination(original))
            self.assertTrue(ok)
            self.assertEqual(restored, original)
            self.assertEqual(errors, [])

    def test_preserves_query_values_and_duplicates(self):
        from urllib.parse import parse_qsl, urlsplit
        ok, path, errors = self.restore('/api/index?__stratevo_path=/api/suppliers/public&q=steel+parts&q=a%26b&empty=')
        self.assertTrue(ok)
        self.assertEqual(urlsplit(path).path, '/api/suppliers/public')
        self.assertEqual(parse_qsl(urlsplit(path).query, keep_blank_values=True), [('q','steel parts'),('q','a&b'),('empty','')])
        self.assertEqual(errors, [])

    def test_rejects_malformed_envelopes(self):
        for value in ('//outside.invalid','https://outside.invalid','/%0a','/x%3fy=1','/x%23fragment','/x%5cy'):
            with self.subTest(value=value):
                ok, _, errors = self.restore('/api/index?__stratevo_path='+value)
                self.assertFalse(ok)
                self.assertEqual(errors, [400])
        self.assertFalse(self.restore('/api/index?__stratevo_path=/&__stratevo_path=/admin')[0])

    def test_direct_paths_are_not_overridden(self):
        path = '/supplier?__stratevo_path=/admin'
        self.assertEqual(self.restore(path), (True, path, []))
        self.assertEqual(self.restore('/api/index'), (True, '/api/index', []))
