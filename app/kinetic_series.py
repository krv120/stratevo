"""The 19-episode kinetic series that markets the whole StratEvo business.

Every episode is the same seven-scene spine at 20.60 s, but scenes 1-3 are drawn
from one of four layouts, chosen per episode, so the series does not repeat the
same "PROFILE / SUBSCRIBE" mockup:

====  ==================================================================
A     Product / audit showcase: audit dashboard, 3-step verification radar,
      escrow checklist
B     Cost and ROI: bank transfer screen paused by StratEvo, quote vs landed
      cost bars, hidden defect math
C     Founder story / red flag: supplier alert chat, the missing documents,
      what StratEvo verifies before shipping
D     Contrarian breakdown: the kinetic card + glass refraction layout, every
      header and label read from the episode payload
====  ==================================================================

Scenes 5-7 (the three questions, the equation and the chrome sign-off) are shared
by every layout. Each episode dict carries:

``episode_data``    copy, on-screen strings, voice script (MiniMax ``<#x#>`` and
                    generic ``<break/>`` form) and the scene beats
``audio_blueprint`` 26 timestamped foley layers plus the music bed spec
``metadata``        comment-bait caption, hashtags, layout, runtime, CTA

Nothing here touches the network; narration is a separate, keyed step
(:mod:`app.kinetic_voice`).
"""

SERIES_NAME = 'Find. Vet. Verify.'

DURATION = 20.60
FPS = 30
SAMPLE_RATE = 48000
TAIL = {'start_time': 19.90, 'duration': 0.70}

TAGS = ('#sourcing #supplierverification #china sourcing #factoryaudit #importing '
        '#b2b #qualitycontrol #manufacturing #stratevo #findvetverify').replace(' ', '')

CLOSING_VO = 'Strat Evo. Find, vet, verify.'

SCENES = (
    ('hook', 0.00, 2.60),
    ('illusions', 2.60, 6.70),
    ('chat', 6.70, 8.30),
    ('wipe', 8.30, 9.90),
    ('questions', 9.90, 13.60),
    ('equation', 13.60, 16.50),
    ('signoff', 16.50, 20.60),
)

MUSIC = {
    'style': 'dark B2B deep house, lo-fi',
    'bpm': 100,
    'key': 'A minor',
    'layers': ['kick', 'sub-bass', 'closed hat', 'warm pad', 'vinyl noise'],
    'level_db': -19.0,
    'notes': ('Sits under the narration, never on top of it: sidechain-style duck of '
              'the pad on every kick, sub-bass root on A1, hats on the off-beat, vinyl '
              'floor noise at -34 dB so silence never sounds digital.'),
}

