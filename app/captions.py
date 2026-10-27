"""Vertical-video captions: styled ASS subtitles burned in with ffmpeg.

The script is authored by us, so caption text is accurate by construction: it is
never transcribed from audio by a speech model. Timing is derived from the
script's own word count, spread across the exact clip duration.

Two output variants are produced for each approved idea:
  * ``caption`` — the words spoken/read on screen, one short phrase at a time
  * ``hook``    — the hook line as a larger top-of-frame overlay for the opening

ffmpeg comes from the ``imageio-ffmpeg`` wheel (a static build with libass), so a
worker needs no system packages. Verified in this repo's tests against a
synthetic clip: see tests/test_captions.py.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
MAX_CAPTION_CHARS = 26
MIN_LINE_SECONDS = 1.1
MAX_DURATION_SECONDS = 30
TIMEOUT = 600
# Vercel caps a serverless response body at 4.5 MB, and Buffer downloads the
# whole file from /media/<token>.mp4. A hard bitrate ceiling keeps a 15-second
# 1080x1920 clip under ~4.1 MB regardless of content complexity.
MAX_VIDEO_BITRATE = '2200k'
MAX_VIDEO_BUFFER = '4000k'

FONT_CANDIDATES = (
    ('DejaVu Sans', ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                     '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')),
)


class CaptionError(Exception):
    """A caption render failure that is safe to show to an operator."""


def ffmpeg_missing():
    try:
        _ffmpeg()
        return ''
    except CaptionError as error:
        return str(error)


def _ffmpeg():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise CaptionError('ffmpeg is not available on this worker. Install imageio-ffmpeg (see requirements-worker.txt).') from None


def font_name():
    """Pick an installed font by family name, defaulting to whatever libass has."""
    for name, paths in FONT_CANDIDATES:
        if any(Path(path).exists() for path in paths):
            return name
    return 'sans-serif'


def _ass_time(seconds):
    seconds = max(0.0, seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, rest = divmod(rest, 60)
    whole = int(rest)
    centis = int(round((rest - whole) * 100))
    if centis == 100:
        whole += 1
        centis = 0
    if whole == 60:
        minutes += 1
        whole = 0
    return '%d:%02d:%02d.%02d' % (hours, minutes, whole, centis)


def _escape(text):
    # ASS treats braces as override blocks and newlines as hard breaks.
    value = str(text).replace('\\', '').replace('{', '(').replace('}', ')')
    return re.sub(r'\s+', ' ', value).strip()


def phrases(text, max_chars=MAX_CAPTION_CHARS):
    """Split a script into short on-screen phrases, keeping each under max_chars."""
    text = re.sub(r'\s+', ' ', str(text)).strip()
    if not text:
        return []
    raw = re.split(r'(?<=[.!?;:])\s+', text)
    result = []
    for sentence in raw:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            result.append(sentence)
            continue
        words, current = sentence.split(' '), ''
        for word in words:
            candidate = (current + ' ' + word).strip()
            if current and len(candidate) > max_chars:
                result.append(current)
                current = word
            else:
                current = candidate
        if current:
            result.append(current)
    # Merge a dangling tail into the previous phrase so nothing flashes briefly.
    if len(result) > 1 and len(result[-1]) < 8:
        merged = (result[-2] + ' ' + result[-1]).strip()
        if len(merged) <= max_chars + 8:
            result[-2:] = [merged]
    return [item for item in result if item]


def _timeline(items, duration, minimum=MIN_LINE_SECONDS):
    """Distribute the duration across items proportional to their word count."""
    weights = [max(1, len(re.findall(r'\S+', item))) for item in items]
    total = float(sum(weights))
    spans = []
    elapsed = 0.0
    for index, weight in enumerate(weights):
        remaining = duration - elapsed
        left = sum(weights[index:])
        share = remaining * weight / left if left else remaining / (len(weights) - index)
        share = max(share, minimum) if len(items) <= int(duration / minimum) else share
        spans.append([elapsed, elapsed + share])
        elapsed += share
    spans[-1][1] = duration
    for index in range(len(spans) - 1):
        spans[index][1] = min(spans[index][1], spans[index + 1][0])
        if spans[index][1] - spans[index][0] < 0.35:
            spans[index][1] = spans[index][0] + 0.35
    return spans


def _header(width, height):
    font = font_name()
    style_main = ('Style: Caption,{font},68,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,'
                  '-1,0,0,0,100,100,0,0,1,6,3,2,90,90,{margin_v},1').format(
                      font=font, width=width, height=height, margin_v=int(height * 0.22))
    return (
        '[Script Info]\n'
        'ScriptType: v4.00+\n'
        'PlayResX: {w}\n'
        'PlayResY: {h}\n'
        'WrapStyle: 0\n'
        'ScaledBorderAndShadow: yes\n'
        'YCbCr Matrix: TV.709\n'
        '\n'
        '[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, '
        'Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, '
        'Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
        '{main}\n'
        'Style: Hook,{font},84,&H0000E8FF,&H000000FF,&H00000000,&H80000000,'
        '-1,0,0,0,100,100,0,0,1,8,4,8,80,80,{hook_v},1\n'
        '\n'
        '[Events]\n'
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    ).format(w=width, h=height, main=style_main, font=font, hook_v=int(height * 0.075))


def build_ass(script, duration_seconds, hook='', *, width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT):
    """Return an ASS subtitle document for one clip."""
    try:
        duration = float(duration_seconds)
    except (TypeError, ValueError):
        raise CaptionError('Invalid clip duration for captions.') from None
    if not 0 < duration <= MAX_DURATION_SECONDS:
        raise CaptionError('Clip duration is outside the supported caption range.')
    lines = phrases(script)
    if not lines:
        raise CaptionError('The script has no caption text.')
    spans = _timeline(lines, duration)
    events = []
    hook_text = _escape(hook)[:90]
    if hook_text:
        hook_end = min(duration, max(2.4, min(4.0, duration * 0.6)))
        # Long hooks wrap into four lines at 84px. Shrink, never re-flow past
        # the safe area measured on a rendered 1080x1920 frame.
        size = 84 if len(hook_text) <= 32 else 72 if len(hook_text) <= 48 else 62
        events.append('Dialogue: 1,{start},{end},Hook,,0,0,0,,{{\\fs{size}}}{text}\\N'.format(
            start=_ass_time(0), end=_ass_time(hook_end), text=hook_text.upper(), size=size))
    for line, (start, end) in zip(lines, spans):
        if end <= start:
            continue
        events.append('Dialogue: 0,{start},{end},Caption,,0,0,0,,{text}'.format(
            start=_ass_time(start), end=_ass_time(end), text=_escape(line)))
    return _header(width, height) + '\n'.join(events) + '\n'


def probe(path):
    """Return {'duration': float, 'has_audio': bool, 'width': int, 'height': int}."""
    executable = _ffmpeg()
    result = subprocess.run([executable, '-hide_banner', '-i', str(path)],
                            capture_output=True, text=True, timeout=120)
    text = (result.stderr or '') + (result.stdout or '')
    duration = 0.0
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', text)
    if match:
        duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    size = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', text)
    return {'duration': round(duration, 3), 'has_audio': 'Audio:' in text,
            'width': int(size.group(1)) if size else 0,
            'height': int(size.group(2)) if size else 0}


def render(source, destination, script, duration_seconds, hook='', *, crf=20, preset='veryfast'):
    """Burn captions into ``source``, writing a 1080x1920 MP4 to ``destination``.

    ``source`` may be a local path, or bytes (written to a scratch file).
    Returns probe metadata for the output.
    """
    executable = _ffmpeg()
    workdir = tempfile.mkdtemp(prefix='stratevo-captions-')
    try:
        if isinstance(source, (bytes, bytearray)):
            local = os.path.join(workdir, 'input.mp4')
            with open(local, 'wb') as handle:
                handle.write(source)
        else:
            local = str(source)
        if not os.path.exists(local):
            raise CaptionError('The source video could not be read for captions.')
        info = probe(local)
        duration = duration_seconds or info['duration']
        if not duration:
            raise CaptionError('The source video has no readable duration.')
        ass_path = os.path.join(workdir, 'captions.ass')
        with open(ass_path, 'w', encoding='utf-8') as handle:
            handle.write(build_ass(script, duration, hook))
        output = os.path.join(workdir, 'output.mp4')
        filters = ('scale={w}:{h}:force_original_aspect_ratio=decrease,'
                   'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,subtitles=captions.ass'
                   ).format(w=OUTPUT_WIDTH, h=OUTPUT_HEIGHT)
        command = [executable, '-y', '-hide_banner', '-loglevel', 'error', '-i', local]
        if info['has_audio']:
            command += ['-map', '0:v:0', '-map', '0:a:0', '-c:a', 'aac', '-b:a', '128k']
        else:
            command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                        '-map', '0:v:0', '-map', '1:a:0', '-shortest',
                        '-c:a', 'aac', '-b:a', '96k']
        command += ['-vf', filters, '-c:v', 'libx264', '-preset', preset, '-crf', str(crf),
                    '-maxrate', MAX_VIDEO_BITRATE, '-bufsize', MAX_VIDEO_BUFFER,
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-t', str(duration), output]
        try:
            result = subprocess.run(command, cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            raise CaptionError('Caption rendering timed out.') from None
        if result.returncode != 0 or not os.path.exists(output) or os.path.getsize(output) < 2048:
            detail = (result.stderr or '').strip().splitlines()
            message = detail[-1][:300] if detail else 'unknown ffmpeg failure'
            raise CaptionError('Caption rendering failed: ' + message)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(output, str(target))
        final = probe(target)
        final['bytes'] = target.stat().st_size
        return final
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
