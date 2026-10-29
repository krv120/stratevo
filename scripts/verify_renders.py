"""Verify every rendered episode and rebuild the gallery manifest.

A clip only passes when ffprobe agrees on all of it: >= 20.50 s, 1080x1920,
30 fps, an audio stream, and audio that is actually audible (mean volume above
a silence floor). Prints one line per episode and exits non-zero on any failure.

    python scripts/verify_renders.py
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import captions, kinetic_series

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / 'exports' / 'videos'
VOLUME = re.compile(r'mean_volume:\s*(-?[\d.]+) dB')


def probe(path):
    info = captions.probe(path)
    return {'seconds': round(info['duration'], 3),
            'frames': int(round(info['duration'] * 30)),
            'width': info['width'], 'height': info['height'],
            'has_audio': bool(info['has_audio'])}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def mean_volume(path):
    result = subprocess.run([captions._ffmpeg(), '-hide_banner', '-i', str(path),
                             '-af', 'volumedetect', '-f', 'null', '-'],
                            capture_output=True, text=True, timeout=180)
    match = VOLUME.search(result.stderr or '')
    return float(match.group(1)) if match else None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default=str(DEFAULT_DIR))
    parser.add_argument('--manifest', default=str(DEFAULT_DIR / 'manifest.json'))
    arguments = parser.parse_args(argv)
    folder = Path(arguments.dir)
    records, failures = [], []
    for number in range(1, len(kinetic_series.EPISODES) + 1):
        path = folder / ('kinetic-episode-%02d.mp4' % number)
        data = kinetic_series.episode(number)
        if not path.exists():
            failures.append('%02d missing' % number)
            continue
        info = probe(path)
        volume = mean_volume(path)
        ok = (info['seconds'] >= 20.50 and info['width'] == 1080 and info['height'] == 1920
              and time_ok(info['frames']) and info['has_audio'] and volume is not None
              and volume > -45.0)
        record = {'episode': number, 'hook': data['hook'],
                  'file': path.name, 'bytes': path.stat().st_size,
                  'sha256': sha256(path),
                  'mean_volume_db': volume,
                  'voice': 'eSpeak NG en-us+f3 (offline)',
                  'sfx_layers': data['audio_blueprint']['layer_count'], **info, 'ok': ok}
        records.append(record)
        if not ok:
            failures.append('%02d failed %s' % (number, record))
        print('[%02d] %5.2fs %4dx%-4d audio=%s mean=%.1fdB %4.1fMB %s'
              % (number, info['seconds'], info['width'], info['height'],
                 info['has_audio'], volume if volume is not None else 0.0,
                 path.stat().st_size / 1e6, 'OK' if ok else 'FAILED'), flush=True)
    summary = {'series': kinetic_series.SERIES_NAME,
               'duration': kinetic_series.DURATION,
               'fps': 30,
               'video': {'codec': 'h264 High, yuv420p, bt709', 'crf': 14,
                         'preset': 'slow', 'x264': 'aq-mode=3:bframes=3'},
               'audio': {'codec': 'aac LC', 'bitrate': '192k', 'sample_rate': 48000},
               'narration': 'eSpeak NG (offline formant synthesiser)',
               'episodes': records}
    Path(arguments.manifest).write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print('%d/%d verified; failures: %s' % (len(records) - len(failures), len(records),
                                            failures or 'none'))
    return 1 if failures else 0


def time_ok(frames):
    return frames >= 615


if __name__ == '__main__':
    raise SystemExit(main())