# ---------------------------------------------------------------------------
# foley spine (identical timings for every episode; layer 7 is swapped for a
# per-episode accent so the transients never sound copy-pasted)
# ---------------------------------------------------------------------------
SFX_SPINE = (
    (0.00, 0.90, 'hum', 'power-on-hum',
     'Deep 42 Hz sine power-on hum with a slow 6 Hz beating drift, mono, fading in '
     'over 120 ms, the room tone under a phone waking up.'),
    (0.80, 0.12, 'tick', 'ui-wake-tick',
     'Phone screen wake tick, 1 ms click plus a 120 ms damped 2.2 kHz ping, dry, quiet.'),
    (1.35, 0.45, 'sub', 'hook-sub-slam',
     'Single 55 Hz sub-bass slam under a headline landing: 30 ms attack, pitch drop '
     'from 90 Hz to 55 Hz, 450 ms decay, saturated but clean.'),
    (2.60, 0.35, 'whoosh', 'scene-whoosh',
     'Tight reverse whoosh into the next scene: filtered pink noise sweeping 900 Hz to '
     '3 kHz over 350 ms, hard start on the cut.'),
    (3.42, 0.18, 'tick', 'panel-tick-1',
     'Soft UI toggle click, 1.2 ms transient plus 180 ms body, recorded close, dry.'),
    (4.24, 0.18, 'tick', 'panel-tick-2',
     'Second UI toggle click, slightly brighter than the first, dry.'),
    (5.06, 0.18, 'tick', 'panel-tick-3',
     'Third UI toggle click, slightly darker, dry; the three should feel like a rhythm.'),
    (5.88, 0.35, 'shimmer', 'data-shimmer',
     'Glassy shimmer: three sine partials at 1.6, 2.4 and 3.9 kHz with micro-detune, '
     '350 ms crescendo, icy, no melody.'),
    (6.70, 0.35, 'whoosh', 'scene-whoosh-2',
     'Quick upward noise sweep into scene three, 250 ms, plus a soft 8-bit blip.'),
    (7.50, 0.14, 'tick', 'alert-pop',
     'Single notification pop, 1 kHz sine with 60 ms decay, phone speaker.'),
    (8.30, 0.40, 'glass', 'glass-refraction',
     'Glass flute refraction hit: 3.2 kHz sine plus a 900 Hz body, 40 ms attack, 400 ms '
     'shimmering decay.'),
    (9.10, 0.30, 'glass', 'refraction-flash',
     'Sharper glass flash, 4.6 kHz partial with a 200 ms tail, one hit only.'),
    (9.90, 0.20, 'tick', 'danger-tick',
     'Mechanical clock tick pitched down 400 Hz, 20 ms, dry: a countdown under a question.'),
    (10.64, 0.30, 'heartbeat', 'heartbeat-1',
     'Low heartbeat thud, 50 Hz sine, 12 ms attack, 300 ms decay, close and dry.'),
    (11.38, 0.30, 'heartbeat', 'heartbeat-2',
     'Second heartbeat thud, 3 dB quieter and 10 ms shorter than the first.'),
    (12.12, 0.50, 'riser', 'tension-riser',
     'Reverse breath riser: filtered white noise, highpass 300 Hz sweeping to 2 kHz over '
     '500 ms, airy, no pitch.'),
    (12.86, 0.40, 'taiko', 'taiko-soft',
     'Soft taiko hit, 70 Hz skin tone, 15 ms attack, 400 ms decay, medium room.'),
    (13.60, 0.40, 'taiko', 'equation-hit-1',
     'Hard taiko hit on the equation reveal: 70 Hz body, 200 Hz beater click, tight room.'),
    (14.32, 0.40, 'taiko', 'equation-hit-2',
     'Second taiko hit, 8% lower in pitch than the first, identical room.'),
    (15.05, 0.40, 'metal', 'metal-ring',
     'Struck metal ring: 640 Hz and 1.9 kHz inharmonic partials, 450 ms decay.'),
    (15.78, 0.35, 'sub', 'equation-sub-drop',
     'Sub drop under the equation settling: 80 Hz falling to 45 Hz over 350 ms, clean.'),
    (16.50, 0.60, 'bloom', 'chrome-bloom',
     'Chrome bloom: wide 220 Hz sine swell plus 3 kHz sparkle, 600 ms, rising filter.'),
    (17.35, 0.45, 'sheen', 'sheen-sweep',
     'Specular sheen sweep across a chrome logo: 120 ms noise sweep through a bandpass at '
     '2.8 kHz, smooth, never hissy.'),
    (18.20, 0.25, 'tick', 'logo-latch',
     'Mechanical latch click, 1.5 ms transient plus 250 ms metallic settle, small and precise.'),
    (19.05, 0.60, 'chime', 'cta-chime',
     'Soft two-note chime, 880 Hz then 1.32 kHz, 600 ms bell decay, warm, low level.'),
    (19.90, 0.70, 'tail', 'lowpass-tail',
     'Lowpass tail at 400 Hz closing the clip: the whole bed filtered down, 700 ms fade to '
     'silence, no new transient, loop-ready into the opening hum.'),
)

SIGNATURE_SFX = (
    (4.60, 0.30, 'tick', 'paper-tear', 'Short paper tear accent, 300 ms, dry.'),
    (4.60, 0.40, 'shimmer', 'document-flick', 'Binder page flick with a glassy tail, 400 ms.'),
    (5.60, 0.30, 'tick', 'envelope-open', 'Envelope flap opening, 300 ms, dry.'),
    (7.90, 0.20, 'tick', 'typing-burst', 'Four fast keyboard clicks, 200 ms total.'),
    (11.80, 0.30, 'heartbeat', 'breath-gasp', 'A single sharp inhale, 300 ms, close mic.'),
    (12.40, 0.30, 'tick', 'coin-drop', 'One coin dropped on glass, 300 ms, dry.'),
    (14.80, 0.35, 'metal', 'cash-register', 'Single till drawer ping, 350 ms, small room.'),
    (17.80, 0.30, 'chime', 'badge-ping', 'Small verification ping, 300 ms, phone speaker.'),
    (18.70, 0.35, 'tail', 'room-drop', 'A quiet room drop, 350 ms, low thud, dry.'),
)

FEAR_LADDER = (
    'operational blindspot: you cannot see who really makes the product',
    'quality failure: the batch that ships is not the batch you approved',
    'catastrophic loss: the money, the cargo, or the liability is yours alone',
)

