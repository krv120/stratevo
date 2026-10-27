"""Deterministic concept, script and prompt generation for the 40-video series.

No third-party language model is used. Every idea is composed from a curated
sourcing knowledge base so generation is free, offline, reproducible and
reviewable: the same series seed always produces the same 40 ideas, and no idea
is generated twice inside a batch.

If you later want an LLM in the loop, replace ``build_idea`` — everything
downstream (captions, prompts, publishing) only depends on the returned dict.
"""
import hashlib

MAX_SCRIPT_WORDS = 34
READING_WORDS_PER_SECOND = 3.1

# Each topic carries a concrete, defensible sourcing point. `check` is the
# action the viewer should take; `scene` is a faceless visual brief.
TOPICS = [
    {'key': 'landed-cost', 'short': 'landed cost', 'topic': 'Landed cost vs unit price',
     'point': 'the unit price is not the cost you pay',
     'check': 'add freight, duty, packaging and payment fees before comparing quotes',
     'scene': 'a cardboard carton, a shipping label and a calculator on a warehouse bench',
     'tags': ['landedcost', 'sourcing', 'importing']},
    {'key': 'moq-trap', 'short': 'the MOQ', 'topic': 'MOQ that looks small',
     'point': 'a low MOQ often hides a higher total commitment',
     'check': 'compare total order value, not the minimum quantity',
     'scene': 'stacks of identical cartons with a clipboard and a measuring tape',
     'tags': ['moq', 'sourcing', 'suppliercheck']},
    {'key': 'golden-sample', 'short': 'the golden sample', 'topic': 'The golden sample',
     'point': 'the approved sample is the only reference that matters at inspection',
     'check': 'sign, date and photograph the approved sample and keep a copy',
     'scene': 'a single product sample on a clean table under a spotlight with a paper tag',
     'tags': ['qualitycontrol', 'sourcing', 'sample']},
    {'key': 'trade-assurance', 'short': 'verification paperwork', 'topic': 'Verification paperwork',
     'point': 'a registration number proves the company exists, not that it works on your product',
     'check': 'ask what they produced for which buyer, then verify one reference',
     'scene': 'a stack of stamped documents and a magnifying glass on a dark desk',
     'tags': ['supplierverification', 'sourcing', 'b2b']},
    {'key': 'factory-vs-trader', 'short': 'factory or trader', 'topic': 'Factory or trading company',
     'point': 'traders can be the better partner when you need several components',
     'check': 'ask who owns the machinery and who answers for defects',
     'scene': 'two workshop doors, one with warm light spilling out and one closed',
     'tags': ['sourcingchina', 'suppliercheck', 'manufacturing']},
    {'key': 'inspection-timing', 'short': 'inspection timing', 'topic': 'When to inspect',
     'point': 'inspecting after shipping is inspecting someone else’s problem',
     'check': 'book inspection while the goods are still in the factory',
     'scene': 'a carton open under a work lamp with calipers resting on the product',
     'tags': ['inspection', 'qualitycontrol', 'importing']},
    {'key': 'tooling-cost', 'short': 'tooling', 'topic': 'Tooling and moulds',
     'point': 'tooling is often paid once and owned silently by the factory',
     'check': 'state in writing who owns the tool and where it is stored',
     'scene': 'a heavy steel mould resting on a pallet in a dim workshop',
     'tags': ['tooling', 'manufacturing', 'suppliercheck']},
    {'key': 'lead-time', 'short': 'lead time', 'topic': 'Quoted lead time',
     'point': 'production time usually starts after deposit and material arrival',
     'check': 'ask for the date the finished goods leave the factory, not just days',
     'scene': 'a wall calendar with a red marker line and a production schedule board',
     'tags': ['leadtime', 'supplychain', 'sourcingchina']},
    {'key': 'payment-split', 'short': 'the payment split', 'topic': 'Payment structure',
     'point': 'the payment split is your only real leverage after production starts',
     'check': 'tie the balance to a passed inspection report',
     'scene': 'a contract page with a pen and two folded bank slips on a dark table',
     'tags': ['payments', 'negotiation', 'importing']},
    {'key': 'spec-sheet', 'short': 'the spec sheet', 'topic': 'A specification sheet',
     'point': 'unspecified tolerances are decided by the cheapest acceptable option',
     'check': 'write tolerance, material grade and finish into the request',
     'scene': 'a printed technical drawing with calipers and a pencil on a metal bench',
     'tags': ['specification', 'qualitycontrol', 'manufacturing']},
    {'key': 'packaging-cost', 'short': 'packaging', 'topic': 'Retail packaging',
     'point': 'packaging is a second supply chain with its own MOQ and lead time',
     'check': 'price packaging with the product, not after it',
     'scene': 'flat-packed printed boxes stacked beside a roll of tape in a packing area',
     'tags': ['packaging', 'ecommerce', 'sourcing']},
    {'key': 'freight-mode', 'short': 'freight mode', 'topic': 'Freight choice',
     'point': 'air freight buys time and spends margin, sea freight does the reverse',
     'check': 'model both against your actual stock-out date',
     'scene': 'a cargo container door open with pallets inside, seen from the loading bay',
     'tags': ['freight', 'logistics', 'importing']},
    {'key': 'duty-classification', 'short': 'the tariff code', 'topic': 'Customs classification',
     'point': 'the tariff code decides your duty and the wrong code is your liability',
     'check': 'agree the code with your broker before the goods ship',
     'scene': 'a customs declaration form with a stamp and a lit desk lamp',
     'tags': ['customs', 'duty', 'importing']},
    {'key': 'defect-rate', 'short': 'the defect rate', 'topic': 'Acceptable defect rate',
     'point': 'a defect rate with no sampling plan is a guess with a percentage sign',
     'check': 'define sample size, critical defects and the reject threshold',
     'scene': 'rows of identical parts on a light table with one part set aside',
     'tags': ['qualitycontrol', 'inspection', 'manufacturing']},
    {'key': 'supplier-red-flags', 'short': 'fast quotes', 'topic': 'Fast enthusiastic quotes',
     'point': 'a quote with no questions usually means no reading',
     'check': 'send a requirement that needs a question back to be credible',
     'scene': 'an inbox on a laptop screen in a dark room, casting light on a notebook',
     'tags': ['suppliercheck', 'sourcing', 'b2b']},
    {'key': 'material-grade', 'short': 'material grade', 'topic': 'Material grade',
     'point': 'the same material name can hide different grades and recycled content',
     'check': 'ask for the grade and the test report, not just the material name',
     'scene': 'material swatches laid out in a row under a directional lamp',
     'tags': ['materials', 'manufacturing', 'qualitycontrol']},
    {'key': 'sample-cost', 'short': 'sample fees', 'topic': 'Paying for samples',
     'point': 'a sample fee is cheap compared to a container of the wrong product',
     'check': 'pay for the sample and ask for the cost to be credited against the order',
     'scene': 'a small parcel open on a desk with bubble wrap and a product inside',
     'tags': ['samples', 'sourcing', 'suppliercheck']},
    {'key': 'communication', 'short': 'written confirmation', 'topic': 'Written confirmation',
     'point': 'a verbal agreement is a memory, not a term',
     'check': 'confirm every change in writing in the same thread',
     'scene': 'a phone on a workshop bench showing a chat thread next to production parts',
     'tags': ['negotiation', 'sourcing', 'b2b']},
    {'key': 'volume-breaks', 'short': 'price breaks', 'topic': 'Quantity price breaks',
     'point': 'the second price break is where most of the saving hides',
     'check': 'ask for pricing at three quantities and compare the total spend',
     'scene': 'a pricing table on paper with a calculator and a pencil circle',
     'tags': ['negotiation', 'sourcing', 'costcontrol']},
    {'key': 'backup-supplier', 'short': 'a single supplier', 'topic': 'Single supplier risk',
     'point': 'one approved supplier is a single point of failure',
     'check': 'qualify a second source before you need it urgently',
     'scene': 'two identical parts on a bench, one lit and one in shadow',
     'tags': ['supplychain', 'risk', 'sourcing']},
    {'key': 'photos-vs-reality', 'short': 'catalogue photos', 'topic': 'Photos and catalogue claims',
     'point': 'a catalogue photo is marketing, an inspection photo is evidence',
     'check': 'ask for a photo of your order, dated, before it is packed',
     'scene': 'a camera on a tripod photographing a product on a packing table',
     'tags': ['qualitycontrol', 'inspection', 'sourcing']},
    {'key': 'returns-damage', 'short': 'transit damage', 'topic': 'Damage in transit',
     'point': 'damage is a packaging problem as often as a carrier problem',
     'check': 'test the carton drop before you scale the order',
     'scene': 'a dented carton corner in a loading bay with tape and labels',
     'tags': ['packaging', 'logistics', 'ecommerce']},
    {'key': 'hidden-fees', 'short': 'excluded fees', 'topic': 'Quotes that exclude everything',
     'point': 'a price that excludes tooling, testing and packaging is not a price',
     'check': 'ask what is excluded before you compare',
     'scene': 'a quote sheet with blank lines and a red pen resting on it',
     'tags': ['costcontrol', 'sourcing', 'b2b']},
    {'key': 'scale-readiness', 'short': 'scaling a sample', 'topic': 'Scaling a good sample',
     'point': 'a perfect sample from a pilot line is not a production promise',
     'check': 'ask how the process changes at your target volume',
     'scene': 'a small pilot bench beside a large production conveyor',
     'tags': ['manufacturing', 'supplychain', 'sourcing']},
]

