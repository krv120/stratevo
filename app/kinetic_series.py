"""The 19-part kinetic typography series, as creative data.

Every episode is the same seven-scene template, which is what makes the format
recognisable and cheap to render: only the copy changes. Episodes 1 is the
master reference; 2-19 are the variations.

Fields
------
hook         the contrarian opening line, spoken and slammed on screen
illusions    the three "looks credible" surface signals (scene 2 tiles, scene 3
             chat bubbles). Two or three words each, never more than 22 chars.
questions    the three fear-stacking questions (scene 5), each at most 42 chars,
             escalating operational blindspot -> quality failure -> catastrophic
             financial or legal loss
left/right   the equation payoff (scene 6): LEFT != RIGHT

Each episode dict also carries three nested blocks, so the same source of truth
feeds the renderer, the sound designer and the publisher:

``episode_data``    the copy plus the timed voice script (MiniMax pause tags for
                    the API, ``<break time="x.xxs"/>`` tags for every other TTS)
``audio_blueprint`` 24-26 timestamped sound layers over the 20.60 s runtime, with
                    one transient every 0.6-0.9 s and a lowpass tail at 19.90 s
``metadata``        polarising comment-bait caption, hashtags, fear ladder, CTA

Nothing here touches the network: the whole series is data, and rendering it
costs $0.
"""

SERIES_NAME = 'Profile is not proof'

# Runtime of one clip. The brief is "strictly >= 20.50 s"; the sign-off needs
# room for its four stacked elements, so the timeline is 20.60 s and the last
# sound cue (a lowpass tail) starts at 19.90 and rings out over 0.70 s.
DURATION = 20.60
FPS = 30
SAMPLE_RATE = 48000
TAIL = {'start_time': 19.90, 'duration': 0.70}

TAGS = ('#sourcing #chinasourcing #suppliercheck #importing #b2b '
        '#productdevelopment #qualitycontrol #manufacturing #stratevo')

CLOSING_VO = 'Strat Evo. Find, vet, verify.'

# Scene cuts, kept in step with ``kinetic.CUTS`` so the blueprint's layer names
# line up with the picture.
SCENES = (
    ('hook', 0.00, 2.60),
    ('illusions', 2.60, 6.70),
    ('chat', 6.70, 8.30),
    ('wipe', 8.30, 9.90),
    ('questions', 9.90, 13.60),
    ('equation', 13.60, 16.50),
    ('signoff', 16.50, 20.60),
)

