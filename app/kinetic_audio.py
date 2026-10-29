"""Render an episode's ``audio_blueprint`` into the music bed and foley stem.

The blueprint in ``app/kinetic_series.py`` is the sound-design spec: 26 layers
with millisecond starts and a prompt per layer. Those prompts are what a sound
designer (or a paid SFX model) would render. Until that budget is approved,
this module synthesises a free, deterministic stand-in from the same timings, so
the picture and the sound plan stay in sync and a clip is never silent:

* every layer becomes a short procedural transient of its declared ``kind``
* layers are summed at their ``start_time`` with their ``gain_db``
* the 19.90 s lowpass tail closes the clip and fades to silence at 20.60 s

No samples on disk, no API call, no network: one pure-Python WAV writer.
"""
import math
import struct
import wave
from array import array

from app import kinetic_series

RATE = kinetic_series.SAMPLE_RATE
TWO_PI = 2.0 * math.pi


def _env(position, length, attack, release):
    """Trapezoid envelope in 0..1 over ``length`` samples."""
    index = position
    if index < attack:
        return index / max(1e-9, attack)
    remaining = length - index
    if remaining < release:
        return max(0.0, remaining / max(1e-9, release))
    return 1.0


def _decay(position, length, attack, tau):
    """Fast attack, exponential decay, exactly zero at the end of the layer."""
    if position < attack:
        return position / max(1e-9, attack)
    tail = math.exp(-(position - attack) / max(1e-9, tau))
    edge = 1.0 - position / max(1.0, length)
    return tail * edge


def _noise(state):
    """Deterministic LCG noise in -1..1 (no global random state)."""
    state = (1103515245 * state + 12345) & 0x7FFFFFFF
    return state / 1073741823.5 - 1.0, state


def _layer_samples(kind, length, rate, seed):
    """Yield ``length`` floats in -1..1 for one layer kind."""
    attack = max(1.0, rate * 0.004)
    state = seed | 1
    phase = 0.0
    low = 0.0
    band = 0.0
    for position in range(length):
        moment = position / rate
        span = length / rate
        value = 0.0
        if kind == 'hum':
            beat = 1.0 + 0.04 * math.sin(TWO_PI * 6.0 * moment)
            value = 0.55 * math.sin(TWO_PI * 42.0 * moment) * beat
            value += 0.06 * math.sin(TWO_PI * 84.0 * moment)
            value *= _env(position, length, rate * 0.12, rate * 0.25)
        elif kind == 'tick':
            sample, state = _noise(state)
            click = sample * math.exp(-moment / 0.0015)
            ping = 0.5 * math.sin(TWO_PI * 1800.0 * moment) * math.exp(-moment / 0.045)
            value = 0.8 * click + ping
        elif kind == 'sub':
            sweep = 90.0 - 35.0 * min(1.0, moment / 0.10)
            value = math.sin(TWO_PI * sweep * moment)
            value = math.tanh(1.8 * value) / math.tanh(1.8)
            value *= _decay(position, length, attack, rate * 0.10)
        elif kind == 'whoosh':
            sample, state = _noise(state)
            cutoff = 0.06 + 0.35 * min(1.0, moment / max(1e-6, span))
            low += cutoff * (sample - low)
            value = (low - band) * 2.4
            band += cutoff * 0.4 * (low - band)
            value *= _env(position, length, rate * 0.09, rate * 0.14)
        elif kind == 'shimmer':
            value = (0.34 * math.sin(TWO_PI * 1600.0 * moment + 0.8 * math.sin(TWO_PI * 7.0 * moment)) +
                     0.28 * math.sin(TWO_PI * 2400.0 * moment + 1.3 * math.sin(TWO_PI * 5.0 * moment)) +
                     0.22 * math.sin(TWO_PI * 3900.0 * moment))
            value *= _env(position, length, rate * 0.20, rate * 0.12)
        elif kind == 'glass':
            vibrato = 1.0 + 0.02 * math.sin(TWO_PI * 9.0 * moment)
            value = (0.55 * math.sin(TWO_PI * 3200.0 * moment * vibrato) +
                     0.30 * math.sin(TWO_PI * 900.0 * moment))
            value *= _decay(position, length, rate * 0.004, rate * 0.09)
        elif kind == 'heartbeat':
            value = math.sin(TWO_PI * 50.0 * moment)
            value *= _decay(position, length, rate * 0.012, rate * 0.09)
        elif kind == 'riser':
            sample, state = _noise(state)
            low += 0.08 * (sample - low)
            value = (sample - low) * 0.9
            value *= _env(position, length, rate * 0.30, rate * 0.10)
        elif kind == 'taiko':
            sample, state = _noise(state)
            value = 0.85 * math.sin(TWO_PI * 70.0 * moment) * math.exp(-moment / 0.16)
            value += 0.30 * sample * math.exp(-moment / 0.010)
            value += 0.22 * math.sin(TWO_PI * 200.0 * moment) * math.exp(-moment / 0.03)
            value *= min(1.0, (length - position) / max(1.0, rate * 0.02))
        elif kind == 'metal':
            value = (0.5 * math.sin(TWO_PI * 640.0 * moment) +
                     0.32 * math.sin(TWO_PI * 1900.0 * moment) +
                     0.18 * math.sin(TWO_PI * 2870.0 * moment))
            value *= _decay(position, length, rate * 0.003, rate * 0.12)
        elif kind == 'bloom':
            riser = min(1.0, moment / max(1e-6, span))
            value = 0.5 * math.sin(TWO_PI * 220.0 * moment) * riser
            value += 0.25 * math.sin(TWO_PI * 3000.0 * moment) * riser * riser
            value *= _env(position, length, rate * 0.12, rate * 0.25)
        elif kind == 'sheen':
            sample, state = _noise(state)
            band += 0.22 * (sample - band)
            value = (band - low) * 3.0
            low += 0.02 * (band - low)
            value *= _env(position, length, rate * 0.06, rate * 0.20)
        elif kind == 'chime':
            if moment < 0.22:
                value = math.sin(TWO_PI * 880.0 * moment) * _decay(position, length, attack, rate * 0.10)
            else:
                shifted = position - int(rate * 0.22)
                value = math.sin(TWO_PI * 1320.0 * moment)
                value *= _decay(shifted, max(1, length - int(rate * 0.22)), attack, rate * 0.14)
        elif kind == 'tail':
            sample, state = _noise(state)
            low += 0.055 * (sample - low)
            value = 0.9 * low * 3.0 + 0.25 * math.sin(TWO_PI * 60.0 * moment)
            value *= _env(position, length, rate * 0.08, length * 0.75)
        else:                                    # unknown kind: a soft click
            sample, state = _noise(state)
            value = sample * math.exp(-moment / 0.01)
        yield value