# ---------------------------------------------------------------------------
# the episodes
# ---------------------------------------------------------------------------
# (layout, hook, subject, scenes, illusions, flash, questions, left, right, bait)
# Scene payloads are plain dicts read by app/kinetic.py; every string a viewer
# sees comes from here, never from the renderer.
_EPISODES = (
    # ---- 1-4: product and outcome showcases ------------------------------
    ('A',
     'Here is what a real factory audit catches before you wire $20,000.',
     'a real factory audit',
     {'one': {'title': 'STRATEVO AUDIT REPORT', 'ref': 'SUPPLIER #A-1841',
              'rows': [('BUSINESS LICENSE', 'NO FACTORY SCOPE'),
                       ('FLOOR INSPECTION', 'DECLINED TWICE'),
                       ('SAMPLE LOCK', 'NEVER AGREED')],
              'before': 'FAILED', 'after': 'NOT WIRED'},
      'two': {'title': 'THREE-STEP VERIFICATION',
              'steps': ['FACTORY OWNERSHIP', 'LAB COMPLIANCE', 'PRODUCTION LINE']},
      'three': {'title': 'ESCROW RELEASE CHECKLIST',
                'items': ['DEED MATCHES THE SELLER', 'AQL 2.5 PASSED ON SITE',
                          'SAMPLE LOCK SIGNED', 'REPORT FILED TO YOU']}},
     ['Paid badge', 'Polished deck', 'Fast quote'],
     ['FIND.', 'VET.', 'VERIFY.', 'WIRE.'],
     ['Who owns the building?', 'Will the line run your spec?', 'Who refunds $20,000?'],
     'AN AUDIT', 'AN ASSUMPTION',
     'Half of what you call a factory is a trading desk with a nice logo.'),
    ('A',
     'How we find the actual factory hiding behind 10 middlemen.',
     'ten middlemen',
     {'one': {'title': 'SUPPLY CHAIN MAP', 'ref': '10 LAYERS, 1 PLANT',
              'rows': [('TRADER #1', 'NO PLANT'), ('TRADER #2', 'NO PLANT'),
                       ('THE FACTORY', 'FOUND')],
              'before': '10 LAYERS', 'after': '1 PLANT'},
      'two': {'title': 'HOW WE TRACE IT',
              'steps': ['COMPANY REGISTRY', 'CUSTOMS RECORDS', 'PLANT WALK']},
      'three': {'title': 'DIRECT-TO-PLANT TERMS',
                'items': ['CONTRACT WITH THE PLANT', 'PAYMENT TO THE PLANT',
                          'QC AT THE PLANT', 'NO MIDDLE MARGIN']}},
     ['Ten-year badge', 'Trade history', 'Slick catalog'],
     ['TEN', 'MIDDLEMEN', 'ONE', 'PLANT'],
     ['Who signs the contract?', 'Who actually owns the line?', 'Who takes the margin?'],
     'MIDDLEMEN', 'A FACTORY',
     'If five "factories" answer you in a day, you are talking to one trader five times.'),
    ('C',
     'This 48-hour check saved a founder $42,000 in dead inventory.',
     'a forty-two thousand dollar save',
     {'one': {'app': 'SUPPLIER', 'time': 'now',
              'messages': ['Container held at customs.',
                           'Need $8,400 today to release.']},
      'two': {'title': 'THREE DOCUMENTS MISSING',
              'items': ['ORIGINAL BILL OF LADING', 'CE TEST REPORT', 'IMPORTER OF RECORD']},
      'three': {'title': 'WHAT WE CHECKED FIRST',
                'items': ['CUSTOMS PRE-CLEARANCE', 'LAB TEST VERIFIED',
                          'ESCROW RELEASED ON PASS']}},
     ['Fast shipping', 'Good price', 'Long warranty'],
     ['48', 'HOURS', '$42K', 'SAVED'],
     ['Who releases the container?', 'Which document is fake?', 'Who eats $42,000 in stock?'],
     'A CHECK', 'A LOSS',
     'The container was already on the water when the documents stopped being true.'),
    ('A',
     'Stop guessing if your supplier is real. Watch us verify a plant in 3 steps.',
     'a three-step plant verification',
     {'one': {'title': 'PLANT VERIFICATION', 'ref': 'LIVE WALK-THROUGH',
              'rows': [('GATE SIGN', 'MATCHES CONTRACT'),
                       ('LINE', 'RUNNING YOUR SPEC'),
                       ('SAMPLES', 'LOCKED ON SITE')],
              'before': 'UNVERIFIED', 'after': 'VERIFIED'},
      'two': {'title': 'FIND, VET, VERIFY',
              'steps': ['FIND THE PLANT', 'VET THE EVIDENCE', 'VERIFY ON SITE']},
      'three': {'title': 'THE REPORT YOU GET',
                'items': ['SIGNED SITE REPORT', 'PHOTO AND VIDEO LOG',
                          'AQL INSPECTION DATA', 'ESCROW RELEASE']}},
     ['Directory listing', 'Five star badge', 'Nice brochure'],
     ['STOP', 'GUESSING', 'START', 'VERIFYING'],
     ['Can they prove the plant?', 'Will the line match the sample?', 'Who holds the deposit?'],
     'GUESSING', 'VERIFYING',
     'A factory that cannot show you its gate has never opened it for a buyer.'),
    # ---- 5-8: specific numbers and data ----------------------------------
    ('B',
     'We audited 300+ suppliers. 64% were actually trading companies.',
     'three hundred audited suppliers',
     {'one': {'label': 'WIRE TRANSFER', 'amount': '$25,000', 'beneficiary': 'TRADING CO. #2210',
              'reference': 'DEPOSIT / 30%', 'pause': 'PAUSED BY STRATEVO'},
      'two': {'title': 'WHAT THE AUDIT FOUND',
              'bars': [('TRADING COMPANIES', 64, '64%', 'bad'),
                       ('REAL PLANTS', 36, '36%', 'good')]},
      'three': {'title': 'WHERE THE 64% ENDS',
                'rows': ['No deed in their name', 'No plant behind the badge',
                         'All the risk on you'],
                'total': 'VET BEFORE YOU WIRE'}},
     ['Golden badge', 'Five stars', 'Fast quotes'],
     ['300', 'AUDITS', '64%', 'TRADERS'],
     ['Do they own a plant at all?', 'Who runs the actual line?', 'Who refunds a fake order?'],
     'ACCOUNTS', 'FACTORIES',
     'Sixty-four percent of "factories" on the biggest directories do not own a machine.'),
    ('A',
     'The 3 contract clauses that prevent 90% of manufacturing scams.',
     'three contract clauses',
     {'one': {'title': 'CONTRACT REVIEW', 'ref': '3 CLAUSES MISSING',
              'rows': [('IP OWNERSHIP', 'NOT DEFINED'), ('LATE PENALTY', 'NOTHING'),
                       ('JURISDICTION', 'THEIR CITY')],
              'before': 'UNSAFE', 'after': 'AMENDED'},
      'two': {'title': 'THE THREE CLAUSES',
              'steps': ['OWNERSHIP', 'PENALTIES', 'JURISDICTION']},
      'three': {'title': 'SIGNED BEFORE THE DEPOSIT',
                'items': ['TOOLING IN YOUR NAME', 'LATE DELIVERY PENALTY',
                          'YOUR COURT, YOUR LAW', 'EXIT AND TRANSFER']}},
     ['Proforma invoice', 'Bank details', 'Fast start'],
     ['3', 'CLAUSES', '90%', 'BLOCKED'],
     ['Who owns the tooling?', 'What happens when they are late?', 'Where do you sue them?'],
     'TRUST', 'TERMS',
     'A supplier who will not sign a penalty clause is telling you the truth about delivery.'),
    ('B',
     'Why a 5% cheaper quote ends up costing 40% more at the port.',
     'a five percent cheaper quote',
     {'one': {'label': 'WIRE TRANSFER', 'amount': '$9,800', 'beneficiary': 'LOWEST BIDDER',
              'reference': 'QUOTE / FOB', 'pause': 'PAUSED BY STRATEVO'},
      'two': {'title': 'QUOTE VERSUS LANDED',
              'bars': [('VETTED QUOTE', 72, '$13,700', 'good'),
                       ('CHEAP QUOTE', 100, '$19,200', 'bad')]},
      'three': {'title': 'WHERE THE EXTRA 40% LIVES',
                'rows': ['Port and demurrage fees', 'Duty reclassification', 'Rework on arrival'],
                'total': '$19,200 REAL COST'}},
     ['Lowest price', 'Free shipping', 'Zero tooling'],
     ['5%', 'CHEAPER', '40%', 'WORSE'],
     ['What is excluded from the quote?', 'Who pays the port fees?', 'Who pays for the rework?'],
     'A QUOTE', 'A LANDED COST',
     'The cheapest quote is priced to the port, not to your warehouse floor.'),
    ('A',
     '4 checks every buyer must run before paying a 30% deposit.',
     'a thirty percent deposit',
     {'one': {'title': 'PRE-DEPOSIT CHECK', 'ref': '4 CHECKS',
              'rows': [('COMPANY DEED', 'UNVERIFIED'), ('BANK NAME', 'MISMATCH'),
                       ('PAST BUYERS', 'NO REFERENCES')],
              'before': 'AT RISK', 'after': 'CLEARED'},
      'two': {'title': 'THE FOUR CHECKS',
              'steps': ['DEED', 'BANK', 'REFERENCES', 'INSPECTION']},
      'three': {'title': 'DEPOSIT PROTECTION',
                'items': ['ESCROW INSTEAD OF WIRE', 'MILESTONE RELEASE',
                          'PENALTY CLAUSE', 'SITE VISIT BOOKED']}},
     ['30% discount', 'Fast start', 'Trusted supplier'],
     ['4', 'CHECKS', '1', 'DEPOSIT'],
     ['Whose name is on the bank?', 'Who bought from them before?', 'Who holds the money if it fails?'],
     'A DEPOSIT', 'SECURITY',
     'A wire transfer is not protection. It is a donation with a reference number.'),
    # ---- 9-12: niche callouts and urgency ---------------------------------
    ('C',
     'If you are launching a physical product this year, do not skip this step.',
     'your launch window',
     {'one': {'app': 'PROJECT CHAT', 'time': '2 days ago',
              'messages': ['Launch is in 6 weeks.', 'Factory just went quiet.']},
      'two': {'title': 'WHAT THAT COSTS YOU',
              'items': ['THE TOOLING DEPOSIT', 'THE LAUNCH WINDOW', 'THE RETAIL SLOT']},
      'three': {'title': 'WHAT WE DO FIRST',
                'items': ['VET BEFORE TOOLING', 'ESCROW MILESTONES',
                          'BACKUP PLANT MAPPED']}},
     ['Big factory', 'Years online', 'Great samples'],
     ['LAUNCH', 'WINDOW', 'VET', 'FIRST'],
     ['Who owns the tooling?', 'What if the plant vanishes?', 'Who eats the delay?'],
     'A LAUNCH', 'A GAMBLE',
     'Your launch date is decided by the slowest supplier you did not check.'),
    ('C',
     'E-commerce founders: stop trusting golden samples until you ask this.',
     'a golden sample',
     {'one': {'app': 'SUPPLIER', 'time': 'now',
              'messages': ['Sample looks perfect.', 'Bulk will match. Trust me.']},
      'two': {'title': 'WHAT THE SAMPLE HIDES',
              'items': ['HAND BUILT BY A TECH', 'A DIFFERENT MOLD', 'NO AQL TEST']},
      'three': {'title': 'WHAT WE VERIFY',
                'items': ['SAME LINE, SAME MOLD', 'AQL 2.5 AT THREE STAGES',
                          'SAMPLE LOCK SIGNED']}},
     ['Flawless sample', 'Luxury packaging', 'Free air freight'],
     ['A SAMPLE', 'IS NOT', 'A', 'SHIPMENT'],
     ['Who made the sample?', 'Will the mold hold at scale?', 'Who eats 30% defects?'],
     'SAMPLE', 'SHIPMENT',
     'The sample was built by the best technician they have. You will never meet him.'),
    ('C',
     'If your supplier says no problem to every custom spec, run.',
     'an instant yes',
     {'one': {'app': 'SUPPLIER', 'time': 'now',
              'messages': ['No problem, we can make it.', 'Send the deposit today.']},
      'two': {'title': 'WHY THAT IS A WARNING',
              'items': ['NO ENGINEER ASKED', 'NO TOLERANCE REVIEW', 'NO DFM FEEDBACK']},
      'three': {'title': 'WHAT A REAL PLANT DOES',
                'items': ['ASKS FOR DRAWINGS', 'FLAGS TOLERANCES', 'QUOTES TOOLING']}},
     ['Instant yes', 'Zero pushback', 'Fast deal'],
     ['NO', 'PROBLEM', 'MEANS', 'RUN'],
     ['Why did no engineer ask?', 'Are they guessing tolerances?', 'Who eats a rejected lot?'],
     'AN EASY YES', 'CAPABILITY',
     'A supplier who never pushes back on your spec has already subcontracted your order.'),
    ('C',
     'Before you reorder your best-selling SKU, check who owns your mold.',
     'your mold',
     {'one': {'app': 'SUPPLIER', 'time': 'now',
              'messages': ['New price for the reorder: +22%.', 'Or we keep the mold.']},
      'two': {'title': 'WHAT YOU NEVER SIGNED',
              'items': ['MOLD OWNERSHIP', 'TOOLING RECEIPT', 'EXIT CLAUSE']},
      'three': {'title': 'WHAT WE SECURE',
                'items': ['TOOLING IN YOUR NAME', 'RECEIPT ON PAYMENT',
                          'TRANSFER CLAUSE']}},
     ['Loyal supplier', 'Long history', 'Best price'],
     ['WHO', 'OWNS', 'YOUR', 'MOLD'],
     ['Who holds the tooling title?', 'What is the exit price?', 'Who can move the mold?'],
     'A MOLD', 'A HOSTAGE',
     'The day your SKU starts selling is the day your mold becomes their leverage.'),
    # ---- 13-18: contrarian and hidden risk -------------------------------
    ('D',
     'A professional profile is not a professional supplier.',
     'a professional profile',
     {'one': {'device': 'PROFILE', 'sub': 'VERIFIED BADGE', 'button': 'SUBSCRIBE'},
      'two': {'title': 'LOOKS CREDIBLE',
              'cards': ['Verified badge', 'Great photos', 'Fast replies']},
      'three': {'heading': 'FAST REPLIES',
                'messages': ['We are the factory.', 'Best price for you.', 'Send deposit.']}},
     ['Verified badge', 'Great photos', 'Fast replies'],
     ['A PROFILE', 'CAN\u2019T', 'SHOW', 'THINGS'],
     ['Who actually runs the floor?', 'Will bulk match the photos?', 'Who refunds a dead order?'],
     'PROFILE', 'PROOF',
     'A verified badge means someone paid a fee. That is all it has ever meant.'),
    ('D',
     'Everyone says to get 3 supplier quotes. Here is why that fails.',
     'three supplier quotes',
     {'one': {'device': '3 QUOTES', 'sub': 'SAME TRADER?', 'button': 'COMPARE'},
      'two': {'title': 'LOOKS INDEPENDENT',
              'cards': ['Same broker', 'Same plant', 'Same price']},
      'three': {'heading': 'QUOTE INBOX',
                'messages': ['Quote A: 4 weeks', 'Quote B: 4 weeks', 'Quote C: 4 weeks']}},
     ['Three emails', 'Three logos', 'Three prices'],
     ['3', 'QUOTES', '0', 'FACTS'],
     ['Are they the same trader?', 'Which plant is behind them?', 'What is excluded from each?'],
     '3 QUOTES', '3 FACTS',
     'Three quotes from three "factories" that share one bank account is one quote.'),
    ('D',
     'An ISO certificate PDF won\u2019t save a defective production run.',
     'an ISO certificate',
     {'one': {'device': 'ISO 9001', 'sub': 'PDF ONLY', 'button': 'DOWNLOAD'},
      'two': {'title': 'LOOKS CERTIFIED',
              'cards': ['Stamped PDF', 'Wall plaque', 'Compliance logo']},
      'three': {'heading': 'QUALITY DESK',
                'messages': ['We are certified.', 'Quality is guaranteed.', 'Skip inspection.']}},
     ['Stamped PDF', 'Wall plaque', 'Compliance logo'],
     ['A PDF', 'IS NOT', 'A', 'PROCESS'],
     ['Does the scope cover your line?', 'Is the audit still current?', 'Who checks the first article?'],
     'A CERTIFICATE', 'A PROCESS',
     'Half the certificates in this industry expired before the supplier uploaded them.'),
    ('D',
     'Why trade show booths are the most expensive trap in sourcing.',
     'a trade show booth',
     {'one': {'device': 'BOOTH 4B', 'sub': 'HALL 2', 'button': 'SCAN BADGE'},
      'two': {'title': 'LOOKS LIKE A FACTORY',
              'cards': ['Huge expo stand', 'Fluent reps', 'Glossy brochures']},
      'three': {'heading': 'AFTER THE SHOW',
                'messages': ['Visit our factory.', 'Send a deposit first.', 'We will send photos.']}},
     ['Huge expo stand', 'Fluent reps', 'Glossy brochures'],
     ['A BOOTH', 'IS NOT', 'A', 'FACTORY'],
     ['Who employs the engineers?', 'What does the plant look like?', 'Who audits the sub-tier?'],
     'A BOOTH', 'A PLANT',
     'A booth is a set. The factory is the film set nobody shows you.'),
    ('D',
     'On-time shipping means nothing if your cargo fails customs.',
     'a container at customs',
     {'one': {'device': 'ON TIME', 'sub': 'PORT OF ENTRY', 'button': 'TRACK'},
      'two': {'title': 'LOOKS LIKE DELIVERY',
              'cards': ['Loaded container', 'Tracking number', 'Vessel departed']},
      'three': {'heading': 'CUSTOMS DESK',
                'messages': ['Docs are fine.', 'No test needed.', 'Release is automatic.']}},
     ['Loaded container', 'Tracking number', 'Vessel departed'],
     ['SHIPPED', 'IS NOT', 'DELIVERED', 'YET'],
     ['Are the HS codes correct?', 'Will the lab pass your port?', 'Who absorbs a seizure?'],
     'SHIPPED', 'DELIVERED',
     'Your supplier is finished the moment the container leaves. You are not.'),
    ('D',
     'Why 10 years on a directory doesn\u2019t mean 10 years of manufacturing.',
     'a ten year old listing',
     {'one': {'device': '10 YEARS', 'sub': 'DIRECTORY AGE', 'button': 'VIEW BADGE'},
      'two': {'title': 'LOOKS EXPERIENCED',
              'cards': ['Ten-year badge', 'Old account', 'Trade history']},
      'three': {'heading': 'SINCE WHEN?',
                'messages': ['We started in 2014.', 'We make everything.', 'Trust the badge.']}},
     ['Ten-year badge', 'Old account', 'Trade history'],
     ['TENURE', 'IS NOT', 'EXPERIENCE', 'HERE'],
     ['Was the account bought?', 'Have they made your category?', 'Who is liable for a recall?'],
     'TENURE', 'EXPERIENCE',
     'Platform age is a number the platform sells. It is not a factory.'),
    # ---- 19: the modular custom slot -------------------------------------
    ('D',
     'The 60-second supplier check that prevents a $6,000 mistake.',
     'the sixty second check',
     {'one': {'device': '60 SECONDS', 'sub': 'SUPPLIER CHECK', 'button': 'START'},
      'two': {'title': 'THE WHOLE METHOD',
              'cards': ['Find the plant', 'Vet the file', 'Verify on site']},
      'three': {'heading': 'DUE DILIGENCE',
                'messages': ['Find the real factory.', 'Vet the evidence.', 'Verify before you wire.']}},
     ['Find', 'Vet', 'Verify'],
     ['FIND.', 'VET.', 'VERIFY.', 'ONLINE'],
     ['Who is the real factory?', 'What proof do they hold?', 'Who protects your deposit?'],
     '60 SECONDS', '$6,000',
     'This is the modular slot: swap the hook, the three cards and the equation, '
     'keep the spine. Designed for your own reel reference.'),
)