# ---------------------------------------------------------------------------
# the shared sound spine
# ---------------------------------------------------------------------------
# (start, length, kind, name, prompt). ``{subject}`` is replaced with the
# episode's short subject ("a perfect sample", "an ISO certificate", ...).
# 25 layers, every gap between 0.72 s and 0.85 s except the deliberate 1.25 s
# breath between the hook slam and the tile sequence.
SFX_SPINE = (
    (0.00, 0.90, 'hum', 'power-on-hum',
     'Deep 42 Hz sine power-on hum with a slow 6 Hz beating drift, recorded '
     'close, mono, fading in over 120 ms; the room tone under a phone screen '
     'waking up. No music, no pitch bend at the end.'),
    (0.80, 0.12, 'tick', 'ui-wake-tick',
     'Phone screen wake tick, 1 ms click plus a 120 ms 2.2 kHz damped ping, dry, '
     'quiet, the UI drawing itself before the hook lands.'),
    (1.35, 0.45, 'sub', 'hook-sub-slam',
     'Single 55 Hz sub-bass slam under a headline landing: 30 ms attack, fast '
     'pitch drop from 90 Hz to 55 Hz, 450 ms exponential decay, saturated but '
     'clean, no click, no reverb tail longer than the 450 ms.'),
    (2.60, 0.35, 'whoosh', 'tile-whoosh',
     'Tight reverse whoosh as three cards fly in from frame right: filtered '
     'pink noise, 900 Hz to 3 kHz sweep upward, 350 ms, hard start on the cut, '
     'no tone, no music.'),
    (3.42, 0.18, 'tick', 'card-flick-1',
     'Cardboard card flick, 1.2 ms transient then 180 ms paper slap, recorded '
     '8 cm from the microphone, dry, no room.'),
    (4.24, 0.18, 'tick', 'card-flick-2',
     'Second cardboard card flick, slightly brighter than the first, 180 ms '
     'paper slap, dry, no room.'),
    (5.06, 0.18, 'tick', 'card-flick-3',
     'Third cardboard card flick, slightly darker, 180 ms paper slap, dry, no '
     'room; the triplet should feel like a dealt hand.'),
    (5.88, 0.35, 'shimmer', 'shimmer-riser',
     'Glassy shimmer: three sine partials at 1.6 kHz, 2.4 kHz and 3.9 kHz with '
     'random micro-detune, 350 ms crescendo, icy, no melody.'),
    (6.70, 0.35, 'whoosh', 'send-whoosh',
     'Chat message send whoosh: 250 ms upward noise sweep plus a soft 8-bit '
     'blip at the end, phone-speaker character.'),
    (7.50, 0.14, 'tick', 'notification-pop-1',
     'Single notification pop, 1 kHz sine with 60 ms decay, dry, phone speaker.'),
    (8.30, 0.40, 'glass', 'glass-refraction',
     'Glass flute refraction hit: 3.2 kHz sine plus a 900 Hz body, 40 ms '
     'attack, 400 ms shimmering decay with fast vibrato, like a lens catching '
     'a light.'),
    (9.10, 0.30, 'glass', 'refraction-flash',
     'Sharper glass flash, 4.6 kHz partial with a 200 ms tail, one hit only, no '
     'reverb wash.'),
    (9.90, 0.20, 'tick', 'danger-tick',
     'Mechanical clock tick pitched down 400 Hz, 20 ms, dry, the sound of a '
     'countdown starting under a question.'),
    (10.64, 0.30, 'heartbeat', 'heartbeat-1',
     'Low heartbeat thud, 50 Hz sine with a 12 ms attack and 300 ms decay, close '
     'and dry, first of a pair.'),
    (11.38, 0.30, 'heartbeat', 'heartbeat-2',
     'Second heartbeat thud, 3 dB quieter and 10 ms shorter than the first, dry, '
     'closing the pair.'),
    (12.12, 0.50, 'riser', 'fear-riser',
     'Reverse breath riser: filtered white noise, highpass 300 Hz sweeping to '
     '2 kHz, 500 ms crescendo, airy, no pitch.'),
    (12.86, 0.40, 'taiko', 'taiko-soft',
     'Soft taiko hit, 70 Hz skin tone with a 15 ms attack and 400 ms decay, '
     'medium room, one hit.'),
    (13.60, 0.40, 'taiko', 'taiko-hit-1',
     'Hard taiko hit on the equation reveal: 70 Hz body, 200 Hz beater click, '
     '400 ms decay, tight room.'),
    (14.32, 0.40, 'taiko', 'taiko-hit-2',
     'Second taiko hit, 8% lower in pitch than the first, 400 ms decay, '
     'identical room.'),
    (15.05, 0.40, 'metal', 'metal-ring',
     'Struck metal ring: 640 Hz and 1.9 kHz inharmonic partials, 450 ms decay, '
     'small bright room, like a chrome bar being tapped.'),
    (15.78, 0.35, 'sub', 'equation-sub-drop',
     'Sub drop under the equation settling: 80 Hz falling to 45 Hz over 350 ms, '
     'clean, no distortion.'),
    (16.50, 0.60, 'bloom', 'chrome-bloom',
     'Chrome bloom: a wide 220 Hz sine swell plus a 3 kHz sparkle, 600 ms, '
     'rising filter, the sound of polished metal catching light.'),
    (17.35, 0.45, 'sheen', 'sheen-sweep',
     'Specular sheen sweep across a chrome logo: 120 ms noise sweep through a '
     'bandpass at 2.8 kHz, smooth, never hissy.'),
    (18.20, 0.25, 'tick', 'logo-latch',
     'Mechanical latch click, 1.5 ms transient plus 250 ms metallic settle, '
     'small and precise, the sign-off locking into place.'),
    (19.05, 0.60, 'chime', 'cta-chime',
     'Soft two-note chime, 880 Hz then 1.32 kHz, 600 ms bell decay, warm, low '
     'level, the call to action landing.'),
    (19.90, 0.70, 'tail', 'lowpass-tail',
     'Lowpass tail at 400 Hz closing the clip: the whole bed filtered down, 700 '
     'ms fade to silence, no new transient, loop-ready into the opening hum.'),
)

