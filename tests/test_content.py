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

from app import buffer_api, captions, content, content_library, kinetic, kinetic_series, media, video, voice
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
            'CONTENT_MEDIA_DIR': str(Path(self.tmp.name) / 'media'), 'CONTENT_NIGHTLY_COUNT': '0',
            'VOICE_ENABLED': 'false',
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
        self.assertEqual(len([line for line in document.splitlines() if line.startswith('Style:')]), 3)
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

    # --- voiceover --------------------------------------------------------
    def test_pause_tags_are_stripped_for_models_that_would_speak_them(self):
        text = 'One<#0.35#>two <#1.5#> three.'
        self.assertEqual(voice.strip_pauses(text), 'One two three.')
        kokoro = voice._payload('kokoro', text, 'af_heart')
        self.assertEqual(kokoro['text'], 'One two three.')
        minimax = voice._payload('minimax-speech-hd', text, 'Deep_Voice_Man')
        self.assertIn('<#0.35#>', minimax['prompt'])   # MiniMax honours pauses

    def test_voice_payloads_and_estimates(self):
        plan = voice.estimate('x' * 220)
        self.assertEqual(plan['model'], 'minimax-speech-hd')
        self.assertAlmostEqual(plan['usd'], 0.022, places=3)
        self.assertAlmostEqual(voice.estimate('x' * 220, 'kokoro')['usd'], 0.0044, places=4)
        payload = voice._payload('minimax-speech-hd', 'hello', None)
        self.assertEqual(payload['language_boost'], 'English')
        self.assertEqual(payload['voice_setting']['voice_id'], voice.DEFAULT_VOICE)
        self.assertEqual(payload['audio_setting']['format'], 'mp3')
        self.assertIn('text', voice._payload('kokoro', 'hello', None))

    def test_narration_fits_the_clip_length(self):
        long_text = 'one two three four five six seven eight nine ten ' * 4
        self.assertLessEqual(len(voice.fit(long_text, 10).split()), 26)
        self.assertLessEqual(len(voice.fit(long_text, 5).split()), 13)
        self.assertEqual(voice.fit('Short line.', 10), 'Short line.')

    def test_narration_script_is_hook_plus_body(self):
        idea = {'hook': 'Nobody warns you about fast quotes.', 'script': 'Ask for the sampling plan first.'}
        self.assertEqual(content.narration_script(idea),
                         'Nobody warns you about fast quotes. Ask for the sampling plan first.')

    def test_voiceover_is_mixed_into_the_clip_and_costed(self):
        clip = make_clip(Path(self.tmp.name) / 'clip.mp4', 3)
        audio = Path(self.tmp.name) / 'voice.mp3'
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'sine=frequency=660:duration=3',
                        '-c:a', 'libmp3lame', '-b:a', '128k', str(audio)], check=True)
        environment = {'VOICE_ENABLED': 'true', 'CONTENT_VOICE_LIMIT_USD': '3'}
        with patch.dict(os.environ, environment):
            with patch.object(voice, 'synthesize', lambda text, idea_id='': {
                    'bytes': audio.read_bytes(), 'cost_usd': 0.02, 'characters': len(text),
                    'model': 'minimax-speech-hd', 'voice': 'Deep_Voice_Man'}):
                with patch.object(content, 'fal_download', lambda url: clip):
                    series_id = self.series(1)
                    code, body, _ = self.http('/api/admin/content/overview', cookie=self.admin())
                    idea = json.loads(body)['ideas'][0]
                    self.http('/api/admin/content/decide', {'id': idea['id'], 'action': 'approve'},
                              cookie=self.admin())
                    self.http('/api/admin/content/generate', {'series_id': series_id, 'limit': 1},
                              cookie=self.admin())
                    self.stub.complete(self.stub.submissions[0]['request_id'])
                    report = content.tick('voice-worker', max_caption=1)
        self.assertEqual(len(report['captions']), 1)
        with s.database() as db:
            row = db.execute('SELECT status,caption_error,media_asset_id FROM content_ideas').fetchone()
        self.assertEqual(row['status'], 'ready_to_publish')
        self.assertEqual(row['caption_error'], '')
        with s.database() as db:
            token = db.execute('SELECT token FROM media_assets WHERE id=?', (row['media_asset_id'],)).fetchone()
        code, served, headers = self.http('/media/' + token['token'] + '.mp4')
        self.assertEqual(code, 200)
        self.assertTrue(served.find(b'mvhd') > 0)

    # --- in-code kinetic renderer -----------------------------------------
    def test_kinetic_series_seeds_episode_copy_and_costs_nothing(self):
        series_id = self.series(3, model='kinetic-typography', duration_seconds=20, resolution='')
        overview = content.overview(series_id)
        self.assertEqual(overview['series']['renderer'], 'kinetic')
        self.assertEqual(overview['cost']['total_usd'], 0.0)
        ideas = overview['ideas']
        self.assertEqual(len(ideas), 3)
        # The copy is the episode's own, so the on-screen type and the posted
        # caption cannot drift apart.
        episode = kinetic_series.episode(1)
        self.assertEqual(ideas[0]['hook'], episode['hook'])
        self.assertIn(episode['hook'].split('.')[0], ideas[0]['tiktok_caption'])
        self.assertTrue(ideas[1]['hook'])
        estimate = content.estimate('kinetic-typography', 20, count=40)
        self.assertEqual(estimate['total_usd'], 0.0)
        self.assertEqual(estimate['affordable_videos'], 40)
        self.assertEqual(estimate['renderer'], 'kinetic')

    def test_kinetic_generation_queues_local_renders_without_a_key(self):
        series_id = self.series(2, model='kinetic-typography', duration_seconds=20, resolution='')
        with s.database() as db:
            identifiers = [row['id'] for row in
                           db.execute('SELECT id FROM content_ideas ORDER BY position')]
        for idea_id in identifiers:
            content.decide({'id': idea_id, 'action': 'approve'}, 'unit-test')
        with patch.dict(os.environ, {'FAL_KEY': ''}):
            result = content.submit_batch({'series_id': series_id, 'limit': 2}, 'unit-test')
        self.assertEqual(result['queued_count'], 2)
        self.assertEqual(result['spend_usd'], 0.0)
        self.assertEqual(result['renderer'], 'kinetic')
        self.assertEqual(self.stub.submissions, [])
        with s.database() as db:
            statuses = {row['status'] for row in db.execute('SELECT status FROM content_ideas')}
            jobs = db.execute("SELECT COUNT(*) AS n FROM content_jobs WHERE kind='caption'").fetchone()['n']
        self.assertEqual(statuses, {'video_ready'})
        self.assertEqual(jobs, 2)

    def test_kinetic_worker_renders_stores_and_serves_the_clip(self):
        series_id = self.series(1, model='kinetic-typography', duration_seconds=20, resolution='')
        with s.database() as db:
            idea_id = db.execute('SELECT id FROM content_ideas').fetchone()['id']
        content.decide({'id': idea_id, 'action': 'approve'}, 'unit-test')
        content.submit_batch({'series_id': series_id, 'limit': 1}, 'unit-test')
        clip = make_clip(Path(self.tmp.name) / 'kinetic.mp4', seconds=1)
        calls = []

        def fake_render(data, destination, **options):
            calls.append(options)
            Path(destination).write_bytes(clip)
            return {'duration': 19.73, 'has_audio': False, 'width': 1080, 'height': 1920}

        with patch.object(kinetic, 'render', fake_render):
            report = content.tick('kinetic-worker', max_caption=1, max_generate=0)
        self.assertEqual(len(report['captions']), 1)
        with s.database() as db:
            row = db.execute('SELECT status,media_asset_id,source_video_url,caption_error '
                             'FROM content_ideas').fetchone()
            token = db.execute('SELECT token FROM media_assets WHERE id=?',
                               (row['media_asset_id'],)).fetchone()['token']
        self.assertEqual(row['status'], 'ready_to_publish')
        self.assertEqual(row['source_video_url'], 'kinetic://episode-1')
        self.assertEqual(row['caption_error'], '')
        self.assertEqual(len(calls), 1)
        # Voice is disabled in the tests, so the clip is silent but complete.
        self.assertFalse(calls[0]['audio'])
        code, served, _ = self.http('/media/' + token + '.mp4')
        self.assertEqual(code, 200)
        self.assertTrue(served.find(b'mvhd') > 0)

    def test_kinetic_render_requires_no_fal_endpoint(self):
        with self.assertRaises(s.WorkflowError) as caught:
            video.submit({'prompt': 'x' * 40, 'model': 'kinetic-typography',
                          'duration_seconds': 20, 'aspect_ratio': '9:16',
                          'client_key': 'kinetic-test-0123456789'})
        self.assertEqual(caught.exception.status, 400)
        self.assertIn('rendered in code', str(caught.exception))
        self.assertEqual(self.stub.submissions, [])

    # --- nightly cadence --------------------------------------------------
    def test_nightly_target_respects_the_window_and_the_budget(self):
        series_id = self.series(8)
        with patch.dict(os.environ, {'CONTENT_NIGHTLY_COUNT': '6', 'CONTENT_AUTO_APPROVE': 'true'}):
            zone = content._zone()
            night = datetime.datetime.now(zone).replace(hour=23, minute=0, second=0, microsecond=0)
            with patch.object(content, 'inside_night', lambda now=None: True):
                with patch.object(content, 'generated_tonight', lambda now=None: 0):
                    first = content.nightly_topup(max_submit=2)
                    second = content.nightly_topup(max_submit=2)
            self.assertEqual(first['submitted'], 2)
            self.assertEqual(second['submitted'], 2)
            self.assertEqual(len(self.stub.submissions), 4)
            with patch.object(content, 'inside_night', lambda now=None: False):
                closed = content.nightly_topup(max_submit=2)
            self.assertEqual(closed['submitted'], 0)
            self.assertIn('Outside the nightly window', closed['reason'])
            with patch.object(content, 'inside_night', lambda now=None: True):
                with patch.object(content, 'generated_tonight', lambda now=None: 6):
                    done = content.nightly_topup(max_submit=2)
            self.assertEqual(done['submitted'], 0)
            self.assertIn('already met', done['reason'])

    def test_night_window_boundaries_are_local_hours(self):
        zone = content._zone()
        cases = {23: True, 20: True, 9: False, 8: True, 0: True, 19: False, 12: False}
        for hour, expected in cases.items():
            moment = datetime.datetime.now(zone).replace(hour=hour, minute=0, second=0,
                                                         microsecond=0)
            self.assertEqual(content.inside_night(int(moment.timestamp())), expected,
                             'inside_night failed at %02d:00 Athens' % hour)
        start, end = content.night_window(int(datetime.datetime.now(zone).replace(
            hour=2, minute=30, tzinfo=None).timestamp()))
        self.assertEqual(content.inside_night(start + 60), True)
        self.assertEqual(content.inside_night(end), False)

    def test_nightly_never_exceeds_the_monthly_limit(self):
        series_id = self.series(8)
        with patch.dict(os.environ, {'CONTENT_NIGHTLY_COUNT': '6', 'CONTENT_AUTO_APPROVE': 'true',
                                     'VIDEO_SPEND_LIMIT_USD': '1'}):
            with patch.object(content, 'inside_night', lambda now=None: True):
                with patch.object(content, 'generated_tonight', lambda now=None: 0):
                    result = content.nightly_topup(max_submit=6)
        self.assertEqual(result['submitted'], 2)
        self.assertIn('spending limit', result['reason'])

    # --- unattended scheduling and Buffer quota ---------------------------
    def test_auto_schedule_appends_slots_without_duplicating(self):
        series_id = self.series(9, model='kinetic-typography', duration_seconds=20, resolution='')
        with s.database() as db:
            identifiers = [row['id'] for row in
                           db.execute('SELECT id FROM content_ideas ORDER BY position')]
        for idea_id in identifiers:
            content.decide({'id': idea_id, 'action': 'approve'}, 'unit-test')
        with patch.dict(os.environ, {'FAL_KEY': ''}):
            content.submit_batch({'series_id': series_id, 'limit': 3}, 'unit-test')
        # Only rendered clips can be scheduled: mark three as ready with media.
        with s.database() as db:
            for index, idea_id in enumerate(identifiers[:3]):
                db.execute("UPDATE content_ideas SET status='ready_to_publish', media_asset_id=? WHERE id=?",
                           ('asset-%d' % index, idea_id))
        with patch.dict(os.environ, {'CONTENT_AUTO_SCHEDULE': 'true', 'CONTENT_AUTO_SCHEDULE_AHEAD': '3'}):
            first = content.auto_schedule()
            second = content.auto_schedule()
        self.assertEqual(first['created'], 6)      # 3 ideas x 2 platforms
        self.assertEqual(second['created'], 0)     # nothing duplicated
        with s.database() as db:
            rows = db.execute('SELECT platform,due_at,local_slot FROM content_publications '
                              'ORDER BY due_at').fetchall()
            ideas = db.execute("SELECT COUNT(*) AS n FROM content_ideas "
                               "WHERE COALESCE(media_asset_id,'')=''").fetchone()['n']
        self.assertEqual(len(rows), 6)
        self.assertEqual({row['platform'] for row in rows}, {'tiktok', 'instagram'})
        # Every slot is in the future and on a configured local time.
        now = s.now()
        self.assertTrue(all(row['due_at'] > now for row in rows))
        hours = {(hour, minute) for hour, minute in content.slot_hours()}
        for row in rows:
            local = datetime.datetime.fromtimestamp(row['due_at'], content._zone())
            self.assertIn((local.hour, local.minute), hours)
        self.assertEqual(ideas, 6)                 # clips with no media stay unscheduled

    def test_auto_schedule_can_be_switched_off(self):
        with patch.dict(os.environ, {'CONTENT_AUTO_SCHEDULE': 'false'}):
            result = content.auto_schedule()
        self.assertEqual(result['created'], 0)
        self.assertIn('CONTENT_AUTO_SCHEDULE is off', result['reason'])

    def test_buffer_polling_respects_the_interval(self):
        calls = []

        def fake_post(identifier):
            calls.append(identifier)
            return {'id': identifier, 'status': 'sent', 'sentAt': 'now'}

        with patch.object(buffer_api, 'post', fake_post), \
                patch.dict(os.environ, {'CONTENT_BUFFER_POLL_SECONDS': '1800'}):
            first = content.refresh_publications(3, force=True)
            self.assertEqual(len(calls), 0)          # nothing due yet
            self.assertEqual(first, [])
            # A second call inside the interval makes no request at all.
            content.refresh_publications(3)
            self.assertEqual(len(calls), 0)
            self.assertEqual(content.refresh_interval(), 1800)
            with patch.dict(os.environ, {'CONTENT_BUFFER_POLL_SECONDS': '60'}):
                self.assertEqual(content.refresh_interval(), 300)   # floored
        self.assertLess(content.refresh_interval(), 3600)

    # --- scheduling -------------------------------------------------------
    def test_slots_are_spread_across_thirty_days_in_athens(self):
        slots = content.build_slots(40, 30)
        self.assertEqual(len(slots), 40)
        stamps = [stamp for stamp, _ in slots]
        self.assertEqual(stamps, sorted(stamps))
        zone = content._zone()
        local = [datetime.datetime.fromtimestamp(stamp, zone) for stamp in stamps]
        self.assertTrue(all((item.hour, item.minute) in content.DEFAULT_SLOT_HOURS for item in local))
        tomorrow = (datetime.datetime.now(zone) + datetime.timedelta(days=1)).date()
        self.assertGreaterEqual(local[0].date(), tomorrow)
        self.assertLessEqual((local[-1].date() - local[0].date()).days, 29)
        self.assertEqual(len({(item.year, item.month, item.day) for item in local}), 30)
        # Winter time is +2, summer time is +3: the stored UTC epoch follows the zone.
        january = content.build_slots(2, 2, start=datetime.datetime(2027, 1, 10, tzinfo=zone))
        hour, minute = content.DEFAULT_SLOT_HOURS[0]
        # 09:00 Athens in January is UTC+2, so the epoch is 07:00 UTC.
        self.assertEqual(january[0][0] % 86400, ((hour - 2) * 3600 + minute * 60) % 86400)

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
        # The tick that rendered it also queued it for posting (auto-schedule),
        # so nothing is sent yet because publishing is off.
        with s.database() as db:
            queued = db.execute("SELECT COUNT(*) AS n FROM content_publications WHERE status='planned'").fetchone()['n']
        self.assertEqual(queued, 2)
        code, body, _ = self.http('/api/admin/content/schedule', {'series_id': series_id, 'days': 30},
                                  cookie=self.admin())
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)['planned'], 0)   # no duplicate slots
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