def _scene_at(start):
    for name, begin, end in SCENES:
        if begin <= start < end:
            return name
    return SCENES[-1][0]


def _layer(index, start, length, kind, name, prompt):
    return {
        'index': index,
        'start_time': round(start, 2),
        'duration': round(length, 2),
        'end_time': round(start + length, 3),
        'scene': _scene_at(start),
        'name': name,
        'kind': kind,
        'gain_db': -9.0 if kind in ('hum', 'tail') else (-6.0 if kind in ('sub', 'heartbeat', 'taiko') else -3.5),
        'sfx_prompt': prompt,
    }


def audio_blueprint(data, index=None):
    """The 26 foley layers plus the music bed for one episode."""
    layers = [_layer(number + 1, *item) for number, item in enumerate(SFX_SPINE)]
    slot = ((index or data.get('index') or 1) - 1) % len(SIGNATURE_SFX)
    anchor = layers[6]
    accent = SIGNATURE_SFX[slot]
    layers[6] = _layer(anchor['index'], anchor['start_time'], anchor['duration'],
                       accent[2], accent[3], accent[4])
    return {
        'episode': data.get('index') or index,
        'duration': DURATION,
        'sample_rate': SAMPLE_RATE,
        'layer_count': len(layers),
        'layers': layers,
        'music': dict(MUSIC),
        'tail': dict(TAIL, scene='signoff', name='lowpass-tail'),
        'mix_notes': (
            'Voice at 0 dB. Music bed at -19 dB with the pad ducked on every kick. '
            'Foley per-layer gain_db. Master limited to -0.5 dBFS. Transients land '
            'every 0.72-0.85 s; the lowpass tail at 19.90 s must never be truncated.'
        ),
    }


