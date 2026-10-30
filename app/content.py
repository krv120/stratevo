"""The 40-video production line: ideas, approvals, rendering, scheduling.

State machine per idea::

    draft ──approve──> approved ──submit──> video_pending ──completed──> video_ready
      ▲                   │                                              │
      └──reject/regenerate┘                                    captions  │
                                                                        ▼
    published <── buffer confirmed ── scheduled <── submit ── ready_to_publish

Every paid action is gated by ``app.video`` (budget lock, per-job cap, idempotent
client keys). Caption rendering is local ffmpeg and free. Buffer submission is
gated by ``PUBLISHING_ENABLED`` and records a post id only when Buffer returns
one.
"""
import datetime
import json
import logging
import os
import uuid

from app import (buffer_api, captions, content_library, kinetic, kinetic_audio, kinetic_series,
                 kinetic_voice, media, video, voice)
from app import suppliers as s

SCHEMA = '''
CREATE TABLE IF NOT EXISTS content_series (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, niche TEXT NOT NULL DEFAULT 'sourcing',
 audience TEXT NOT NULL DEFAULT '', tone TEXT NOT NULL DEFAULT 'direct',
 target_count INTEGER NOT NULL DEFAULT 40, model TEXT NOT NULL DEFAULT 'minimax-h3-max-turbo',
 duration_seconds INTEGER NOT NULL DEFAULT 10, resolution TEXT NOT NULL DEFAULT '768P',
 aspect_ratio TEXT NOT NULL DEFAULT '9:16', created_by TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS content_ideas (
 id TEXT PRIMARY KEY, series_id TEXT NOT NULL, position INTEGER NOT NULL,
 topic TEXT NOT NULL, angle TEXT NOT NULL, hook TEXT NOT NULL, script TEXT NOT NULL,
 video_prompt TEXT NOT NULL, negative_prompt TEXT NOT NULL DEFAULT '',
 tiktok_caption TEXT NOT NULL DEFAULT '', tiktok_hashtags TEXT NOT NULL DEFAULT '',
 instagram_caption TEXT NOT NULL DEFAULT '', instagram_hashtags TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL, video_job_id TEXT, source_video_url TEXT NOT NULL DEFAULT '',
 media_asset_id TEXT, caption_error TEXT NOT NULL DEFAULT '', approved_by TEXT NOT NULL DEFAULT '',
 approved_at BIGINT, reject_reason TEXT NOT NULL DEFAULT '', regenerate_count INTEGER NOT NULL DEFAULT 0,
 created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL, UNIQUE(series_id, position)
);
CREATE INDEX IF NOT EXISTS content_ideas_series ON content_ideas(series_id, position);
CREATE INDEX IF NOT EXISTS content_ideas_status ON content_ideas(status, updated_at);
CREATE TABLE IF NOT EXISTS content_publications (
 id TEXT PRIMARY KEY, idea_id TEXT NOT NULL, platform TEXT NOT NULL, channel_id TEXT NOT NULL DEFAULT '',
 due_at BIGINT NOT NULL, local_slot TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
 buffer_post_id TEXT NOT NULL DEFAULT '', error_message TEXT NOT NULL DEFAULT '',
 response_json TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
 created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL, UNIQUE(idea_id, platform)
);
CREATE INDEX IF NOT EXISTS content_publications_due ON content_publications(status, due_at);
CREATE INDEX IF NOT EXISTS content_publications_idea ON content_publications(idea_id);
CREATE TABLE IF NOT EXISTS content_jobs (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, idea_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
 available_at BIGINT NOT NULL, leased_until BIGINT NOT NULL DEFAULT 0,
 leased_by TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS content_jobs_ready ON content_jobs(status, available_at);
CREATE INDEX IF NOT EXISTS content_jobs_idea ON content_jobs(idea_id, kind);
CREATE TABLE IF NOT EXISTS content_state (
 name TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '', updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS content_costs (
 id TEXT PRIMARY KEY, idea_id TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL,
 units INTEGER NOT NULL DEFAULT 0, usd REAL NOT NULL DEFAULT 0,
 model TEXT NOT NULL DEFAULT '', created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS content_costs_kind ON content_costs(kind, created_at);
'''

IDEAS_STATES = ('draft', 'approved', 'rejected', 'video_pending', 'video_ready',
                'caption_pending', 'ready_to_publish', 'scheduled', 'published', 'failed')
ATHENS = 'Europe/Athens'
# Six posting moments a day: one per generated clip when the nightly job runs 6x.
DEFAULT_SLOT_HOURS = ((9, 0), (11, 30), (14, 0), (16, 30), (19, 0), (21, 0))
# Vercel caps a function response at 4.5 MB and Buffer downloads the whole file.
log = logging.getLogger(__name__)

MAX_SERVED_BYTES = 4_400_000
PLAN_DAYS = 30


def _zone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(ATHENS)
    except Exception:  # pragma: no cover - only on a host without tzdata
        raise s.WorkflowError('Server timezone data is missing; install tzdata to plan Europe/Athens slots.', 503)


# ---------------------------------------------------------------------------
# series and ideas
# ---------------------------------------------------------------------------
def _series(identifier):
    with s.database() as db:
        row = db.execute('SELECT * FROM content_series WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise s.WorkflowError('Series not found.', 404)
    return row


KINETIC_MODEL = 'kinetic-typography'


def default_model():
    """Renderer preselected for a new series.

    Kinetic is the default because it is free and deterministic; setting
    CONTENT_RENDERER=fal keeps the text-to-video path as the default instead.
    """
    choice = (os.environ.get('CONTENT_RENDERER') or 'kinetic').strip().lower()
    return video.DEFAULT_MODEL if choice == 'fal' else KINETIC_MODEL


def is_kinetic(series):
    """True when this series renders its clips in code instead of calling fal.ai."""
    entry = video.MODELS.get(series['model'], {})
    return entry.get('renderer') == 'kinetic'


def renderer_name(series=None):
    """Which renderer clips use, for the dashboard and the docs.

    Without a series the answer is the configured default, so the nightly status
    never claims "fal" while the pipeline is drawing episodes in code.
    """
    if series is not None:
        return 'kinetic' if is_kinetic(series) else 'fal'
    return 'kinetic' if default_model() == KINETIC_MODEL else 'fal'


def _idea(identifier):
    with s.database() as db:
        row = db.execute('SELECT * FROM content_ideas WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise s.WorkflowError('Idea not found.', 404)
    return row


def create_series(data, actor='operator'):
    if not isinstance(data, dict):
        raise s.WorkflowError('Invalid request.', 400)
    name = (data.get('name') or 'STRATEVO faceless series').strip()[:120]
    count = data.get('count', 40)
    try:
        count = int(count)
    except (TypeError, ValueError):
        raise s.WorkflowError('Choose how many ideas to generate.', 400, field='count') from None
    if not 1 <= count <= 200:
        raise s.WorkflowError('A series must contain between 1 and 200 videos.', 400, field='count')
    model = data.get('model') or default_model()
    if model not in video.MODELS:
        raise s.WorkflowError('Choose a supported video model.', 400, field='model')
    entry = video.MODELS[model]
    try:
        # Default to the model's own shortest duration: a kinetic episode only
        # exists at 20 s, and a fal model knows its own range.
        duration = int(data.get('duration_seconds', entry['durations'][0]))
    except (TypeError, ValueError):
        raise s.WorkflowError('Choose a supported duration.', 400, field='duration_seconds') from None
    if duration not in entry['durations']:
        raise s.WorkflowError('Choose a supported duration for this model.', 400, field='duration_seconds')
    resolution = data.get('resolution') or entry.get('default_resolution', '')
    if entry.get('resolutions') and resolution not in entry['resolutions']:
        raise s.WorkflowError('Choose a supported resolution.', 400, field='resolution')
    aspect = data.get('aspect_ratio') or '9:16'
    if aspect not in entry['aspect_ratios']:
        raise s.WorkflowError('Faceless vertical series need a supported aspect ratio.', 400, field='aspect_ratio')
    seed = str(data.get('seed') or uuid.uuid4().hex)[:64]
    if entry.get('renderer', 'fal') == 'kinetic':
        # One idea per kinetic episode, cycling the modular variations. The
        # copy is the episode's own, so the on-screen type and the posted
        # caption always match.
        ideas = []
        for index in range(1, count + 1):
            row = kinetic_series.copy_for(index)
            row['position'] = index
            ideas.append(row)
    else:
        ideas = content_library.generate(seed, count)
    identifier = str(uuid.uuid4())
    now = s.now()
    with s.database() as db:
        db.execute('INSERT INTO content_series (id,name,niche,audience,tone,target_count,model,duration_seconds,'
                   'resolution,aspect_ratio,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (identifier, name, str(data.get('niche') or 'sourcing')[:60], str(data.get('audience') or '')[:200],
                    str(data.get('tone') or 'direct')[:40], count, model, duration, resolution, aspect,
                    str(actor)[:100], now, now))
        for idea in ideas:
            db.execute('INSERT INTO content_ideas (id,series_id,position,topic,angle,hook,script,video_prompt,'
                       'negative_prompt,tiktok_caption,tiktok_hashtags,instagram_caption,instagram_hashtags,'
                       'status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (str(uuid.uuid4()), identifier, idea['position'], idea['topic'], idea['angle'],
                        idea['hook'], idea['script'], idea['video_prompt'], idea['negative_prompt'],
                        idea['tiktok_caption'], idea['tiktok_hashtags'], idea['instagram_caption'],
                        idea['instagram_hashtags'], 'draft', now, now))
    return {'series_id': identifier, 'created': len(ideas), 'seed': seed}


