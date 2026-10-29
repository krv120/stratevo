"""Formant narration, shaped into a broadcast voice.

The neural providers in `app/kinetic_voice.py` are the first choice. When the
worker has no route to them (this sandbox blocks every TTS host) and no key is
configured, this module is the fallback: eSpeak NG speaks the script at a
conversational 145 WPM with a low male variant, and the take is then run through
a studio DSP chain so it stops sounding like a formant synthesiser reading a
phone book:

    high-pass 90 Hz          removes rumble
    low-pass 6.5 kHz         removes the metallic fizz above the formants
    peaking EQ               +2 dB at 180 Hz (chest), -2.5 dB at 420 Hz (honk),
                             -3 dB at 2.6 kHz and -3.5 dB at 4.8 kHz (harshness)
    asoftclip tanh           tube-style saturation, adds even harmonics
    aexciter                 a little air back at the top
    acompressor 3:1          evens the read out
    chorus (very light)      smears the formant edges just enough to stop the
                             "robot" tell without sounding seasick
    aecho                    a short studio room, 26 ms tapped
    alimiter                 safety ceiling

It is honest about what it is: `take()` returns ``engine='espeak-ng+dsp'`` and
every manifest written from it records that string, so a rendered file can never
be mistaken for a neural take.

    python -m app.kinetic_formant --episode 1 --out /tmp/voice-01.wav
"""
import argparse
import ctypes
import json
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

from app import kinetic_series

RATE = 22050
DEFAULT_VOICE = 'en-gb-x-rp+m3'      # received pronunciation, low male variant
DEFAULT_WPM = 145
DEFAULT_PITCH = 26                   # 0-99, 50 is eSpeak's neutral
MAX_SECONDS = kinetic_series.TAIL['start_time'] - 0.25      # 19.65 s

_AUDIO_OUTPUT_RETRIEVAL = 1
_espeak = None
_buffer = bytearray()


def _library():
    """Load libespeak-ng from the PyPI wheel and initialise it once."""
    global _espeak
    if _espeak is not None:
        return _espeak
    import espeakng_loader
    lib = ctypes.CDLL(str(espeakng_loader.get_library_path()))
    lib.espeak_Initialize.restype = ctypes.c_int
    lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    lib.espeak_SetVoiceByName.restype = ctypes.c_int
    lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    lib.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.espeak_Synth.restype = ctypes.c_int
    lib.espeak_Synth.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
                                 ctypes.c_uint, ctypes.c_uint,
                                 ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p]
    lib.espeak_Synchronize.restype = ctypes.c_int
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short),
                                     ctypes.c_int, ctypes.c_void_p)
    lib.espeak_SetSynthCallback.argtypes = [callback_type]

    def collect(samples, count, events):
        if count > 0:
            _buffer.extend(bytes(ctypes.string_at(samples, count * 2)))
        return 0

    lib._callback = callback_type(collect)
    lib.espeak_SetSynthCallback(lib._callback)
    path = str(espeakng_loader.get_data_path()).encode()
    if lib.espeak_Initialize(_AUDIO_OUTPUT_RETRIEVAL, 0, path, 0) <= 0:
        raise RuntimeError('espeak-ng could not start')
    _espeak = lib
    return lib


def speak(text, destination, voice=DEFAULT_VOICE, wpm=DEFAULT_WPM, pitch=DEFAULT_PITCH):
    """Render one line to a mono 22.05 kHz WAV and return its duration."""
    lib = _library()
    if lib.espeak_SetVoiceByName(voice.encode()) != 0:
        raise RuntimeError('espeak-ng has no voice %r' % voice)
    lib.espeak_SetParameter(1, int(wpm), 0)          # espeakRATE
    lib.espeak_SetParameter(2, int(pitch), 0)        # espeakPITCH
    lib.espeak_SetParameter(3, 120, 0)               # espeakRANGE, slightly wide
    lib.espeak_SetParameter(4, 0, 0)                 # no word gap
    global _buffer
    _buffer = bytearray()
    payload = text.encode('utf-8') + b'\0'
    pointer = ctypes.c_char_p(payload)
    lib.espeak_Synth(pointer, len(payload), 0, 1, 0, 0x01, None, None)   # 0x01 = UTF-8
    lib.espeak_Synchronize()
    samples = _buffer
    # eSpeak pads the tail with silence; trim it so lines can be placed exactly.
    usable = len(samples) // 2 * 2
    frames = memoryview(bytes(samples[:usable])).cast('h')
    end = len(frames)
    while end > 0 and abs(frames[end - 1]) < 180:
        end -= 1
    trimmed = bytes(frames[:end])
    with wave.open(str(destination), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(trimmed)
    return len(trimmed) / 2 / RATE


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def arrange(lines, destination, total):
    """Place ``(start, wav)`` lines on a silent canvas and return the WAV."""
    canvas = [0.0] * int(round(total * RATE))
    for start, path in lines:
        with wave.open(str(path), 'rb') as handle:
            raw = handle.readframes(handle.getnframes())
        frames = memoryview(raw).cast('h')
        offset = int(round(start * RATE))
        for index, sample in enumerate(frames):
            position = offset + index
            if 0 <= position < len(canvas):
                canvas[position] += sample / 32768.0
    peak = max((abs(value) for value in canvas), default=0.0) or 1.0
    scale = 0.89 / peak          # eSpeak's own output peaks around -14 dBFS
    with wave.open(str(destination), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v * scale)) * 32767))
                                    for v in canvas))
    return destination