def validate(data):
    """Return a list of brief violations for one episode (empty when clean)."""
    problems = []
    layout = data.get('layout')
    if layout not in ('A', 'B', 'C', 'D'):
        problems.append('unknown layout %r' % layout)
    hook = data['hook'].rstrip('.')
    if len(hook.split()) > 16:
        problems.append('hook is longer than 16 words')
    for item in data['illusions']:
        if len(item.split()) > 3 or len(item) > 22:
            problems.append('card over 3 words / 22 chars: %r' % item)
    if len(data.get('flash') or []) != 4:
        problems.append('scene 4 needs exactly four flash words')
    for item in data['questions']:
        if len(item) > 42:
            problems.append('question over 42 chars: %r' % item)
        if not item.endswith('?'):
            problems.append('question is not a question: %r' % item)
    scenes = data.get('scenes') or {}
    for key in ('one', 'two', 'three'):
        if not isinstance(scenes.get(key), dict):
            problems.append('missing scene payload %r' % key)
    blueprint = data.get('audio_blueprint') or {}
    layers = blueprint.get('layers') or []
    if not 24 <= len(layers) <= 26:
        problems.append('needs 24-26 foley layers, found %d' % len(layers))
    starts = [layer['start_time'] for layer in layers]
    if starts != sorted(starts):
        problems.append('foley layers are not in time order')
    gaps = [round(b - a, 3) for a, b in zip(starts, starts[1:])]
    if gaps and max(gaps) > 1.3:
        problems.append('foley gap over 1.3 s: %s' % max(gaps))
    tail = layers[-1] if layers else {}
    if (tail.get('start_time'), tail.get('duration')) != (TAIL['start_time'], TAIL['duration']):
        problems.append('the lowpass tail must close the clip at 19.90 s / 0.70 s')
    if not blueprint.get('music'):
        problems.append('missing the music bed spec')
    if voice_seconds(data) > DURATION - 0.7:
        problems.append('narration would run past the tail')
    return problems


