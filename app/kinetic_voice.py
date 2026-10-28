"""Offline narration: eSpeak NG through its C API, no network and no API key.

The paid path is fal.ai MiniMax (``app/voice.py``, ~$0.031 per clip). That path
needs ``FAL_KEY``. When it is missing — or the sandbox cannot reach fal — this
module still produces a real spoken take for every episode, offline:

* eSpeak NG is a formant synthesiser, not a neural model, so the read is
  mechanical. It is a stand-in that keeps the picture and the voice in sync,
  not a replacement for the paid voices.
* Pauses come from the episode's own ``<#x#>`` tags, so the read lands on the
  scene cuts exactly like the MiniMax take would.
* The take is EQ'd and compressed with the bundled ffmpeg, then padded to the
  full 20.60 s picture so ``mix_audio`` never has to shorten the video.

``espeakng_loader`` ships the library and voice data inside its wheel, so this
works with no system packages: ``pip install espeakng-loader``.
"""
import ctypes
import re
import subprocess
import wave
from array import array
from pathlib import Path

from app import captions, kinetic_series

PAUSE = re.compile(r'<#\s*([\d.]+)\s*#>')
DEFAULT_VOICE = 'en-us+f3'
DEFAULT_WPM = 165
MAX_SECONDS = kinetic_series.TAIL['start_time'] - 0.3        # 19.60 s of speech

_ESPEAK = None
_CALLBACK = None


class VoiceError(Exception):
    """A narration failure that is safe to show to an operator."""


def available():
    """Is the offline engine importable?"""
    try:
        import espeakng_loader                       # noqa: F401
    except Exception:
        return False
    return True


def _engine():
    """Initialise eSpeak NG once and return (library, samplerate, sink)."""
    global _ESPEAK, _CALLBACK
    if _ESPEAK is not None:
        return _ESPEAK
    try:
        import espeakng_loader
    except Exception:
        raise VoiceError('Offline narration needs `pip install espeakng-loader`.') from None
    library = ctypes.cdll.LoadLibrary(espeakng_loader.get_library_path())
    data = espeakng_loader.get_data_path().encode()
    samplerate = library.espeak_Initialize(2, 0, data, 0)      # 2 = synchronous callback
    if samplerate <= 0:
        raise VoiceError('eSpeak NG could not initialise its voice data.')
    sink = {'chunks': []}
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                     ctypes.c_int, ctypes.c_void_p)

    def collect(wav, count, events):                            # pragma: no cover - C callback
        if count > 0:
            sink['chunks'].append(ctypes.string_at(wav, count * 2))
        return 0

    callback = callback_type(collect)
    library.espeak_SetSynthCallback(callback)
    library.espeak_Synth.restype = ctypes.c_int
    _ESPEAK = (library, samplerate, sink)
    _CALLBACK = callback                       # keep the callback alive
    return _ESPEAK


def speak(text, voice=DEFAULT_VOICE, wpm=DEFAULT_WPM, pitch=48):
    """Synthesise one phrase and return (samples, samplerate)."""
    library, samplerate, sink = _engine()
    if library.espeak_SetVoiceByName(voice.encode()) != 0:
        raise VoiceError('Unknown eSpeak voice: ' + voice)
    library.espeak_SetParameter(1, int(wpm), 0)                 # 1 = rate
    library.espeak_SetParameter(3, int(pitch), 0)               # 3 = pitch
    sink['chunks'] = []
    payload = text.encode('utf-8')
    if library.espeak_Synth(payload, len(payload), 0, 0, 0, 1, None, None) != 0:
        raise VoiceError('eSpeak NG refused to synthesise the text.')
    library.espeak_Synchronize()
    samples = array('h')
    for chunk in sink['chunks']:
        samples.frombytes(chunk)
    sink['chunks'] = []
    return samples, samplerate


def _silence(seconds, samplerate):
    return array('h', bytes(2 * int(round(seconds * samplerate))))


def take(episode_data, voice=DEFAULT_VOICE, wpm=DEFAULT_WPM):
    """The whole episode read, with its pause tags honoured, as raw samples."""
    library, samplerate, _ = _engine()
    script = kinetic_series.voiceover(episode_data)
    pieces, position = [], 0
    for match in PAUSE.finditer(script):
        spoken = script[position:match.start()].strip()
        if spoken:
            samples, _ = speak(spoken, voice=voice, wpm=wpm)
            pieces.append(samples)
        pieces.append(_silence(float(match.group(1)), samplerate))
        position = match.end()
    tail = script[position:].strip()
    if tail:
        samples, _ = speak(tail, voice=voice, wpm=wpm)
        pieces.append(samples)
    combined = array('h')
    for piece in pieces:
        combined.extend(piece)
    return combined, samplerate


def _write_raw(samples, samplerate, destination):
    with wave.open(str(destination), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(samplerate)
        handle.writeframes(samples.tobytes())
    return destination


def synthesize(episode_data, destination, voice=DEFAULT_VOICE, wpm=DEFAULT_WPM,
               duration=kinetic_series.DURATION):
    """Render one episode's narration to a padded, EQ'd 48 kHz WAV.

    If the read overshoots the 19.60 s speech window the rate is raised and the
    take is re-synthesised — never time-stretched with artefacts, and never
    allowed to run into the 19.90 s lowpass tail.
    """
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rate = wpm
    combined, samplerate = take(episode_data, voice=voice, wpm=rate)
    seconds = len(combined) / float(samplerate)
    for _ in range(2):
        if seconds <= MAX_SECONDS:
            break
        rate = min(230, int(round(rate * (seconds / (MAX_SECONDS - 0.2)))))
        combined, samplerate = take(episode_data, voice=voice, wpm=rate)
        seconds = len(combined) / float(samplerate)
    raw = destination.with_suffix('.raw.wav')
    _write_raw(combined, samplerate, raw)
    graph = ('highpass=f=85,lowpass=f=9500,acompressor=threshold=-18dB:ratio=3:attack=8:release=180,'
             'volume=2.0,alimiter=limit=0.95,apad=whole_dur=%.3f,atrim=0:%.3f'
             % (duration, duration))
    command = [captions._ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
               '-i', str(raw), '-af', graph, '-ar', '48000', '-ac', '1',
               '-c:a', 'pcm_s16le', str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    raw.unlink(missing_ok=True)
    if result.returncode != 0 or not destination.exists():
        raise VoiceError('Could not post-process the narration: ' + (result.stderr or '')[-300:])
    return {'path': destination, 'seconds': round(seconds, 2), 'wpm': rate,
            'voice': voice, 'engine': 'espeak-ng'}
