"""Voiceover for the vertical clips, generated on fal.ai.

The reference style this pipeline targets (reseller / sourcing TikToks) is
narration-led: a short, punchy voice reading the hook and the point, with big
captions over b-roll. Text-to-video alone produces silent clips, which look and
perform worse on TikTok and Instagram, so each idea gets a real generated voice.

Pricing checked 2026-10-27 on fal.ai:

* ``fal-ai/minimax/speech-2.8-hd`` — $0.10 / 1,000 characters (highest quality,
  stock voices, emotion control).
* ``fal-ai/kokoro/american-english`` — $0.02 / 1,000 characters (cheap fallback).

A 220-character script costs $0.022 with MiniMax HD and $0.0044 with Kokoro, so
180 clips a month is roughly $4 or $0.80 respectively. Voiceover is disabled
unless ``VOICE_ENABLED=true`` and capped by ``CONTENT_VOICE_LIMIT_USD``.
"""
import json
import os
import time
import urllib.request
from urllib.parse import urlsplit

from app import fal
from app import suppliers as s

ENDPOINTS = {
    'minimax-speech-hd': {
        'endpoint': 'fal-ai/minimax/speech-2.8-hd',
        'label': 'MiniMax Speech 2.8 HD',
        'per_1k_chars_usd': 0.10,
        'docs': 'https://fal.ai/models/fal-ai/minimax/speech-2.8-hd',
    },
    'kokoro': {
        'endpoint': 'fal-ai/kokoro/american-english',
        'label': 'Kokoro',
        'per_1k_chars_usd': 0.02,
        'docs': 'https://fal.ai/models/fal-ai/kokoro/american-english',
    },
}
DEFAULT_MODEL = 'minimax-speech-hd'
# Documented stock voice ids; the first is used when nothing is configured.
DEFAULT_VOICE = 'Deep_Voice_Man'
MAX_CHARS = 1200
TIMEOUT = 45


class VoiceError(Exception):
    """A voiceover failure that is safe to show to an operator."""


def configured():
    return fal.configured() and os.environ.get('VOICE_ENABLED', 'false').strip().lower() == 'true'


def model_key():
    value = (os.environ.get('VOICE_MODEL') or DEFAULT_MODEL).strip()
    return value if value in ENDPOINTS else DEFAULT_MODEL


def voice_id():
    value = (os.environ.get('VOICE_ID') or DEFAULT_VOICE).strip()
    if not value or len(value) > 60 or any(ch.isspace() for ch in value):
        return DEFAULT_VOICE
    return value


def limit_usd():
    try:
        value = float(os.environ.get('CONTENT_VOICE_LIMIT_USD', '3'))
    except ValueError:
        raise s.WorkflowError('CONTENT_VOICE_LIMIT_USD must be a number.', 503) from None
    return max(0.0, min(value, 50.0))


def spent(now=None):
    """Voice spend committed this calendar month (UTC)."""
    start = s.now() - (s.now() % 86400)  # replaced below by the month boundary
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc)
    start = int(datetime.datetime(today.year, today.month, 1, tzinfo=datetime.timezone.utc).timestamp())
    with s.database() as db:
        row = db.execute("SELECT COALESCE(SUM(usd),0) AS total FROM content_costs WHERE kind='voice' AND created_at>=?",
                         (start,)).fetchone()
    return round(float(row['total'] or 0), 4)


def estimate(text, model=None):
    name = model if model in ENDPOINTS else model_key()
    entry = ENDPOINTS[name]
    characters = len(text or '')
    return {'model': name, 'label': entry['label'], 'characters': characters,
            'usd': round(entry['per_1k_chars_usd'] * characters / 1000.0, 4),
            'per_1k_chars_usd': entry['per_1k_chars_usd']}


def _record(idea_id, characters, usd, model):
    with s.database() as db:
        db.execute('INSERT INTO content_costs (id,idea_id,kind,units,usd,model,created_at) VALUES (?,?,?,?,?,?,?)',
                   (str(__import__('uuid').uuid4()), str(idea_id)[:64], 'voice', int(characters),
                    float(usd), model, s.now()))