ANGLES = [
    {'key': 'insight', 'label': 'Insight',
     'hooks': ['The number that decides your margin is not the unit price.',
               'Nobody puts {short} on the quote. It decides everything.',
               'This is the line most buyers skip when they compare offers.',
               'If you only learn one thing about {short}, learn this.',
               '{short_cap} quietly decides whether the order makes money.',
               'Watch what happens to your margin when {short} is ignored.'],
     'script': '{point_cap}. Suppliers quote what they control, not what you will pay. {check_cap}.',
     'motion': 'slow lateral camera slide, shallow depth of field, dust in the light'},
    {'key': 'mistake', 'label': 'Mistake',
     'hooks': ['This is the most expensive assumption in sourcing.',
               'The mistake with {short} is invisible until the invoice arrives.',
               'Most buyers get {short} wrong in the same way.',
               'Cheap here usually means expensive two weeks later.',
               'Nobody warns you about {short}. The invoice does.',
               'One detail about {short} that changes the whole quote.'],
     'script': 'The expensive mistake: {point}. Most buyers find out after the deposit. {check_cap}.',
     'motion': 'slow push in, subtle handheld drift, warm practical light'},
    {'key': 'checklist', 'label': 'Checklist',
     'hooks': ['Before you send a deposit, check three things.',
               'Three checks that survive a bad supplier week.',
               'Run this list before you approve {short}.',
               'If you cannot answer these three, do not order yet.',
               'Three questions to ask before {short} gets signed off.',
               'Answer these before the first payment leaves your account.'],
     'script': 'Before you pay: one, {point}. Two, {check}. Three, who signs when it goes wrong. Get it in writing.',
     'motion': 'static tripod shot, gentle parallax, cool workshop light'},
    {'key': 'comparison', 'label': 'Comparison',
     'hooks': ['Two quotes. One is cheaper. It is not the one you think.',
               'Same product, two prices. Only one includes {short}.',
               'The lower quote wins until you read what it left out.',
               'Compare offers on {short}, not on the headline number.',
               'Two identical briefs, two different versions of {short}.',
               'The gap between these two quotes is hidden in {short}.',
               'Same product. Different {short}. Different real price.'],
     'script': '{point_cap}. Two suppliers can write that sentence very differently. {check_cap}.',
     'motion': 'split lighting from both sides, slow dolly across the scene'},
]

