"""The 18-part kinetic typography series, as creative data.

Every episode is the same seven-scene template, which is what makes the format
recognisable and cheap to render: only the copy changes. The copy below is the
client's own 18-variation list, kept verbatim so the rendered videos match the
brief they wrote.

Fields
------
hook         the contrarian opening line, spoken and slammed on screen
illusions    the three "looks credible" surface signals (scene 2 tiles, scene 3
             chat bubbles)
questions    the three fear-stacking questions (scene 5), full screen
left/right   the equation payoff (scene 6): LEFT ≠ RIGHT
"""

SERIES_NAME = 'Profile is not proof'

EPISODES = [
    {
        'hook': 'A professional profile is not a professional supplier.',
        'illusions': ['Verified badge', 'Great photos', 'Fast replies'],
        'questions': ['WHO ACTUALLY MAKES THE PRODUCT?',
                      'IS THE PRODUCTION CONSISTENT?',
                      'DOES THE SAMPLE MATCH THE SHIPMENT?'],
        'left': 'PROFILE', 'right': 'PROOF',
    },
    {
        'hook': "A golden verified badge is not a factory audit.",
        'illusions': ['Paid directory status', 'Five-star badge', 'Shiny storefront'],
        'questions': ['DID THEY JUST PAY THREE THOUSAND FOR A BADGE?',
                      'ARE THEY A TRADING COMPANY?',
                      'HAVE THEY EVER BEEN INSPECTED?'],
        'left': 'BADGE', 'right': 'VETTED',
    },
    {
        'hook': "A perfect sample doesn't mean a perfect bulk order.",
        'illusions': ['Flawless prototype', 'Luxury packaging', 'Fast air shipping'],
        'questions': ['WAS IT HAND-MADE BY ONE MASTER TECH?',
                      'WILL MASS PRODUCTION CUT CORNERS?',
                      'ARE BULK MATERIALS SWAPPED?'],
        'left': 'SAMPLE', 'right': 'SHIPMENT',
    },
    {
        'hook': 'The lowest quote is rarely the lowest cost.',
        'illusions': ['Rock-bottom price', 'Zero tooling fee', 'Instant discount'],
        'questions': ['WHAT HAPPENS WHEN 30 PERCENT ARRIVE DEFECTIVE?',
                      'WHERE ARE THE HIDDEN PORT FEES?',
                      'WHY IS THE MATERIAL GRADE MISSING?'],
        'left': 'QUOTE', 'right': 'COST',
    },
    {
        'hook': 'A massive product catalog is a massive red flag.',
        'illusions': ['Ten thousand SKUs', 'Every category', 'Trendy 3D renders'],
        'questions': ['HOW CAN ONE PLANT MAKE EVERYTHING?',
                      'WHO IS THE REAL MANUFACTURER?',
                      'WHAT IS THE MIDDLEMAN MARKUP?'],
        'left': 'CATALOG', 'right': 'FACTORY',
    },
    {
        'hook': "Fast replies don't build your product.",
        'illusions': ['Two-minute texts', 'Friendly emojis', '24/7 sales chat'],
        'questions': ['DOES SALES EVER VISIT THE FLOOR?',
                      'WILL THEY GHOST ON DEFECTS?',
                      'WHO MANAGES THE ASSEMBLY LINE?'],
        'left': 'FAST CHAT', 'right': 'GOOD QC',
    },
    {
        'hook': "An ISO certificate PDF doesn't stop defects.",
        'illusions': ['Stamped PDF files', 'Wall plaques', 'Compliance logos'],
        'questions': ['IS THE REG NUMBER PHOTOSHOPPED?',
                      'DID THE CERT EXPIRE TWO YEARS AGO?',
                      'DOES IT COVER YOUR PRODUCT LINE?'],
        'left': 'CERTIFICATE', 'right': 'COMPLIANCE',
    },
    {
        'hook': 'We make for big brands is sourcing\u2019s easiest lie.',
        'illusions': ['Famous logos', 'Retail boxes', 'Name dropping'],
        'questions': ['DID THEY JUST MAKE THE POLYBAG?',
                      'CAN THEY SHOW A BILL OF LADING?',
                      'IS IT AN UNAUTHORISED REPLICA?'],
        'left': 'LOGO DROP', 'right': 'CREDIBILITY',
    },
    {
        'hook': 'A low MOQ can trap your cash flow.',
        'illusions': ['Fifty unit minimum', 'Zero setup cost', 'Ready stock'],
        'questions': ['IS IT LEFTOVER REJECTED STOCK?',
                      'CAN THEY SCALE TO TEN THOUSAND UNITS?',
                      'WHO ACTUALLY OWNS THE MOLD?'],
        'left': 'LOW MOQ', 'right': 'SCALABLE',
    },
    {
        'hook': 'A factory tour video can be rented in ten minutes.',
        'illusions': ['Drone shots', 'Clean assembly lines', 'Busy workers'],
        'questions': ['WHOSE NAME IS ON THE GATE?',
                      'WHY ARE THE SHIPPING LABELS BLURRED?',
                      'ARE THOSE WORKERS ON THEIR PAYROLL?'],
        'left': 'VIDEO TOUR', 'right': 'OWNERSHIP',
    },
    {
        'hook': 'One hundred percent inspection usually means a two-minute glance.',
        'illusions': ['Checkmark sheets', 'Thumbs-up photos', 'Sealed cartons'],
        'questions': ['DID THEY TEST OR JUST COUNT BOXES?',
                      'WHAT IS THEIR AQL TOLERANCE?',
                      'WHO INSPECTS THE INSPECTOR?'],
        'left': 'CHECKLIST', 'right': 'INSPECTION',
    },
    {
        'hook': 'A thirty percent deposit without a contract is a donation.',
        'illusions': ['Proforma invoice', 'Bank wire details', 'Fast start promise'],
        'questions': ['IS IT ENFORCEABLE IN A LOCAL COURT?',
                      'ARE LATE PENALTIES DEFINED?',
                      'WHO LEGALLY OWNS YOUR IP?'],
        'left': 'INVOICE', 'right': 'PROTECTION',
    },
    {
        'hook': 'On-time shipping means nothing if it fails customs.',
        'illusions': ['Loaded containers', 'Tracking numbers', 'Vessel departure'],
        'questions': ['ARE THE HS CODES ACCURATE?',
                      'IS THE LAB TESTING VALID FOR YOUR PORT?',
                      'WILL CUSTOMS SEIZE THE CONTAINER?'],
        'left': 'SHIPPED', 'right': 'DELIVERED',
    },
    {
        'hook': 'Ten years on a platform is not ten years of manufacturing.',
        'illusions': ['Ten year badge', 'Old account age', 'Transaction history'],
        'questions': ['WAS THE ACCOUNT BOUGHT LAST MONTH?',
                      'DID COMPANY OWNERSHIP CHANGE?',
                      'HAVE THEY MADE YOUR CATEGORY?'],
        'left': 'TENURE', 'right': 'EXPERIENCE',
    },
    {
        'hook': '3D renders hide fatal engineering flaws.',
        'illusions': ['Photoreal 360 renders', 'Exploded views', 'Sleek shaders'],
        'questions': ['CAN THIS BE INJECTION MOLDED?',
                      'WILL THE HINGES SNAP AFTER TEN USES?',
                      'HAS TOLERANCE TESTING BEEN RUN?'],
        'left': 'RENDER', 'right': 'ENGINEERED',
    },
    {
        'hook': 'Unverified eco claims are lawsuits waiting to happen.',
        'illusions': ['Green leaf icons', 'One hundred percent recycled', 'Kraft boxes'],
        'questions': ['WHERE DID THE RESIN ORIGINATE?',
                      'CAN THEY TRACE THE BATCH NUMBER?',
                      'WILL IT PASS LAB SPECTROSCOPY?'],
        'left': 'GREEN CLAIM', 'right': 'CERTIFIED',
    },
    {
        'hook': 'A domestic warehouse address is not domestic manufacturing.',
        'illusions': ['Local map pin', 'Local phone number', 'Domestic returns'],
        'questions': ['IS IT JUST A FORWARDING HUB?',
                      'ARE YOU PAYING LOCAL FOR IMPORTS?',
                      'WHAT HAPPENS WHEN TARIFFS HIT?'],
        'left': 'LOCAL PIN', 'right': 'LOCAL MADE',
    },
    {
        'hook': 'Trade show booths are built to impress, not to produce.',
        'illusions': ['Huge expo display', 'Fluent sales reps', 'Glossy brochures'],
        'questions': ['DID THEY RENT IT TO BROKER DEALS?',
                      'DO THE ENGINEERS WORK FOR THEM?',
                      'WHAT DOES THE PLANT LOOK LIKE?'],
        'left': 'BIG BOOTH', 'right': 'REAL PLANT',
    },
    {
        'hook': 'No problem we can make it is manufacturing\u2019s deadliest phrase.',
        'illusions': ['Instant yes to specs', 'Zero pushback', 'Fast deal'],
        'questions': ['WHY DIDN\u2019T ENGINEERS ASK QUESTIONS?',
                      'ARE THEY GUESSING YOUR TOLERANCES?',
                      'WILL THEY SUBCONTRACT YOUR ORDER?'],
        'left': 'EASY YES', 'right': 'CAPABILITY',
    },
]