def estimate(model=None, duration=10, resolution='', count=40):
    """Projected spend for a hypothetical batch (no database, no side effects)."""
    name = model if model in video.MODELS else video.DEFAULT_MODEL
    entry = video.MODELS[name]
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 10
    if duration not in entry['durations']:
        duration = min(max(duration, min(entry['durations'])), max(entry['durations']))
    resolution = resolution if resolution in entry.get('resolutions', ()) else entry.get('default_resolution', '')
    unit = entry.get('resolution_prices', {}).get(resolution, entry['per_second_usd'])
    promo = entry.get('promo_prices', {}).get(resolution)
    try:
        count = max(1, min(int(count), 40))
    except (TypeError, ValueError):
        count = 40
    per_video = round(unit * duration, 4)
    budget = video.budget()
    if entry.get('renderer', 'fal') == 'kinetic':
        return {'model': name, 'label': entry['label'], 'duration_seconds': duration,
                'resolution': resolution, 'unit_price_usd': 0.0, 'per_video_usd': 0.0,
                'videos': count, 'total_usd': 0.0,
                'promotional_unit_price_usd': None, 'promotional_total_usd': None,
                'promo_ends': '', 'budget_limit_usd': budget['limit_usd'],
                'budget_spent_usd': budget['spent_usd'],
                'budget_remaining_usd': budget['remaining_usd'],
                'affordable_videos': count, 'renderer': 'kinetic',
                'note': 'Rendered in code with Pillow and ffmpeg: no video-model charge. '
                        'Narration is billed separately by the voice provider.',
                'options': [{'model': key, 'label': item['label'],
                             'resolutions': list(item.get('resolutions', ())),
                             'per_second_usd': item['per_second_usd'],
                             'prices': item.get('resolution_prices', {})} for key, item in video.MODELS.items()]}
    return {'model': name, 'label': entry['label'], 'duration_seconds': duration,
            'resolution': resolution, 'unit_price_usd': unit, 'per_video_usd': per_video,
            'videos': count, 'total_usd': round(per_video * count, 2),
            'promotional_unit_price_usd': promo,
            'promotional_total_usd': round(promo * duration * count, 2) if promo else None,
            'promo_ends': entry.get('promo_ends', ''),
            'budget_limit_usd': budget['limit_usd'], 'budget_spent_usd': budget['spent_usd'],
            'budget_remaining_usd': budget['remaining_usd'],
            'affordable_videos': int(budget['remaining_usd'] // per_video) if per_video else 0,
            'options': [{'model': key, 'label': item['label'], 'resolutions': list(item.get('resolutions', ())),
                         'per_second_usd': item['per_second_usd'],
                         'prices': item.get('resolution_prices', {})} for key, item in video.MODELS.items()],
            'note': 'Budgeted at list price; fal billing is authoritative.'}


def cost_plan(series, count=None):
    """Exact projected spend for a number of videos, before anything is queued."""
    entry = video.MODELS.get(series['model'], video.MODELS[video.DEFAULT_MODEL])
    resolution = series['resolution'] or entry.get('default_resolution', '')
    unit = entry.get('resolution_prices', {}).get(resolution, entry['per_second_usd'])
    promo = entry.get('promo_prices', {}).get(resolution)
    target = int(count if count is not None else series['target_count'])
    per_video = round(unit * int(series['duration_seconds']), 4)
    budget = video.budget()
    if entry.get('renderer', 'fal') == 'kinetic':
        return {'model': series['model'], 'label': entry['label'], 'resolution': resolution,
                'duration_seconds': int(series['duration_seconds']), 'unit_price_usd': 0.0,
                'per_video_usd': 0.0, 'videos': target, 'total_usd': 0.0,
                'promotional_unit_price_usd': None, 'promotional_total_usd': None,
                'promo_ends': '', 'budget_limit_usd': budget['limit_usd'],
                'budget_spent_usd': budget['spent_usd'],
                'budget_remaining_usd': budget['remaining_usd'],
                'affordable_videos': target, 'renderer': 'kinetic',
                'note': 'Rendered in code: the only per-video cost is narration (if enabled).'}
    return {'model': series['model'], 'label': entry['label'], 'resolution': resolution,
            'duration_seconds': int(series['duration_seconds']),
            'unit_price_usd': unit, 'per_video_usd': per_video,
            'videos': target, 'total_usd': round(per_video * target, 2),
            'promotional_unit_price_usd': promo,
            'promotional_total_usd': round(promo * int(series['duration_seconds']) * target, 2) if promo else None,
            'promo_ends': entry.get('promo_ends', ''),
            'budget_limit_usd': budget['limit_usd'], 'budget_spent_usd': budget['spent_usd'],
            'budget_remaining_usd': budget['remaining_usd'],
            'affordable_videos': int(budget['remaining_usd'] // per_video) if per_video else 0,
            'note': 'Budget uses the list price and the committed monthly limit; fal billing is authoritative.'}


def smoke(actor='operator'):
    """The smallest honest end-to-end test: one idea, one short clip, real charge."""
    if not video.fal.configured():
        raise s.WorkflowError('FAL_KEY is not configured on the server.', 503)
    created = create_series({'name': 'First real test ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
                             'count': 1, 'model': 'minimax-h3-max-turbo', 'duration_seconds': 5,
                             'resolution': '768P', 'aspect_ratio': '9:16'}, actor)
    overview_data = overview(created['series_id'])
    idea = overview_data['ideas'][0]
    decide({'id': idea['id'], 'action': 'approve'}, actor)
    result = submit_batch({'series_id': created['series_id'], 'limit': 1}, actor)
    if not result['queued']:
        raise s.WorkflowError('The test video was not queued: ' +
                              (result['skipped'] or result['failed'] or [{'reason': 'unknown'}])[0]['reason'], 409)
    return {'series_id': created['series_id'], 'idea_id': idea['id'], 'queued': result['queued'],
            'spend_usd': result['spend_usd'], 'budget': result['budget'],
            'next': 'The worker will caption it automatically once fal.ai finishes. Watch the Generating and Captioned filters.'}


def overview(series_id=None, base=''):
    with s.database() as db:
        if series_id:
            series = db.execute('SELECT * FROM content_series WHERE id=?', (series_id,)).fetchone()
        else:
            series = db.execute('SELECT * FROM content_series ORDER BY created_at DESC LIMIT 1').fetchone()
        if not series:
            return {'series': None, 'ideas': [], 'counts': {}, 'cost': None, 'publications': [],
                    'publishing': publishing_status(), 'worker': worker_status(),
                    'default_model': default_model(), 'renderer': renderer_name()}
        rows = db.execute('SELECT * FROM content_ideas WHERE series_id=? ORDER BY position', (series['id'],)).fetchall()
        publications = db.execute(
            'SELECT p.*, i.position AS idea_position FROM content_publications p '
            'JOIN content_ideas i ON i.id=p.idea_id WHERE i.series_id=? ORDER BY p.due_at', (series['id'],)).fetchall()
        # One query for every media asset in the series: the dashboard polls this
        # endpoint every 20 seconds against a remote PostgreSQL.
        assets = {row['id']: row for row in db.execute(
            'SELECT id, token, external_url FROM media_assets WHERE idea_id IN '
            '(SELECT id FROM content_ideas WHERE series_id=?)', (series['id'],)).fetchall()}
    counts = {}
    for row in rows:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    series_payload = dict(series)
    series_payload['renderer'] = renderer_name(series)
    return {'series': series_payload, 'ideas': [public_idea(row, base, assets) for row in rows], 'counts': counts,
            'cost': cost_plan(series), 'publications': [dict(row) for row in publications],
            'publishing': publishing_status(), 'worker': worker_status(),
            'nightly': nightly_status(series), 'voice': voice.status(), 'cta': cta_text(),
            'default_model': default_model(), 'renderer': renderer_name(series),
            'media': media.stats()}


def public_idea(row, base='', assets=None):
    asset = row['media_asset_id']
    return {
        'id': row['id'], 'position': row['position'], 'topic': row['topic'], 'angle': row['angle'],
        'hook': row['hook'], 'script': row['script'], 'video_prompt': row['video_prompt'],
        'tiktok_caption': row['tiktok_caption'], 'tiktok_hashtags': row['tiktok_hashtags'],
        'instagram_caption': row['instagram_caption'], 'instagram_hashtags': row['instagram_hashtags'],
        'status': row['status'], 'video_job_id': row['video_job_id'] or '',
        'source_video_url': row['source_video_url'] or '',
        'video_url': (media.url_from_row((assets or {}).get(asset), base) if assets is not None
                      else media.url_for(asset, base)) if asset else (row['source_video_url'] or ''),
        'caption_error': row['caption_error'] or '', 'approved_at': row['approved_at'],
        'reject_reason': row['reject_reason'] or '', 'regenerate_count': row['regenerate_count'],
        'reading_seconds': content_library.estimate_seconds(row['script']),
    }


def set_status(idea_id, status, **columns):
    columns['status'] = status
    columns['updated_at'] = s.now()
    keys = list(columns)
    with s.database() as db:
        db.execute('UPDATE content_ideas SET ' + ', '.join(key + '=?' for key in keys) + ' WHERE id=?',
                   tuple(columns[key] for key in keys) + (idea_id,))


def decide(data, actor):
    """Approve or reject an idea. Only drafts and rejected ideas can move."""
    identifier = data.get('id')
    idea = _idea(identifier)
    action = data.get('action')
    if action not in ('approve', 'reject'):
        raise s.WorkflowError('Choose approve or reject.', 400, field='action')
    if action == 'reject':
        reason = str(data.get('reason') or 'Rejected by operator')[:300]
        set_status(identifier, 'rejected', reject_reason=reason, approved_by='', approved_at=None)
        return {'message': 'Idea rejected. It will not be generated.', 'idea': public_idea(_idea(identifier))}
    if idea['status'] not in ('draft', 'rejected', 'failed'):
        raise s.WorkflowError('This idea has already moved past review.', 409)
    if not idea['script'] or not idea['video_prompt']:
        raise s.WorkflowError('This idea is missing a script or prompt.', 409)
    set_status(identifier, 'approved', approved_by=str(actor)[:100], approved_at=s.now(), reject_reason='')
    return {'message': 'Idea approved.', 'idea': public_idea(_idea(identifier))}


def regenerate(data, actor):
    """Replace the concept at the same position with a fresh, distinct one."""
    idea = _idea(data.get('id'))
    if idea['status'] in ('video_pending', 'scheduled', 'published'):
        raise s.WorkflowError('This idea already has a paid generation or a live post; it cannot be regenerated.', 409)
    series = _series(idea['series_id'])
    seed = 'regen-%s-%s' % (idea['id'], int(idea['regenerate_count']) + 1)
    fresh = content_library.generate(seed, int(series['target_count']))
    with s.database() as db:
        taken = {row['hook'] for row in db.execute(
            'SELECT hook FROM content_ideas WHERE series_id=?', (series['id'],)).fetchall()}
    replacement = next((item for item in fresh if item['hook'] not in taken), None)
    if not replacement:
        raise s.WorkflowError('Could not build a distinct replacement; try again.', 503)
    with s.database() as db:
        db.execute('UPDATE content_ideas SET topic=?,angle=?,hook=?,script=?,video_prompt=?,negative_prompt=?,'
                   'tiktok_caption=?,tiktok_hashtags=?,instagram_caption=?,instagram_hashtags=?,status=?,'
                   'regenerate_count=regenerate_count+1,reject_reason=?,caption_error=?,updated_at=? WHERE id=?',
                   (replacement['topic'], replacement['angle'], replacement['hook'], replacement['script'],
                    replacement['video_prompt'], replacement['negative_prompt'], replacement['tiktok_caption'],
                    replacement['tiktok_hashtags'], replacement['instagram_caption'],
                    replacement['instagram_hashtags'], 'draft', '', '', s.now(), idea['id']))
    return {'message': 'A new concept replaced this position.', 'idea': public_idea(_idea(idea['id']))}


# ---------------------------------------------------------------------------
# generation queue (paid)
# ---------------------------------------------------------------------------
def submit_batch(data, actor='operator', limit=None):
    """Queue video generation for approved ideas. Never exceeds the budget."""
    series = _series(data.get('series_id'))
    entry = video.MODELS[series['model']]
    try:
        requested = int(data.get('limit') or limit or (limit or 5))
    except (TypeError, ValueError):
        raise s.WorkflowError('Choose how many videos to queue.', 400, field='limit') from None
    requested = max(1, min(requested, 40))
    if not is_kinetic(series) and not video.fal.configured():
        raise s.WorkflowError('FAL_KEY is not configured on the server.', 503)
    with s.database() as db:
        rows = db.execute("SELECT * FROM content_ideas WHERE series_id=? AND status='approved' "
                          "ORDER BY position LIMIT ?", (series['id'], requested)).fetchall()
    if not rows:
        raise s.WorkflowError('No approved ideas are waiting. Approve ideas first.', 409)
    if is_kinetic(series):
        # No provider, no budget: queue the local render. Each clip is drawn on
        # the worker and stored in media_assets exactly like a captioned one.
        queued = []
        for idea in rows:
            set_status(idea['id'], 'video_ready')
            enqueue('caption', idea['id'])
            queued.append({'idea_id': idea['id'], 'position': idea['position'],
                           'job_id': '', 'cost_usd': 0.0})
        return {'queued': queued, 'skipped': [], 'failed': [], 'queued_count': len(queued),
                'spend_usd': 0.0, 'budget': video.budget(), 'renderer': 'kinetic'}
    queued, skipped, failures = [], [], []
    for idea in rows:
        # One deterministic key per attempt: a retry of a genuinely failed
        # submission gets a fresh key, while the same attempt stays idempotent.
        # An unresolved attempt blocks the retry so nobody is charged twice.
        with s.database() as db:
            row = db.execute(
                'SELECT COUNT(*) AS n, SUM(CASE WHEN status IN (?,?,?,?,?,?) THEN 1 ELSE 0 END) AS active '
                'FROM video_jobs WHERE idea_id=?', video.ACTIVE + ('unknown', idea['id'])).fetchone()
        if int(row['active'] or 0):
            skipped.append({'idea_id': idea['id'], 'position': idea['position'],
                            'reason': 'A previous generation for this idea is still unresolved. Check the video studio and the fal.ai dashboard before retrying.'})
            continue
        attempt = int(row['n'] or 0) + 1
        payload = {'prompt': idea['video_prompt'], 'negative_prompt': idea['negative_prompt'],
                   'model': series['model'], 'duration_seconds': int(series['duration_seconds']),
                   'aspect_ratio': series['aspect_ratio'], 'resolution': series['resolution'],
                   'client_key': ('idea-' + idea['id'].replace('-', '') + '-' + str(attempt))[:64]}
        try:
            result = video.submit(payload, actor, idea_id=idea['id'])
            job = result['job']
            set_status(idea['id'], 'video_pending', video_job_id=job['id'])
            queued.append({'idea_id': idea['id'], 'position': idea['position'], 'job_id': job['id'],
                           'cost_usd': job['cost_usd']})
        except s.WorkflowError as error:
            if error.status == 409:
                skipped.append({'idea_id': idea['id'], 'position': idea['position'], 'reason': str(error)})
                break
            failures.append({'idea_id': idea['id'], 'position': idea['position'], 'reason': str(error)})
            if error.status >= 500 or 'unknown' in str(error).lower():
                set_status(idea['id'], 'failed', caption_error=str(error)[:300])
    return {'queued': queued, 'skipped': skipped, 'failed': failures,
            'queued_count': len(queued), 'spend_usd': round(sum(item['cost_usd'] for item in queued), 2),
            'budget': video.budget()}


# ---------------------------------------------------------------------------
# local caption rendering
# ---------------------------------------------------------------------------
def cta_text():
    """End card. Defaults to the business site, so every clip markets it."""
    value = (os.environ.get('CONTENT_CTA') or 'stratevo.online').strip()
    return value[:40]


def narration_script(idea):
    """What the voice reads: hook, then the script. No hashtags, no emoji."""
    hook = (idea['hook'] or '').strip().rstrip('.')
    body = (idea['script'] or '').strip()
    return (hook + '. ' + body).strip()


def render_captions(idea_id):
    """Burn captions into a completed generation and store the result durably."""
    idea = _idea(idea_id)
    if is_kinetic(_series(idea['series_id'])):
        return render_kinetic(idea)
    if not idea['video_job_id']:
        raise s.WorkflowError('This idea has no video job.', 409)
    job = video.find(idea['video_job_id'])
    if not job or job['status'] != 'completed' or not job['video_url']:
        raise s.WorkflowError('The video is not ready yet.', 409)
    series = _series(idea['series_id'])
    payload = fal_download(job['video_url'])
    root = _media_dir()
    target = root / (idea_id + '.mp4')
    preset = os.environ.get('CONTENT_CAPTION_PRESET', 'veryfast').strip() or 'veryfast'
    if preset not in ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium'):
        preset = 'veryfast'
    try:
        crf = int(os.environ.get('CONTENT_CAPTION_CRF', '20'))
    except ValueError:
        crf = 20
    # Optional narration. A voice failure never blocks the clip: the captioned
    # silent version is still usable and the reason is recorded on the idea.
    narration, voice_note = b'', ''
    if voice.configured():
        try:
            spoken = voice.synthesize(voice.fit(narration_script(idea), job['duration_seconds']),
                                     idea_id=idea_id)
            narration = spoken['bytes']
        except (voice.VoiceError, s.WorkflowError) as error:
            voice_note = str(error)[:300]
    options = {'hook': idea['hook'], 'cta': cta_text(), 'voice': narration or None,
               'crf': max(16, min(crf, 30)), 'preset': preset}
    info = captions.render(payload, target, idea['script'], int(job['duration_seconds']), **options)
    if target.stat().st_size > MAX_SERVED_BYTES:
        # A function response is capped at 4.5 MB; squeeze once, then fail loudly
        # rather than storing a file Buffer cannot download.
        options.update({'crf': min(30, max(16, crf) + 6), 'preset': 'faster'})
        info = captions.render(payload, target, idea['script'], int(job['duration_seconds']), **options)
    if target.stat().st_size > MAX_SERVED_BYTES:
        target.unlink(missing_ok=True)
        raise s.WorkflowError('The captioned clip is larger than the 4.5 MB response limit. Shorten the clip or lower CONTENT_CAPTION_CRF.', 413)
    asset = media.store(target.read_bytes(), idea_id=idea_id)
    target.unlink(missing_ok=True)
    set_status(idea_id, 'ready_to_publish', media_asset_id=asset['id'],
               source_video_url=job['video_url'], caption_error=voice_note)
    return {'idea_id': idea_id, 'asset': asset, 'video': info,
            'narrated': bool(narration), 'voice_note': voice_note}


def render_kinetic(idea):
    """Draw one episode in code, add narration, and store it durably.

    The clip is deterministic: the same episode always renders to the same
    frames, so a retry costs nothing and produces the same video. Only the
    narration (if a voice provider is configured) costs money.
    """
    series = _series(idea['series_id'])
    position = int(idea['position'] or 1)
    data = kinetic_series.episode(position)
    root = _media_dir()
    target = root / (idea['id'] + '.mp4')
    narration, voice_note = None, ''
    try:
        crf = int(os.environ.get('CONTENT_CAPTION_CRF', '20'))
    except ValueError:
        crf = 20
    # Narration is neural-only: fal (MiniMax), OpenAI or ElevenLabs. There is no
    # robotic fallback — if no provider is configured the clip is rendered with
    # music and foley only, and the reason is recorded on the idea.
    if kinetic_voice.provider():
        try:
            info = kinetic_voice.synthesize(data, root / (idea['id'] + '-voice.mp3'))
            narration = info['path']
            voice_note = '%s / %s' % (info['provider'], info['model'])
        except (kinetic_voice.VoiceError, voice.VoiceError, s.WorkflowError) as error:
            voice_note = str(error)[:300]
    else:
        # No key is a normal state, not a per-clip error: the clip still ships with
        # music and foley, and the admin panel reports the missing variable.
        log.info('kinetic episode %s rendered without narration: no neural voice key',
                 idea['id'])
    # The 26-layer blueprint is rendered to a free scratch stem, so the clip has
    # the designed transients even with no paid SFX generation and no narration.
    scratch = None
    bed = None
    sfx = []
    if os.environ.get('CONTENT_KINETIC_SFX', 'true').strip().lower() != 'false':
        try:
            scratch = root / (idea['id'] + '-sfx.wav')
            kinetic_audio.synthesize(data['audio_blueprint'], scratch)
            bed = root / (idea['id'] + '-bed.wav')
            kinetic_audio.music_bed(bed, blueprint=data['audio_blueprint'])
            sfx = [(scratch, 0.0), (bed, 0.0)]
        except Exception:                       # never block a clip on the scratch track
            scratch = None
            bed = None
            sfx = []
    try:
        info = kinetic.render(data, target, index=position, cta=cta_text(),
                              audio=narration, sfx=sfx, bed=not narration and not sfx,
                              crf=max(16, min(crf, 30)))
        if target.stat().st_size > MAX_SERVED_BYTES:
            info = kinetic.render(data, target, index=position, cta=cta_text(),
                                  audio=narration, sfx=sfx, bed=not narration and not sfx,
                                  crf=min(30, max(16, crf) + 6), preset='faster')
        if target.stat().st_size > MAX_SERVED_BYTES:
            target.unlink(missing_ok=True)
            raise s.WorkflowError('The rendered clip is larger than the 4.5 MB response limit. '
                                  'Raise CONTENT_CAPTION_CRF.', 413)
        asset = media.store(target.read_bytes(), idea_id=idea['id'])
    finally:
        target.unlink(missing_ok=True)
        if narration is not None:
            narration.unlink(missing_ok=True)
        if scratch is not None:
            scratch.unlink(missing_ok=True)
        if bed is not None:
            bed.unlink(missing_ok=True)
    set_status(idea['id'], 'ready_to_publish', media_asset_id=asset['id'],
               source_video_url='kinetic://episode-' + str(position), caption_error=voice_note)
    return {'idea_id': idea['id'], 'asset': asset, 'video': info, 'renderer': 'kinetic',
            'narrated': narration is not None, 'voice_note': voice_note,
            'episode': (position - 1) % max(1, len(kinetic_series.EPISODES)) + 1}


def fal_download(url):
    """Download a fal CDN file. Only fal hosts are accepted."""
    import urllib.request
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not any(host == allowed or host.endswith('.' + allowed)
                                           for allowed in video.MEDIA_HOSTS):
        raise s.WorkflowError('Refusing to download media from an untrusted host.', 400)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'stratevo-content-studio/1'}),
                                    timeout=120) as response:
            data = response.read(media.MAX_BYTES + 1)
    except Exception:
        raise s.WorkflowError('The generated video could not be downloaded from fal for captions.', 502) from None
    if len(data) > media.MAX_BYTES:
        raise s.WorkflowError('The generated video is too large to caption.', 502)
    return data


