"""Deterministic kinetic-typography renderer for the STRATEVO short-form series.

The reference videos this reproduces are *motion graphics*, not generated
footage: a black canvas, an ultra-heavy condensed face, neon bloom, a phone
mockup, brush-stroke defacement, and seven scenes in 19.7 seconds. Because every
frame is a function of the timeline, this module renders it in code — 1080x1920,
no model call, no per-video cost, byte-identical on every run.

Rendering is split in two so it fits a serverless function:

``segment()``  renders ``[start, end)`` seconds of frames and encodes one H.264
               segment. Scenes are pure functions of time, so any range can be
               rendered independently and stitched later.
``assemble()`` concatenates the segments in order and muxes the narration/SFX
               track, producing the final faststart MP4.

The design constants (palette, safe zone, type sizes, scene cuts) are at the top;
per-episode copy lives in ``app/kinetic_series.py``.
"""
import functools
import math
import os
import random
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app import captions

W, H = 1080, 1920
FPS = 30
DURATION = 20.60
# Encoder defaults shared by segment() and render():
#   aq-mode=3     variance AQ biased against stripping dark scenes
#   bframes=3     default, spelled out so a preset change cannot surprise us
ENCODE_X264 = 'aq-mode=3:bframes=3'
# Deliverable settings. Measured against a lossless FFV1 reference of a 3 s
# window (PSNR, average): CRF 20/veryfast = 38.69 dB, CRF 16/medium + aq-mode 3 =
# 38.88 dB, CRF 14/slow + aq-mode 3 = 38.89 dB at the same drawing cost. The
# remaining gap to the source is 4:2:0 chroma subsampling, which is kept because
# yuv420p is what every player and social platform accepts.
MASTER_CRF = 14
MASTER_PRESET = 'slow'
MASTER_AUDIO_BITRATE = '192k'
SAFE = (86, 168, W - 86, H - 240)          # central ~80 %, above platform chrome

BLACK = (0, 0, 0)
CHARCOAL = (13, 13, 13)
GRID = (23, 23, 23)
WHITE = (255, 255, 255)
MINT = (167, 243, 208)
EMERALD = (74, 222, 128)
CHROME_DARK = (38, 38, 38)
CHROME_MID = (82, 82, 82)
CHROME_LIGHT = (150, 150, 150)

FONT_DIR = Path(__file__).resolve().parent / 'assets' / 'fonts'
DISPLAY = 'Anton-Regular.ttf'
BODY = 'Inter-Black.ttf'

# Scene cuts, in seconds, from the client's storyboard.
CUTS = (0.0, 2.60, 6.70, 8.30, 9.90, 13.60, 16.50, DURATION)
SCENE_NAMES = ('hook', 'illusions', 'chat', 'wipe', 'questions', 'equation', 'signoff')

# The brand mark from web/favicon.svg, in its own 48x48 coordinate space.
LOGO_PATH = 'M32 2H13C3 2 0 11 8 16L22 24H5L1 31H21C32 31 35 22 26 16L13 9H28Z'
LOGO_ORIGIN = (7, 8)


class RenderError(Exception):
    """A render failure that is safe to show to an operator."""


# ---------------------------------------------------------------------------
# easing and small helpers
# ---------------------------------------------------------------------------
def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def ramp(t, start, end):
    """0 before ``start``, 1 after ``end``, linear between."""
    if end <= start:
        return 1.0 if t >= end else 0.0
    return clamp((t - start) / (end - start))


def ease_out(value):
    value = clamp(value)
    return 1 - (1 - value) ** 3


def ease_in(value):
    value = clamp(value)
    return value ** 3


def ease_back(value, overshoot=1.7):
    value = clamp(value)
    c3 = overshoot + 1
    return 1 + c3 * (value - 1) ** 3 + overshoot * (value - 1) ** 2


def pop(t, start, duration=0.34):
    """Scale factor for a pop-in element (slam + settle)."""
    if t < start:
        return 0.0
    return 0.72 + 0.28 * ease_back(ramp(t, start, start + duration))


# ---------------------------------------------------------------------------
# fonts and sprites
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=24)
def font(name, size):
    path = FONT_DIR / name
    if not path.exists():
        raise RenderError('Missing bundled font: ' + name)
    return ImageFont.truetype(str(path), int(size))


def measure(text, face):
    box = face.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def wrap(text, face, max_width):
    """Greedy word wrap using real glyph widths."""
    words, lines, current = text.split(), [], ''
    for word in words:
        candidate = (current + ' ' + word).strip()
        if measure(candidate, face)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fitted(text, size, colour=WHITE, face=DISPLAY, glow=0, width=None, tracking=0.0,
            minimum=56):
    """A text sprite scaled down until no line exceeds the safe area."""
    width = width or (SAFE[2] - SAFE[0])
    while size > minimum:
        typeface = font(face, size)
        lines = wrap(text, typeface, width)
        widest = max(typeface.getlength(line) for line in lines)
        if widest <= width:
            break
        size -= 4
    return text_sprite(text, size, colour, face, glow, width, tracking)


def tracked_width(line, typeface, tracking, size):
    """Width of a line once letter-spacing is applied (last glyph excluded)."""
    if not tracking or len(line) < 2:
        return typeface.getlength(line)
    return (typeface.getlength(line) + tracking * size * (len(line) - 1))


@functools.lru_cache(maxsize=256)
def text_sprite(text, size, colour=WHITE, face=DISPLAY, glow=0, width=SAFE[2] - SAFE[0],
                tracking=0.0):
    """Render one block of text, centred, with an optional pre-baked bloom.

    Cached because every frame reuses the same handful of words; only their
    position, scale and opacity change.
    """
    typeface = font(face, size)
    lines = wrap(text, typeface, width)
    pad = int(size * 0.55) + glow * 2
    line_height = int(size * 1.06)
    height = line_height * len(lines) + pad * 2
    canvas = Image.new('RGBA', (width + pad * 2, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        x = pad + (width - tracked_width(line, typeface, tracking, size)) / 2
        for char in line:
            draw.text((x, pad + index * line_height), char, font=typeface, fill=colour + (255,))
            x += typeface.getlength(char) + (tracking * size if tracking else 0.0)
    if glow:
        bloom = canvas.filter(ImageFilter.GaussianBlur(glow))
        # Two passes: a wide soft halo plus a tight hot edge.
        wide = bloom.filter(ImageFilter.GaussianBlur(glow * 1.6))
        canvas = Image.alpha_composite(wide, bloom)
        canvas = Image.alpha_composite(canvas, canvas)
        draw = ImageDraw.Draw(canvas)
        for index, line in enumerate(lines):
            x = pad + (width - tracked_width(line, typeface, tracking, size)) / 2
            for char in line:
                draw.text((x, pad + index * line_height), char, font=typeface, fill=colour + (255,))
                x += typeface.getlength(char) + (tracking * size if tracking else 0.0)
    return canvas


def paste(base, sprite, centre, scale=1.0, alpha=1.0):
    """Alpha-composite a sprite onto ``base`` (RGB) at a centre point."""
    if alpha <= 0.004 or scale <= 0.01:
        return
    layer = sprite
    if abs(scale - 1.0) > 0.004:
        width = max(1, int(layer.width * scale))
        height = max(1, int(layer.height * scale))
        layer = layer.resize((width, height), Image.LANCZOS)
    if alpha < 0.996:
        layer = layer.copy()
        channel = layer.getchannel('A').point(lambda value: int(value * alpha))
        layer.putalpha(channel)
    x = int(centre[0] - layer.width / 2)
    y = int(centre[1] - layer.height / 2)
    base.paste(layer, (x, y), layer)


# ---------------------------------------------------------------------------
# the brand mark (parsed from the same path the site uses)
# ---------------------------------------------------------------------------
def _flatten_path(path, samples=14):
    """Turn the simple M/L/H/V/C/Z path into a polygon. No library needed."""
    tokens = re.findall(r'([MLHVCZmlhvcz])|(-?\d*\.?\d+)', path)
    operations, points, current, start = [], [], (0.0, 0.0), (0.0, 0.0)
    index, buffer = 0, []
    sequence = [token for pair in tokens for token in pair if token]
    while index < len(sequence):
        item = sequence[index]
        if item.isalpha():
            command = item
            index += 1
            needed = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6}.get(command.upper(), 0)
            args = [float(value) for value in sequence[index:index + needed]]
            index += needed
            if command == 'M':
                current = (args[0], args[1])
                start = current
                points.append(current)
            elif command == 'L':
                current = (args[0], args[1])
                points.append(current)
            elif command == 'H':
                current = (args[0], current[1])
                points.append(current)
            elif command == 'V':
                current = (current[0], args[0])
                points.append(current)
            elif command == 'C':
                p0 = current
                p1, p2, p3 = (args[0], args[1]), (args[2], args[3]), (args[4], args[5])
                for step in range(1, samples + 1):
                    s = step / samples
                    x = ((1 - s) ** 3 * p0[0] + 3 * (1 - s) ** 2 * s * p1[0]
                         + 3 * (1 - s) * s ** 2 * p2[0] + s ** 3 * p3[0])
                    y = ((1 - s) ** 3 * p0[1] + 3 * (1 - s) ** 2 * s * p1[1]
                         + 3 * (1 - s) * s ** 2 * p2[1] + s ** 3 * p3[1])
                    points.append((x, y))
                current = p3
            elif command in 'Zz':
                points.append(start)
                current = start
        else:
            index += 1
    return points


@functools.lru_cache(maxsize=8)
def logo_mask(size, supersample=4):
    """Anti-aliased alpha mask of the S ribbon at ``size`` pixels wide."""
    points = _flatten_path(LOGO_PATH)
    scale = size * supersample / 48.0
    polygon = [((x + LOGO_ORIGIN[0] - 6) * scale, (y + LOGO_ORIGIN[1] - 6) * scale) for x, y in points]
    canvas = Image.new('L', (size * supersample, size * supersample), 0)
    ImageDraw.Draw(canvas).polygon(polygon, fill=255)
    return canvas.resize((size, size), Image.LANCZOS)


def metallic_logo(size):
    """Chrome-gradient S mark with a vertical bevel, as a RGBA sprite."""
    mask = logo_mask(size)
    gradient = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    pixels = gradient.load()
    for y in range(size):
        position = y / max(1, size - 1)
        if position < 0.45:
            value = CHROME_DARK[0] + (CHROME_LIGHT[0] - CHROME_DARK[0]) * (position / 0.45)
        else:
            value = CHROME_LIGHT[0] + (CHROME_MID[0] - CHROME_LIGHT[0]) * ((position - 0.45) / 0.55)
        for x in range(size):
            pixels[x, y] = (int(value), int(value), int(value), 255)
    gradient.putalpha(mask)
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.2))
    highlight = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    highlight.putalpha(edge.point(lambda value: int(value * 1.6)))
    return Image.alpha_composite(gradient, highlight)