# One extra accent layer, chosen by episode so two clips never sound identical.
# Kept inside an existing gap, so the transient spacing stays under 0.9 s.
SIGNATURE_SFX = (
    (4.60, 0.30, 'tick', 'paper-tear', 'Short paper tear accent, 300 ms, dry.'),
    (4.60, 0.40, 'shimmer', 'photo-flash', 'Camera flash capacitor whine, 400 ms, tight.'),
    (5.60, 0.30, 'tick', 'envelope-open', 'Envelope flap opening, 300 ms, dry.'),
    (7.90, 0.20, 'tick', 'typing-burst', 'Four fast keyboard clicks, 200 ms total.'),
    (11.80, 0.30, 'heartbeat', 'breath-gasp', 'A single sharp inhale, 300 ms, close mic.'),
    (12.40, 0.30, 'tick', 'coin-drop', 'One coin dropped on glass, 300 ms, dry.'),
    (14.80, 0.35, 'metal', 'cash-register', 'Single till drawer ping, 350 ms, small room.'),
    (17.80, 0.30, 'chime', 'badge-ping', 'Small badge verification ping, 300 ms, phone speaker.'),
    (18.70, 0.35, 'tail', 'room-drop', 'A quiet room drop, 350 ms, low thud, dry.'),
)


def _scene_at(start):
    for name, begin, end in SCENES:
        if begin <= start < end:
            return name
    return SCENES[-1][0]


def _layer(index, start, length, kind, name, prompt, subject):
    return {
        'index': index,
        'start_time': round(start, 2),
        'duration': round(length, 2),
        'end_time': round(start + length, 3),
        'scene': _scene_at(start),
        'name': name,
        'kind': kind,
        'gain_db': -9.0 if kind in ('hum', 'tail') else (-6.0 if kind in ('sub', 'heartbeat', 'taiko') else -3.5),
        'sfx_prompt': prompt.replace('{subject}', subject),
    }


def audio_blueprint(data, index=None):
    """The 24-26 layer sound design for one episode, in milliseconds.

    Layers are sorted by ``start_time`` and the last one is always the lowpass
    tail at 19.90 s / 0.70 s, which is what lets clips loop back into the
    opening hum without a click.
    """
    subject = data.get('subject') or data['hook'].rstrip('.')
    spine = [item for item in SFX_SPINE]
    picks = list(SIGNATURE_SFX)
    slot = ((index or data.get('index') or 1) - 1) % len(picks)
    accent = picks[slot]
    layers = [_layer(number + 1, *item, subject) for number, item in enumerate(spine)]
    if data.get('signature', True):
        # Swap the fourth scene-2 card flick for this episode's signature accent,
        # so the layer count (and the transient spacing) never changes.
        anchor = layers[6]
        layers[6] = _layer(anchor['index'], anchor['start_time'], anchor['duration'],
                           accent[2], accent[3], accent[4], subject)
    return {
        'episode': data.get('index') or index,
        'duration': DURATION,
        'sample_rate': SAMPLE_RATE,
        'layer_count': len(layers),
        'layers': layers,
        'tail': dict(TAIL, scene='signoff', name='lowpass-tail'),
        'mix_notes': (
            'Sum all layers with amix normalize=0 so nothing ducks the narration. '
            'Voice sits at 0 dB, SFX at the per-layer gain_db above, master '
            'limited to -0.5 dBFS. Transients land every 0.72-0.85 s; the only '
            'long gap is the 1.25 s breath after the hook slam. The 19.90 s '
            'lowpass tail must never be truncated: the picture runs to 20.60 s.'
        ),
    }