def _media_dir():
    from pathlib import Path
    path = Path(os.environ.get('CONTENT_MEDIA_DIR') or '/tmp/stratevo-media')
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# scheduling (Europe/Athens)
# ---------------------------------------------------------------------------
def slot_hours():
    raw = os.environ.get('CONTENT_SLOT_LOCAL', '').strip()
    if not raw:
        return list(DEFAULT_SLOT_HOURS)
    found = []
    for part in raw.split(','):
        try:
            hour, minute = part.strip().split(':')
            hour, minute = int(hour), int(minute)
        except ValueError:
            raise s.WorkflowError('CONTENT_SLOT_LOCAL must look like 12:30,19:00', 503) from None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise s.WorkflowError('CONTENT_SLOT_LOCAL has an invalid time.', 503)
        found.append((hour, minute))
    if not 1 <= len(found) <= 8:
        raise s.WorkflowError('Configure between 1 and 8 daily posting slots.', 503)
    return found


def build_slots(count, days=PLAN_DAYS, start=None):
    """Spread ``count`` posts over ``days`` days at fixed local times.

    Returns a list of (utc_epoch, local_label) in chronological order.
    """
    zone = _zone()
    hours = slot_hours()
    now = datetime.datetime.now(zone)
    begin = (start or (now + datetime.timedelta(days=1))).replace(hour=0, minute=0, second=0, microsecond=0)
    days = max(1, min(int(days), 60))
    capacity = days * len(hours)
    if count > capacity:
        raise s.WorkflowError('Not enough slots: %d posts do not fit %d days at %d per day.' %
                              (count, days, len(hours)), 409)
    # Even spread. A short run starts tomorrow instead of waiting for a gap:
    # the span is capped by the number of posts, one per day when count < days.
    span = max(1, min(days, count))
    slots = []
    previous = 0
    for index in range(span):
        target = (index + 1) * count // span
        todays = target - previous
        previous = target
        for position in range(todays):
            hour, minute = hours[(position + index) % len(hours)]
            local = begin + datetime.timedelta(days=index, hours=hour, minutes=minute)
            slots.append((int(local.timestamp()), local.strftime('%Y-%m-%d %H:%M %Z')))
    return sorted(slots)


