"""Content pipeline contracts: library, captions, scheduling, worker, media.

Everything here runs locally: the fal.ai queue is a stub, ffmpeg is the
`imageio-ffmpeg` build, Buffer is never contacted. A passing test is contract
evidence, not proof of a real generation or a real Buffer schedule.
"""
import datetime
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app import buffer_api, captions, content, content_library, media, video
from app import suppliers as s
from app.server import Handler
from fal_stub import StubServer

KEY = 'test-key-0123456789abcdef'
CRON = 'cron-secret-' + 'x' * 40


def make_clip(path, seconds=3):
    """Render a tiny vertical test clip with the bundled ffmpeg."""
    import imageio_ffmpeg
    executable = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([executable, '-y', '-hide_banner', '-loglevel', 'error',
                    '-f', 'lavfi', '-i', 'testsrc2=size=360x640:rate=24:duration=' + str(seconds),
                    '-f', 'lavfi', '-i', 'sine=frequency=440:duration=' + str(seconds),
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-shortest', str(path)], check=True, timeout=120)
    return Path(path).read_bytes()


class ContentPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s.PRIVATE.mkdir(exist_ok=True)
        cls.stub = StubServer(key=KEY)
        cls.server = threading.Thread(target=lambda: None)
        cls.http_server = __import__('http.server', fromlist=['ThreadingHTTPServer']).ThreadingHTTPServer(
            ('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.http_server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.http_server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http_server.shutdown()
        cls.http_server.server_close()
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
            'VIDEO_JOBS_PER_HOUR': '60', 'VIDEO_WEBHOOK_ENABLED': 'false',
            'CRON_SECRET': CRON, 'PUBLISHING_ENABLED': 'false', 'BUFFER_API_KEY': '',
            'CONTENT_MEDIA_DIR': str(Path(self.tmp.name) / 'media'),
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        for item in (patch.object(video.fal, 'QUEUE_BASE', self.stub.base),
                     patch.object(video.fal, 'PRICING_URL', self.stub.base + '/v1/models/pricing'),
                     patch.object(video.fal, 'JWKS_URL', self.stub.base + '/.well-known/jwks.json')):
            item.start()
            self.addCleanup(item.stop)
        self.stub.submissions.clear()
        self.stub.states.clear()
        self.stub.results.clear()
        self.stub.errors.clear()
        video.fal._PRICING_CACHE.clear()
        s.initialize()

    def http(self, path, data=None, cookie='', headers=None):
        head = {'Content-Type': 'application/json', 'Cookie': cookie, **(headers or {})}
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(self.base + path, data=body, headers=head)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def admin(self):
        return 'stratevo_session=' + s.admin_login({'username': 'owner', 'password': self.password})[1]

    def series(self, count=40, **changes):
        payload = {'name': 'Test series', 'count': count, 'model': 'minimax-h3-max-turbo',
                   'duration_seconds': 10, 'resolution': '768P', 'aspect_ratio': '9:16',
                   'seed': 'unit-seed', **changes}
        code, body, _ = self.http('/api/admin/content/series', payload, cookie=self.admin())
        self.assertEqual(code, 200, body)
        return json.loads(body)['series_id']

    # --- library ----------------------------------------------------------
    def test_forty_ideas_are_distinct_and_short(self):
        ideas = content_library.generate('unit-seed', 40)
        self.assertEqual(len(ideas), 40)
        self.assertEqual(len({idea['hook'] for idea in ideas}), 40)
        self.assertEqual(len({idea['script'] for idea in ideas}), 40)
        self.assertEqual(len({idea['video_prompt'] for idea in ideas}), 40)
        self.assertEqual(len({(idea['topic'], idea['angle']) for idea in ideas}), 40)
        for idea in ideas:
            self.assertTrue(10 <= len(idea['script'].split()) <= 34, idea['script'])
            self.assertLessEqual(content_library.estimate_seconds(idea['script']), 12)
            self.assertLessEqual(len(idea['tiktok_caption']), 145)
            self.assertTrue(idea['tiktok_hashtags'].startswith('#'))
            self.assertGreaterEqual(idea['instagram_hashtags'].count('#'), 5)
            self.assertNotIn('—', idea['script'])
            self.assertNotIn('"', idea['tiktok_caption'])
        self.assertEqual([i['position'] for i in ideas], list(range(1, 41)))
        self.assertEqual([i['hook'] for i in activities('unit-seed')], [i['hook'] for i in ideas])

    # --- captions ---------------------------------------------------------
    def test_ass_contains_hook_and_word_timed_captions(self):
        document = captions.build_ass('Check tolerances before you pay a deposit today.', 10, hook='Read this first')
        self.assertIn('[Script Info]', document)
        self.assertIn('READ THIS FIRST', document)
        dialogues = [line for line in document.splitlines() if line.startswith('Dialogue:')]
        self.assertGreaterEqual(len(dialogues), 3)
        self.assertEqual(len([line for line in document.splitlines() if line.startswith('Style:')]), 2)
        for line in captions.phrases('Check tolerances before you pay a deposit today.'):
            self.assertLessEqual(len(line), captions.MAX_CAPTION_CHARS)

    @unittest.skipUnless(shutil.which('ffmpeg') or not captions.ffmpeg_missing(), 'ffmpeg unavailable')
    def test_caption_render_outputs_vertical_mp4(self):
        source = Path(self.tmp.name) / 'src.mp4'
        make_clip(source, 3)
        target = Path(self.tmp.name) / 'out.mp4'
        info = captions.render(source.read_bytes(), target, 'Three checks before you approve a sample.', 3,
                               hook='Before you pay')
        self.assertEqual((info['width'], info['height']), (1080, 1920))
        self.assertTrue(info['has_audio'])
        self.assertGreater(target.stat().st_size, 20000)
        # Vercel caps a serverless response body at 4.5 MB and Buffer downloads
        # the whole file, so the encoder keeps every clip well under that.
        self.assertLess(target.stat().st_size, 4_400_000)

    # --- series and review ------------------------------------------------
    def test_series_approval_and_regeneration_flow(self):
        series_id = self.series(8)
        code, body, _ = self.http('/api/admin/content/overview?series_id=' + series_id, cookie=self.admin())
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(len(data['ideas']), 8)
        self.assertEqual(data['counts'].get('draft'), 8)
        self.assertIsNone(data['publishing']['channels'] or None)
        first = data['ideas'][0]
        self.assertEqual(first['status'], 'draft')
        code, body, _ = self.http('/api/admin/content/decide', {'id': first['id'], 'action': 'approve'},
                                  cookie=self.admin())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['idea']['status'], 'approved')
        code, body, _ = self.http('/api/admin/content/decide', {'id': data['ideas'][1]['id'], 'action': 'reject'},
                                  cookie=self.admin())
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['idea']['status'], 'rejected')
        # An approved idea cannot be approved twice.
        code, _, _ = self.http('/api/admin/content/decide', {'id': first['id'], 'action': 'approve'},
                               cookie=self.admin())
        self.assertEqual(code, 409)
        old_hook = data['ideas'][2]['hook']
        code, body, _ = self.http('/api/admin/content/regenerate', {'id': data['ideas'][2]['id']},
                                  cookie=self.admin())
        self.assertEqual(code, 200)
        self.assertNotEqual(json.loads(body)['idea']['hook'], old_hook)
        self.assertEqual(json.loads(body)['idea']['regenerate_count'], 1)

    def test_content_endpoints_require_admin(self):
        for path in ('/api/admin/content/overview', '/api/admin/content/plugins'):
            self.assertIn(self.http(path)[0], (401, 403))
        code, _, _ = self.http('/api/admin/content/series', {'name': 'x', 'count': 4})
        self.assertIn(code, (401, 403))

    def test_estimate_shows_total_before_batch(self):
        code, body, _ = self.http('/api/admin/content/estimate?model=minimax-h3-max-turbo&duration=10&resolution=768P&count=40',
                                  cookie=self.admin())
        self.assertEqual(code, 200)
        plan = json.loads(body)
        self.assertEqual(plan['total_usd'], 16.0)
        self.assertEqual(plan['per_video_usd'], 0.4)
        self.assertEqual(plan['budget_limit_usd'], 5.0)
        self.assertEqual(plan['affordable_videos'], 12)
        self.assertEqual(plan['promotional_total_usd'], 10.4)

    # --- paid queue -------------------------------------------------------
    def test_batch_is_budget_checked_and_records_idea_and_resolution(self):
        series_id = self.series(4)
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        ideas = json.loads(body)['ideas']
        for idea in ideas[:3]:
            self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'}, cookie=self.admin())
        code, body, _ = self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 3},
                                  cookie=self.admin())
        self.assertEqual(code, 200, body)
        result = json.loads(body)
        self.assertEqual(result['queued_count'], 3)
        self.assertAlmostEqual(result['spend_usd'], 1.2, places=2)
        self.assertEqual(len(self.stub.submissions), 3)
        payload = self.stub.submissions[0]['payload']
        self.assertEqual(payload['resolution'], '768P')
        self.assertEqual(payload['prompt_expansion_mode'], 'balanced')
        self.assertEqual(payload['aspect_ratio'], '9:16')
        self.assertEqual(self.stub.submissions[0]['path'], '/minimax/h3-max-turbo/text-to-video')
        with s.database() as db:
            rows = db.execute('SELECT idea_id,resolution,cost_usd FROM video_jobs').fetchall()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row['resolution'] == '768P' for row in rows))
        self.assertTrue(all(row['idea_id'] for row in rows))
        self.assertAlmostEqual(sum(float(row['cost_usd']) for row in rows), 1.2, places=2)

    def test_batch_stops_at_the_monthly_limit(self):
        series_id = self.series(4)
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        ideas = json.loads(body)['ideas']
        for idea in ideas:
            self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'}, cookie=self.admin())
        with patch.dict(os.environ, {'VIDEO_SPEND_LIMIT_USD': '1'}):
            code, body, _ = self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 4},
                                      cookie=self.admin())
        self.assertEqual(code, 200)
        result = json.loads(body)
        self.assertEqual(result['queued_count'], 2)
        self.assertEqual(len(result['skipped']), 1)
        self.assertIn('spending limit', result['skipped'][0]['reason'])
        self.assertEqual(len(self.stub.submissions), 2)
        self.assertEqual(result['queued'][0]['cost_usd'], 0.4)

    def test_unresolved_attempt_blocks_a_second_charge(self):
        series_id = self.series(2)
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        idea = json.loads(body)['ideas'][0]
        self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'}, cookie=self.admin())
        self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 1}, cookie=self.admin())
        self.assertEqual(len(self.stub.submissions), 1)
        # Simulate an operator putting the idea back into the approved queue
        # while its paid job is still running.
        with s.database() as db:
            db.execute("UPDATE content_ideas SET status='approved' WHERE id=?", (idea['id'],))
        code, body, _ = self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 1},
                                  cookie=self.admin())
        self.assertEqual(code, 200)
        result = json.loads(body)
        self.assertEqual(result['queued_count'], 0)
        self.assertIn('unresolved', result['skipped'][0]['reason'])
        self.assertEqual(len(self.stub.submissions), 1)

    def test_one_video_smoke_test_is_small_and_charged(self):
        code, body, _ = self.http('/api/admin/content/smoke', {}, cookie=self.admin())
        self.assertEqual(code, 200, body)
        result = json.loads(body)
        self.assertEqual(len(result['queued']), 1)
        self.assertAlmostEqual(result['spend_usd'], 0.2, places=2)
        self.assertEqual(len(self.stub.submissions), 1)
        payload = self.stub.submissions[0]['payload']
        self.assertEqual(payload['duration'], 5.0)
        self.assertEqual(payload['resolution'], '768P')
        with s.database() as db:
            row = db.execute('SELECT status,cost_usd FROM video_jobs').fetchone()
            idea = db.execute('SELECT status FROM content_ideas').fetchone()
        self.assertEqual(row['status'], 'queued')
        self.assertAlmostEqual(float(row['cost_usd']), 0.2, places=2)
        self.assertEqual(idea['status'], 'video_pending')

    def test_smoke_test_refuses_without_a_key(self):
        with patch.dict(os.environ, {'FAL_KEY': ''}):
            code, body, _ = self.http('/api/admin/content/smoke', {}, cookie=self.admin())
        self.assertEqual(code, 503)
        self.assertEqual(self.stub.submissions, [])

    # --- scheduling -------------------------------------------------------
    def test_slots_are_spread_across_thirty_days_in_athens(self):
        slots = content.build_slots(40, 30)
        self.assertEqual(len(slots), 40)
        stamps = [stamp for stamp, _ in slots]
        self.assertEqual(stamps, sorted(stamps))
        zone = content._zone()
        local = [datetime.datetime.fromtimestamp(stamp, zone) for stamp in stamps]
        self.assertTrue(all((item.hour, item.minute) in ((12, 30), (19, 0)) for item in local))
        tomorrow = (datetime.datetime.now(zone) + datetime.timedelta(days=1)).date()
        self.assertGreaterEqual(local[0].date(), tomorrow)
        self.assertLessEqual((local[-1].date() - local[0].date()).days, 29)
        self.assertEqual(sum(1 for item in local if item.hour == 12), 20)
        self.assertEqual(len({(item.year, item.month, item.day) for item in local}), 30)
        # Winter time is +2, summer time is +3: the stored UTC epoch follows the zone.
        january = content.build_slots(2, 2, start=datetime.datetime(2027, 1, 10, tzinfo=zone))
        self.assertEqual(january[0][0] % 86400, (10 * 3600 + 30 * 60) % 86400)

    def test_schedule_requires_a_rendered_video(self):
        series_id = self.series(4)
        code, body, _ = self.http('/api/admin/content/schedule', {'series_id': series_id, 'days': 30},
                                  cookie=self.admin())
        self.assertEqual(code, 409)
        self.assertIn('Nothing to schedule', json.loads(body)['error'])

    # --- worker -----------------------------------------------------------
    def test_worker_syncs_captions_and_publishes_media(self):
        series_id = self.series(2)
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        ideas = json.loads(body)['ideas']
        for idea in ideas:
            self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'}, cookie=self.admin())
        self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 1}, cookie=self.admin())
        self.assertEqual(len(self.stub.submissions), 1)
        request_id = self.stub.submissions[0]['request_id']
        self.stub.complete(request_id)
        clip = make_clip(Path(self.tmp.name) / 'clip.mp4', 3)
        with patch.object(content, 'fal_download', lambda url: clip):
            report = content.tick('test-worker', max_caption=2)
        self.assertTrue(report['video']['synced'])
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        data = json.loads(body)
        ready = [idea for idea in data['ideas'] if idea['status'] == 'ready_to_publish']
        self.assertEqual(len(ready), 1)
        self.assertTrue(ready[0]['video_url'].startswith(self.base + '/media/'))
        token = ready[0]['video_url'].rsplit('/', 1)[-1]
        code, served, headers = self.http('/media/' + token)
        self.assertEqual(code, 200)
        self.assertEqual(headers['Content-Type'], 'video/mp4')
        with s.database() as db:
            stored = db.execute('SELECT sha256,bytes FROM media_assets WHERE idea_id=?', (ready[0]['id'],)).fetchone()
        self.assertEqual(stored['bytes'], len(served))
        self.assertEqual(stored['sha256'], __import__('hashlib').sha256(served).hexdigest())
        self.assertGreater(served.find(b'mvhd'), 0)
        self.assertEqual(self.http('/media/' + 'a' * 32 + '.mp4')[0], 404)
        self.assertEqual(self.http('/media/../etc/passwd')[0], 404)
        # The next pass schedules it; nothing is sent because publishing is off.
        code, body, _ = self.http('/api/admin/content/schedule', {'series_id': series_id, 'days': 30},
                                  cookie=self.admin())
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)['planned'], 2)
        report = content.tick('test-worker')
        self.assertEqual(report['publishing'], [])
        self.assertIn('publishing_note', report)

    def test_worker_endpoint_requires_the_cron_secret(self):
        self.assertEqual(self.http('/api/jobs/content-tick')[0], 401)
        self.assertEqual(self.http('/api/jobs/content-tick', headers={'Authorization': 'Bearer nope'})[0], 401)
        code, body, _ = self.http('/api/jobs/content-tick', headers={'Authorization': 'Bearer ' + CRON})
        self.assertEqual(code, 200, body)
        report = json.loads(body)
        self.assertFalse(report['publishing'])
        self.assertIn('publishing_note', report)
        self.assertIn('status', report)

    # --- Buffer -----------------------------------------------------------
    def test_buffer_payloads_match_the_documented_schema(self):
        video_payload = buffer_api._post_input(text='hello', channel_id='ch1', due_at='2026-11-02T10:30:00.000Z',
                                               video_url='https://example.com/v.mp4', platform='tiktok')
        self.assertEqual(video_payload['schedulingType'], 'automatic')
        self.assertEqual(video_payload['mode'], 'customScheduled')
        self.assertEqual(video_payload['dueAt'], '2026-11-02T10:30:00.000Z')
        self.assertEqual(video_payload['assets'], [{'video': {'url': 'https://example.com/v.mp4',
                                                              'metadata': {'thumbnailOffset': 1500}}}])
        self.assertEqual(video_payload['metadata'], {'tiktok': {'isAiGenerated': True}})
        instagram = buffer_api._post_input(text='hello', channel_id='ch2', video_url='https://example.com/v.mp4',
                                           platform='instagram')
        self.assertEqual(instagram['mode'], 'addToQueue')
        self.assertNotIn('dueAt', instagram)
        self.assertEqual(instagram['metadata']['instagram'], {'type': 'reel', 'shouldShareToFeed': False})

    def test_buffer_refusal_is_not_recorded_as_scheduled(self):
        series_id = self.series(1)
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        idea = json.loads(body)['ideas'][0]
        self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'}, cookie=self.admin())
        self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 1}, cookie=self.admin())
        request_id = self.stub.submissions[0]['request_id']
        self.stub.complete(request_id)
        clip = make_clip(Path(self.tmp.name) / 'clip.mp4', 2)
        with patch.object(content, 'fal_download', lambda url: clip):
            content.tick('test-worker', max_caption=2)
        self.http('/api/admin/content/schedule', {'series_id': series_id, 'days': 30}, cookie=self.admin())
        with s.database() as db:
            publication = db.execute("SELECT * FROM content_publications WHERE platform='tiktok'").fetchone()
        environment = {'PUBLISHING_ENABLED': 'true', 'BUFFER_API_KEY': 'buffer-key-0123456789abcdef'}
        with patch.dict(os.environ, environment):
            with patch.object(content, 'channel_for',
                              lambda platform: {'id': 'tiktok-1', 'service': platform}):
                with patch.object(buffer_api, '_call', lambda query, variables=None: {
                        'createPost': {'__typename': 'MutationError', 'message': 'TikTok account needs reconnecting.'}}):
                    code, body, _ = self.http('/api/admin/content/publish',
                                              {'publication_id': publication['id']}, cookie=self.admin())
        self.assertEqual(code, 422, body)
        with s.database() as db:
            row = db.execute('SELECT * FROM content_publications WHERE id=?', (publication['id'],)).fetchone()
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['buffer_post_id'], '')
        self.assertIn('reconnecting', row['error_message'])

    def test_confirmed_post_stores_the_buffer_id_only_after_success(self):
        series_id = self.series(1)
        code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
        idea = json.loads(body)['ideas'][0]
        self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'}, cookie=self.admin())
        self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 1}, cookie=self.admin())
        self.stub.complete(self.stub.submissions[0]['request_id'])
        clip = make_clip(Path(self.tmp.name) / 'clip.mp4', 2)
        with patch.object(content, 'fal_download', lambda url: clip):
            content.tick('test-worker', max_caption=2)
        self.http('/api/admin/content/schedule', {'series_id': series_id, 'days': 30}, cookie=self.admin())
        with s.database() as db:
            publication = db.execute("SELECT * FROM content_publications WHERE platform='instagram'").fetchone()
        captured = []

        def fake_call(query, variables=None):
            captured.append(variables['input'])
            number = len(captured)
            return {'createPost': {'__typename': 'PostActionSuccess',
                                   'post': {'id': 'buffer-post-' + str(number),
                                            'dueAt': variables['input']['dueAt'], 'status': 'scheduled',
                                            'channelId': variables['input']['channelId']}}}

        environment = {'PUBLISHING_ENABLED': 'true', 'BUFFER_API_KEY': 'buffer-key-0123456789abcdef'}
        with s.database() as db:
            both = db.execute('SELECT id,platform FROM content_publications WHERE idea_id=?', (idea['id'],)).fetchall()
        with patch.dict(os.environ, environment):
            with patch.object(content, 'channel_for', lambda platform: {'id': platform + '-1', 'service': platform}):
                with patch.object(buffer_api, '_call', fake_call):
                    for row in both:
                        code, body, _ = self.http('/api/admin/content/publish',
                                                  {'publication_id': row['id']}, cookie=self.admin())
                        self.assertEqual(code, 200, body)
                    self.assertEqual(json.loads(body)['buffer_post_id'], 'buffer-post-2')
                    with s.database() as db:
                        stored = db.execute('SELECT status FROM content_ideas WHERE id=?', (idea['id'],)).fetchone()
                    self.assertEqual(stored['status'], 'scheduled')
        self.assertEqual(len(captured), 2)
        instagram = next(item for item in captured if 'instagram' in item['metadata'])
        self.assertEqual(instagram['channelId'], 'instagram-1')
        self.assertEqual(instagram['metadata']['instagram']['type'], 'reel')
        self.assertTrue(instagram['assets'][0]['video']['url'].startswith(self.base + '/media/'))
        with s.database() as db:
            rows = db.execute('SELECT * FROM content_publications WHERE idea_id=?', (idea['id'],)).fetchall()
        self.assertTrue(all(row['status'] == 'confirmed' for row in rows))
        self.assertEqual(sorted(row['buffer_post_id'] for row in rows), ['buffer-post-1', 'buffer-post-2'])


def activities(seed):
    return content_library.generate(seed, 40)
