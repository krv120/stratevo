"""Render every kinetic episode to a real MP4, with narration and the SFX stem.

This is the batch driver behind `exports/videos/`: one file per episode, each
20.60 s, 1080x1920 at 30 fps, with a mixed soundtrack (voice + the 26-layer
scratch stem). It verifies every file after writing it and refuses to report a
clip that is short, silent or the wrong shape.

    python scripts/render_kinetic_series.py                 # all 19
    python scripts/render_kinetic_series.py --start 1 --end 3
    python scripts/render_kinetic_series.py --start 1 --end 1  # one preview
    python scripts/render_kinetic_series.py --episodes 1,5,3,13  # one per layout
    python scripts/render_kinetic_series.py --narration silent   # no voice

Narration is a neural voice from `app/kinetic_voice.py` (fal MiniMax, OpenAI or
ElevenLabs) and is **required**: the script refuses to render a silent or robotic
clip: with no key configured it raises `VoiceError` before drawing a frame.
`--narration silent` is the only way to render picture + music + foley alone.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import captions, kinetic, kinetic_audio, kinetic_series, kinetic_voice

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'exports' / 'videos'


def render_one(number, output_dir, narration='neural', stems=None,
               crf=kinetic.MASTER_CRF, preset=kinetic.MASTER_PRESET,
               audio_bitrate=kinetic.MASTER_AUDIO_BITRATE):
    """Render one episode and return a verification record."""
    data = kinetic_series.episode(number)
    target = Path(output_dir) / ('kinetic-episode-%02d.mp4' % number)
    stems = Path(stems or '/tmp/stratevo-kinetic-stems')
    stems.mkdir(parents=True, exist_ok=True)
    started = time.time()

    voice = None
    voice_note = ''
    if narration == 'neural':
        # A missing key is fatal on purpose: rendering 19 robotic clips wastes
        # more time than stopping here.
        info = kinetic_voice.synthesize(data, stems / ('voice-%02d.mp3' % number))
        voice = info['path']
        voice_note = '%s / %s, %.2f s of speech' % (info['provider'], info['model'],
                                                    info['seconds'])
    else:
        voice_note = 'silent (--allow-silent)'

    sfx = []
    stem = stems / ('sfx-%02d.wav' % number)
    kinetic_audio.synthesize(data['audio_blueprint'], stem)
    sfx = [(stem, 0.0)]
    bed = stems / ('bed-%02d.wav' % number)
    kinetic_audio.music_bed(bed, blueprint=data['audio_blueprint'])
    sfx.append((bed, 0.0))

    info = kinetic.render(data, target, index=number, sfx=sfx, voice=voice, crf=crf,
                          preset=preset, audio_bitrate=audio_bitrate)
    probe = captions.probe(target)
    record = {
        'episode': number,
        'hook': data['hook'],
        'file': str(target),
        'seconds': round(probe['duration'], 3),
        'frames': int(round(probe['duration'] * kinetic.FPS)),
        'width': probe['width'],
        'height': probe['height'],
        'has_audio': probe['has_audio'],
        'bytes': target.stat().st_size,
        'render_seconds': round(time.time() - started, 1),
        'voice': voice_note,
        'sfx_layers': data['audio_blueprint']['layer_count'],
        'encode': {'crf': crf, 'preset': preset, 'x264': kinetic.ENCODE_X264,
                   'audio_bitrate': audio_bitrate},
    }
    record['layout'] = data.get('layout')
    record['ok'] = (record['seconds'] >= 20.50 and record['width'] == 1080
                    and record['height'] == 1920 and record['has_audio'])
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--stems', default='/tmp/stratevo-kinetic-stems')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=len(kinetic_series.EPISODES))
    parser.add_argument('--episodes', default='',
                        help='comma-separated episode numbers, overrides --start/--end')
    parser.add_argument('--narration', choices=('neural', 'silent'), default='neural')
    parser.add_argument('--crf', type=int, default=kinetic.MASTER_CRF)
    parser.add_argument('--preset', default=kinetic.MASTER_PRESET)
    parser.add_argument('--audio-bitrate', default=kinetic.MASTER_AUDIO_BITRATE)
    parser.add_argument('--manifest', default=str(DEFAULT_OUT / 'manifest.json'))
    arguments = parser.parse_args(argv)

    output_dir = Path(arguments.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    numbers = ([int(item) for item in arguments.episodes.split(',') if item.strip()]
               if arguments.episodes.strip() else range(arguments.start, arguments.end + 1))
    for number in numbers:
        record = render_one(number, output_dir, arguments.narration,
                            arguments.stems, arguments.crf, arguments.preset,
                            arguments.audio_bitrate)
        records.append(record)
        print('[%02d] %s %.2fs %dx%d audio=%s %.1fMB %s | %s'
              % (number, record['layout'], record['seconds'], record['width'],
                 record['height'], record['has_audio'], record['bytes'] / 1e6,
                 'OK' if record['ok'] else 'FAILED', record['voice']), flush=True)
    manifest = Path(arguments.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({'duration': kinetic_series.DURATION,
                                    'fps': kinetic.FPS,
                                    'episodes': records}, indent=2), encoding='utf-8')
    failures = [record['episode'] for record in records if not record['ok']]
    print('Rendered %d episode(s); failures: %s' % (len(records), failures or 'none'))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
