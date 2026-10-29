"""Neural narration for the kinetic episodes — no formant synthesis, ever.

Every path here produces a human-sounding voice from a pretrained neural model:

===========  ==========================================================  ==========
provider     what it is                                                  needs
===========  ==========================================================  ==========
``fal``      fal.ai MiniMax speech-2.8 HD (the pipeline's paid voice)     ``FAL_KEY``
``openai``   OpenAI ``gpt-4o-mini-tts`` (voice ``onyx`` by default)       ``OPENAI_API_KEY``
``elevenlabs`` ElevenLabs multilingual v2                                ``ELEVENLABS_API_KEY``
===========  ==========================================================  ==========

There is deliberately **no offline fallback**. eSpeak NG was removed after it
shipped robotic narration: a missing key is an error the operator has to see, not
something to paper over with a synthetic voice. ``synthesize`` raises
:class:`VoiceError` listing what to configure instead.

Only the standard library is used (``urllib``), so this adds no dependency.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from app import kinetic_series
from app import voice as fal_voice

# provider -> (env var, default model, default voice)
PROVIDERS = {
    'fal': ('FAL_KEY', 'fal-ai/minimax/speech-2.8-hd', 'Deep_Voice_Man'),
    'openai': ('OPENAI_API_KEY', 'gpt-4o-mini-tts', 'onyx'),
    'elevenlabs': ('ELEVENLABS_API_KEY', 'eleven_multilingual_v2', 'onwK4e9ZLuTAKqWW03F9'),
}
PREFERENCE = ('fal', 'openai', 'elevenlabs')

OPENAI_URL = 'https://api.openai.com/v1/audio/speech'
ELEVEN_URL = 'https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_128'
MAX_SECONDS = kinetic_series.TAIL['start_time'] - 0.3        # 19.60 s of speech
PAUSE = re.compile(r'<#\s*([\d.]+)\s*#>')
BREAK = re.compile(r'<break\s+time="([\d.]+)s"\s*/>')


class VoiceError(Exception):
    """A narration failure that is safe to show to an operator."""


def enabled():
    """The operator's global kill switch, shared with the old fal voice path."""
    return os.environ.get('VOICE_ENABLED', 'true').strip().lower() != 'false'


def configured():
    """Which neural providers have a key in the environment, in order of use."""
    if not enabled():
        return []
    # KINETIC_PROVIDER=elevenlabs picks a specific voice character, e.g. the
    # British read that suits a consultative B2B audience, even when a cheaper
    # provider also has a key.
    forced = os.environ.get('KINETIC_PROVIDER', '').strip().lower()
    order = ([forced] if forced in PROVIDERS else []) + \
            [name for name in PREFERENCE if name != forced]
    return [name for name in order if os.environ.get(PROVIDERS[name][0], '').strip()]


def provider():
    """The provider that would be used, or ``None`` when nothing is configured."""
    available = configured()
    return available[0] if available else None


def requirements():
    """What an operator must set, for the error message and the admin panel."""
    return {'providers': {name: {'env': env, 'model': model, 'voice': voice}
                          for name, (env, model, voice) in PROVIDERS.items()},
            'configured': configured(),
            'active': provider(),
            'note': 'No offline/robotic fallback exists: narration requires one of these keys.'}


def _speech_text(episode_data):
    """The script as plain prose with real pauses spelled out for the model."""
    script = kinetic_series.voiceover(episode_data)
    script = PAUSE.sub(lambda match: ' … ' if float(match.group(1)) >= 0.4 else ', ',
                       script)
    # A leading pause leaves a stray comma or ellipsis; models will read it as a
    # breath before the first word, or worse, say nothing at all.
    script = script.lstrip(' ,.…')
    return ' '.join(script.split())