def plan_schedule(data):
    """Create planned publications for approved, rendered ideas."""
    series = _series(data.get('series_id'))
    days = int(data.get('days') or PLAN_DAYS)
    platforms = [item for item in (data.get('platforms') or ['tiktok', 'instagram'])
                 if item in ('tiktok', 'instagram')]
    if not platforms:
        raise s.WorkflowError('Choose at least one platform.', 400)
    with s.database() as db:
        rows = db.execute("SELECT * FROM content_ideas WHERE series_id=? AND status IN "
                          "('ready_to_publish','video_ready','scheduled','published') ORDER BY position",
                          (series['id'],)).fetchall()
    ready = [row for row in rows if row['media_asset_id'] or row['source_video_url']]
    if not ready:
        raise s.WorkflowError('Nothing to schedule yet: generate and caption at least one video.', 409)
    slots = build_slots(len(ready), days)
    now = s.now()
    created = 0
    with s.database() as db:
        for idea, (due, label) in zip(ready, slots):
            for platform in platforms:
                existing = db.execute('SELECT id,status FROM content_publications WHERE idea_id=? AND platform=?',
                                      (idea['id'], platform)).fetchone()
                if existing:
                    if existing['status'] in ('submitted', 'confirmed', 'planned'):
                        continue
                    db.execute('UPDATE content_publications SET due_at=?,local_slot=?,status=?,error_message=?,updated_at=? '
                               'WHERE id=?', (due, label, 'planned', '', now, existing['id']))
                    created += 1
                    continue
                db.execute('INSERT INTO content_publications (id,idea_id,platform,channel_id,due_at,local_slot,status,'
                           'buffer_post_id,error_message,response_json,attempts,created_at,updated_at) '
                           'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (str(uuid.uuid4()), idea['id'], platform, '', due, label, 'planned', '', '', '', 0, now, now))
                created += 1
    return {'planned': created, 'ideas': len(ready), 'days': days, 'platforms': platforms,
            'first_slot': slots[0][1] if slots else '', 'last_slot': slots[-1][1] if slots else '',
            'message': 'Planned locally. Nothing is scheduled in Buffer until the worker submits it and Buffer returns a post id.'}


def auto_schedule_enabled():
    return os.environ.get('CONTENT_AUTO_SCHEDULE', 'true').strip().lower() != 'false'


def auto_schedule_ahead():
    """How many posts should be sitting planned/confirmed per platform."""
    try:
        value = int(os.environ.get('CONTENT_AUTO_SCHEDULE_AHEAD', '4'))
    except ValueError:
        value = 4
    return max(1, min(value, 20))


def schedule_next(series_id, platforms=('tiktok', 'instagram'), days=PLAN_DAYS, limit=None):
    """Append slots for rendered ideas that have no publication yet.

    Unlike ``plan_schedule`` (which re-spreads a whole batch and is meant as a
    deliberate one-off), this only ever *adds* the next few posts after the last
    slot already in the queue, so a nightly run can keep the queue topped up
    without a person in the loop.
    """
    scheduled = ('planned', 'submitting', 'submitted', 'confirmed')
    target = max(1, int(limit if limit is not None else auto_schedule_ahead()))
    with s.database() as db:
        rows = db.execute(
            "SELECT i.id,i.position FROM content_ideas i WHERE i.series_id=? "
            "AND i.status IN ('ready_to_publish','video_ready','scheduled','published') "
            "AND COALESCE(i.media_asset_id,'')<>'' "
            "AND NOT EXISTS (SELECT 1 FROM content_publications p WHERE p.idea_id=i.id) "
            "ORDER BY i.position LIMIT ?", (series_id, target)).fetchall()
        newest = db.execute(
            'SELECT MAX(due_at) AS due FROM content_publications WHERE status IN (?,?,?,?)',
            scheduled).fetchone()
    if not rows:
        return {'created': 0, 'ideas': 0, 'platforms': list(platforms)}
    zone = _zone()
    now = s.now()
    last_due = int(newest['due'] or 0) if newest else 0
    cursor = datetime.datetime.fromtimestamp(max(last_due, now), zone) + datetime.timedelta(minutes=1)
    hours = slot_hours()
    slots = []
    while len(slots) < len(rows):
        day = cursor.date()
        chosen = None
        for hour, minute in hours:
            candidate = datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=zone)
            if candidate > cursor:
                chosen = candidate
                break
        if chosen is None:
            cursor = datetime.datetime.combine(day + datetime.timedelta(days=1),
                                               datetime.time(0, 0), tzinfo=zone)
            continue
        slots.append(int(chosen.timestamp()))
        cursor = chosen
    created = 0
    with s.database() as db:
        for idea, due in zip(rows, slots):
            label = datetime.datetime.fromtimestamp(due, zone).strftime('%Y-%m-%d %H:%M %Z')
            for platform in platforms:
                exists = db.execute('SELECT id FROM content_publications WHERE idea_id=? AND platform=?',
                                    (idea['id'], platform)).fetchone()
                if exists:
                    continue
                db.execute('INSERT INTO content_publications (id,idea_id,platform,channel_id,due_at,local_slot,'
                           'status,buffer_post_id,error_message,response_json,attempts,created_at,updated_at) '
                           'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (str(uuid.uuid4()), idea['id'], platform, '', due, label, 'planned',
                            '', '', '', 0, now, now))
                created += 1
    return {'created': created, 'ideas': len(rows), 'platforms': list(platforms)}