def synthesize(text, *, idea_id='', model=None, voice=None):
    """Generate speech and return ``{'bytes', 'cost_usd', 'characters', 'model'}``."""
    if not fal.configured():
        raise VoiceError('FAL_KEY is not configured, so no voiceover can be generated.')
    text = ' '.join((text or '').split())
    if len(text) < 12:
        raise VoiceError('The script is too short for a voiceover.')
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit(' ', 1)[0]
    plan = estimate(text, model)
    remaining = limit_usd() - spent()
    if plan['usd'] > remaining + 1e-9:
        raise VoiceError('The voiceover budget for this month is used up '
                         '($%.2f of $%.2f). It will retry next month.' % (spent(), limit_usd()))
    name = plan['model']
    entry = ENDPOINTS[name]
    payload = _payload(name, text, voice)
    started = time.time()
    submitted = fal.submit(entry['endpoint'], payload)
    deadline = started + TIMEOUT
    state = ''
    while time.time() < deadline:
        state = str(fal.status(submitted['status_url']).get('status') or '').upper()
        if state == 'COMPLETED':
            break
        if state in ('FAILED', 'CANCELED'):
            raise VoiceError('The voice model did not complete the request.')
        time.sleep(1.2)
    if state != 'COMPLETED':
        raise VoiceError('The voiceover timed out; the clip was captioned without narration.')
    body = fal.result(submitted['response_url'])
    url = (body.get('audio') or {}).get('url') if isinstance(body, dict) else ''
    if not isinstance(url, str) or not url.startswith('https://'):
        raise VoiceError('The voice model returned no audio file.')
    data = _download(url)
    _record(idea_id, plan['characters'], plan['usd'], name)
    return {'bytes': data, 'cost_usd': plan['usd'], 'characters': plan['characters'],
            'model': name, 'voice': voice or voice_id()}


def fit(text, seconds, words_per_second=2.6):
    """Trim a script so the read finishes inside the clip.

    MiniMax at speed 1.02 speaks roughly 2.6 words a second; a 10 s clip can
    hold about 26 words. Without this the last sentence is cut off by ``-t``.
    """
    words = (text or '').split()
    limit = max(4, int(float(seconds or 0) * words_per_second))
    if len(words) <= limit:
        return ' '.join(words)
    kept = words[:limit]
    # Prefer ending on a sentence boundary when one is close to the limit.
    joined = ' '.join(kept)
    for mark in ('. ', '? ', '! '):
        index = joined.rfind(mark)
        if index >= len(joined) * 0.55:
            return joined[:index + 1]
    return joined.rstrip(',;:-') + '.'


def _payload(name, text, voice):
    if name == 'kokoro':
        return {'text': text, 'voice': (voice or os.environ.get('KOKORO_VOICE') or 'af_heart'),
                'speed': 1.05}
    return {'prompt': text, 'language_boost': 'English', 'output_format': 'url',
            'voice_setting': {'voice_id': voice or voice_id(), 'speed': 1.02, 'vol': 1.0,
                              'emotion': 'neutral', 'english_normalization': True},
            'audio_setting': {'format': 'mp3', 'sample_rate': '44100', 'bitrate': '128000', 'channel': '1'}}


def _download(url):
    host = (urlsplit(url).hostname or '').lower()
    if not any(host == allowed or host.endswith('.' + allowed)
               for allowed in ('fal.media', 'storage.googleapis.com', 'fal.run')):
        raise VoiceError('The voice file was hosted somewhere unexpected.')
    request = urllib.request.Request(url, headers={'User-Agent': 'stratevo-content-studio/1'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(8 * 1024 * 1024 + 1)
    except Exception:
        raise VoiceError('The voice file could not be downloaded.') from None
    if len(data) > 8 * 1024 * 1024 or len(data) < 512:
        raise VoiceError('The voice file was empty or too large.')
    return data


def status():
    return {'enabled': configured(), 'model': model_key(), 'label': ENDPOINTS[model_key()]['label'],
            'voice': voice_id(), 'limit_usd': limit_usd(), 'spent_usd': spent(),
            'remaining_usd': round(max(0.0, limit_usd() - spent()), 4),
            'models': [{'id': key, 'label': item['label'], 'per_1k_chars_usd': item['per_1k_chars_usd']}
                       for key, item in ENDPOINTS.items()]}