STYLE = ('Vertical 9:16 cinematic product photography, no people, no on-screen text, '
         'realistic industrial setting, natural grain, high detail, steady camera.')

HASHTAG_POOLS = {
    'tiktok': ['sourcing', 'suppliercheck', 'importing', 'smallbusiness', 'productdesign',
               'supplychain', 'manufacturing', 'ecommerce', 'b2b', 'chinabusiness'],
    'instagram': ['sourcing', 'supplychain', 'manufacturing', 'importing', 'smallbusiness',
                  'productdevelopment', 'qualitycontrol', 'ecommerce', 'b2b', 'private label'.replace(' ', ''),
                  'supplierverification', 'logistics', 'freightforwarding', 'procurement'],
}


def _seed_value(seed):
    return int(hashlib.sha256(str(seed).encode()).hexdigest()[:12], 16)


def _title(text):
    return text[:1].upper() + text[1:]


def _web_safe(text):
    return (text.replace('\u2019', "'").replace('\u2018', "'")
            .replace('\u201c', '"').replace('\u201d', '"').replace('\u2014', '-'))


def _word_count(text):
    return len([word for word in text.replace('-', ' ').split() if word])


def fit_script(text, limit=MAX_SCRIPT_WORDS):
    """Trim a script to the words a 10-second clip can actually show."""
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    trimmed = ' '.join(words[:limit]).rstrip(',;:')
    if not trimmed.endswith(('.', '!', '?')):
        trimmed += '.'
    return trimmed


def hashtags(platform, tags, limit):
    pool = HASHTAG_POOLS.get(platform, [])
    ordered = []
    for tag in list(tags) + list(pool):
        clean = ''.join(ch for ch in str(tag).lower() if ch.isalnum())
        if clean and clean not in ordered:
            ordered.append(clean)
    return ordered[:limit]