def _openai(text, destination, model, voice_name):
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    payload = json.dumps({'model': model, 'voice': voice_name, 'input': text,
                          'response_format': 'mp3',
                          'instructions': ('Warm, authoritative B2B narration. Calm pace, '
                                           'crisp consonants, no upspeak, no shouting.')}).encode()
    request = urllib.request.Request(OPENAI_URL, data=payload, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    _download(request, destination, 'OpenAI TTS')
    return {'engine': 'openai ' + model, 'voice': voice_name}


def _elevenlabs(text, destination, model, voice_name):
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    voice_id = os.environ.get('ELEVENLABS_VOICE_ID', voice_name).strip()
    payload = json.dumps({'text': text, 'model_id': model,
                          'voice_settings': {'stability': 0.45, 'similarity_boost': 0.75,
                                             'style': 0.25, 'use_speaker_boost': True}}).encode()
    request = urllib.request.Request(ELEVEN_URL % voice_id, data=payload, method='POST',
                                     headers={'xi-api-key': key, 'Content-Type': 'application/json'})
    _download(request, destination, 'ElevenLabs')
    return {'engine': 'elevenlabs ' + model, 'voice': voice_id}


def _fal(text, destination, model, voice_name):
    """MiniMax through the pipeline's existing fal client."""
    spoken = fal_voice.synthesize(text, model='minimax-speech-hd'
                                  if 'minimax' in model else 'kokoro')
    Path(destination).write_bytes(spoken['bytes'])
    return {'engine': 'fal ' + model, 'voice': voice_name}


def _download(request, destination, label):
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read()[:300].decode('utf-8', 'ignore')
        raise VoiceError('%s refused the request (%s): %s' % (label, error.code, detail)) from None
    except Exception:
        raise VoiceError('%s could not be reached from this worker.' % label) from None
    if len(payload) < 2048:
        raise VoiceError('%s returned an empty audio file.' % label)
    Path(destination).write_bytes(payload)


def synthesize(episode_data, destination, duration=kinetic_series.DURATION, voice_name=None):
    """Render one episode's narration with a neural voice.

    Raises :class:`VoiceError` when no provider is configured — it never falls
    back to a synthetic voice, because a robotic read is worse than shipping
    nothing and approving it costs a whole render.
    """
    active = provider()
    if not active:
        raise VoiceError(
            'No neural voice provider is configured. Set one of FAL_KEY, '
            'OPENAI_API_KEY or ELEVENLABS_API_KEY in the environment, then re-run. '
            'There is no offline fallback: eSpeak NG was removed and must not return.')
    env, model, default_voice = PROVIDERS[active]
    text = _speech_text(episode_data)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    voice_name = voice_name or os.environ.get('KINETIC_VOICE', default_voice)
    handler = {'fal': _fal, 'openai': _openai, 'elevenlabs': _elevenlabs}[active]
    info = handler(text, destination, model, voice_name)
    seconds = _seconds(destination)
    info.update({'path': destination, 'seconds': seconds, 'characters': len(text),
                 'provider': active, 'model': model})
    if seconds > MAX_SECONDS:
        raise VoiceError('The read is %.2f s and would run into the 19.90 s tail; '
                         'shorten the script or raise the rate.' % seconds)
    return info


def _seconds(path):
    """Duration of an audio file using ffprobe (via the caption helper)."""
    from app import captions
    return float(captions.probe(path)['duration'])

def check(text='Stratevo verifies the factory before you wire the deposit.'):
    """Prove a neural voice is active: reachable, funded and audible.

    ``python -m app.kinetic_voice --check`` prints one line per provider, then
    synthesises a short sentence with the active one and reports its duration.
    Run this before a batch so a dead key or a blocked host costs seconds, not
    the whole render.
    """
    import tempfile
    active = provider()
    lines = ['voice kill switch (VOICE_ENABLED): %s' % ('on' if enabled() else 'off')]
    for name, (env, model, voice_name) in PROVIDERS.items():
        present = bool(os.environ.get(env, '').strip())
        lines.append('  %-11s %-34s %-18s %-14s %s %s'
                     % (name, model, env, voice_name,
                        'set' if present else 'missing',
                        '<- ACTIVE' if name == active else ''))
    if not active:
        lines.append('RESULT: no neural provider configured — set one of FAL_KEY, '
                     'OPENAI_API_KEY or ELEVENLABS_API_KEY.')
        return False, '\n'.join(lines)
    with tempfile.TemporaryDirectory() as workdir:
        target = Path(workdir) / 'check.mp3'
        try:
            info = synthesize({'hook': text, 'questions': [], 'left': 'x', 'right': 'y',
                               'scenes': {}}, target)
        except VoiceError as error:
            lines.append('RESULT: %s is configured but not usable here: %s' % (active, error))
            return False, '\n'.join(lines)
    lines.append('RESULT: %s / %s produced %.2f s of audio — narration is live.'
                 % (active, info['model'], info['seconds']))
    return True, '\n'.join(lines)


if __name__ == '__main__':
    import sys
    ok, report = check()
    print(report)
    raise SystemExit(0 if ok else 1)