def auto_schedule(limit=None):
    """Top the publishing queue up to CONTENT_AUTO_SCHEDULE_AHEAD planned posts."""
    if not auto_schedule_enabled():
        return {'created': 0, 'reason': 'CONTENT_AUTO_SCHEDULE is off.'}
    with s.database() as db:
        series = db.execute('SELECT * FROM content_series ORDER BY created_at DESC LIMIT 1').fetchone()
        if not series:
            return {'created': 0, 'reason': 'No series exists yet.'}
        ahead = db.execute("SELECT COUNT(*) AS n FROM content_publications WHERE status IN "
                           "('planned','submitting','confirmed') AND platform='tiktok'").fetchone()['n']
        ready = db.execute("SELECT COUNT(*) AS n FROM content_ideas WHERE series_id=? AND "
                           "status IN ('ready_to_publish','video_ready') AND COALESCE(media_asset_id,'')<>''",
                           (series['id'],)).fetchone()['n']
    want = int(limit if limit is not None else auto_schedule_ahead()) - int(ahead or 0)
    if want <= 0 or ready <= 0:
        return {'created': 0, 'ahead': int(ahead or 0), 'ready': int(ready or 0),
                'reason': 'Queue is already deep enough.' if want <= 0 else 'No rendered clips waiting.'}
    return schedule_next(series['id'], limit=want)