def validate(data):
    """Return a list of brief violations for one episode (empty when clean)."""
    problems = []
    hook = data['hook'].rstrip('.')
    if len(hook.split()) > 10:
        problems.append('hook is longer than 10 words')
    for item in data['illusions']:
        if len(item.split()) > 3 or len(item) > 22:
            problems.append('illusion over 3 words / 22 chars: %r' % item)
    for item in data['questions']:
        if len(item) > 42:
            problems.append('question over 42 chars: %r' % item)
        if not item.endswith('?'):
            problems.append('question is not a question: %r' % item)
    if not data.get('left') or not data.get('right'):
        problems.append('equation is incomplete')
    blueprint = data.get('audio_blueprint') or {}
    layers = blueprint.get('layers') or []
    if not 24 <= len(layers) <= 26:
        problems.append('needs 24-26 sound layers, found %d' % len(layers))
    starts = [layer['start_time'] for layer in layers]
    if starts != sorted(starts):
        problems.append('sound layers are not in time order')
    gaps = [round(b - a, 3) for a, b in zip(starts, starts[1:])]
    if max(gaps) > 1.3:
        problems.append('sound gap over 1.3 s: %s' % max(gaps))
    if sum(1 for gap in gaps if gap > 0.9) > 1:
        problems.append('more than one gap over 0.9 s: %s' % gaps)
    tail = layers[-1] if layers else {}
    if (tail.get('start_time'), tail.get('duration')) != (TAIL['start_time'], TAIL['duration']):
        problems.append('the lowpass tail must close the clip at 19.90 s / 0.70 s')
    if voice_seconds(data) > DURATION - 0.7:
        problems.append('narration would run past the tail')
    return problems


def episode(index):
    """Return one episode by 1-based index, cycling through the series."""
    if not EPISODES:
        raise ValueError('The kinetic series has no episodes.')
    return EPISODES[(max(1, int(index)) - 1) % len(EPISODES)]


def voiceover(episode_data):
    """The narration for one episode, in scene order.

    MiniMax accepts ``<#x#>`` pause tags, so the whole read is a single cheap
    request whose pauses land on the scene cuts. ``tts_script`` is the same read
    with the ``<break time="x.xxs"/>`` form used by every other engine.
    """
    illusions = ', '.join(item.lower() for item in episode_data['illusions'])
    if not illusions.endswith('.'):
        illusions += '.'
    questions = ' '.join(_question_phrase(item) for item in episode_data['questions'])
    left = episode_data['left'].title()
    right = episode_data['right'].lower()
    return ('<#0.35#>%s<#0.45#>%s<#0.5#> '
            'And a profile can\u2019t show you %s<#0.45#>'
            '%s is not %s.<#0.55#>%s' % (
                episode_data['hook'].rstrip('.'), illusions, questions, left, right, CLOSING_VO))


def tts_script(episode_data):
    """The same narration with ``<break time="x.xxs"/>`` tags (generic TTS)."""
    text = voiceover(episode_data)
    return _BREAK_TAG.sub(lambda match: '<break time="%ss"/>' % match.group(1), text)


_BREAK_TAG = __import__('re').compile(r'<#\s*([\d.]+)\s*#>')


def _question_phrase(text):
    cleaned = text.strip().rstrip('?').lower()
    return cleaned + '?'


def voice_seconds(episode_data):
    """Rough spoken length at 2.7 words per second plus the tagged pauses."""
    text = voiceover(episode_data)
    pauses = sum(float(value) for value in _BREAK_TAG.findall(text))
    words = len(_BREAK_TAG.sub(' ', text).split())
    return round(words / 2.7 + pauses, 2)