@functools.lru_cache(maxsize=4)
def not_equal_sprite(width=300, bar=44, gap=74, glow=18):
    """The "\u2260" mark, drawn by hand: no latin subset ships the glyph."""
    canvas_w = int(width * 1.5)
    canvas_h = bar * 2 + gap + int(bar * 2.6)
    pad_x = (canvas_w - width) // 2
    top = int(bar * 1.4)
    art = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(art)
    for offset in (top, top + bar + gap):
        draw.rounded_rectangle([pad_x, offset, pad_x + width, offset + bar],
                               radius=bar // 2, fill=EMERALD + (255,))
    # Slash drawn edge to edge so it reads as a strike-through, not a dash.
    slash = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(slash)
    sdraw.line([(pad_x - width * 0.05, top + bar * 2 + gap + bar * 0.55),
                (pad_x + width * 1.05, top - bar * 0.55)],
               fill=(255, 255, 255, 255), width=int(bar * 0.58))
    art = Image.alpha_composite(art, slash)
    halo = art.filter(ImageFilter.GaussianBlur(glow))
    canvas = Image.alpha_composite(halo, halo)
    return Image.alpha_composite(canvas, art)


# ---------------------------------------------------------------------------
# background furniture
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=4)
def background():
    """Black canvas, faint engineering grid, crosshairs and a vignette."""
    canvas = Image.new('RGB', (W, H), BLACK)
    draw = ImageDraw.Draw(canvas)
    step = 90
    for x in range(0, W + 1, step):
        draw.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H + 1, step):
        draw.line([(0, y), (W, y)], fill=GRID, width=1)
    for x in range(step, W, step * 2):
        for y in range(step, H, step * 2):
            draw.line([(x - 12, y), (x + 12, y)], fill=(52, 52, 52), width=1)
            draw.line([(x, y - 12), (x, y + 12)], fill=(52, 52, 52), width=1)
    # Vignette: darken the edges so the type reads at full contrast.
    vignette = Image.new('L', (W, H), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse([-int(W * 0.45), -int(H * 0.25), int(W * 1.45), int(H * 1.25)], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(180))
    dark = Image.new('RGB', (W, H), BLACK)
    return Image.composite(canvas, dark, vignette)


@functools.lru_cache(maxsize=4)
def watermark():
    """The persistent bottom-left S ribbon."""
    mark = metallic_logo(46)
    sprite = Image.new('RGBA', (70, 70), (0, 0, 0, 0))
    sprite.paste(mark, (10, 12), mark)
    channel = sprite.getchannel('A').point(lambda value: int(value * 0.55))
    sprite.putalpha(channel)
    return sprite


def draw_watermark(canvas):
    canvas.paste(watermark(), (46, H - 132), watermark())


@functools.lru_cache(maxsize=2)
def sunburst(size=1400):
    """Radial line burst used behind the question stack."""
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    centre = size / 2
    for index in range(56):
        angle = index * (360 / 56)
        length = size * (0.5 if index % 2 == 0 else 0.34)
        radians = math.radians(angle)
        draw.line([(centre, centre),
                   (centre + math.cos(radians) * length, centre + math.sin(radians) * length)],
                  fill=(255, 255, 255, 26 if index % 2 == 0 else 14), width=3)
    return canvas.filter(ImageFilter.GaussianBlur(1.2))


# ---------------------------------------------------------------------------
# scene props
# ---------------------------------------------------------------------------
def bokeh_screen(width, height, seed=7):
    """Procedural night-city bokeh for the phone screen (no stock footage)."""
    rng = random.Random(seed)
    screen = Image.new('RGB', (width, height), (8, 9, 12))
    draw = ImageDraw.Draw(screen)
    for _ in range(70):
        x = rng.randint(0, width)
        y = rng.randint(int(height * 0.15), height)
        radius = rng.randint(3, 14)
        warmth = rng.choice([(255, 196, 120), (255, 226, 170), (150, 200, 255), (255, 150, 90)])
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=warmth)
    screen = screen.filter(ImageFilter.GaussianBlur(9))
    draw = ImageDraw.Draw(screen)
    draw.rectangle([0, 0, width, int(height * 0.16)], fill=(0, 0, 0))
    return screen


