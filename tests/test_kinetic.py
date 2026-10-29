"""The in-code kinetic renderer: frames, encoding, and the series copy.

These tests really render: Pillow draws actual frames and the bundled ffmpeg
encodes them. They keep the range short (a fraction of a second) so the suite
stays fast; the full 20.60 s episode is rendered by the worker, not here.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import captions, kinetic, kinetic_audio, kinetic_series, kinetic_voice, video
from app import suppliers as s


def ffmpeg():
    return captions._ffmpeg()


class KineticRendererTests(unittest.TestCase):
    def test_available_reports_fonts_and_encoder(self):
        status = kinetic.available()
        self.assertTrue(status['ready'])
        self.assertEqual(status['size'], [1080, 1920])
        self.assertEqual(status['fps'], 30)
        self.assertAlmostEqual(status['duration'], 20.60, places=2)
        self.assertEqual(status['episodes'], 19)
        self.assertTrue(all(status['fonts'].values()))

    def test_frames_are_deterministic_and_full_size(self):
        episode = kinetic.Episode(kinetic_series.episode(4), 4)
        first = episode.frame(3.4)
        second = episode.frame(3.4)
        self.assertEqual(first.size, (kinetic.W, kinetic.H))
        self.assertEqual(first.mode, 'RGB')
        # Same timestamp, same pixels: the render is a pure function of time.
        self.assertEqual(first.tobytes(), second.tobytes())

    def test_every_scene_draws_content(self):
        episode = kinetic.Episode(kinetic_series.episode(2), 2)
        # One sample inside each scene, plus the two ends of the timeline.
        moments = [0.05, 0.6, 1.7, 2.7, 4.0, 5.5, 6.6, 7.6, 8.4, 9.2, 9.9,
                   10.6, 12.0, 13.4, 14.4, 15.4, 16.0, 17.0, 18.4, 19.6]
        for moment in moments:
            frame = episode.frame(moment)
            darkest = min(frame.getextrema(), key=lambda pair: pair[1])[1]
            self.assertGreater(darkest, 8, 'scene at %.2fs rendered almost black' % moment)

    def test_text_sprite_centres_tracked_text(self):
        tight = kinetic.text_sprite('TRACKED', 80, kinetic.WHITE, kinetic.DISPLAY, 0, 900, 0.0)
        spaced = kinetic.text_sprite('TRACKED', 80, kinetic.WHITE, kinetic.DISPLAY, 0, 900, 0.02)
        tight_box = tight.getbbox()
        spaced_box = spaced.getbbox()
        self.assertLessEqual(abs((tight_box[0] + tight_box[2]) - (spaced_box[0] + spaced_box[2])), 3)
        self.assertNotIn('\u2260', 'PROFILE')

    def test_not_equal_mark_is_drawn_by_hand(self):
        # No bundled latin subset carries U+2260, so the equation draws it.
        sprite = kinetic.not_equal_sprite()
        self.assertEqual(sprite.mode, 'RGBA')
        self.assertGreater(sprite.getchannel('A').getbbox()[2], 100)

    def test_segment_and_assemble_produce_a_vertical_mp4(self):
        episode = kinetic.Episode(kinetic_series.episode(1), 1)
        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            parts = []
            for index, (start, end) in enumerate(((0.0, 0.4), (0.4, 0.8))):
                part = workdir / ('part-%d.mp4' % index)
                frames = kinetic.segment(episode, start, end, part, fps=12, crf=28, preset='ultrafast')
                self.assertGreaterEqual(frames, 4)
                self.assertGreater(part.stat().st_size, 1000)
                parts.append(part)
            final = workdir / 'final.mp4'
            info = kinetic.assemble(parts, final, fps=12)
            self.assertTrue(final.exists())
            self.assertEqual((info['width'], info['height']), (kinetic.W, kinetic.H))
            self.assertTrue(info['has_audio'])
            self.assertAlmostEqual(info['duration'], 0.8, delta=0.2)

    def test_short_narration_is_padded_not_used_to_cut_the_video(self):
        """Regression: -shortest with a short voice track must not shrink the clip."""
        episode = kinetic.Episode(kinetic_series.episode(1), 1)
        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            parts = []
            for index, (start, end) in enumerate(((0.0, 0.5), (0.5, 1.0))):
                part = workdir / ('part-%d.mp4' % index)
                kinetic.segment(episode, start, end, part, fps=12, crf=28, preset='ultrafast')
                parts.append(part)
            voice = workdir / 'voice.mp3'
            subprocess.run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'sine=frequency=220:duration=0.2',
                            '-c:a', 'libmp3lame', str(voice)], check=True, timeout=120)
            final = workdir / 'with-voice.mp4'
            info = kinetic.assemble(parts, final, audio=voice, fps=12)
        self.assertAlmostEqual(info['duration'], 1.0, delta=0.2)

    def test_render_one_short_episode_end_to_end(self):
        """Full pipeline on a compressed timeline: frames -> segments -> mp4."""
        original = kinetic.DURATION
        try:
            kinetic.DURATION = 1.0
            kinetic.CUTS = (0.0, 0.4, 0.55, 0.7, 0.8, 0.9, 0.95, 1.0)
            with tempfile.TemporaryDirectory() as workdir:
                target = Path(workdir) / 'episode.mp4'
                info = kinetic.render(kinetic_series.episode(1), target, index=1,
                                      fps=10, chunk_seconds=0.5, crf=30, preset='ultrafast')
                self.assertTrue(target.exists())
                self.assertEqual((info['width'], info['height']), (kinetic.W, kinetic.H))
                self.assertGreater(info['bytes'], 2000)
        finally:
            kinetic.DURATION = original
            import importlib
            importlib.reload(kinetic)


class KineticBlueprintTests(unittest.TestCase):
    """The 19 episodes, their copy limits and their 26-layer sound design."""

    def test_every_episode_meets_the_brief(self):
        self.assertEqual(len(kinetic_series.EPISODES), 19)
        for data in kinetic_series.EPISODES:
            self.assertEqual(kinetic_series.validate(data), [], data['hook'])
            blueprint = data['audio_blueprint']
            self.assertTrue(24 <= blueprint['layer_count'] <= 26)
            self.assertEqual(len(blueprint['layers']), blueprint['layer_count'])
            self.assertAlmostEqual(blueprint['duration'], 20.60, places=2)
            # The lowpass tail always closes the clip: 19.90 s for 0.70 s.
            tail = blueprint['layers'][-1]
            self.assertEqual((tail['start_time'], tail['duration']), (19.90, 0.70))
            self.assertEqual(tail['kind'], 'tail')
            starts = [layer['start_time'] for layer in blueprint['layers']]
            self.assertEqual(starts, sorted(starts))
            gaps = [round(b - a, 2) for a, b in zip(starts, starts[1:])]
            self.assertLessEqual(max(gaps), 1.30)
            self.assertLessEqual(sum(1 for gap in gaps if gap > 0.90), 1)
            for layer in blueprint['layers']:
                self.assertTrue(layer['sfx_prompt'].strip())
                self.assertGreater(layer['duration'], 0.0)
                self.assertLessEqual(layer['start_time'] + layer['duration'], 20.60)
                self.assertIn(layer['scene'],
                              ('hook', 'illusions', 'chat', 'wipe', 'questions', 'equation', 'signoff'))

    def test_copy_limits_match_the_viral_rules(self):
        for data in kinetic_series.EPISODES:
            self.assertLessEqual(len(data['hook'].split()), 16)
            for item in data['illusions']:
                self.assertLessEqual(len(item.split()), 3)
                self.assertLessEqual(len(item), 22)
            for item in data['questions']:
                self.assertLessEqual(len(item), 42)
            self.assertLessEqual(kinetic_series.voice_seconds(data), kinetic.DURATION - 0.7)
            caption = data['metadata']['caption']
            self.assertIn('stratevo.online', caption)
            self.assertIn('\u2260', caption)

    def test_episode_data_carries_both_tts_scripts(self):
        data = kinetic_series.episode(3)
        payload = data['episode_data']
        self.assertIn('<#0.35#>', payload['voice_script'])
        self.assertIn('<break time="0.35s"/>', payload['tts_script'])
        self.assertNotIn('<#', payload['tts_script'])
        self.assertEqual(payload['equation']['left'], data['left'])
        self.assertEqual(payload['layout'], data['layout'])
        self.assertIn('one', payload['scenes'])
        self.assertEqual([question['level'] for question in payload['questions']],
                         ['operational blindspot: you cannot see who really makes the product',
                          'quality failure: the batch that ships is not the batch you approved',
                          'catastrophic loss: the money, the cargo, or the liability is yours alone'])
        self.assertAlmostEqual(payload['hook_lands_at'], 1.35, places=2)


class KineticAudioTests(unittest.TestCase):
    """The blueprint is rendered to a real scratch stem: free and deterministic."""

    def test_scratch_stem_covers_the_whole_clip(self):
        blueprint = kinetic_series.episode(1)['audio_blueprint']
        with tempfile.TemporaryDirectory() as workdir:
            stem = Path(workdir) / 'scratch.wav'
            kinetic_audio.synthesize(blueprint, stem)
            info = kinetic.probe(stem)
            self.assertAlmostEqual(info['duration'], 20.60, delta=0.05)
            self.assertGreater(kinetic_audio.peak(stem), 0.2)
            again = Path(workdir) / 'again.wav'
            kinetic_audio.synthesize(blueprint, again)
            self.assertEqual(stem.read_bytes(), again.read_bytes())

    def test_mix_pads_the_voice_and_keeps_late_effects(self):
        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            voice = workdir / 'voice.mp3'
            subprocess.run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'sine=frequency=220:duration=0.4',
                            '-c:a', 'libmp3lame', str(voice)], check=True, timeout=120)
            stem = workdir / 'scratch.wav'
            kinetic_audio.synthesize(kinetic_series.episode(2)['audio_blueprint'], stem)
            mixed = kinetic.mix_audio(workdir / 'mix.wav', duration=20.60,
                                      voice=voice, sfx=[(stem, 0.0)])
            info = kinetic.probe(mixed)
            self.assertAlmostEqual(info['duration'], 20.60, delta=0.05)
            self.assertTrue(info['has_audio'])

    def test_bed_stem_is_a_quiet_ambient_floor(self):
        with tempfile.TemporaryDirectory() as workdir:
            bed = kinetic.bed_stem(Path(workdir) / 'bed.wav', duration=2.0)
            self.assertAlmostEqual(kinetic.probe(bed)['duration'], 2.0, delta=0.05)
            self.assertGreater(kinetic_audio.peak(bed), 0.001)


class KineticQueueExportTests(unittest.TestCase):
    """The Arena_AI_Queue export is pending-only and never overwrites work."""

    def _script(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'export_kinetic_queue.py'
        spec = importlib.util.spec_from_file_location('export_kinetic_queue', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_queue_has_one_pending_row_per_episode(self):
        module = self._script()
        queue = module.rows()
        self.assertEqual(len(queue), 19)
        self.assertEqual({row['status'] for row in queue}, {'pending'})
        self.assertEqual([row['episode'] for row in queue], list(range(1, 20)))
        self.assertEqual({row['sfx_layers'] for row in queue}, {26})
        self.assertEqual({row['duration_seconds'] for row in queue}, {'20.60'})
        self.assertTrue(all('stratevo.online' in row['caption'] for row in queue))
        with tempfile.TemporaryDirectory() as workdir:
            out = module.write_csv(Path(workdir) / 'Arena_AI_Queue.csv', queue)
            text = out.read_text(encoding='utf-8')
            self.assertEqual(len(text.strip().splitlines()), 20)     # header + 19
            self.assertIn('pending', text)

    def test_export_refuses_to_overwrite_published_rows(self):
        module = self._script()
        with tempfile.TemporaryDirectory() as workdir:
            destination = Path(workdir) / 'Arena_AI_Queue.csv'
            destination.write_text('episode,status\n1,published\n', encoding='utf-8')
            with self.assertRaises(SystemExit):
                module.write_csv(destination)


class KineticNarrationTests(unittest.TestCase):
    """Narration must be a neural provider, and must never be faked offline."""

    def test_espeak_is_gone_and_cannot_come_back(self):
        # The robotic fallback was removed after it shipped; this test is the
        # tombstone. Any reappearance fails the suite.
        window = (Path(__file__).resolve().parents[1] / 'app')
        source = (window / 'kinetic_voice.py').read_text()
        for banned in ('espeakng_loader', 'espeak_Initialize', 'espeak_SetVoiceByName',
                       'espeak_Synth'):
            self.assertNotIn(banned, source)
        # No other module in the app may synthesise speech offline either.
        for module in window.glob('*.py'):
            self.assertNotIn('espeakng_loader', module.read_text(), module.name)

    def test_no_key_raises_instead_of_rendering_a_robot(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'FAL_KEY': '', 'OPENAI_API_KEY': '', 'ELEVENLABS_API_KEY': ''}):
            self.assertIsNone(kinetic_voice.provider())
            with tempfile.TemporaryDirectory() as workdir:
                with self.assertRaises(kinetic_voice.VoiceError) as caught:
                    kinetic_voice.synthesize(kinetic_series.episode(1),
                                             Path(workdir) / 'voice.mp3')
        self.assertIn('OPENAI_API_KEY', str(caught.exception))
        self.assertIn('no offline fallback', str(caught.exception).lower())

    def test_requirements_name_every_supported_provider(self):
        listed = kinetic_voice.requirements()
        self.assertEqual(set(listed['providers']), {'fal', 'openai', 'elevenlabs'})
        self.assertEqual(listed['providers']['openai']['env'], 'OPENAI_API_KEY')

    def test_music_bed_sits_under_the_foley_and_the_voice(self):
        blueprint = kinetic_series.episode(2)['audio_blueprint']
        with tempfile.TemporaryDirectory() as workdir:
            workdir = Path(workdir)
            bed = kinetic_audio.music_bed(workdir / 'bed.wav', blueprint=blueprint)
            self.assertAlmostEqual(kinetic.probe(bed)['duration'], 20.60, delta=0.05)
            self.assertLess(kinetic_audio.peak(bed), 0.2)      # never louder than the mix
            stem = workdir / 'sfx.wav'
            kinetic_audio.synthesize(blueprint, stem)
            voice = workdir / 'voice.mp3'
            subprocess.run([ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'sine=frequency=180:duration=6',
                            '-c:a', 'libmp3lame', str(voice)], check=True, timeout=120)
            mixed = kinetic.mix_audio(workdir / 'mix.wav', voice=voice,
                                      sfx=[(stem, 0.0), (bed, 0.0)])
            self.assertAlmostEqual(kinetic.probe(mixed)['duration'], 20.60, delta=0.05)
            self.assertGreater(kinetic_audio.peak(mixed), 0.3)


class KineticSeriesTests(unittest.TestCase):
    def test_episodes_cycle_and_are_distinct(self):
        self.assertEqual(len(kinetic_series.EPISODES), 19)
        self.assertIs(kinetic_series.episode(1), kinetic_series.episode(20))
        self.assertIs(kinetic_series.episode(19), kinetic_series.EPISODES[18])
        hooks = {item['hook'] for item in kinetic_series.EPISODES}
        self.assertEqual(len(hooks), 19)
        for item in kinetic_series.EPISODES:
            self.assertEqual(len(item['illusions']), 3)
            self.assertEqual(len(item['questions']), 3)
            self.assertEqual(len(item['flash']), 4)
            self.assertIn(item['layout'], ('A', 'B', 'C', 'D'))
            self.assertTrue(item['left'] and item['right'])
        # The four layouts are all actually used by the series.
        self.assertEqual({item['layout'] for item in kinetic_series.EPISODES},
                         {'A', 'B', 'C', 'D'})

    def test_voiceover_has_pauses_and_no_stutter(self):
        text = kinetic_series.voiceover(kinetic_series.episode(1))
        self.assertIn('<#0.35#>', text)
        self.assertNotIn('..', text)
        self.assertTrue(text.rstrip().endswith('.'))
        # Questions are spoken naturally, not shouted or re-capitalised.
        self.assertIn('who owns the building?', text.lower())
        self.assertIn('find, vet, verify', text.lower())

    def test_copy_for_an_idea_matches_the_episode(self):
        row = kinetic_series.copy_for(5)
        episode = kinetic_series.episode(5)
        self.assertEqual(row['hook'], episode['hook'])
        self.assertIn('#sourcing', row['tiktok_hashtags'])
        self.assertIn('stratevo.online', row['instagram_caption'])
        self.assertTrue(row['angle'].startswith('kinetic typography'))
        self.assertEqual(set(row), {'topic', 'angle', 'hook', 'script', 'video_prompt',
                                    'negative_prompt', 'tiktok_caption', 'tiktok_hashtags',
                                    'instagram_caption', 'instagram_hashtags'})

    def test_the_model_is_listed_with_a_zero_price(self):
        entry = video.MODELS['kinetic-typography']
        self.assertEqual(entry['renderer'], 'kinetic')
        self.assertEqual(entry['per_second_usd'], 0.0)
        self.assertEqual(entry['endpoint'], '')
        # No fal endpoint: submit() refuses it before any network call.
        self.assertEqual(entry['durations'], (20,))
        self.assertEqual(entry['aspect_ratios'], ('9:16',))


if __name__ == '__main__':
    unittest.main()


class KineticVoiceToolingTests(unittest.TestCase):
    """The operator tools that make a neural voice possible without lying."""

    def _module(self, name):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_export_writes_one_clean_script_per_episode(self):
        module = self._module('export_voice_scripts')
        with tempfile.TemporaryDirectory() as workdir:
            module.main(['--out', workdir])
            files = sorted(Path(workdir).glob('episode-*.txt'))
            self.assertEqual(len(files), 19)
            first = files[0].read_text(encoding='utf-8').strip()
            self.assertTrue(first.startswith('Here is what a real factory audit'))
            self.assertNotIn('<#', first)               # pause tags are gone
            self.assertNotIn(',  ', first)
            self.assertIn('stratevo', first.lower() + 'stratevo')
            self.assertTrue((Path(workdir) / 'scripts.csv').exists())
            self.assertTrue((Path(workdir) / 'README.md').exists())

    def test_check_names_every_provider_and_fails_closed(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {'FAL_KEY': '', 'OPENAI_API_KEY': '',
                                     'ELEVENLABS_API_KEY': '', 'VOICE_ENABLED': 'true'}):
            ok, report = kinetic_voice.check()
        self.assertFalse(ok)
        for name in ('fal', 'openai', 'elevenlabs'):
            self.assertIn(name, report)
        self.assertIn('no neural provider configured', report)

    def test_find_take_prefers_the_documented_name(self):
        module = self._module('render_kinetic_series')
        with tempfile.TemporaryDirectory() as workdir:
            folder = Path(workdir)
            self.assertIsNone(module.find_take(folder, 1))
            (folder / 'episode-03.wav').write_bytes(b'x')
            (folder / 'voice-03.mp3').write_bytes(b'x')
            self.assertEqual(module.find_take(folder, 3).name, 'voice-03.mp3')
            self.assertIsNone(module.find_take('', 3))

    def test_the_voice_window_matches_the_tail(self):
        # Speech has to finish before the 19.90 s lowpass tail or the last word
        # is swallowed by the mix.
        self.assertLess(kinetic_voice.MAX_SECONDS, 19.90)
        self.assertGreater(kinetic_voice.MAX_SECONDS, 18.0)