def caption(episode_data, index=None):
    """Polarising comment-bait: a claim people will argue with, then the CTA."""
    bait = episode_data.get('comment_bait') or ''
    left = episode_data['left']
    right = episode_data['right'].lower()
    lines = [episode_data['hook'].rstrip('.'), '', left + ' \u2260 ' + right, '']
    if bait:
        lines += [bait, '']
    lines.append('If you still believe this, you have never paid for it. Argue with '
                 'me below. Full checklist at stratevo.online')
    return chr(10).join(lines)

def description(episode_data):
    left, right = episode_data['left'], episode_data['right'].lower()
    return ('%s\n\n%s \u2260 %s\n\n%s\n\n%s' % (
        episode_data['hook'], left, right,
        '\n'.join('- ' + item for item in episode_data['questions']), TAGS))


def script(episode_data):
    """The spoken/on-screen body as one paragraph (used for platform copy)."""
    return ' '.join(item.strip().rstrip('?').lower() + '?' for item in episode_data['questions'])


def copy_for(index):
    """Everything the pipeline needs to store one episode as a content idea."""
    data = episode(index)
    left, right = data['left'], data['right'].lower()
    return {
        'topic': '%s vs %s' % (left.lower(), right),
        'angle': 'kinetic typography',
        'hook': data['hook'],
        'script': script(data),
        'video_prompt': 'Rendered in code: %.2f s kinetic typography episode %d (%s \u2260 %s), '
                        '%d timed sound layers.' % (DURATION, index, left, right,
                                                    data['audio_blueprint']['layer_count']),
        'negative_prompt': '',
        'tiktok_caption': caption(data, index),
        'tiktok_hashtags': TAGS,
        'instagram_caption': caption(data, index),
        'instagram_hashtags': TAGS,
    }