def episode(index):
    """Return one episode by 1-based index, cycling through the series."""
    if not EPISODES:
        raise ValueError('The kinetic series has no episodes.')
    return EPISODES[(max(1, int(index)) - 1) % len(EPISODES)]


def voiceover(episode_data):
    """The narration, in scene order, with MiniMax pause tags.

    Scenes 2 and 3 are read by the eye, not the ear: their labels are already on
    screen, and speaking them pushed every read past the 19.90 s tail. The voice
    carries the hook, the three questions and the equation, which is also how the
    format reads best — the middle is where the music and foley do the work.
    """
    hook = episode_data['hook'].rstrip('.')
    questions = ' '.join(_question_phrase(item) for item in episode_data['questions'])
    left = episode_data['left'].lower()
    right = episode_data['right'].lower()
    return ('<#0.35#>%s<#0.55#>%s<#0.45#>'
            '%s is not %s.<#0.5#>%s' % (
                hook, questions, left, right, CLOSING_VO))


def _spoken_second(episode_data):
    """One sentence that narrates whatever scene 2 draws."""
    scenes = episode_data['scenes']
    two = scenes.get('two') or {}
    if two.get('steps'):
        return ' '.join(step.lower() for step in two['steps']) + '.'
    if two.get('bars'):
        return ', '.join('%s %s' % (bar[0].lower(), bar[2]) for bar in two['bars']) + '.'
    if two.get('items'):
        return 'What is missing: ' + ', '.join(item.lower() for item in two['items']) + '.'
    if two.get('cards'):
        return ', '.join(card.lower() for card in two['cards']) + '.'
    return ''