def publishing_status():
    channels = {'configured': buffer_api.configured(), 'enabled': buffer_api.enabled(),
                'key_variable': 'BUFFER_API_KEY', 'queue_cap': queue_cap(), 'channels': [],
                'error': ''}
    if not buffer_api.configured():
        return channels
    try:
        channels['channels'] = buffer_api.publishable_channels()
    except buffer_api.BufferError as error:
        channels['error'] = str(error)
    return channels


def queue_cap():
    try:
        value = int(os.environ.get('BUFFER_QUEUE_CAP', '10'))
    except ValueError:
        raise s.WorkflowError('BUFFER_QUEUE_CAP must be a number.', 503) from None
    return max(1, min(value, 500))


def _pending_count(db, channel_id):
    row = db.execute("SELECT COUNT(*) AS n FROM content_publications WHERE channel_id=? AND status IN "
                     "('submitted','confirmed')", (channel_id,)).fetchone()
    return int(row['n'] or 0)


def channel_for(platform):
    """Pick the first usable Buffer channel for a platform."""
    rows = publishing_status().get('channels') or []
    return next((row for row in rows if row['service'] == platform), None)


def post_text(idea, platform):
    if platform == 'tiktok':
        return (idea['tiktok_caption'] + '\n\n' + idea['tiktok_hashtags']).strip()[:2100]
    return (idea['instagram_caption'] + '\n\n' + idea['instagram_hashtags']).strip()[:2100]


def submit_publication(publication_id):
    """Send one planned publication to Buffer. Records confirmed only on a post id."""
    with s.database() as db:
        publication = db.execute('SELECT * FROM content_publications WHERE id=?', (publication_id,)).fetchone()
        if not publication:
            raise s.WorkflowError('Publication not found.', 404)
        idea = db.execute('SELECT * FROM content_ideas WHERE id=?', (publication['idea_id'],)).fetchone()
    if publication['status'] not in ('planned', 'failed'):
        raise s.WorkflowError('This publication is not waiting to be submitted.', 409)
    if not idea:
        raise s.WorkflowError('The idea for this publication is missing.', 409)
    if idea['status'] not in ('ready_to_publish', 'scheduled', 'video_ready'):
        raise s.WorkflowError('The idea is not ready to publish.', 409)
    if not media.public_base():
        raise s.WorkflowError('PUBLIC_BASE_URL is not configured, so Buffer could not fetch the video. Set it to the public HTTPS origin and redeploy.', 409)
    url = media.url_for(idea['media_asset_id']) if idea['media_asset_id'] else ''
    if not url:
        raise s.WorkflowError('The captioned video has no public URL yet. Render captions first.', 409)
    channel = channel_for(publication['platform'])
    if not channel:
        set_publication(publication_id, 'failed', error_message='No connected %s channel in Buffer.' % publication['platform'])
        raise s.WorkflowError('No connected %s channel in Buffer.' % publication['platform'], 409)
    due = datetime.datetime.fromtimestamp(publication['due_at'], datetime.timezone.utc)
    due_iso = due.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    with s.database() as db:
        pending = _pending_count(db, channel['id'])
    if pending >= queue_cap():
        # Never hold a write transaction while calling out to Buffer, and never
        # count a queued-limit skip as an attempt.
        set_publication(publication_id, 'planned',
                        error_message='Buffer queue cap reached for this channel; the worker will top up later.')
        raise s.WorkflowError('The Buffer queue cap for this channel is full (%d).' % queue_cap(), 429)
    with s.database() as db:
        db.execute('UPDATE content_publications SET status=?, attempts=attempts+1, updated_at=? WHERE id=?',
                   ('submitting', s.now(), publication_id))
    try:
        result = buffer_api.create_post(text=post_text(idea, publication['platform']),
                                        channel_id=channel['id'], video_url=url,
                                        platform=publication['platform'], due_at=due_iso)
    except buffer_api.BufferError as error:
        set_publication(publication_id, 'failed', error_message=str(error), channel_id=channel['id'])
        raise s.WorkflowError(str(error), error.status) from None
    set_publication(publication_id, 'confirmed', buffer_post_id=result['id'],
                    channel_id=channel['id'], response_json=json.dumps(result)[:4000],
                    error_message='')
    with s.database() as db:
        remaining = db.execute("SELECT COUNT(*) AS n FROM content_publications WHERE idea_id=? AND "
                               "status IN ('planned','submitting','submitted')", (idea['id'],)).fetchone()['n']
        if not remaining:
            db.execute('UPDATE content_ideas SET status=?, updated_at=? WHERE id=?',
                       ('scheduled', s.now(), idea['id']))
    return {'publication_id': publication_id, 'platform': publication['platform'],
            'buffer_post_id': result['id'], 'due_at': result.get('due_at') or due_iso,
            'status': 'confirmed'}


def set_publication(identifier, status, **columns):
    columns['status'] = status
    columns['updated_at'] = s.now()
    keys = list(columns)
    with s.database() as db:
        db.execute('UPDATE content_publications SET ' + ', '.join(key + '=?' for key in keys) + ' WHERE id=?',
                   tuple(columns[key] for key in keys) + (identifier,))