def channel(source, destination, room=0.55, target_lufs=-16.0):
    """Run the raw take through the studio chain.

    The chain is deliberately gain-staged: the raw take is lifted to -3 dBFS so
    the saturation stage actually colours it, the chirpy 2-4 kHz band is pulled
    down, the chorus smears the formant edges, and the whole thing is finished
    with EBU-style loudness normalisation so it sits on top of the bed instead of
    under it.
    """
    chain = ','.join([
        'highpass=f=90',
        'lowpass=f=6500',
        'equalizer=f=180:t=q:w=1.1:g=2.2',
        'equalizer=f=420:t=q:w=1.2:g=-3.0',
        'equalizer=f=2600:t=q:w=1.4:g=-3.5',
        'equalizer=f=4800:t=q:w=1.6:g=-4.0',
        'volume=13dB',                       # gain-stage before saturation
        'asoftclip=type=tanh:threshold=0.85',
        'acompressor=threshold=-18dB:ratio=3:attack=6:release=160:makeup=2',
        'chorus=0.4:0.9:42|56:0.22|0.18:0.18|0.14:2|1.8',
        'aecho=0.86:0.5:26|41:%.2f|%.2f' % (0.10 * room, 0.06 * room),
        'aexciter=level_in=1:level_out=1:amount=1.2:drive=5:blend=0.28:freq=4200',
        'loudnorm=I=%.1f:TP=-1.5:LRA=9' % target_lufs,
        'alimiter=limit=0.94',
        'apad=whole_dur=%.3f' % kinetic_series.DURATION,
        'atrim=0:%.3f' % kinetic_series.DURATION,      # drop the reverb tail
        'aresample=44100',
    ])
    command = [_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
               '-i', str(source), '-af', chain, '-c:a', 'pcm_s16le', str(destination)]
    subprocess.run(command, check=True, timeout=300)
    return destination


def lines_for(episode_data):
    """The episode's narration as ``(start, text, wpm)`` cues.

    Each entry is a separate eSpeak call, placed on the timeline like a VO cue,
    so the read lands on the scene cuts instead of drifting from one long take.
    """
    cues = []
    for line in episode_data.get('voice_lines') or []:
        start, text = line[0], line[1]
        rate = line[2] if len(line) > 2 else DEFAULT_WPM
        cues.append((float(start), text, int(rate)))
    return cues


def take(episode_data, destination, voice=None, wpm=None, pitch=None, total=None):
    """Build the finished narration track for one episode.

    Returns ``{'path', 'seconds', 'engine', 'voice', 'lines'}``. Raises
    ``ValueError`` when the arranged read runs past the 19.90 s tail.
    """
    import tempfile
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = float(total or kinetic_series.DURATION)
    cues = lines_for(episode_data)
    if not cues:
        raise ValueError('episode has no voice_lines')
    with tempfile.TemporaryDirectory() as workdir:
        workdir = Path(workdir)
        placed = []
        spoken = []
        for index, (start, text, rate) in enumerate(cues):
            piece = workdir / ('line-%02d.wav' % index)
            seconds = speak(text, piece, voice or DEFAULT_VOICE,
                            int(wpm or rate),
                            int(pitch if pitch is not None else DEFAULT_PITCH))
            placed.append((start, piece))
            spoken.append({'start': round(start, 2), 'seconds': round(seconds, 2),
                           'text': text})
        stage = workdir / 'arranged.wav'
        arrange(placed, stage, total)
        channel(stage, destination)
    info = probe(destination)
    # The file is the full 20.60 s canvas, so the window is measured on the last
    # spoken cue, not on the padding.
    end_of_speech = max(line['start'] + line['seconds'] for line in spoken)
    if end_of_speech > MAX_SECONDS:
        raise ValueError('the read ends at %.2f s; the window closes at %.2f s'
                         % (end_of_speech, MAX_SECONDS))
    return {'path': destination, 'seconds': info['duration'],
            'speech_ends': round(end_of_speech, 2), 'engine': 'espeak-ng+dsp',
            'voice': voice or DEFAULT_VOICE, 'wpm': int(wpm or DEFAULT_WPM),
            'pitch': int(pitch if pitch is not None else DEFAULT_PITCH), 'lines': spoken}


def probe(path):
    """Duration and a cheap speech-band energy measure via ffprobe."""
    command = [_ffmpeg().replace('ffmpeg', 'ffprobe') if False else 'ffprobe',
               '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)]
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=120)
        return {'duration': float(json.loads(out.stdout)['format']['duration'])}
    except Exception:
        # imageio-ffmpeg ships no ffprobe; fall back to ffmpeg's own parse.
        out = subprocess.run([_ffmpeg(), '-hide_banner', '-i', str(path)],
                             capture_output=True, text=True, timeout=120)
        for line in out.stderr.splitlines():
            if 'Duration:' in line:
                stamp = line.split('Duration:')[1].split(',')[0].strip()
                hours, minutes, seconds = stamp.split(':')
                return {'duration': float(hours) * 3600 + float(minutes) * 60 + float(seconds)}
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=int, default=1)
    parser.add_argument('--out', default='/tmp/voice-01.wav')
    parser.add_argument('--voice', default=DEFAULT_VOICE)
    parser.add_argument('--wpm', type=int, default=DEFAULT_WPM)
    parser.add_argument('--pitch', type=int, default=DEFAULT_PITCH)
    arguments = parser.parse_args(argv)
    data = kinetic_series.episode(arguments.episode)
    info = take(data, arguments.out, arguments.voice, arguments.wpm, arguments.pitch)
    print(json.dumps(info, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
