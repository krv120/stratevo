"""Content Studio contracts against a local fal.ai stub.

These tests prove the HTTP client, validation, budget, persistence, webhook
signature checks and retry paths. They do NOT prove a real generation: the
sandbox cannot reach fal.ai, and no live key is used here.
"""
import json
import os
import secrets
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app import fal, settings, video
from app import suppliers as s
from app.server import Handler
from fal_stub import StubServer, signed_headers

KEY = 'test-key-0123456789abcdef'


class VideoStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s.PRIVATE.mkdir(exist_ok=True)
        cls.stub = StubServer(key=KEY)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.stub.stop()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=s.PRIVATE)
        self.addCleanup(self.tmp.cleanup)
        self.db = patch.object(s, 'DATABASE', Path(self.tmp.name) / 'test.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)
        self.password = secrets.token_urlsafe(24)
        self.env = patch.dict(os.environ, {
            'APP_ENV': 'test', 'PUBLIC_BASE_URL': self.base, 'COOKIE_SECURE': 'false',
            'MAIL_DELIVERY_ENABLED': 'false', 'ADMIN_PASSWORD': self.password,
            'FAL_KEY': KEY, 'VIDEO_SPEND_LIMIT_USD': '5', 'VIDEO_MAX_JOB_USD': '1',
            'VIDEO_JOBS_PER_HOUR': '30', 'VIDEO_WEBHOOK_ENABLED': 'true',
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.patches = [
            patch.object(fal, 'QUEUE_BASE', self.stub.base),
            patch.object(fal, 'PRICING_URL', self.stub.base + '/v1/models/pricing'),
            patch.object(fal, 'JWKS_URL', self.stub.base + '/.well-known/jwks.json'),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.stub.submissions.clear()
        self.stub.states.clear()
        self.stub.errors.clear()
        self.stub.results.clear()
        self.stub.pricing = dict(self.stub.default_pricing)
        self.stub.pricing_fail = False
        self.stub.cancel_status = 200
        fal._PRICING_CACHE.clear()
        fal._JWKS_CACHE.update({'keys': [], 'fetched_at': 0})
        s.initialize()

    def http(self, path, data=None, cookie='', raw=None, headers=None, method=None):
        head = {'Content-Type': 'application/json', 'Cookie': cookie, **(headers or {})}
        body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        request = urllib.request.Request(self.base + path, data=body, headers=head, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def admin(self):
        return 'stratevo_session=' + s.admin_login({'username': 'owner', 'password': self.password})[1]

    def submit(self, **changes):
        payload = {'prompt': 'A slow push-in on a matte aluminium bracket on a workshop bench, soft window light.',
                   'model': 'kling-2.5-turbo-pro', 'duration_seconds': 5, 'aspect_ratio': '16:9',
                   'client_key': secrets.token_hex(16), **changes}
        return self.http('/api/admin/video/jobs', payload, cookie=self.admin())

    # --- configuration and authentication ---------------------------------
    def test_studio_endpoints_require_admin_session(self):
        for path in ('/api/admin/video/status', '/api/admin/video/jobs'):
            self.assertIn(self.http(path)[0], (401, 403))
        self.assertIn(self.http('/api/admin/video/jobs', {'prompt': 'x'})[0], (401, 403))
        self.assertEqual(self.stub.submissions, [])

    def test_status_reports_configuration_and_budget_without_the_key(self):
        code, body, _ = self.http('/api/admin/video/status', cookie=self.admin())
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertTrue(payload['configured'])
        self.assertEqual(payload['key_variable'], 'FAL_KEY')
        self.assertEqual(payload['budget']['limit_usd'], 5.0)
        self.assertEqual(payload['budget']['remaining_usd'], 5.0)
        self.assertTrue(payload['webhook_configured'])
        self.assertEqual([entry['id'] for entry in payload['models']], ['kling-2.5-turbo-pro', 'kling-3-pro'])
        self.assertNotIn(KEY, body.decode())
        self.assertNotIn('Authorization', body.decode())

    def test_missing_key_blocks_generation_before_any_network_call(self):
        with patch.dict(os.environ, {'FAL_KEY': ''}):
            code, body, _ = self.submit()
        self.assertEqual(code, 503)
        self.assertIn('FAL_KEY', json.loads(body)['error'])
        self.assertEqual(self.stub.submissions, [])
        with s.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM video_jobs').fetchone()['n'], 0)

    def test_placeholder_key_is_not_treated_as_configured(self):
        with patch.dict(os.environ, {'FAL_KEY': 'replace_me'}):
            self.assertFalse(fal.configured())
            self.assertEqual(self.submit()[0], 503)

    # --- validation --------------------------------------------------------
    def test_prompt_and_option_validation(self):
        cases = [
            ({'prompt': 'too short'}, 'prompt'),
            ({'prompt': 'x' * 2001}, 'prompt'),
            ({'prompt': 'Valid words here.\x00bad'}, 'prompt'),
            ({'duration_seconds': 7}, 'duration_seconds'),
            ({'duration_seconds': 'ten'}, 'duration_seconds'),
            ({'aspect_ratio': '4:3'}, 'aspect_ratio'),
            ({'model': 'not-a-model'}, 'model'),
            ({'client_key': 'short'}, 'client_key'),
        ]
        cookie = self.admin()
        for changes, field in cases:
            with self.subTest(field=field):
                payload = {'prompt': 'A slow push-in on a matte aluminium bracket.', 'client_key': secrets.token_hex(16), **changes}
                code, body, _ = self.http('/api/admin/video/jobs', payload, cookie=cookie)
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body)['field'], field)
        self.assertEqual(self.stub.submissions, [])

    def test_long_prompt_within_model_limit_is_accepted(self):
        code, body, _ = self.submit(prompt='A' * 2000)
        self.assertEqual(code, 200)
        self.assertEqual(len(self.stub.submissions), 1)

    # --- submission lifecycle ---------------------------------------------
    def test_submit_stores_job_id_and_cost_and_is_idempotent(self):
        payload = {'prompt': 'A slow push-in on a matte aluminium bracket with soft window light.',
                   'model': 'kling-2.5-turbo-pro', 'duration_seconds': 5, 'aspect_ratio': '16:9',
                   'client_key': secrets.token_hex(16)}
        cookie = self.admin()
        code, body, _ = self.http('/api/admin/video/jobs', payload, cookie=cookie)
        self.assertEqual(code, 200)
        job = json.loads(body)['job']
        self.assertEqual(job['status'], 'queued')
        self.assertEqual(job['cost_usd'], 0.35)
        self.assertEqual(job['cost_basis'], 'fal_pricing_api')
        self.assertEqual(job['fal_request_id'], 'req-1')
        self.assertNotIn(KEY, body.decode())

        code, again, _ = self.http('/api/admin/video/jobs', payload, cookie=cookie)
        self.assertEqual(code, 200)
        duplicate = json.loads(again)
        self.assertTrue(duplicate['deduplicated'])
        self.assertEqual(duplicate['job']['id'], job['id'])
        self.assertEqual(len(self.stub.submissions), 1, 'a retried submit must not buy a second generation')

        sent = self.stub.submissions[0]
        self.assertEqual(sent['path'], '/fal-ai/kling-video/v2.5-turbo/pro/text-to-video')
        self.assertEqual(sent['payload']['prompt'], payload['prompt'])
        self.assertEqual(sent['payload']['duration'], '5')
        self.assertEqual(sent['payload']['aspect_ratio'], '16:9')
        self.assertEqual(sent['query']['fal_webhook'], [self.base + '/api/video/fal-webhook'])
        self.assertNotIn('generate_audio', sent['payload'])

        with s.database() as db:
            row = db.execute('SELECT * FROM video_jobs WHERE id=?', (job['id'],)).fetchone()
        self.assertEqual(row['fal_request_id'], 'req-1')
        self.assertEqual(round(float(row['cost_usd']), 2), 0.35)
        self.assertNotIn(KEY, json.dumps(dict(row)))

    def test_completion_returns_video_url_and_records_cost(self):
        job = json.loads(self.submit()[1])['job']
        self.stub.complete(job['fal_request_id'])
        code, body, _ = self.http('/api/admin/video/sync', {'id': job['id']}, cookie=self.admin())
        self.assertEqual(code, 200)
        synced = json.loads(body)['job']
        self.assertEqual(synced['status'], 'completed')
        self.assertEqual(synced['video_url'], 'https://v3.fal.media/files/test/clip.mp4')
        self.assertGreater(synced['completed_at'], 0)
        listing = json.loads(self.http('/api/admin/video/jobs', cookie=self.admin())[1])
        self.assertEqual(listing['jobs'][0]['status'], 'completed')
        self.assertEqual(listing['jobs'][0]['cost_usd'], 0.35)

    def test_untrusted_result_host_is_rejected(self):
        job = json.loads(self.submit()[1])['job']
        job_id = job['fal_request_id']
        self.stub.states[job_id] = 'COMPLETED'
        self.stub.results[job_id] = {'video': {'url': 'https://evil.example/clip.mp4'}}
        code, body, _ = self.http('/api/admin/video/sync', {'id': job['id']}, cookie=self.admin())
        self.assertEqual(json.loads(body)['job']['status'], 'failed')
        self.assertEqual(json.loads(body)['job']['video_url'], '')

    def test_queued_then_in_progress_updates(self):
        job = json.loads(self.submit()[1])['job']
        self.stub.states[job['fal_request_id']] = 'IN_PROGRESS'
        body = json.loads(self.http('/api/admin/video/sync', {'id': job['id']}, cookie=self.admin())[1])
        self.assertEqual(body['job']['status'], 'in_progress')

    def test_failure_releases_budget_and_can_be_retried(self):
        job = json.loads(self.submit()[1])['job']
        self.stub.complete(job['fal_request_id'], error='content policy rejected the prompt')
        body = json.loads(self.http('/api/admin/video/sync', {'id': job['id']}, cookie=self.admin())[1])
        self.assertEqual(body['job']['status'], 'failed')
        self.assertEqual(body['job']['cost_usd'], 0)
        status = json.loads(self.http('/api/admin/video/status', cookie=self.admin())[1])
        self.assertEqual(status['budget']['spent_usd'], 0)

        code, retried, _ = self.http('/api/admin/video/retry', {'id': job['id']}, cookie=self.admin())
        self.assertEqual(code, 200)
        replacement = json.loads(retried)['job']
        self.assertEqual(replacement['status'], 'queued')
        self.assertEqual(replacement['attempts'], 2)
        self.assertEqual(replacement['retried_from'], job['id'])
        self.assertNotEqual(replacement['fal_request_id'], job['fal_request_id'])
        self.assertEqual(len(self.stub.submissions), 2)

    def test_unbilled_failure_path_marks_submit_failed(self):
        with patch.object(fal, 'submit', side_effect=fal.FalError('fal.ai rejected the request: bad body', 502, retryable=False)):
            code, body, _ = self.submit()
        self.assertEqual(code, 502)
        with s.database() as db:
            row = db.execute('SELECT * FROM video_jobs ORDER BY created_at DESC').fetchone()
        self.assertEqual(row['status'], 'submit_failed')
        self.assertEqual(row['cost_usd'], 0)
        self.assertEqual(json.loads(self.http('/api/admin/video/status', cookie=self.admin())[1])['budget']['spent_usd'], 0)

    def test_ambiguous_submission_keeps_the_reservation(self):
        with patch.object(fal, 'submit', side_effect=fal.FalError('fal.ai could not be reached', 503, ambiguous=True)):
            code, body, _ = self.submit()
        self.assertEqual(code, 503)
        with s.database() as db:
            row = db.execute('SELECT * FROM video_jobs ORDER BY created_at DESC').fetchone()
        self.assertEqual(row['status'], 'unknown')
        self.assertEqual(round(float(row['cost_usd']), 2), 0.35)
        budget = json.loads(self.http('/api/admin/video/status', cookie=self.admin())[1])['budget']
        self.assertEqual(budget['spent_usd'], 0.35)
        with self.assertRaises(s.WorkflowError):
            video.retry({'id': row['id']}, 'owner')

    # --- budget ------------------------------------------------------------
    def test_spending_limit_blocks_the_second_generation(self):
        with patch.dict(os.environ, {'VIDEO_SPEND_LIMIT_USD': '0.50'}):
            self.assertEqual(self.submit()[0], 200)
            code, body, _ = self.submit()
            self.assertEqual(code, 409)
            self.assertIn('spending limit', json.loads(body)['error'].lower())
        self.assertEqual(len(self.stub.submissions), 1)
        with s.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM video_jobs').fetchone()['n'], 1)

    def test_per_job_cap(self):
        with patch.dict(os.environ, {'VIDEO_MAX_JOB_USD': '0.20'}):
            code, body, _ = self.submit()
        self.assertEqual(code, 400)
        self.assertIn('per-job cap', json.loads(body)['error'])
        self.assertEqual(self.stub.submissions, [])

    def test_pinned_table_is_used_when_live_pricing_is_unavailable(self):
        self.stub.pricing_fail = True
        body = json.loads(self.submit()[1])
        self.assertEqual(body['job']['cost_basis'], 'pinned_price_table')
        self.assertEqual(body['job']['cost_usd'], 0.35)

    def test_live_price_is_used_when_available(self):
        self.stub.pricing['fal-ai/kling-video/v2.5-turbo/pro/text-to-video'] = 0.09
        body = json.loads(self.submit()[1])
        self.assertEqual(body['job']['cost_basis'], 'fal_pricing_api')
        self.assertEqual(body['job']['cost_usd'], 0.45)

    def test_budget_window_is_calendar_month(self):
        import time as clock
        start = video.month_start()
        self.assertLessEqual(start, clock.time())
        self.assertEqual(video.month_start(start), start)
        self.assertEqual(video.month_start(start - 1) < start, True)

    # --- cancel ------------------------------------------------------------
    def test_cancel_releases_the_reservation(self):
        job = json.loads(self.submit()[1])['job']
        code, body, _ = self.http('/api/admin/video/cancel', {'id': job['id']}, cookie=self.admin())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['job']['status'], 'canceled')
        self.assertEqual(json.loads(self.http('/api/admin/video/status', cookie=self.admin())[1])['budget']['spent_usd'], 0)

    def test_cancel_in_progress_stays_billable(self):
        job = json.loads(self.submit()[1])['job']
        self.stub.cancel_status = 202
        body = json.loads(self.http('/api/admin/video/cancel', {'id': job['id']}, cookie=self.admin())[1])
        self.assertEqual(body['job']['status'], 'canceling')
        self.assertEqual(body['job']['cost_usd'], 0.35)

    # --- webhook -----------------------------------------------------------
    def test_webhook_requires_a_valid_signature_and_then_syncs(self):
        job = json.loads(self.submit()[1])['job']
        self.stub.complete(job['fal_request_id'])
        payload = json.dumps({'request_id': job['fal_request_id'], 'status': 'OK',
                              'payload': {'video': {'url': 'https://v3.fal.media/files/test/clip.mp4'}}}).encode()
        headers = signed_headers(payload, request_id=job['fal_request_id'])
        code, body, _ = self.http('/api/video/fal-webhook', raw=payload, headers=headers)
        self.assertEqual(code, 200)
        self.assertTrue(json.loads(body)['matched'])
        self.assertEqual(json.loads(body)['status'], 'completed')

    def test_webhook_rejects_bad_signature_stale_timestamp_and_missing_headers(self):
        job = json.loads(self.submit()[1])['job']
        self.stub.complete(job['fal_request_id'])
        payload = json.dumps({'request_id': job['fal_request_id'], 'status': 'OK'}).encode()

        good = signed_headers(payload, request_id=job['fal_request_id'])
        tampered = dict(good)
        tampered['X-Fal-Webhook-Signature'] = '00' * 64
        self.assertEqual(self.http('/api/video/fal-webhook', raw=payload, headers=tampered)[0], 403)

        stale = signed_headers(payload, request_id=job['fal_request_id'], timestamp=1)
        self.assertEqual(self.http('/api/video/fal-webhook', raw=payload, headers=stale)[0], 403)

        self.assertEqual(self.http('/api/video/fal-webhook', raw=payload, headers={})[0], 403)

        forged = json.dumps({'request_id': job['fal_request_id'], 'status': 'OK',
                             'payload': {'video': {'url': 'https://v3.fal.media/files/forged.mp4'}}}).encode()
        self.assertEqual(self.http('/api/video/fal-webhook', raw=forged,
                                   headers=dict(good, **{'X-Fal-Webhook-Signature': '11' * 64}))[0], 403)
        with s.database() as db:
            row = db.execute('SELECT video_url, status FROM video_jobs WHERE id=?', (job['id'],)).fetchone()
        self.assertEqual(row['status'], 'queued', 'a rejected callback must not change state')

    def test_webhook_for_unknown_request_is_acknowledged_not_stored(self):
        payload = b'{"request_id":"does-not-exist","status":"OK"}'
        headers = signed_headers(payload, request_id='does-not-exist')
        code, body, _ = self.http('/api/video/fal-webhook', raw=payload, headers=headers)
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(body)['matched'])

    def test_webhook_rejects_oversized_body(self):
        self.assertEqual(self.http('/api/video/fal-webhook', raw=b'x' * 70000)[0], 413)

    # --- transport guards --------------------------------------------------
    def test_queue_urls_from_another_host_are_rejected(self):
        with patch.object(fal, 'QUEUE_BASE', 'https://queue.fal.run'):
            with self.assertRaises(fal.FalError):
                fal.status('https://attacker.example/steal')
            with self.assertRaises(fal.FalError):
                fal.status('http://queue.fal.run/insecure')
            with self.assertRaises(fal.FalError):
                fal.result('https://queue.fal.run.evil.example/x')

    def test_upstream_401_is_reported_as_a_key_problem_without_echoing_it(self):
        with patch.dict(os.environ, {'FAL_KEY': 'wrong-key-0123456789abcdef'}):
            self.stub.key = KEY
            code, body, _ = self.submit()
        self.assertEqual(code, 502)
        self.assertIn('rejected the API key', json.loads(body)['error'])
        self.assertNotIn('wrong-key-0123456789abcdef', body.decode())

    def test_prompt_is_never_rendered_as_html(self):
        payload = '<script>alert(1)</script> A workshop bench with soft light and a slow camera push.'
        job = json.loads(self.submit(prompt=payload)[1])['job']
        self.assertEqual(job['prompt'], payload)
        page = self.http('/admin')[1].decode()
        self.assertNotIn(payload, page)
        self.assertIn('src="/video.js"', page)
        self.assertIn('id="content-studio"', page)

    def test_admin_page_allows_fal_media_only(self):
        code, body, headers = self.http('/admin')
        self.assertEqual(code, 200)
        policy = headers['Content-Security-Policy']
        self.assertIn('media-src', policy)
        self.assertIn('https://*.fal.media', policy)
        self.assertNotIn("media-src *", policy)
        other = self.http('/')[2]['Content-Security-Policy']
        self.assertNotIn('fal.media', other)

    def test_rate_limit_applies_per_operator(self):
        with patch.dict(os.environ, {'VIDEO_JOBS_PER_HOUR': '1'}):
            self.assertEqual(self.submit()[0], 200)
            self.assertEqual(self.submit()[0], 429)

    def test_local_dev_storage_is_allowed_but_hosted_ephemeral_is_not(self):
        self.assertEqual(settings.storage_status()['durable'], False)
        with patch.object(settings, 'environment', return_value='production'):
            with self.assertRaises(s.WorkflowError) as caught:
                video._ensure_ready()
        self.assertEqual(caught.exception.status, 503)
        self.assertIn('durable PostgreSQL', str(caught.exception))


class Ed25519Tests(unittest.TestCase):
    """RFC 8032 section 7.1 test vectors."""

    VECTORS = [
        ('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60',
         'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a', '',
         'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b'),
        ('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb',
         '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c', '72',
         '92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00'),
        ('c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7',
         'fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025', 'af82',
         '6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a'),
    ]

    def test_rfc8032_vectors(self):
        from app import ed25519
        for seed, public, message, signature in self.VECTORS:
            with self.subTest(public=public[:8]):
                self.assertTrue(ed25519.verify(bytes.fromhex(public), bytes.fromhex(message), bytes.fromhex(signature)))
                self.assertEqual(ed25519.public_key_for_tests(bytes.fromhex(seed)), bytes.fromhex(public))
                self.assertEqual(ed25519.sign_for_tests(bytes.fromhex(seed), bytes.fromhex(message)), bytes.fromhex(signature))

    def test_tampering_is_rejected(self):
        from app import ed25519
        seed, public, message, signature = self.VECTORS[1]
        key, sig = bytes.fromhex(public), bytearray.fromhex(signature)
        self.assertFalse(ed25519.verify(key, bytes.fromhex(message) + b'x', bytes(sig)))
        bad = bytearray(sig)
        bad[0] ^= 1
        self.assertFalse(ed25519.verify(key, bytes.fromhex(message), bytes(bad)))
        self.assertFalse(ed25519.verify(b'', bytes.fromhex(message), bytes(sig)))
        self.assertFalse(ed25519.verify(key, bytes.fromhex(message), bytes(sig[:63])))

    def test_application_code_never_signs(self):
        root = Path(__file__).resolve().parents[1] / 'app'
        for path in root.glob('*.py'):
            text = path.read_text()
            if path.name == 'ed25519.py':
                continue
            self.assertNotIn('sign_for_tests', text, path.name)


if __name__ == '__main__':
    unittest.main()