# ---------------------------------------------------------------------------
# the episodes
# ---------------------------------------------------------------------------
# (hook, subject, illusions, questions, left, right, signature, comment bait)
_COPY = (
    ('A professional profile is not a professional supplier.',
     'a professional profile',
     ('Verified badge', 'Great photos', 'Fast replies'),
     ('Who actually runs the floor?', 'Will bulk match the photos?', 'Who refunds a dead order?'),
     'PROFILE', 'PROOF', True,
     'A verified badge means someone paid a fee. That is all it has ever meant.'),
    ('A perfect sample is not a perfect shipment.',
     'a perfect sample',
     ('Hand-made prototype', 'Luxury packaging', 'Free air freight'),
     ('Who made the sample?', 'Will the mold hold at scale?', 'Who eats 30% defects?'),
     'SAMPLE', 'SHIPMENT', False,
     'The sample was made by the best technician they have. You will never meet him.'),
    ('The lowest quote is rarely the lowest cost.',
     'a rock-bottom quote',
     ('Rock-bottom price', 'Zero tooling fee', 'Instant discount'),
     ('What is missing from this quote?', 'Who pays when 30% arrive broken?', 'Where do port fees land?'),
     'QUOTE', 'COST', True,
     'Anyone who buys on the first quote has already paid for the lesson.'),
    ('A huge catalog is not a factory.',
     'a ten thousand SKU catalog',
     ('10,000 SKUs', 'Every category', 'Stylish 3D renders'),
     ('How does one plant make all this?', 'Who really makes item one?', 'What margin does the broker add?'),
     'CATALOG', 'FACTORY', True,
     'No factory on earth makes ten thousand products. You are talking to a reseller.'),
    ('Fast replies do not build products.',
     'two-minute replies',
     ('Two-minute texts', 'Friendly emojis', '24/7 sales chat'),
     ('Has sales ever seen the floor?', 'Who checks the first article?', 'Who is liable when QC fails?'),
     'FAST CHAT', 'GOOD QC', False,
     'The fastest rep you ever met will disappear the moment the defects land.'),
    ('An ISO PDF is not a factory audit.',
     'an ISO certificate',
     ('Stamped PDF', 'Wall plaque', 'Compliance logo'),
     ('Does that cert cover your product?', 'Is the audit scope real?', 'Who refunds a seized container?'),
     'ISO CERT', 'COMPLIANCE', True,
     'Half the certificates in this industry expired before the supplier uploaded them.'),
    ('We supply big brands is a lie.',
     'a famous logo',
     ('Famous logos', 'Retail boxes', 'Name dropping'),
     ('Which line did they make?', 'Can they show a bill of lading?', 'Who sues for a replica?'),
     'BIG BRANDS', 'REAL WORK', True,
     'Making the polybag for a famous brand is not making the product for that brand.'),
    ('A low MOQ can still trap your cash.',
     'a fifty unit minimum',
     ('50-unit minimum', 'Zero setup cost', 'Ready stock'),
     ('Is this rejected stock?', 'Can they scale to 10,000?', 'Who owns the tooling you paid for?'),
     'LOW MOQ', 'SCALABLE', False,
     'Low MOQ usually means someone else already paid for that inventory and walked away.'),
    ('A factory tour is rented in a day.',
     'a drone tour video',
     ('Drone shots', 'Clean lines', 'Busy workers'),
     ('Whose name is on the gate?', 'Whose labels are blurred?', 'Who is insured if it burns down?'),
     'VIDEO TOUR', 'OWNERSHIP', True,
     'Every sourcing agent has access to a clean factory for exactly one afternoon.'),
    ('A checkmark sheet is not an inspection.',
     'a signed checklist',
     ('Signed sheet', 'Thumbs-up photo', 'Sealed cartons'),
     ('Did they test or count boxes?', 'What is the AQL tolerance?', 'Who pays for a failed container?'),
     'CHECKLIST', 'INSPECTION', True,
     'One hundred percent inspection means they looked at every box. Not every unit.'),
    ('A 30% deposit with no contract is a gift.',
     'a thirty percent deposit',
     ('Proforma invoice', 'Bank wire details', 'Fast start promise'),
     ('Is this enforceable locally?', 'Are penalties defined at all?', 'Who owns your IP after payment?'),
     'INVOICE', 'PROTECTION', False,
     'If you cannot sue them where they bank, that deposit was a donation.'),
    ('Shipped is not the same as delivered.',
     'a container on the water',
     ('Loaded container', 'Tracking number', 'Vessel departed'),
     ('Are the HS codes correct?', 'Will the lab pass your port?', 'Who absorbs a customs seizure?'),
     'SHIPPED', 'DELIVERED', True,
     'Your supplier is done the moment the container leaves. You are not.'),
    ('Ten years online is not ten years making.',
     'a ten year old account',
     ('Ten-year badge', 'Old account', 'Trade history'),
     ('Was the account bought last month?', 'Have they made your category?', 'Who is liable for a recall?'),
     'TENURE', 'EXPERIENCE', True,
     'Platform age is a number the platform sells. It is not a factory.'),
    ('A 3D render hides every fatal flaw.',
     'a photoreal render',
     ('Photoreal 360', 'Exploded views', 'Sleek shaders'),
     ('Can this be molded at all?', 'Will the hinge snap at 10 uses?', 'Who pays for a recalled batch?'),
     'RENDER', 'ENGINEERED', False,
     'Anyone can render a beautiful product. Almost nobody can tool it.'),
    ('A green leaf icon is not a certificate.',
     'a recycled claim',
     ('Leaf icons', '100% recycled', 'Kraft boxes'),
     ('Where did the resin start?', 'Can they trace the batch?', 'Who gets fined for a false claim?'),
     'GREEN CLAIM', 'CERTIFIED', True,
     'In the EU a false green claim is a fine with your company name on it.'),
    ('A local warehouse is not a factory.',
     'a domestic address',
     ('Local map pin', 'Local phone', 'Domestic returns'),
     ('Is this just a forwarding hub?', 'Are you paying local prices?', 'Who absorbs the next tariff?'),
     'LOCAL PIN', 'LOCAL MADE', True,
     'A local returns address is a rented shelf, not a production line.'),
    ('A trade show booth is not a factory.',
     'a trade show stand',
     ('Huge expo stand', 'Fluent reps', 'Glossy brochures'),
     ('Who employs the engineers?', 'What does the plant look like?', 'Who audits the sub-tier?'),
     'BIG BOOTH', 'REAL PLANT', True,
     'A booth is a set. The factory is the film set nobody shows you.'),
    ('No problem, we can make it is a warning.',
     'an instant yes',
     ('Instant yes', 'Zero pushback', 'Fast deal'),
     ('Why did no engineer ask?', 'Are they guessing tolerances?', 'Who is liable for a rejected lot?'),
     'EASY YES', 'CAPABILITY', False,
     'A supplier who never pushes back on your spec has already subcontracted your order.'),
    ('A golden badge is not a factory audit.',
     'a paid verified badge',
     ('Paid directory', 'Five-star badge', 'Shiny storefront'),
     ('Did they pay for that badge?', 'Has anyone inspected them?', 'Who refunds a failed order?'),
     'BADGE', 'VETTED', False,
     'Five stars, zero inspections. That is not a supplier, that is an advertisement.'),
)