def _state(name, default=''):
    with s.database() as db:
        row = db.execute('SELECT value FROM content_state WHERE name=?', (name,)).fetchone()
    return row['value'] if row else default


def _set_state(name, value):
    with s.database() as db:
        db.execute('INSERT INTO content_state (name,value,updated_at) VALUES (?,?,?) '
                   'ON CONFLICT(name) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
                   (name, str(value), s.now()))


def refresh_interval():
    """Seconds between Buffer status polls (default 30 min).

    Buffer bills API calls per channel and plan, so polling on every 5-minute
    tick would exhaust the quota on day one. Posts are checked a few at a time,
    only once they are due.
    """
    try:
        value = int(os.environ.get('CONTENT_BUFFER_POLL_SECONDS', '1800'))
    except ValueError:
        value = 1800
    return max(300, value)


def refresh_publications(limit=3, force=False):
    """Ask Buffer for the state of confirmed posts that are already due.

    Returns [] (and records why) when the poll interval has not elapsed, so the
    worker's 5-minute cadence does not multiply into hundreds of API calls.
    """
    interval = refresh_interval()
    last = int(_state('buffer_poll_at', '0') or 0)
    if not force and s.now() - last < interval:
        return []
    _set_state('buffer_poll_at', s.now())
    updated = []
    with s.database() as db:
        rows = db.execute("SELECT id,buffer_post_id FROM content_publications WHERE status='confirmed' "
                          "AND buffer_post_id<>'' AND due_at<=? ORDER BY due_at LIMIT ?",
                          (s.now() + 300, int(limit))).fetchall()
    for row in rows:
        try:
            post = buffer_api.post(row['buffer_post_id'])
        except buffer_api.BufferError:
            continue
        raw_status = str(post.get('status') or '').lower()
        if post.get('sentAt') or raw_status in ('sent', 'published', 'shared'):
            set_publication(row['id'], 'submitted', response_json=json.dumps(post)[:4000])
            with s.database() as db:
                db.execute("UPDATE content_ideas SET status='published', updated_at=? WHERE id="
                           "(SELECT idea_id FROM content_publications WHERE id=?)", (s.now(), row['id']))
            updated.append({'publication_id': row['id'], 'status': 'submitted'})
    return updated


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------
def lease_jobs(worker_id, limit=4, lease_seconds=300):
    """Claim pending jobs with an expiring lease (safe across concurrent workers)."""
    now = s.now()
    claimed = []
    with s.database() as db:
        db.execute("UPDATE content_jobs SET status='pending', leased_until=0, updated_at=? "
                   "WHERE status='running' AND leased_until<?", (now, now))
        rows = db.execute("SELECT id,kind,idea_id FROM content_jobs WHERE status='pending' AND available_at<=? "
                          "ORDER BY available_at LIMIT ?", (now, int(limit))).fetchall()
        for row in rows:
            result = db.execute("UPDATE content_jobs SET status='running', attempts=attempts+1, leased_until=?, "
                                "leased_by=?, updated_at=? WHERE id=? AND status='pending'",
                                (now + int(lease_seconds), worker_id[:60], now, row['id']))
            if getattr(result, 'rowcount', 1) == 1:
                claimed.append(dict(row))
    return claimed