def phone_frame(width, height, glow=26, bezel=14, glass=False):
    """Phone body with a lit edge, soft halo, and an optional glass tint.

    ``bezel`` is the dark band between the edge and the screen, so the mockup
    reads as a device instead of a picture in a rounded box.
    """
    pad = glow * 3
    sprite = Image.new('RGBA', (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sprite)
    box = [pad, pad, pad + width, pad + height]
    draw.rounded_rectangle(box, radius=64, fill=(10, 11, 13, 255))
    inner = [box[0] + bezel, box[1] + bezel, box[2] - bezel, box[3] - bezel]
    draw.rounded_rectangle(inner, radius=52, fill=(0, 0, 0, 0))
    # Interior mask + hole for the screen so the bezel frames the content.
    mask = Image.new('L', sprite.size, 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle(box, radius=64, fill=255)
    for offset, alpha in ((4, 28), (2, 64)):
        draw.rounded_rectangle([box[0] - offset, box[1] - offset, box[2] + offset, box[3] + offset],
                               radius=64 + offset, outline=(255, 255, 255, alpha), width=2)
    draw.rounded_rectangle(box, radius=64, outline=(255, 255, 255, 255), width=5)
    if glass:
        sheen = Image.new('RGBA', sprite.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(sheen)
        sdraw.polygon([(pad + width * 0.12, pad), (pad + width * 0.55, pad),
                       (pad + width * 0.15, pad + height), (pad + width * 0.02, pad + height)],
                      fill=(255, 255, 255, 18))
        mask_big = Image.new('L', sprite.size, 0)
        ImageDraw.Draw(mask_big).rounded_rectangle(box, radius=64, fill=255)
        sheen.putalpha(ImageChops.multiply(sheen.getchannel('A'), mask_big))
        sprite = Image.alpha_composite(sprite, sheen)
    return sprite


def brush_stroke(points, width, seed=3, colour=(255, 255, 255)):
    """A tapered, textured paint stroke through ``points``.

    Built as a filled polygon along the path (so it reads as one drag of a
    roller) plus a few dry-brush streaks *inside* the stroke, never as loose
    dots across the frame.
    """
    rng = random.Random(seed)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    # Dense resample of the path.
    path = []
    for index in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[index], points[index + 1]
        for step in range(60):
            s = step / 60
            path.append((x1 + (x2 - x1) * s, y1 + (y2 - y1) * s))
    path.append(points[-1])
    total = len(path) - 1
    left, right = [], []
    for index, (x, y) in enumerate(path):
        s = index / max(1, total)
        taper = math.sin(math.pi * clamp(s * 0.94 + 0.03)) ** 0.35
        half = width * 0.5 * taper * rng.uniform(0.94, 1.06)
        nx, ny = (path[min(index + 1, total)][1] - path[max(index - 1, 0)][1],
                  path[max(index - 1, 0)][0] - path[min(index + 1, total)][0])
        length = math.hypot(nx, ny) or 1.0
        nx, ny = nx / length, ny / length
        left.append((x + nx * half, y + ny * half))
        right.append((x - nx * half, y - ny * half))
    polygon = left + right[::-1]
    draw.polygon(polygon, fill=colour + (255,))
    # Dry-brush streaks: thin lines clipped to the stroke's own bounding box.
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    box = (int(min(xs)) - 4, int(min(ys)) - 4, int(max(xs)) + 4, int(max(ys)) + 4)
    streaks = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(streaks)
    for _ in range(70):
        x = rng.uniform(box[0], box[2])
        y = rng.uniform(box[1], box[3])
        angle = math.atan2(points[-1][1] - points[0][1], points[-1][0] - points[0][0])
        length = rng.uniform(40, 160)
        sdraw.line([(x, y), (x + math.cos(angle) * length, y + math.sin(angle) * length)],
                   fill=colour + (rng.randint(40, 110),), width=rng.randint(1, 4))
    streaks.putalpha(ImageChops.multiply(streaks.getchannel('A'), layer.getchannel('A')))
    layer = Image.alpha_composite(layer, streaks)
    return layer.filter(ImageFilter.GaussianBlur(0.8))


def truncated_stroke(layer, progress):
    """Reveal a brush stroke from its top-left end."""
    if progress >= 1.0:
        return layer
    mask = Image.new('L', (W, H), 0)
    draw = ImageDraw.Draw(mask)
    # Diagonal wipe roughly along the stroke direction.
    edge = -W * 0.4 + progress * (W * 1.9)
    draw.polygon([(0, 0), (edge, 0), (edge - H * 0.55, H), (0, H)], fill=255)
    result = layer.copy()
    result.putalpha(ImageChops.multiply(layer.getchannel('A'), mask))
    return result


def panel(canvas, box, alpha=1.0, fill=(17, 17, 17), outline=(58, 58, 58), radius=30):
    """A rounded dark card, the base chrome for layouts A, B and C."""
    if alpha <= 0.01:
        return
    x, y, width, height = box
    layer = Image.new('RGBA', (int(width), int(height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius,
                           fill=fill + (int(250 * alpha),),
                           outline=outline + (int(255 * alpha),), width=2)
    canvas.paste(layer, (int(x), int(y)), layer)


def chat_card(width, height):
    sprite = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sprite)
    draw.rounded_rectangle([0, 0, width, height], radius=58, fill=(16, 17, 20, 255),
                           outline=(255, 255, 255, 120), width=3)
    return sprite


# ---------------------------------------------------------------------------
# the frame renderer
# ---------------------------------------------------------------------------
class Episode:
    """Everything that can be pre-rendered once for one episode."""

    def __init__(self, data, index=1, cta='stratevo.online', brand='STRATEVO'):
        self.data = data
        self.index = index
        self.cta = cta
        self.brand = brand
        self.hook = data['hook']
        self.questions = data['questions']
        self.left = data['left']
        self.right = data['right']
        self.illusions = data['illusions']
        # Layout drives what scenes 1-3 actually draw: A audit showcase, B cost,
        # C founder story, D the contrarian card/glass layout.
        self.layout = (data.get('layout') or 'D').upper()
        self.scenes = data.get('scenes') or {}
        self.flash = list(data.get('flash') or FLASH_WORDS)
        # Optional per-episode labels, so a tile says what the episode is about
        # while the master keeps the reference's wording.
        self.tile_title = (data.get('tile_title') or data['illusions'][0]).upper()
        self.chat_heading = (data.get('chat_heading') or data['illusions'][2]).upper()
        self.equation_top = data.get('left') or ''
        self._wipe_base = None

    # -- scene 1 (layout D): hook + defacement -----------------------------
    def _scene_hook_d(self, canvas, t):
        phone_w, phone_h = 470, 950
        centre = (W / 2, 760)
        enter = ease_out(ramp(t, 0.0, 0.42))
        scale = 0.86 + 0.14 * enter
        alpha = 1.0

        bezel = 16
        screen_w, screen_h = phone_w - bezel * 2, phone_h - bezel * 2
        # Screen content: night-city bokeh, status bar, the episode's own header
        # and button. Nothing here is hardcoded: layout D reads its device copy
        # from episode_data.scenes.one.
        one = self.scenes.get('one') or {}
        screen = Image.new('RGB', (screen_w, screen_h))
        screen.paste(bokeh_screen(screen_w, screen_h, seed=9 + self.index), (0, 0))
        sdraw = ImageDraw.Draw(screen)
        sdraw.ellipse([screen_w / 2 - 52, 14, screen_w / 2 + 52, 46], fill=(0, 0, 0))
        clock = text_sprite('9:41', 30, (235, 235, 235), BODY, 0, 120)
        screen.paste(clock, (34, 22), clock)
        for column in range(4):
            bar_h = 8 + column * 5
            sdraw.rectangle([screen_w - 96 + column * 11, 44 - bar_h,
                             screen_w - 90 + column * 11, 44], fill=(235, 235, 235))
        sdraw.rounded_rectangle([screen_w - 42, 28, screen_w - 18, 44], radius=6,
                                outline=(200, 200, 200), width=2)
        sdraw.rectangle([screen_w - 40, 31, screen_w - 26, 41], fill=(235, 235, 235))

        title = text_sprite((one.get('device') or 'PROFILE').upper(), 66, WHITE,
                            DISPLAY, 10, screen_w - 80)
        header_scrim = Image.new('RGBA', (screen_w, 190), (0, 0, 0, 0))
        hgrad = header_scrim.load()
        for y in range(190):
            hgrad_row = int(180 * (1 - y / 190))
            for x in range(screen_w):
                hgrad[x, y] = (0, 0, 0, hgrad_row)
        screen.paste(header_scrim, (0, 60), header_scrim)
        screen.paste(title, (int((screen_w - title.width) / 2), 96), title)

        pill = Image.new('RGBA', (250, 78), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle([0, 0, 250, 78], radius=39,
                                               fill=(255, 255, 255, 240))
        pill_text = text_sprite((one.get('button') or 'SUBSCRIBE').upper(), 32,
                                (8, 8, 8), BODY, 0, 230)
        pill.paste(pill_text, (int((250 - pill_text.width) / 2),
                               int((78 - pill_text.height) / 2)), pill_text)
        screen.paste(pill, (int((screen_w - 250) / 2), screen_h - 150), pill)

        # A hint of a feed under the header, so the screen isn't just bokeh.
        for row in range(2):
            top = 300 + row * 210
            card = Image.new('RGBA', (screen_w - 60, 180), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, screen_w - 60, 180], radius=24,
                                                    fill=(255, 255, 255, 12))
            screen.paste(card, (30, top), card)

        if t >= 1.0:
            # Defacement: blur and green-tint the screen behind the brush X.
            amount = ramp(t, 1.0, 1.35)
            screen = screen.filter(ImageFilter.GaussianBlur(10 * amount))
            tint = Image.new('RGB', screen.size, (6, 40, 24))
            screen = Image.blend(screen, tint, 0.5 * amount)

        frame = phone_frame(phone_w, phone_h, glass=True)
        pad = 26 * 3
        phone_layer = Image.new('RGBA', (phone_w + pad * 2, phone_h + pad * 2), (0, 0, 0, 0))
        phone_layer.paste(screen.convert('RGBA'), (pad + bezel, pad + bezel))
        phone_layer.alpha_composite(frame, (0, 0))
        if abs(scale - 1.0) > 0.004 or alpha < 0.996:
            width = int(phone_layer.width * scale)
            height = int(phone_layer.height * scale)
            phone_layer = phone_layer.resize((width, height), Image.LANCZOS)
        canvas.paste(phone_layer, (int(centre[0] - phone_layer.width / 2),
                                   int(centre[1] - phone_layer.height / 2)), phone_layer)

        # Brush X over the phone, then the hook type slam.
        if t >= 1.0:
            progress = ease_out(ramp(t, 1.0, 1.42))
            layer = brush_stroke([(W * 0.18, 300), (W * 0.82, 1080)], 46, seed=11)
            layer2 = brush_stroke([(W * 0.82, 300), (W * 0.18, 1080)], 46, seed=12)
            combined = Image.alpha_composite(layer, layer2)
            canvas.paste(truncated_stroke(combined, progress), (0, 0), truncated_stroke(combined, progress))

        if t >= 1.35:
            # Bottom scrim: keeps the type legible without dimming the X.
            scrim = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gradient = scrim.load()
            for y in range(int(H * 0.52), H):
                weight = min(1.0, (y - H * 0.52) / (H * 0.18))
                for x in range(W):
                    gradient[x, y] = (0, 0, 0, int(238 * weight))
            canvas.paste(scrim, (0, 0), scrim)
            size = 108 if len(self.hook) < 62 else 94
            head = fitted(self.hook, size, EMERALD, DISPLAY, 18, SAFE[2] - SAFE[0])
            paste(canvas, head, (W / 2, 1425), scale=pop(t, 1.35), alpha=ramp(t, 1.35, 1.5))

    # -- scene 2 (layout D): filmstrip -> ring -----------------------------
    def _scene_illusions_d(self, t):
        local = t - CUTS[1]
        canvas = background().copy()
        morph = ease_out(ramp(local, 1.6, 2.55))
        centre = (W / 2, 1120)
        radius = 392
        spin = 0.35 * max(0.0, local - 2.0)
        cards = []
        gap = 38
        strip_width = 3 * 300 + 2 * gap
        two = self.scenes.get('two') or {}
        cards_copy = two.get('cards') or self.illusions[:3]
        for index, label in enumerate(cards_copy[:3]):
            card_w, card_h = 246, 336
            sprite = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(sprite)
            draw.rounded_rectangle([0, 0, card_w, card_h], radius=26, fill=(18, 18, 18, 255),
                                   outline=(62, 62, 62, 255), width=2)
            draw.rounded_rectangle([14, 14, card_w - 14, 82], radius=16, fill=(26, 26, 26, 255))
            number = text_sprite('%02d' % (index + 1), 40, MINT, DISPLAY, 0, 200)
            sprite.paste(number, (int((card_w - number.width) / 2), 26), number)
            label_sprite = text_sprite(label.upper(), 32, WHITE, BODY, 0, card_w - 26)
            sprite.paste(label_sprite, (int((card_w - label_sprite.width) / 2),
                                        int(card_h * 0.58)), label_sprite)
            appear = pop(local, 0.12 + index * 0.16)
            # Strips: horizontal row; ring: evenly spaced around the centre.
            strip_x = W / 2 - strip_width / 2 + card_w / 2 + index * (card_w + gap)
            strip_y = centre[1]
            angle = spin + index * (2 * math.pi / 3) - math.pi / 2
            ring_x = centre[0] + math.cos(angle) * radius
            ring_y = centre[1] + math.sin(angle) * radius * 0.78
            x = strip_x + (ring_x - strip_x) * morph
            y = strip_y + (ring_y - strip_y) * morph
            depth = 1.0 - 0.16 * morph * (0.5 + 0.5 * math.sin(angle))
            cards.append((index, sprite, (x, y), appear, depth))
        for index, sprite, position, appear, depth in cards:
            paste(canvas, sprite, position, scale=pop(local, 0.12 + index * 0.16),
                  alpha=min(1.0, appear * 1.4) * depth)

        first_title = (two.get('title') or self.tile_title or 'GREAT PHOTOS').upper()
        second_title = (self.scenes.get('two') or {}).get('turn') or 'LOOKS CREDIBLE'
        title = text_sprite(first_title if local < 2.7 else second_title.upper(), 96, WHITE,
                            DISPLAY, 10, 900)
        paste(canvas, title, (W / 2, 470), scale=pop(local, 0.05), alpha=ramp(local, 0.05, 0.2))
        if local > 2.6:
            caption = text_sprite(self.equation_top, 132, EMERALD, DISPLAY, 22, 900)
            paste(canvas, caption, (centre[0], centre[1]), scale=pop(local, 2.6, 0.35),
                  alpha=ramp(local, 2.6, 2.9))
        return canvas

    # -- scene 3 (layout D): chat card -------------------------------------
    def _scene_chat_d(self, t):
        local = t - CUTS[2]
        canvas = background().copy()
        stroke = brush_stroke([(W * 0.05, 1180), (W * 0.95, 900)], 90, seed=21,
                              colour=(235, 235, 235))
        canvas.paste(stroke, (0, 0), stroke)
        three = self.scenes.get('three') or {}

        heading = text_sprite((three.get('heading') or self.chat_heading).upper(), 104,
                              WHITE, DISPLAY, 14, 900)
        paste(canvas, heading, (W / 2, 300), scale=pop(local, 0.0), alpha=ramp(local, 0.0, 0.12))

        card_w, card_h = 520, 780
        card = chat_card(card_w, card_h)
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle([20, 20, card_w - 20, 92], radius=22, fill=(28, 29, 33, 255))
        draw.ellipse([card_w / 2 - 26, 34, card_w / 2 + 26, 86], fill=(58, 60, 66, 255))
        avatar = text_sprite('SUPPLIER', 30, (200, 200, 200), BODY, 0, 300)
        card.paste(avatar, (int((card_w - avatar.width) / 2), 54), avatar)

        bubbles = three.get('messages') or self.illusions[:3]
        y = 150
        for index, text in enumerate(bubbles):
            appear = ramp(local, 0.25 + index * 0.42, 0.4 + index * 0.42)
            if appear <= 0:
                continue
            incoming = index % 2 == 0
            bubble = text_sprite(text.upper(), 28, WHITE, BODY, 0, 330)
            bw, bh = bubble.width + 46, bubble.height + 34
            shape = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(shape).rounded_rectangle(
                [0, 0, bw, bh], radius=26,
                fill=(38, 39, 44, 255) if incoming else (30, 88, 210, 255))
            shape.paste(bubble, (23, 17), bubble)
            x = 26 if incoming else card_w - bw - 26
            height_scale = 0.6 + 0.4 * ease_back(appear)
            scaled = shape.resize((bw, max(1, int(bh * height_scale))), Image.LANCZOS)
            card.paste(scaled, (x, y), scaled)
            y += bh + 22
        typing = text_sprite('...', 44, (150, 150, 150), BODY, 0, 200)
        if local > 1.05:
            card.paste(typing, (46, min(y, card_h - 90)), typing)
        scale = 0.94 + 0.06 * ease_out(ramp(local, 0.0, 0.3))
        layer = card.resize((int(card_w * scale), int(card_h * scale)), Image.LANCZOS)
        canvas.paste(layer, (int((W - layer.width) / 2), 470), layer)
        return canvas

    # -- scene 4: refraction flash ----------------------------------------
    def scene_wipe(self, t, base):
        """Huge full-frame words on black, warped by a sweeping flute of glass."""
        local = t - CUTS[3]
        canvas = Image.new('RGB', (W, H), BLACK)
        # The trapped chat stays as a faint ghost so the cut doesn't feel empty.
        ghost = base.filter(ImageFilter.GaussianBlur(16))
        canvas = Image.blend(canvas, ghost, 0.16)

        words = tuple(self.flash)
        span = (CUTS[4] - CUTS[3]) / len(words)
        index = min(len(words) - 1, int(local / span))
        into = local - index * span
        size = 186 if len(words[index]) < 8 else 156
        word = text_sprite(words[index], size, WHITE, DISPLAY, 22, 990)
        paste(canvas, word, (W / 2, H / 2),
              scale=0.94 + 0.06 * ease_back(ramp(into, 0.0, 0.16)), alpha=1.0)

        # Fluted glass: vertical prisms that displace what's behind them.
        travel = ((local * 1.45) % 1.25) - 0.12
        if -0.12 < travel < 1.0:
            band_w = 300
            left = int(travel * (W + band_w)) - band_w
            x0, x1 = max(0, left), min(W, left + band_w)
            if x1 - x0 > 16:
                source = canvas.crop((x0, 0, x1, H))
                shifted = Image.new('RGB', source.size, BLACK)
                flute = 30
                for column in range(0, source.width, flute):
                    strip = source.crop((column, 0, min(source.width, column + flute), H))
                    if strip.width < 1:
                        continue
                    offset = int(math.sin((column / flute) * math.pi * 0.5) * 7)
                    target = max(0, column + offset)
                    if target < 0:
                        strip = strip.crop((-target, 0, strip.width, strip.height))
                        target = 0
                    room = shifted.width - target
                    if strip.width > room:
                        strip = strip.crop((0, 0, max(0, room), strip.height))
                    if strip.width > 0 and room > 0:
                        shifted.paste(strip, (target, 0))
                # The prisms lift and cool whatever they cover, like real glass.
                glass = ImageEnhance.Brightness(shifted).enhance(1.5)
                glass = ImageEnhance.Contrast(glass).enhance(1.1)
                glass = glass.filter(ImageFilter.GaussianBlur(1.6))
                glass = Image.blend(glass, Image.new('RGB', glass.size, (228, 244, 235)), 0.05)
                highlights = Image.new('RGBA', glass.size, (0, 0, 0, 0))
                hdraw = ImageDraw.Draw(highlights)
                for column in range(0, glass.width, flute):
                    hdraw.line([(column, 0), (column, glass.height)],
                               fill=(255, 255, 255, 40), width=3)
                    hdraw.line([(column + 4, 0), (column + 4, glass.height)],
                               fill=(255, 255, 255, 20), width=2)
                glass = glass.convert('RGBA')
                glass.alpha_composite(highlights)
                # Feathered left/right edges so the band doesn't look pasted on.
                mask = Image.new('L', glass.size, 255)
                mdraw = ImageDraw.Draw(mask)
                for column in range(min(60, glass.width)):
                    value = int(255 * column / 60)
                    mdraw.line([(column, 0), (column, glass.height)], fill=value)
                    mdraw.line([(glass.width - 1 - column, 0),
                                (glass.width - 1 - column, glass.height)], fill=value)
                canvas.paste(glass.convert('RGB'), (x0, 0), mask)

        # One white frame per word change: the "flash" that sells the cut.
        flash = max(0.0, 0.22 - into * 4.2)
        if flash > 0:
            canvas = Image.blend(canvas, Image.new('RGB', (W, H), (255, 255, 255)), flash)
        return canvas

    # -- scene 5: the three questions -------------------------------------
    def scene_questions(self, t):
        local = t - CUTS[4]
        canvas = background().copy()
        burst = sunburst().rotate(local * 6, resample=Image.BILINEAR)
        burst = ImageEnhance.Brightness(burst.convert('RGB')).enhance(0.55).convert('RGBA')
        burst.putalpha(burst.getchannel('A'))
        canvas.paste(burst, (int(W / 2 - burst.width / 2), int(H / 2 - burst.height / 2)), burst)

        span = (CUTS[5] - CUTS[4]) / 3
        for index, question in enumerate(self.questions[:3]):
            start = index * span
            if local < start:
                continue
            sprite = fitted(question, 104, WHITE, DISPLAY, 16, SAFE[2] - SAFE[0], minimum=60)
            alpha = ramp(local, start, start + 0.16)
            # Only the last question stays until the cut; the others clear fully,
            # so two questions never read on top of each other.
            if index < len(self.questions[:3]) - 1:
                alpha *= 1.0 - ramp(local, start + span * 0.8, start + span * 0.97)
            paste(canvas, sprite, (W / 2, H / 2), scale=pop(local, start, 0.26), alpha=alpha)
        return canvas

    # -- scene 6: the equation --------------------------------------------
    def scene_equation(self, t):
        local = t - CUTS[5]
        canvas = background().copy()
        burst = sunburst().rotate(local * 4, resample=Image.BILINEAR)
        haze = burst.copy()
        haze.putalpha(haze.getchannel('A').point(lambda value: int(value * 0.55)))
        canvas.paste(haze, (int(W / 2 - haze.width / 2), int(H / 2 - haze.height / 2)), haze)
        left = fitted(self.left, 168, WHITE, DISPLAY, 14, 940, minimum=88)
        factor = not_equal_sprite(330)
        right = fitted(self.right, 168, WHITE, DISPLAY, 14, 940, minimum=88)
        rows = ((left, 0.0, 560), (factor, 0.85, H / 2), (right, 1.7, 1360))
        for sprite, start, y in rows:
            if local < start:
                continue
            paste(canvas, sprite, (W / 2, y), scale=pop(local, start, 0.3),
                  alpha=ramp(local, start, start + 0.14))
        return canvas

    # -- scene 7: sign-off -------------------------------------------------
    def scene_signoff(self, t):
        local = t - CUTS[6]
        canvas = Image.new('RGB', (W, H), BLACK)
        fade_in = ease_out(ramp(local, 0.0, 0.5))
        fade_out = 1.0 - ramp(local, 3.52, CUTS[7] - CUTS[6] - 0.02)
        mark = metallic_logo(360)
        scale = 0.82 + 0.18 * fade_in
        # Specular sweep across the chrome bevels.
        sweep_x = -1.0 + 2.4 * ramp(local, 0.55, 1.9)
        lit = mark.copy()
        band = Image.new('L', mark.size, 0)
        ImageDraw.Draw(band).polygon(
            [(sweep_x * mark.width - 60, 0), (sweep_x * mark.width + 60, 0),
             (sweep_x * mark.width + 190, mark.height), (sweep_x * mark.width + 70, mark.height)],
            fill=210)
        band = band.filter(ImageFilter.GaussianBlur(26))
        spec = Image.new('RGBA', mark.size, (255, 255, 255, 0))
        spec.paste((255, 255, 255), (0, 0), ImageChops.multiply(band, mark.getchannel('A')))
        lit = Image.alpha_composite(lit, spec)
        paste(canvas, lit, (W / 2, H / 2 - 120), scale=scale, alpha=fade_in * fade_out)

        name = text_sprite(self.brand, 96, WHITE, DISPLAY, 10, 900)
        paste(canvas, name, (W / 2, H / 2 + 190), scale=pop(local, 0.7, 0.4), alpha=fade_in * fade_out)
        promise = text_sprite('FIND. VET. VERIFY.', 56, EMERALD, DISPLAY, 14, 900)
        paste(canvas, promise, (W / 2, H / 2 + 300), scale=pop(local, 1.1, 0.4), alpha=fade_in * fade_out)
        site = text_sprite(self.cta, 64, WHITE, BODY, 12, 900)
        paste(canvas, site, (W / 2, H / 2 + 430), scale=pop(local, 1.5, 0.4), alpha=fade_in * fade_out)
        return canvas


    # -- scene 1-3 dispatchers ---------------------------------------------
    def scene_hook(self, canvas, t):
        if self.layout == 'A':
            return self._hook_audit(canvas, t)
        if self.layout == 'B':
            return self._hook_bank(canvas, t)
        if self.layout == 'C':
            return self._hook_alert(canvas, t)
        return self._scene_hook_d(canvas, t)

    def scene_illusions(self, t):
        if self.layout == 'A':
            return self._scene2_radar(t)
        if self.layout == 'B':
            return self._scene2_bars(t)
        if self.layout == 'C':
            return self._scene2_missing(t)
        return self._scene_illusions_d(t)

    def scene_chat(self, t):
        if self.layout == 'A':
            return self._scene3_rows(t, tick=True)
        if self.layout == 'B':
            return self._scene3_rows(t, tick=False)
        if self.layout == 'C':
            return self._scene3_rows(t, tick=True)
        return self._scene_chat_d(t)

    # -- shared panel chrome ------------------------------------------------
    def _panel(self, canvas, box, alpha=1.0, fill=(17, 17, 17), outline=(58, 58, 58)):
        panel(canvas, box, alpha=alpha, fill=fill, outline=outline)

    def _panel_title(self, canvas, text, y, size=52, colour=WHITE, alpha=1.0):
        sprite = text_sprite(text, size, colour, DISPLAY, 8, W - 240, 0.02)
        paste(canvas, sprite, (W / 2, y), alpha=alpha)

    def _hook_caption(self, canvas, t):
        """The spoken hook, slammed under whatever scene 1 draws."""
        if t < 1.35:
            return
        scrim = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        pixels = scrim.load()
        for y in range(int(H * 0.62), H):
            weight = min(1.0, (y - H * 0.62) / (H * 0.16))
            for x in range(W):
                pixels[x, y] = (0, 0, 0, int(232 * weight))
        canvas.paste(scrim, (0, 0), scrim)
        size = 86 if len(self.hook) < 62 else 74
        head = fitted(self.hook, size, EMERALD, DISPLAY, 18, SAFE[2] - SAFE[0])
        paste(canvas, head, (W / 2, 1500), scale=pop(t, 1.35), alpha=ramp(t, 1.35, 1.5))

    # -- layout A: audit dashboard -----------------------------------------
    def _hook_audit(self, canvas, t):
        one = self.scenes.get('one') or {}
        enter = ease_out(ramp(t, 0.0, 0.34))
        self._panel(canvas, (76, 292, W - 152, 540), alpha=enter)
        self._panel_title(canvas, one.get('title', 'AUDIT REPORT'), 372, 50,
                          alpha=ramp(t, 0.06, 0.22))
        ref = text_sprite(one.get('ref', ''), 30, MINT, BODY, 0, W - 260)
        paste(canvas, ref, (W / 2, 436), alpha=ramp(t, 0.18, 0.3))
        draw = ImageDraw.Draw(canvas, 'RGBA')
        draw.line([(120, 470), (W - 120, 470)], fill=(60, 60, 60, 255), width=2)
        rows = one.get('rows') or []
        for slot, (label, state) in enumerate(rows):
            appear = ramp(t, 0.30 + slot * 0.26, 0.44 + slot * 0.26)
            if appear <= 0:
                continue
            y = 556 + slot * 118
            # Label left, verdict right, each fitted to its own half of the row so
            # a long name can never run into the state chip.
            text = text_sprite(label.upper(), 32, WHITE, BODY, 0, 470)
            paste(canvas, text, (136 + text.width / 2, y), alpha=appear)
            alarm = any(word in state for word in ('NO ', 'NOT', 'NEVER', 'MISMATCH',
                                                   'UNVERIFIED', 'DECLINED', 'NONE',
                                                   'PAID', 'TRADER', 'UNVERIFIED'))
            chip = text_sprite(state.upper(), 25, (248, 113, 113) if alarm else EMERALD,
                               BODY, 0, 330)
            paste(canvas, chip, (W - 148 - chip.width / 2, y), alpha=appear)
            draw.line([(136, y + 54), (W - 136, y + 54)], fill=(38, 38, 38, 255), width=2)
        # The verdict flips from the finding to what StratEvo did about it.
        before = one.get('before', 'FAILED')
        after = one.get('after', 'VERIFIED')
        flip = t >= 1.55
        badge = after if flip else before
        colour = EMERALD if flip else (248, 113, 113)
        sprite = text_sprite(badge, 62, colour, DISPLAY, 16, 820, 0.04)
        chip_w, chip_h = sprite.width + 86, sprite.height + 44
        shape = Image.new('RGBA', (chip_w, chip_h), (0, 0, 0, 0))
        ImageDraw.Draw(shape).rounded_rectangle(
            [0, 0, chip_w - 1, chip_h - 1], radius=chip_h // 2,
            fill=colour + (34,), outline=colour + (235,), width=3)
        shape.paste(sprite, ((chip_w - sprite.width) // 2, (chip_h - sprite.height) // 2), sprite)
        start = 1.55 if flip else 0.55
        paste(canvas, shape, (W / 2, 1030), scale=pop(t, start, 0.30),
              alpha=ramp(t, start, start + 0.12))
        self._hook_caption(canvas, t)
        return canvas

    # -- layout B: bank transfer paused ------------------------------------
    def _hook_bank(self, canvas, t):
        one = self.scenes.get('one') or {}
        enter = ease_out(ramp(t, 0.0, 0.34))
        self._panel(canvas, (80, 300, W - 160, 700), alpha=enter, fill=(14, 16, 18))
        label = text_sprite(one.get('label', 'WIRE TRANSFER'), 36, MINT, BODY, 0, 620, 0.12)
        paste(canvas, label, (W / 2, 382), alpha=ramp(t, 0.08, 0.22))
        draw = ImageDraw.Draw(canvas, 'RGBA')
        draw.line([(120, 428), (W - 120, 428)], fill=(52, 52, 52, 255), width=2)
        amount = text_sprite(one.get('amount', '$0'), 128, WHITE, DISPLAY, 14, 900)
        paste(canvas, amount, (W / 2, 548), scale=pop(t, 0.18, 0.30),
              alpha=ramp(t, 0.18, 0.3))
        for slot, (caption, value) in enumerate((
                ('BENEFICIARY', one.get('beneficiary', '')),
                ('REFERENCE', one.get('reference', '')))):
            y = 668 + slot * 92
            left = text_sprite(caption, 28, (150, 150, 150), BODY, 0, 380, 0.1)
            paste(canvas, left, (150 + left.width / 2, y), alpha=ramp(t, 0.4 + slot * 0.1, 0.55))
            right = text_sprite(value, 30, WHITE, BODY, 0, 460)
            paste(canvas, right, (W - 150 - right.width / 2, y), alpha=ramp(t, 0.4 + slot * 0.1, 0.55))
        # StratEvo stamps the transfer as held before the money leaves.
        pause_t = 1.22
        if t >= pause_t:
            stamp = text_sprite(one.get('pause', 'PAUSED BY STRATEVO'), 46,
                                (248, 113, 113), DISPLAY, 14, 840, 0.06)
            chip_w, chip_h = stamp.width + 76, stamp.height + 40
            shape = Image.new('RGBA', (chip_w, chip_h), (0, 0, 0, 0))
            ImageDraw.Draw(shape).rounded_rectangle(
                [0, 0, chip_w - 1, chip_h - 1], radius=18,
                fill=(0, 0, 0, 220), outline=(248, 113, 113, 235), width=4)
            shape.paste(stamp, ((chip_w - stamp.width) // 2, (chip_h - stamp.height) // 2), stamp)
            shape = shape.rotate(-3.5, expand=True, resample=Image.BICUBIC)
            # Stamped below the card, clear of every field: the amount and the
            # beneficiary have to stay readable while the transfer is stopped.
            paste(canvas, shape, (W / 2, 1070), scale=pop(t, pause_t, 0.28),
                  alpha=ramp(t, pause_t, pause_t + 0.1))
            draw.rectangle([W - 128, 340, W - 112, 390], fill=(248, 113, 113, 235))
            draw.rectangle([W - 152, 340, W - 136, 390], fill=(248, 113, 113, 235))
        self._hook_caption(canvas, t)
        return canvas

    # -- layout C: supplier alert ------------------------------------------
    def _hook_alert(self, canvas, t):
        one = self.scenes.get('one') or {}
        enter = ease_out(ramp(t, 0.0, 0.34))
        messages = one.get('messages') or []
        # Height follows the conversation: two lines of text should not sit in a
        # 460 px empty card.
        box = (92, 300, W - 184, 150 + len(messages) * 118)
        self._panel(canvas, box, alpha=enter, fill=(12, 16, 14), outline=(38, 62, 48))
        header = Image.new('RGBA', (box[2], 88), (0, 0, 0, 0))
        ImageDraw.Draw(header).rounded_rectangle([0, 0, box[2] - 1, 87], radius=26,
                                                 fill=(31, 82, 56, int(240 * enter)))
        name = text_sprite(one.get('app', 'SUPPLIER'), 34, WHITE, DISPLAY, 0, 460, 0.04)
        header.paste(name, (34, (88 - name.height) // 2), name)
        when = text_sprite(one.get('time', 'now'), 26, MINT, BODY, 0, 200)
        header.paste(when, (box[2] - when.width - 30, (88 - when.height) // 2), when)
        canvas.paste(header, (box[0], box[1]), header)
        y = box[1] + 130
        for slot, message in enumerate(messages):
            appear = ramp(t, 0.22 + slot * 0.36, 0.34 + slot * 0.36)
            if appear <= 0:
                continue
            bubble = text_sprite(message, 34, WHITE, BODY, 0, 700)
            bw, bh = bubble.width + 52, bubble.height + 40
            shape = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            ImageDraw.Draw(shape).rounded_rectangle(
                [0, 0, bw - 1, bh - 1], radius=26,
                fill=(34, 44, 38, 255), outline=(52, 70, 58, 255), width=2)
            shape.paste(bubble, (26, 20), bubble)
            scale_y = 0.7 + 0.3 * ease_back(appear)
            scaled = shape.resize((bw, max(1, int(bh * scale_y))), Image.LANCZOS)
            canvas.paste(scaled, (box[0] + 34, y), scaled)
            y += bh + 26
        self._hook_caption(canvas, t)
        return canvas

    # -- layout A scene 2: verification radar ------------------------------
    def _scene2_radar(self, t):
        local = t - CUTS[1]
        canvas = background().copy()
        two = self.scenes.get('two') or {}
        steps = two.get('steps') or []
        self._panel_title(canvas, two.get('title', 'VERIFICATION'), 430, 56,
                          alpha=ramp(local, 0.0, 0.18))
        centre = (W / 2, 1120)
        radius = 380
        halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        hdraw = ImageDraw.Draw(halo)
        for ring in range(len(steps) + 1):
            size = radius * (ring + 1) / (len(steps) + 1)
            hdraw.ellipse([centre[0] - size, centre[1] - size, centre[0] + size, centre[1] + size],
                          outline=(52, 96, 72, 200), width=2)
        sweep = math.radians((local * 150) % 360)
        for step in range(26):
            angle = sweep - step * 0.045
            alpha = int(120 * (1 - step / 26))
            hdraw.line([centre, (centre[0] + math.cos(angle) * radius,
                                 centre[1] + math.sin(angle) * radius)],
                       fill=(74, 222, 128, alpha), width=4)
        canvas.paste(halo, (0, 0), halo)
        shadows = ImageDraw.Draw(canvas, 'RGBA')
        for slot, label in enumerate(steps):
            angle = -math.pi / 2 + slot * (2 * math.pi / max(1, len(steps))) + math.radians(local * 16)
            x = centre[0] + math.cos(angle) * radius
            y = centre[1] + math.sin(angle) * radius
            passed = (local * 150) % 360 > (slot * (360 / max(1, len(steps))))
            colour = EMERALD if passed else (120, 120, 120)
            draw = ImageDraw.Draw(canvas, 'RGBA')
            draw.ellipse([x - 16, y - 16, x + 16, y + 16], fill=colour + (255,))
            draw.ellipse([x - 30, y - 30, x + 30, y + 30], outline=colour + (120,), width=2)
            label_sprite = text_sprite(label, 28, WHITE if passed else (170, 170, 170),
                                       BODY, 0, 380)
            offset = 84 if math.cos(angle) > -0.2 else -84
            # Clamp inside the safe area: a long step name must never be cut by
            # the frame edge the way "PRODUCTION LINE" was.
            label_x = min(max(x + offset, SAFE[0] + label_sprite.width / 2),
                          SAFE[2] - label_sprite.width / 2)
            paste(canvas, label_sprite, (label_x, y + 62),
                  alpha=ramp(local, 0.2 + slot * 0.2, 0.35 + slot * 0.2))
        return canvas

    # -- layout B scene 2: quote vs landed cost ----------------------------
    def _scene2_bars(self, t):
        local = t - CUTS[1]
        canvas = background().copy()
        two = self.scenes.get('two') or {}
        bars = two.get('bars') or []
        self._panel_title(canvas, two.get('title', 'COST'), 430, 56,
                          alpha=ramp(local, 0.0, 0.18))
        base_y = 1560
        tallest = max((bar[1] for bar in bars), default=100) or 100
        width = 300
        gap = 90
        total = len(bars) * width + max(0, len(bars) - 1) * gap
        for slot, bar in enumerate(bars):
            label, value, display = bar[:3]
            # An optional fourth element marks the tone, so the data decides which
            # bar is the good news instead of its position.
            tone = (bar[3] if len(bar) > 3 else ('good' if slot == 0 else 'bad')).lower()
            grow = ease_out(ramp(local, 0.25 + slot * 0.3, 1.1 + slot * 0.3))
            height = int(760 * (value / tallest) * grow)
            x = W / 2 - total / 2 + slot * (width + gap)
            colour = EMERALD if tone in ('good', 'vetted') else (248, 113, 113)
            draw = ImageDraw.Draw(canvas, 'RGBA')
            draw.rounded_rectangle([x, base_y - height, x + width, base_y], radius=18,
                                   fill=colour + (215,))
            if height > 40:
                value_sprite = text_sprite(display, 54, WHITE, DISPLAY, 10, width)
                paste(canvas, value_sprite, (x + width / 2, base_y - height - 60))
            label_sprite = text_sprite(label, 30, (200, 200, 200), BODY, 0, width + 60)
            paste(canvas, label_sprite, (x + width / 2, base_y + 60))
        draw = ImageDraw.Draw(canvas, 'RGBA')
        draw.line([(110, base_y), (W - 110, base_y)], fill=(70, 70, 70, 255), width=3)
        return canvas

    # -- layout C scene 2: missing documents -------------------------------
    def _scene2_missing(self, t):
        local = t - CUTS[1]
        canvas = background().copy()
        two = self.scenes.get('two') or {}
        items = two.get('items') or []
        self._panel_title(canvas, two.get('title', 'MISSING'), 430, 52,
                          alpha=ramp(local, 0.0, 0.18))
        for slot, label in enumerate(items):
            appear = ramp(local, 0.25 + slot * 0.34, 0.4 + slot * 0.34)
            if appear <= 0:
                continue
            y = 700 + slot * 300
            page_w, page_h = 300, 210
            x = 170
            page = Image.new('RGBA', (page_w, page_h), (0, 0, 0, 0))
            pdraw = ImageDraw.Draw(page)
            pdraw.rounded_rectangle([0, 0, page_w - 1, page_h - 1], radius=16,
                                    fill=(24, 24, 24, 255), outline=(70, 70, 70, 255), width=3)
            for line in range(4):
                pdraw.rectangle([34, 44 + line * 32, page_w - 34, 56 + line * 32],
                                fill=(60, 60, 60, 255))
            pdraw.line([(60, 60), (page_w - 60, page_h - 40)], fill=(248, 113, 113, 235), width=9)
            pdraw.line([(page_w - 60, 60), (60, page_h - 40)], fill=(248, 113, 113, 235), width=9)
            page = page.rotate(-4, expand=True, resample=Image.BICUBIC)
            paste(canvas, page, (x + page_w / 2, y), scale=pop(local, 0.25 + slot * 0.34, 0.3),
                  alpha=appear)
            label_sprite = text_sprite(label, 34, WHITE, BODY, 0, 520)
            paste(canvas, label_sprite, (640, y), alpha=appear)
        return canvas

    # -- scenes 3 for A and C: checklist / verify rows ---------------------
    def _scene3_rows(self, t, tick=True):
        local = t - CUTS[2]
        canvas = background().copy()
        three = self.scenes.get('three') or {}
        if three.get('rows'):
            # layout B: the hidden defect maths
            self._panel_title(canvas, three.get('title', 'MATH'), 480, 52,
                              alpha=ramp(local, 0.0, 0.16))
            for slot, row in enumerate(three['rows']):
                appear = ramp(local, 0.16 + slot * 0.22, 0.3 + slot * 0.22)
                sprite = text_sprite(str(row).upper(), 44, WHITE, BODY, 0, 900)
                paste(canvas, sprite, (W / 2, 760 + slot * 150), alpha=appear)
            total = three.get('total')
            if total:
                sprite = text_sprite(total, 72, EMERALD, DISPLAY, 16, 940, 0.03)
                paste(canvas, sprite, (W / 2, 1420), scale=pop(local, 0.85, 0.34),
                      alpha=ramp(local, 0.85, 1.0))
            return canvas
        items = three.get('items') or []
        self._panel_title(canvas, three.get('title', 'CHECKLIST'), 420, 50,
                          alpha=ramp(local, 0.0, 0.16))
        self._panel(canvas, (84, 500, W - 168, 180 + 132 * len(items)),
                    alpha=ramp(local, 0.05, 0.2))
        for slot, label in enumerate(items):
            appear = ramp(local, 0.16 + slot * 0.2, 0.3 + slot * 0.2)
            if appear <= 0:
                continue
            y = 600 + slot * 132
            draw = ImageDraw.Draw(canvas, 'RGBA')
            if tick:
                draw.line([(140, y), (162, y + 24), (206, y - 22)],
                          fill=(74, 222, 128, int(255 * appear)), width=9)
            else:
                draw.ellipse([146, y - 14, 174, y + 14], fill=(248, 113, 113, int(255 * appear)))
            sprite = text_sprite(label, 36, WHITE, BODY, 0, 700)
            paste(canvas, sprite, (250 + sprite.width / 2, y), alpha=appear)
        return canvas

    # -- the timeline ------------------------------------------------------
    def frame(self, t):
        if t < CUTS[1]:
            canvas = background().copy()
            self.scene_hook(canvas, t)
        elif t < CUTS[2]:
            canvas = self.scene_illusions(t)
        elif t < CUTS[3]:
            canvas = self.scene_chat(t)
        elif t < CUTS[4]:
            if self._wipe_base is None:        # frozen chat behind the glass
                self._wipe_base = self.scene_chat(CUTS[3] - 1e-3)
            canvas = self.scene_wipe(t, self._wipe_base)
        elif t < CUTS[5]:
            canvas = self.scene_questions(t)
        elif t < CUTS[6]:
            canvas = self.scene_equation(t)
        else:
            canvas = self.scene_signoff(t)
        draw_watermark(canvas)
        return canvas


def available():
    """Can this worker render? Fonts on disk and an ffmpeg to encode with."""
    from app import kinetic_series
    fonts = {}
    for name in (DISPLAY, BODY):
        fonts[name] = (FONT_DIR / name).exists()
    encoder = captions._ffmpeg()
    return {'ready': all(fonts.values()) and bool(encoder),
            'fonts': fonts, 'ffmpeg': encoder or 'missing',
            'size': [W, H], 'fps': FPS, 'duration': DURATION,
            'episodes': len(kinetic_series.EPISODES)}


# ---------------------------------------------------------------------------
# encoding
# ---------------------------------------------------------------------------
def _ffmpeg():
    executable = captions._ffmpeg()
    if not executable:
        raise RenderError('ffmpeg is not available on this worker.')
    return executable


def segment(episode, start, end, destination, fps=FPS, crf=19, preset='veryfast',
            x264_params=None):
    """Render ``[start, end)`` and encode one H.264 segment.

    ``x264_params`` is passed straight to libx264. The default of ``aq-mode=3``
    matters here: these clips are mostly black frames with small bright type, and
    mode 3 (variance AQ with a bias against dark scenes starving) keeps the
    emerald glow and chrome gradients from banding. The stream is tagged BT.709 so
    players do not guess the colour space of an RGB render.
    """
    if end <= start:
        raise RenderError('Empty render range.')
    total = max(1, int(round((end - start) * fps)))
    if x264_params is None:
        x264_params = ENCODE_X264
    command = [_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
               '-r', str(fps), '-i', 'pipe:0',
               '-an', '-c:v', 'libx264', '-preset', preset, '-crf', str(crf),
               '-pix_fmt', 'yuv420p', '-g', str(fps * 2), '-movflags', '+faststart',
               '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
    if x264_params:
        command += ['-x264-params', x264_params]
    command += [str(destination)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE)
    try:
        for index in range(total):
            t = start + (index / fps)
            frame = episode.frame(min(t, DURATION - 1e-3))
            process.stdin.write(frame.tobytes())
        process.stdin.close()
    except BrokenPipeError:
        raise RenderError('ffmpeg stopped while encoding the segment.') from None
    finally:
        stderr = process.stderr.read() if process.stderr else b''
        if process.stderr:
            process.stderr.close()
        code = process.wait()
    if code != 0:
        raise RenderError('ffmpeg failed: ' + (stderr.decode('utf-8', 'ignore')[-300:] or 'unknown'))
    return total


def bed_stem(destination, duration=DURATION, sample_rate=48000):
    """A procedural ambient bed: low sub drone plus a brown-noise floor.

    Used when a clip has no narration and no generated SFX, so an episode is
    never dead silent. Deterministic, no sample files, no API call.
    """
    fade_out = max(0.4, min(1.4, duration * 0.08))
    graph = ("[0:a]volume=0.30[a0];"
             "[1:a]lowpass=f=190,volume=0.55[a1];"
             "[a0][a1]amix=inputs=2:duration=longest:normalize=0,"
             "afade=t=in:st=0:d=0.9,afade=t=out:st=%.2f:d=%.2f,"
             "alimiter=limit=0.9[out]" % (duration - fade_out, fade_out))
    command = [_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
               '-f', 'lavfi', '-i', 'sine=frequency=42:sample_rate=%d:duration=%.3f' % (sample_rate, duration),
               '-f', 'lavfi', '-i', 'anoisesrc=color=brown:amplitude=0.05:sample_rate=%d:duration=%.3f'
               % (sample_rate, duration),
               '-filter_complex', graph, '-map', '[out]',
               '-t', '%.3f' % duration, '-ar', str(sample_rate), '-ac', '2',
               '-c:a', 'pcm_s16le', str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not Path(destination).exists():
        raise RenderError('Could not build the ambient bed: ' + (result.stderr or '').strip()[-300:])
    return Path(destination)


def mix_audio(destination, duration=DURATION, voice=None, sfx=(), bed=False,
              voice_gain=1.0, sfx_gain=0.9, sample_rate=48000):
    """Mix narration and timed SFX into one stem of exactly ``duration`` seconds.

    ``sfx`` is a sequence of ``(path, start_seconds)`` pairs. Each effect is
    delayed to its timestamp with ``adelay`` and summed with ``amix`` (no
    normalisation, so adding layers does not duck the voice). The result is then
    padded to the full picture length and trimmed to it, so a short read or a
    clip with effects only past the voice never shortens the video.

    Returns the path to a 48 kHz stereo WAV.
    """
    sources = []
    if voice:
        sources.append((str(voice), 0.0, voice_gain))
    for item in sfx or ():
        path, start = item
        sources.append((str(path), max(0.0, float(start)), sfx_gain))
    sources = [item for item in sources if Path(item[0]).exists()]
    if not sources:
        if not bed:
            return None
        return bed_stem(destination, duration, sample_rate)

    command = [_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error']
    for path, _, _ in sources:
        command += ['-i', path]
    chains = []
    labels = []
    for index, (_, start, gain) in enumerate(sources):
        delay = int(round(start * 1000))
        chains.append('[%d:a]adelay=%d|%d,volume=%.3f,apad=whole_dur=%.3f[a%d]'
                      % (index, delay, delay, gain, duration, index))
        labels.append('[a%d]' % index)
    graph = ';'.join(chains) + ';' + ''.join(labels) + \
        'amix=inputs=%d:duration=longest:normalize=0,atrim=0:%.3f,alimiter=limit=0.95[out]' % (
            len(sources), duration)
    command += ['-filter_complex', graph, '-map', '[out]',
                '-t', '%.3f' % duration, '-ar', str(sample_rate), '-ac', '2',
                '-c:a', 'pcm_s16le', str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0 or not Path(destination).exists():
        raise RenderError('Could not mix the soundtrack: ' + (result.stderr or '').strip()[-300:])
    return Path(destination)


def assemble(segments, destination, audio=None, fps=FPS, duration=None,
             audio_bitrate='160k'):
    """Concatenate segments and mux the soundtrack into the final MP4.

    ``duration`` is the length of the picture, used to pad a narration that is
    shorter than the clip. Padding — never ``-shortest`` on its own — is what
    keeps a quiet read from truncating the video.
    """
    segments = [str(item) for item in segments if Path(item).exists() and Path(item).stat().st_size > 1024]
    if not segments:
        raise RenderError('No rendered segments to assemble.')
    if duration is None and audio:
        duration = sum(captions.probe(item)['duration'] for item in segments)
    with tempfile.TemporaryDirectory(prefix='stratevo-kinetic-') as workdir:
        listing = Path(workdir) / 'segments.txt'
        listing.write_text('\n'.join("file '%s'" % item for item in segments) + '\n')
        command = [_ffmpeg(), '-y', '-hide_banner', '-loglevel', 'error',
                   '-f', 'concat', '-safe', '0', '-i', str(listing)]
        if audio:
            command += ['-i', str(audio)]
        if audio:
            # Pad the read to the exact picture length instead of shortening the
            # picture to the read. An unpadded `-shortest` would cut the video.
            pad = 'apad=whole_dur=' + ('%.3f' % (duration or DURATION))
            command += ['-map', '0:v:0', '-map', '1:a:0', '-af', pad + ',alimiter=limit=0.95',
                        '-c:a', 'aac', '-b:a', audio_bitrate, '-t', ('%.3f' % (duration or DURATION))]
        else:
            command += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                        '-map', '0:v:0', '-map', '1:a:0', '-shortest', '-c:a', 'aac', '-b:a', '96k']
        command += ['-c:v', 'copy', '-movflags', '+faststart', str(destination)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 or not Path(destination).exists():
            raise RenderError('Could not assemble the segments: ' +
                              (result.stderr or '').strip()[-300:])
    return captions.probe(destination)


def probe(path):
    return captions.probe(path)


def render(data, destination, index=1, cta='stratevo.online', brand='STRATEVO', audio=None,
           fps=FPS, chunk_seconds=5.0, crf=20, preset='veryfast', voice=None, sfx=(),
           bed=False, audio_bitrate='160k', x264_params=None):
    """Render one complete episode in a single call (used by tests and CLI).

    ``voice`` is an audio file or bytes for the narration, ``sfx`` a list of
    ``(path, start_seconds)`` effects. Both are mixed with :func:`mix_audio`.
    With neither, ``bed=True`` lays a quiet ambient stem instead of silence.
    """
    episode = Episode(data, index, cta, brand)
    with tempfile.TemporaryDirectory(prefix='stratevo-kinetic-') as workdir:
        workdir_path = Path(workdir)
        if voice is not None and isinstance(voice, (bytes, bytearray)):
            written = workdir_path / 'voice.mp3'
            written.write_bytes(bytes(voice))
            voice = written
        if voice or sfx or (bed and not audio):
            audio = mix_audio(workdir_path / 'mix.wav', DURATION, voice=voice, sfx=sfx, bed=bed)
        parts = []
        start = 0.0
        number = 0
        while start < DURATION - 1e-6:
            end = min(DURATION, start + chunk_seconds)
            part = Path(workdir) / ('part-%03d.mp4' % number)
            segment(episode, start, end, part, fps=fps, crf=crf, preset=preset,
                    x264_params=x264_params)
            parts.append(part)
            start = end
            number += 1
        info = assemble(parts, destination, audio=audio, fps=fps, duration=DURATION,
                        audio_bitrate=audio_bitrate)
    info['bytes'] = Path(destination).stat().st_size
    return info