FEAR_LADDER = (
    'operational blindspot: you cannot see who runs the line',
    'quality failure: the batch that ships is not the batch you approved',
    'catastrophic loss: the money, the cargo, or the liability is yours alone',
)

_SCENE_BEATS = tuple({'scene': name, 'start': begin, 'end': end} for name, begin, end in SCENES)


def _build(index, copy):
    hook, subject, illusions, questions, left, right, signature, bait = copy
    data = {
        'index': index,
        'series': SERIES_NAME,
        'hook': hook,
        'subject': subject,
        'illusions': list(illusions),
        'questions': list(questions),
        'left': left,
        'right': right,
        'signature': signature,
        'comment_bait': bait,
        'tile_title': illusions[0],
        'chat_heading': illusions[2],
    }
    data['episode_data'] = {
        'index': index,
        'hook': hook,
        'hook_lands_at': 1.35,
        'subject': subject,
        'illusions': list(illusions),
        'questions': [
            {'text': text, 'level': level, 'chars': len(text), 'scene_time': 9.90 + slot * 1.25}
            for slot, (text, level) in enumerate(zip(questions, FEAR_LADDER))
        ],
        'equation': {'left': left, 'right': right, 'mark': '\u2260'},
        'on_screen': {
            'hook': hook.upper(),
            'tiles': [item.upper() for item in illusions],
            'chat': [item.upper() for item in illusions],
            'questions': [item.upper() for item in questions],
            'equation': [left.upper(), '\u2260', right.upper()],
            'signoff': ['STRATEVO', 'FIND. VET. VERIFY.', 'stratevo.online'],
        },
        'voice_script': voiceover(data),
        'tts_script': tts_script(data),
        'estimated_seconds': voice_seconds(data),
        'scene_beats': [dict(beat) for beat in _SCENE_BEATS],
    }
    data['audio_blueprint'] = audio_blueprint(data, index)
    data['metadata'] = {
        'episode': index,
        'series': SERIES_NAME,
        'topic': '%s vs %s' % (left.lower(), right.lower()),
        'equation': '%s \u2260 %s' % (left, right.lower()),
        'comment_bait': bait,
        'caption': caption(data, index),
        'hashtags': TAGS,
        'platforms': ['tiktok', 'instagram'],
        'duration_seconds': DURATION,
        'frame_count': int(round(DURATION * FPS)),
        'resolution': '1080x1920',
        'fps': FPS,
        'watermark': 'S',
        'cta': 'stratevo.online',
        'runtime_usd': 0.0,
        'status': 'pending',
    }
    return data


EPISODES = [_build(number + 1, item) for number, item in enumerate(_COPY)]

# Scene 4 flash words: what a profile cannot do. Shared by every episode.
FLASH_WORDS = ['A PROFILE', 'CAN\u2019T', 'SHOW', 'THINGS']