def trim(text, limit):
    """Trim at a word boundary so a caption never ends mid-word."""
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(' ', 1)[0].rstrip(' ,;:-')
    return (cut or text[:limit - 1].rstrip()) + '…'


def platform_copy(platform, topic, angle, tags, brand_tag='stratevo'):
    if platform == 'tiktok':
        caption = '{hook} {check}. Follow for sourcing checks.'.format(
            hook=_web_safe(angle['hook']), check=_title(_web_safe(topic['check'])))
        caption = trim(caption, 145)
        return {'caption': caption, 'hashtags': hashtags('tiktok', list(tags) + [brand_tag], 5)}
    caption = '{topic}\n\n{point_cap}.\n\nWhat to do: {check}.\n\nSave this before your next supplier call.'.format(
        topic=_web_safe(topic['topic']), point_cap=_title(_web_safe(topic['point'])),
        check=_web_safe(topic['check']))
    return {'caption': trim(caption, 2100), 'hashtags': hashtags('instagram', list(tags) + [brand_tag], 12)}


def video_prompt(topic, angle):
    scene = _web_safe(topic['scene'])
    return ('{scene}. {motion}. {style}').format(scene=_title(scene), motion=angle['motion'], style=STYLE)[:900]


def render_hook(pattern, topic):
    short = topic.get('short', topic['topic'].lower())
    return _web_safe(pattern.format(short=short, short_cap=short[:1].upper() + short[1:]))


def pick_hook(topic, angle, used=()):
    """Deterministically choose an unused hook pattern for this topic/angle."""
    pool = angle['hooks']
    start = _seed_value(topic['key'] + angle['key']) % len(pool)
    for offset in range(len(pool)):
        candidate = render_hook(pool[(start + offset) % len(pool)], topic)
        if candidate not in used:
            return candidate
    return render_hook(pool[start], topic) + ' ' + topic['short'] + '.'


def build_idea(topic, angle, position, hook_override=''):
    script = fit_script(angle['script'].format(
        point=_web_safe(topic['point']), point_cap=_web_safe(topic['point'])[:1].upper() + _web_safe(topic['point'])[1:],
        check=_web_safe(topic['check']), check_cap=_web_safe(topic['check'])[:1].upper() + _web_safe(topic['check'])[1:]))
    hook = hook_override or pick_hook(topic, angle)
    tiktok = platform_copy('tiktok', topic, dict(angle, hook=hook), topic['tags'])
    instagram = platform_copy('instagram', topic, dict(angle, hook=hook), topic['tags'])
    return {
        'position': position,
        'topic': topic['topic'],
        'angle': angle['key'],
        'hook': hook,
        'script': _web_safe(script),
        'video_prompt': video_prompt(topic, angle),
        'negative_prompt': 'text, words, captions, logo, watermark, distorted faces, extra fingers, blurry',
        'tiktok_caption': tiktok['caption'],
        'tiktok_hashtags': ' '.join('#' + tag for tag in tiktok['hashtags']),
        'instagram_caption': instagram['caption'],
        'instagram_hashtags': ' '.join('#' + tag for tag in instagram['hashtags']),
    }


def generate(seed, count=40):
    """Return ``count`` distinct ideas. Deterministic for a given seed."""
    if not 1 <= int(count) <= 200:
        raise ValueError('A series must contain between 1 and 200 ideas.')
    count = int(count)
    combos = [(topic, angle) for angle in ANGLES for topic in TOPICS]
    start = _seed_value(seed) % len(combos)
    # Rotate through the combination space with a coprime stride so the batch
    # spreads across topics and angles without repeating a pair.
    stride = 7 if len(combos) % 7 else 11
    chosen, seen = [], set()
    cursor = start
    while len(chosen) < count:
        topic, angle = combos[cursor % len(combos)]
        pair = (topic['key'], angle['key'])
        if pair not in seen:
            seen.add(pair)
            chosen.append((topic, angle))
        cursor += stride
        if len(seen) >= len(combos) and len(chosen) < count:
            raise ValueError('Not enough distinct ideas available for the requested count.')
    ideas, used = [], set()
    for index, (topic, angle) in enumerate(chosen):
        hook = pick_hook(topic, angle, used)
        used.add(hook)
        ideas.append(build_idea(topic, angle, index + 1, hook_override=hook))
    return ideas


def estimate_seconds(script):
    """Rough on-screen reading time, used to sanity-check clip length."""
    return round(_word_count(script) / READING_WORDS_PER_SECOND, 2)