# Scene 4 flash words: what a profile cannot do. Shared by every episode.
FLASH_WORDS = ['A PROFILE', 'CAN\u2019T', 'SHOW', 'THINGS']

TAGS = ('#sourcing #chinasourcing #suppliercheck #importing #b2b '
        '#productdevelopment #qualitycontrol #manufacturing #stratevo')

CLOSING_VO = 'Strat Evo. Find, vet, verify.'


def episode(index):
    """Return one episode by 1-based index, cycling through the series."""
    if not EPISODES:
        raise ValueError('The kinetic series has no episodes.')
    return EPISODES[(max(1, int(index)) - 1) % len(EPISODES)]


def voiceover(episode_data):
    """The narration for one episode, in scene order.

    MiniMax accepts ``<#x#>`` pause tags, so the whole read is a single cheap
    request whose pauses land on the scene cuts.
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


def _question_phrase(text):
    cleaned = text.strip().rstrip('?').lower()
    return cleaned + '?'


def caption(episode_data, index):
    hook = episode_data['hook'].rstrip('.')
    left, right = episode_data['left'].title(), episode_data['right'].lower()
    return ('%s\n\n%s \u2260 %s\n\nThree checks before you pay a deposit. '
            'Full breakdown at stratevo.online' % (hook, left, right))


def description(episode_data):
    left, right = episode_data['left'].title(), episode_data['right'].lower()
    return ('%s\n\n%s \u2260 %s\n\n%s\n\n%s' % (
        episode_data['hook'], left, right,
        '\n'.join('- ' + item for item in episode_data['questions']), TAGS))


def script(episode_data):
    """The spoken/on-screen body as one paragraph (used for platform copy)."""
    return ' '.join(item.strip().rstrip('?').lower() + '?' for item in episode_data['questions'])


def copy_for(index):
    """Everything the pipeline needs to store one episode as a content idea."""
    data = episode(index)
    left, right = data['left'].title(), data['right'].lower()
    return {
        'topic': '%s vs %s' % (left.lower(), right),
        'angle': 'kinetic typography',
        'hook': data['hook'],
        'script': script(data),
        'video_prompt': 'Rendered in code: %d s kinetic typography episode %d (%s \u2260 %s).'
                        % (19, index, left, right),
        'negative_prompt': '',
        'tiktok_caption': caption(data, index),
        'tiktok_hashtags': TAGS,
        'instagram_caption': caption(data, index),
        'instagram_hashtags': TAGS,
    }