def _spoken_third(episode_data):
    scenes = episode_data['scenes']
    three = scenes.get('three') or {}
    if three.get('items'):
        return 'Here is what we do: ' + ', '.join(item.lower() for item in three['items']) + '.'
    if three.get('bars'):
        return ''
    if three.get('rows'):
        return ', '.join(str(row).lower() for row in three['rows']) + '.'
    if three.get('messages'):
        return ' '.join(message.lower() for message in three['messages'])
    return ''


def tts_script(episode_data):
    """The same narration with ``<break time="x.xxs"/>`` tags (generic TTS)."""
    return _BREAK_TAG.sub(lambda match: '<break time="%ss"/>' % match.group(1),
                          voiceover(episode_data))


_BREAK_TAG = __import__('re').compile(r'<#\s*([\d.]+)\s*#>')


def _question_phrase(text):
    return text.strip().rstrip('?').lower() + '?'


def voice_seconds(episode_data):
    """Rough spoken length at 2.7 words per second plus the tagged pauses."""
    import re
    text = voiceover(episode_data)
    pauses = sum(float(value) for value in re.findall(r'<#\s*([\d.]+)\s*#>', text))
    words = len(re.sub(r'<#\s*[\d.]+\s*#>', ' ', text).split())
    return round(words / 2.7 + pauses, 2)