def enqueue(kind, idea_id='', delay=0):
    with s.database() as db:
        existing = db.execute("SELECT id FROM content_jobs WHERE idea_id=? AND kind=? AND status IN "
                              "('pending','running')", (idea_id, kind)).fetchone()
        if existing:
            return existing['id']
        identifier = str(uuid.uuid4())
        now = s.now()
        db.execute('INSERT INTO content_jobs (id,kind,idea_id,status,attempts,max_attempts,available_at,'
                   'leased_until,leased_by,last_error,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (identifier, kind, idea_id, 'pending', 0, 3, now + int(delay), 0, '', '', now, now))
    return identifier


def complete_job(job_id, error=None):
    with s.database() as db:
        if error:
            row = db.execute('SELECT attempts,max_attempts FROM content_jobs WHERE id=?', (job_id,)).fetchone()
            dead = row and int(row['attempts']) >= int(row['max_attempts'])
            db.execute('UPDATE content_jobs SET status=?, last_error=?, leased_until=0, available_at=?, updated_at=? '
                       'WHERE id=?', ('dead' if dead else 'pending', str(error)[:500],
                                      s.now() + min(300, 30 * int(row['attempts'] if row else 1)), s.now(), job_id))
        else:
            db.execute("UPDATE content_jobs SET status='done', leased_until=0, last_error='', updated_at=? WHERE id=?",
                       (s.now(), job_id))


def worker_status():
    now = s.now()
    with s.database() as db:
        row = db.execute("SELECT COUNT(*) AS pending FROM content_jobs WHERE status='pending'").fetchone()
        running = db.execute("SELECT COUNT(*) AS running FROM content_jobs WHERE status='running' AND leased_until>?",
                             (now,)).fetchone()
        dead = db.execute("SELECT COUNT(*) AS dead FROM content_jobs WHERE status='dead'").fetchone()
        last = db.execute("SELECT MAX(updated_at) AS last FROM content_jobs WHERE status='done'").fetchone()
    return {'pending': int(row['pending'] or 0), 'running': int(running['running'] or 0),
            'dead': int(dead['dead'] or 0), 'last_done_at': int(last['last'] or 0) if last else 0,
            'secret_configured': len(os.environ.get('CRON_SECRET', '')) >= 32,
            'ffmpeg': captions.ffmpeg_missing() or 'available'}


def advance_ideas():
    """Move ideas whose video job finished into the caption queue, and record failures."""
    moved = []
    with s.database() as db:
        rows = db.execute("SELECT i.id,i.video_job_id,j.status FROM content_ideas i "
                          "JOIN video_jobs j ON j.id=i.video_job_id WHERE i.status='video_pending'").fetchall()
    for row in rows:
        if row['status'] == 'completed':
            set_status(row['id'], 'video_ready')
            enqueue('caption', row['id'])
            moved.append({'idea_id': row['id'], 'to': 'video_ready'})
        elif row['status'] in ('failed', 'canceled', 'submit_failed'):
            set_status(row['id'], 'failed', caption_error='Generation failed: see the job record.')
            moved.append({'idea_id': row['id'], 'to': 'failed'})
    return moved


def tick(worker_id='worker', max_generate=2, max_caption=2, max_publish=4, sync_jobs=20):
    """One worker pass. Idempotent; safe to call from cron every few minutes."""
    report = {'started_at': s.now(), 'video': {}, 'ideas': [], 'captions': [], 'publishing': [],
              'scheduling': {}, 'jobs': {'leased': 0, 'done': 0, 'failed': 0}, 'errors': []}

    try:
        report['video'] = video.sync_all(sync_jobs)
    except Exception as error:  # never let one subsystem stop the whole tick
        report['errors'].append('video sync: %s' % error)
    try:
        report['ideas'] = advance_ideas()
    except Exception as error:
        report['errors'].append('idea advance: %s' % error)

    # Nightly cadence: submit a couple of clips per pass until the night's
    # target is met. Paced so VIDEO_JOBS_PER_HOUR is never tripped.
    try:
        report['nightly'] = nightly_topup(max_submit=max(1, min(2, int(max_generate or 2))), actor=worker_id)
    except s.WorkflowError as error:
        report['errors'].append('nightly: %s' % error)

    for job in lease_jobs(worker_id, limit=max_caption, lease_seconds=420):
        report['jobs']['leased'] += 1
        try:
            if job['kind'] == 'caption':
                set_status(job['idea_id'], 'caption_pending')
                result = render_captions(job['idea_id'])
                report['captions'].append({'idea_id': job['idea_id'], 'bytes': result['asset']['bytes']})
            complete_job(job['id'])
            report['jobs']['done'] += 1
        except Exception as error:
            with s.database() as db:
                idea = db.execute('SELECT status FROM content_ideas WHERE id=?', (job['idea_id'],)).fetchone()
            if idea and idea['status'] == 'caption_pending':
                set_status(job['idea_id'], 'video_ready', caption_error=str(error)[:300])
            complete_job(job['id'], str(error))
            report['jobs']['failed'] += 1
            report['errors'].append('job %s: %s' % (job['kind'], error))

    # Keep the queue topped up from clips that are already rendered, so a night
    # never ends with finished videos that have no posting slot.
    try:
        report['scheduling'] = auto_schedule()
    except Exception as error:
        report['errors'].append('scheduling: %s' % error)

    if buffer_api.enabled():
        try:
            report['publishing'] = publish_due(max_publish)
            report['refreshed'] = refresh_publications(3)
        except Exception as error:
            report['errors'].append('publishing: %s' % error)
    else:
        report['publishing_note'] = 'PUBLISHING_ENABLED is false or BUFFER_API_KEY is missing; nothing is sent to Buffer.'

    report['finished_at'] = s.now()
    report['status'] = worker_status()
    return report


# ---------------------------------------------------------------------------
# nightly cadence
# ---------------------------------------------------------------------------
NIGHT_START_HOUR = 20   # local time the "night" starts
NIGHT_END_HOUR = 9      # local time the night closes


def nightly_count():
    try:
        value = int(os.environ.get('CONTENT_NIGHTLY_COUNT', '6'))
    except ValueError:
        raise s.WorkflowError('CONTENT_NIGHTLY_COUNT must be a number.', 503) from None
    return max(0, min(value, 20))


def auto_approve():
    return os.environ.get('CONTENT_AUTO_APPROVE', 'false').strip().lower() == 'true'


def night_window(now=None):
    """(start, end) epochs of the night that contains ``now``, Europe/Athens."""
    zone = _zone()
    moment = datetime.datetime.fromtimestamp(now or s.now(), zone)
    start = moment.replace(hour=NIGHT_START_HOUR, minute=0, second=0, microsecond=0)
    if moment.hour < NIGHT_END_HOUR:
        start -= datetime.timedelta(days=1)
    end = start + datetime.timedelta(days=1)
    end = end.replace(hour=NIGHT_END_HOUR, minute=0)
    return int(start.timestamp()), int(end.timestamp())


def inside_night(now=None):
    moment = datetime.datetime.fromtimestamp(now or s.now(), _zone())
    return moment.hour >= NIGHT_START_HOUR or moment.hour < NIGHT_END_HOUR


def generated_tonight(now=None):
    """Clips produced in the current night window.

    Counts paid generations *and* locally rendered episodes; a kinetic night
    creates no video_jobs, so counting only those would never reach the target.
    """
    start, end = night_window(now)
    upper = min(end, (now or s.now()) + 1)
    with s.database() as db:
        paid = db.execute("SELECT COUNT(*) AS n FROM video_jobs WHERE idea_id<>'' "
                          "AND created_at>=? AND created_at<?", (start, upper)).fetchone()
        local = db.execute("SELECT COUNT(*) AS n FROM content_ideas WHERE video_job_id IS NULL "
                           "AND status IN ('video_ready','caption_pending','ready_to_publish',"
                           "'scheduled','published') AND updated_at>=? AND updated_at<?",
                           (start, upper)).fetchone()
    return int(paid['n'] or 0) + int(local['n'] or 0)


def nightly_status(series=None):
    start, end = night_window()
    made = generated_tonight()
    return {'count': nightly_count(), 'generated_tonight': made,
            'remaining_tonight': max(0, nightly_count() - made),
            'window_start': start, 'window_end': end, 'auto_approve': auto_approve(),
            'renderer': renderer_name(series), 'slot_hours': len(slot_hours())}


def nightly_topup(max_submit=2, actor='nightly'):
    """Generate up to ``CONTENT_NIGHTLY_COUNT`` videos per night, unattended.

    Runs from the worker tick. It never exceeds the monthly budget, the
    per-hour submit rate or the per-night count, and it only ever touches
    approved ideas (auto-approving drafts first when CONTENT_AUTO_APPROVE=true).
    """
    count = nightly_count()
    remaining = count - generated_tonight()
    if count <= 0:
        return {'submitted': 0, 'reason': 'Nightly generation is disabled.', 'nightly': nightly_status()}
    if not inside_night():
        return {'submitted': 0, 'reason': 'Outside the nightly window (%02d:00-%02d:00 Europe/Athens).' % (NIGHT_START_HOUR, NIGHT_END_HOUR),
                'nightly': nightly_status()}
    if remaining <= 0:
        return {'submitted': 0, 'reason': 'Nightly target already met.',
                'nightly': nightly_status()}
    with s.database() as db:
        series = db.execute('SELECT * FROM content_series ORDER BY created_at DESC LIMIT 1').fetchone()
    if not series:
        return {'submitted': 0, 'reason': 'No series exists yet.', 'nightly': nightly_status()}
    approved = 0
    with s.database() as db:
        approved = int(db.execute("SELECT COUNT(*) AS n FROM content_ideas WHERE series_id=? AND status='approved'",
                                  (series['id'],)).fetchone()['n'])
    if approved < remaining and auto_approve():
        with s.database() as db:
            drafts = db.execute("SELECT id FROM content_ideas WHERE series_id=? AND status='draft' "
                                "ORDER BY position LIMIT ?", (series['id'], remaining - approved)).fetchall()
        for row in drafts:
            try:
                decide({'id': row['id'], 'action': 'approve'}, 'auto-approve')
            except s.WorkflowError:
                continue
    if approved <= 0 and not auto_approve():
        return {'submitted': 0, 'reason': 'No approved ideas and CONTENT_AUTO_APPROVE is off.',
                'nightly': nightly_status()}
    limit = min(int(max_submit), remaining)
    try:
        result = submit_batch({'series_id': series['id'], 'limit': limit}, actor)
    except s.WorkflowError as error:
        return {'submitted': 0, 'reason': str(error), 'nightly': nightly_status()}
    return {'submitted': result['queued_count'], 'spend_usd': result['spend_usd'],
            'reason': result['skipped'][0]['reason'] if result['skipped'] else '',
            'nightly': nightly_status(), 'jobs': result['queued']}


def nightly_run(limit=2, actor='operator'):
    """Admin-triggered nightly pass (same rules as the worker)."""
    return nightly_topup(max_submit=limit, actor=actor)


def recover_stuck(older_than=600):
    """Return posts abandoned mid-submit to the queue. A crash between the
    Buffer call and the database write must not strand a post forever."""
    cutoff = s.now() - int(older_than)
    with s.database() as db:
        rows = db.execute("SELECT id FROM content_publications WHERE status='submitting' AND updated_at<?",
                          (cutoff,)).fetchall()
        for row in rows:
            db.execute("UPDATE content_publications SET status='planned', error_message=?, updated_at=? WHERE id=?",
                       ('Recovered after an interrupted submission. Check Buffer before retrying.', s.now(), row['id']))
    return len(rows)


def publish_due(limit=4):
    """Submit planned posts whose channel queue has room, earliest slot first."""
    sent = []
    if not buffer_api.enabled():
        return sent
    recover_stuck()
    with s.database() as db:
        rows = db.execute("SELECT id,platform,channel_id FROM content_publications WHERE status='planned' "
                          "ORDER BY due_at LIMIT ?", (int(limit),)).fetchall()
    for row in rows:
        try:
            sent.append(submit_publication(row['id']))
        except s.WorkflowError as error:
            sent.append({'publication_id': row['id'], 'status': 'error', 'error': str(error)})
    return sent
