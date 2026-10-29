"""Render every kinetic episode to a real MP4, with narration and the SFX stem.

This is the batch driver behind `exports/videos/`: one file per episode, each
20.60 s, 1080x1920 at 30 fps, with a mixed soundtrack (voice + the 26-layer
scratch stem). It verifies every file after writing it and refuses to report a
clip that is short, silent or the wrong shape.

    python scripts/render_kinetic_series.py                 # all 19
    python scripts/render_kinetic_series.py --start 1 --end 3
    python scripts/render_kinetic_series.py --narration off  # silent picture

Narration is offline eSpeak NG (`app/kinetic_voice.py`) unless `--narration` is
`off`; the paid MiniMax path lives in the worker (`app/voice.py`) and needs
`FAL_KEY`.
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


def render_one(number, output_dir, narration='offline', stems=None,
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
    if narration == 'offline':
        try:
            info = kinetic_voice.synthesize(data, stems / ('voice-%02d.wav' % number))
            voice = info['path']
            voice_note = '%s @ %d wpm, %.2f s of speech' % (info['voice'], info['wpm'], info['seconds'])
        except Exception as error:                  # never lose the picture over the voice
            voice_note = 'narration failed: ' + str(error)[:200]

    sfx = []
    try:
        stem = stems / ('sfx-%02d.wav' % number)
        kinetic_audio.synthesize(data['audio_blueprint'], stem)
        sfx = [(stem, 0.0)]
    except Exception as error:
        voice_note = (voice_note + ' | ' if voice_note else '') + 'sfx failed: ' + str(error)[:200]

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
    record['ok'] = (record['seconds'] >= 20.50 and record['width'] == 1080
                    and record['height'] == 1920 and record['has_audio'])
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--stems', default='/tmp/stratevo-kinetic-stems')
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=len(kinetic_series.EPISODES))
    parser.add_argument('--narration', choices=('offline', 'off'), default='offline')
    parser.add_argument('--crf', type=int, default=kinetic.MASTER_CRF)
    parser.add_argument('--preset', default=kinetic.MASTER_PRESET)
    parser.add_argument('--audio-bitrate', default=kinetic.MASTER_AUDIO_BITRATE)
    parser.add_argument('--manifest', default=str(DEFAULT_OUT / 'manifest.json'))
    arguments = parser.parse_args(argv)

    output_dir = Path(arguments.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for number in range(arguments.start, arguments.end + 1):
        record = render_one(number, output_dir, arguments.narration,
                            arguments.stems, arguments.crf, arguments.preset,
                            arguments.audio_bitrate)
        records.append(record)
        print('[%02d] %.2fs %dx%d audio=%s %.1fMB %s | %s'
              % (number, record['seconds'], record['width'], record['height'],
                 record['has_audio'], record['bytes'] / 1e6,
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