def caption(episode_data, index=None):
    """Polarising comment-bait: a claim people will argue with, then the CTA."""
    bait = episode_data.get('comment_bait') or ''
    left = episode_data['left']
    right = episode_data['right'].lower()
    lines = [episode_data['hook'].rstrip('.'), '', left + ' \u2260 ' + right, '']
    if bait:
        lines += [bait, '']
    lines.append('Find. Vet. Verify. \u2014 stratevo.online')
    return chr(10).join(lines)


def description(episode_data):
    left, right = episode_data['left'], episode_data['right'].lower()
    return ('%s\n\n%s \u2260 %s\n\n%s\n\nFind. Vet. Verify. at stratevo.online\n\n%s' % (
        episode_data['hook'], left, right,
        '\n'.join('- ' + item for item in episode_data['questions']), TAGS))


def script(episode_data):
    return ' '.join(item.strip().rstrip('?').lower() + '?' for item in episode_data['questions'])


def copy_for(index):
    """Everything the pipeline needs to store one episode as a content idea."""
    data = episode(index)
    left, right = data['left'], data['right'].lower()
    return {
        'topic': '%s vs %s' % (left.lower(), right),
        'angle': 'kinetic typography / layout %s' % data['layout'],
        'hook': data['hook'],
        'script': script(data),
        'video_prompt': 'Rendered in code: %.2f s kinetic typography episode %d, layout %s '
                        '(%s \u2260 %s), %d foley layers plus a music bed.'
                        % (DURATION, index, data['layout'], left, right,
                           data['audio_blueprint']['layer_count']),
        'negative_prompt': '',
        'tiktok_caption': caption(data, index),
        'tiktok_hashtags': TAGS,
        'instagram_caption': caption(data, index),
        'instagram_hashtags': TAGS,
    }


_SCENE_BEATS = tuple({'scene': name, 'start': begin, 'end': end} for name, begin, end in SCENES)


def _build(index, item):
    (layout, hook, subject, scenes, illusions, flash, questions,
     left, right, bait) = item
    data = {
        'index': index,
        'series': SERIES_NAME,
        'layout': layout,
        'hook': hook,
        'subject': subject,
        'scenes': {key: dict(value) for key, value in scenes.items()},
        'illusions': list(illusions),
        'flash': list(flash),
        'questions': list(questions),
        'left': left,
        'right': right,
        'comment_bait': bait,
        'tile_title': scenes['two'].get('title', illusions[0]).upper(),
        'chat_heading': scenes['three'].get('title', scenes['three'].get('heading', illusions[2])).upper(),
    }
    data['episode_data'] = {
        'index': index,
        'layout': layout,
        'hook': hook,
        'hook_lands_at': 1.35,
        'subject': subject,
        'scenes': {key: dict(value) for key, value in scenes.items()},
        'flash_words': list(flash),
        'questions': [
            {'text': text, 'level': level, 'chars': len(text), 'scene_time': 9.90 + slot * 1.25}
            for slot, (text, level) in enumerate(zip(questions, FEAR_LADDER))
        ],
        'equation': {'left': left, 'right': right, 'mark': '\u2260'},
        'on_screen': {
            'hook': hook.upper(),
            'scene_1': scenes['one'],
            'scene_2': scenes['two'],
            'scene_3': scenes['three'],
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
        'layout': layout,
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
        'customisable': index == 19,
    }
    return data


EPISODES = [_build(number + 1, item) for number, item in enumerate(_EPISODES)]

# Kept for the older callers: scene 4 defaults to these when an episode has none.
FLASH_WORDS = ['A PROFILE', 'CAN\u2019T', 'SHOW', 'THINGS']