# ---------------------------------------------------------------------------
# the music bed: dark B2B deep house, 100 BPM in A minor, synthesised locally
# ---------------------------------------------------------------------------
def _music_samples(total, rate, bpm=100.0, level=0.115, seed=4242):
    """Yield ``total`` floats of bed: kick, sub-bass, hats, pad and vinyl floor.

    Deliberately cheap and deterministic. The pad is ducked on every kick so the
    narration stays on top, and the level stays well under the voice.
    """
    beat = 60.0 / bpm                        # 0.6 s
    bar = beat * 4
    two_pi = 2.0 * math.pi
    state = seed | 1
    low = band = 0.0
    root = 55.0                              # A1
    for position in range(total):
        moment = position / rate
        in_beat = moment % beat
        in_bar = moment % bar
        bar_index = int(moment / bar)
        value = 0.0

        # kick: 4-on-the-floor, 90 Hz dropping to 48 Hz, 280 ms
        if in_beat < 0.28:
            sweep = 48.0 + 42.0 * math.exp(-in_beat / 0.020)
            value += 0.85 * math.sin(two_pi * sweep * in_beat) * math.exp(-in_beat / 0.085)

        # sub-bass: root, gated 8th notes, ducked while the kick is sounding
        gate = (moment % (beat / 2)) < (beat / 2) * 0.82
        duck = 0.35 if in_beat < 0.16 else 1.0
        if gate:
            note = root if (int(moment / (beat / 2)) % 8) not in (3, 6) else root * 1.335
            value += 0.34 * duck * math.sin(two_pi * note * moment)

        # closed hat on the off-beats: filtered noise, 45 ms
        off = (moment + beat / 2) % beat
        if off < 0.045:
            sample, state = _noise(state)
            band += 0.35 * (sample - band)
            value += 0.10 * (sample - band) * math.exp(-off / 0.012)

        # warm pad: two detuned sines a fifth apart, 4-bar swell, kick-ducked
        swell = 0.55 + 0.45 * math.sin(two_pi * (bar_index % 4) / 8.0)
        pad = (0.055 * math.sin(two_pi * 220.0 * moment)
               + 0.045 * math.sin(two_pi * 329.6 * moment + 0.6)
               + 0.030 * math.sin(two_pi * 440.0 * moment + 1.4))
        value += pad * swell * duck * 0.9

        # vinyl floor: quiet brown noise so silence never sounds digital
        sample, state = _noise(state)
        low += 0.02 * (sample - low)
        value += 0.030 * low * 3.0

        yield value * level


def music_bed(destination, duration=None, blueprint=None, rate=RATE):
    """Write the music bed for one episode to a 16-bit WAV."""
    duration = float(duration or (blueprint or {}).get('duration') or
                     kinetic_series.DURATION)
    spec = (blueprint or {}).get('music') or kinetic_series.MUSIC
    total = int(round(duration * rate))
    fade_in, fade_out = 0.6, 0.9
    buffer = array('f', bytes(4 * total))
    for position, value in enumerate(_music_samples(total, rate,
                                                   bpm=float(spec.get('bpm', 100)))):
        envelope = 1.0
        if position < fade_in * rate:
            envelope = position / (fade_in * rate)
        tail = (duration - fade_out) * rate
        if position > tail:
            envelope *= max(0.0, 1.0 - (position - tail) / (fade_out * rate))
        buffer[position] = value * envelope
    _write_wav(destination, buffer, rate)
    return destination


def synthesize(blueprint, destination, rate=RATE, layer_scale=1.0):
    """Write ``blueprint`` to a mono 16-bit WAV of the full episode length."""
    duration = float(blueprint.get('duration') or kinetic_series.DURATION)
    total = int(round(duration * rate))
    buffer = array('f', bytes(4 * total))
    tail_layers = []
    for layer in blueprint.get('layers') or ():
        if layer.get('kind') == 'tail':
            tail_layers.append(layer)          # rendered last, over the mix
            continue
        _mix_layer(buffer, layer, rate, layer_scale)
    for layer in tail_layers:
        _mix_layer(buffer, layer, rate, layer_scale, source=buffer)
    peak = max((abs(value) for value in buffer), default=0.0)
    normalise = (1.0 / peak * 0.92) if peak > 0.92 else 1.0
    _write_wav(destination, buffer, rate, normalise)
    return destination


def _write_wav(destination, buffer, rate, normalise=1.0):
    with wave.open(str(destination), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for value in buffer:
            clipped = max(-1.0, min(1.0, value * normalise))
            frames += struct.pack('<h', int(clipped * 32767))
        handle.writeframes(bytes(frames))
    return destination


def _mix_layer(buffer, layer, rate, layer_scale, source=None):
    start = int(round(float(layer.get('start_time', 0.0)) * rate))
    length = max(1, int(round(float(layer.get('duration', 0.2)) * rate)))
    if start >= len(buffer) or start < 0:
        return
    length = min(length, len(buffer) - start)
    gain = layer_scale * (10.0 ** (float(layer.get('gain_db', -3.0)) / 20.0))
    seed = int(layer.get('index', 1)) * 7919 + 17
    if source is not None:
        # The tail rides on the mix that already exists: lowpass it further and
        # fade it out, so the clip closes instead of stopping.
        window = max(1, int(rate / 400.0))
        running = 0.0
        for position in range(length):
            running += source[start + position] - (running / window)
            fade = 1.0 - (position / max(1, length - 1)) ** 1.5
            buffer[start + position] += (running / window) * gain * 1.6 * fade
        return
    for position, value in enumerate(_layer_samples(layer.get('kind'), length, rate, seed)):
        buffer[start + position] += value * gain


def peak(path, rate=RATE):
    """Peak amplitude of a 16-bit mono/stereo WAV, used by the tests."""
    with wave.open(str(path), 'rb') as handle:
        raw = handle.readframes(handle.getnframes())
        width = handle.getsampwidth()
    if width != 2:
        return 0.0
    values = struct.unpack('<%dh' % (len(raw) // 2), raw)
    return (max(abs(value) for value in values) / 32768.0) if values else 0.0
