"""Content Studio video jobs: validated prompts, fal.ai queue, budget, callbacks.

Design boundaries worth preserving:

* Submitting is an explicit, authenticated, budget-checked action. Nothing here
  publishes content or creates batches.
* Spend is reserved in the database *before* the network call, under a row lock,
  so two concurrent requests cannot both pass the limit check.
* A failure that might still have reached fal.ai is marked ``unknown`` and keeps
  its reservation; it is never silently refunded or automatically retried.
* Webhooks are only a wake-up signal. Every state transition is re-read from
  fal.ai with the server-side key, so a forged or replayed body cannot set a
  status, a URL or a cost.
"""
import calendar
import json
import os
import re
import time
import urllib.parse
import uuid

from app import fal, settings
from app import suppliers as s

SCHEMA = '''
CREATE TABLE IF NOT EXISTS video_jobs (
 id TEXT PRIMARY KEY,
 client_key TEXT NOT NULL UNIQUE,
 model TEXT NOT NULL,
 endpoint TEXT NOT NULL,
 prompt TEXT NOT NULL,
 negative_prompt TEXT NOT NULL DEFAULT '',
 duration_seconds INTEGER NOT NULL,
 aspect_ratio TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('reserved','queued','in_progress','retrieving','canceling','completed','failed','canceled','submit_failed','unknown')),
 fal_request_id TEXT,
 status_url TEXT NOT NULL DEFAULT '',
 response_url TEXT NOT NULL DEFAULT '',
 cancel_url TEXT NOT NULL DEFAULT '',
 video_url TEXT NOT NULL DEFAULT '',
 video_content_type TEXT NOT NULL DEFAULT '',
 error_message TEXT NOT NULL DEFAULT '',
 queue_position INTEGER NOT NULL DEFAULT -1,
 attempts INTEGER NOT NULL DEFAULT 1,
 retried_from TEXT NOT NULL DEFAULT '',
 unit_price_usd REAL NOT NULL DEFAULT 0,
 cost_usd REAL NOT NULL DEFAULT 0,
 cost_basis TEXT NOT NULL DEFAULT '',
 currency TEXT NOT NULL DEFAULT 'USD',
 created_by TEXT NOT NULL DEFAULT '',
 idea_id TEXT NOT NULL DEFAULT '',
 resolution TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL,
 updated_at BIGINT NOT NULL,
 completed_at BIGINT
);
CREATE INDEX IF NOT EXISTS video_jobs_date ON video_jobs(created_at DESC, id);
CREATE INDEX IF NOT EXISTS video_jobs_request ON video_jobs(fal_request_id);
CREATE INDEX IF NOT EXISTS video_jobs_client ON video_jobs(client_key);
CREATE INDEX IF NOT EXISTS video_jobs_idea ON video_jobs(idea_id);
'''

# Endpoints and their documented prices. For models whose price depends on
# resolution the reviewed table is authoritative (the pricing API returns one
# unit price per endpoint and would under-estimate a higher resolution). For
# fixed-price models the live pricing API is preferred at runtime.
# Sources (checked 2026-10-27):
#   https://fal.ai/pricing
#   https://fal.ai/models/minimax/h3-max-turbo/text-to-video
#   https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/pro/text-to-video/api
#   https://fal.ai/models/fal-ai/kling-video/v3/pro/text-to-video/api
# MiniMax H3 Max Turbo carries a promotional discount until 2026-10-31:
#   480P $0.01625/s, 768P $0.026/s, 1080P $0.052/s  -> list $0.025 / $0.04 / $0.08
# The *list* price is used for budgeting so a promo ending cannot overspend.
MODELS = {
    'minimax-h3-max-turbo': {
        'endpoint': 'minimax/h3-max-turbo/text-to-video',
        'label': 'MiniMax H3 Max Turbo',
        'provider': 'minimax',
        'durations': tuple(range(3, 16)),
        'aspect_ratios': ('9:16', '16:9', '1:1', '3:4', '4:3', '21:9'),
        'resolutions': ('480P', '768P', '1080P'),
        'default_resolution': '768P',
        'resolution_prices': {'480P': 0.025, '768P': 0.04, '1080P': 0.08},
        'promo_prices': {'480P': 0.01625, '768P': 0.026, '1080P': 0.052},
        'promo_ends': '2026-10-31',
        'per_second_usd': 0.04,
        'docs': 'https://fal.ai/models/minimax/h3-max-turbo/text-to-video',
    },
    'kling-2.5-turbo-pro': {
        'endpoint': 'fal-ai/kling-video/v2.5-turbo/pro/text-to-video',
        'label': 'Kling 2.5 Turbo Pro',
        'provider': 'kling',
        'durations': (5, 10),
        'aspect_ratios': ('16:9', '9:16', '1:1'),
        'per_second_usd': 0.07,
        'docs': 'https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/pro/text-to-video/api',
    },
    # Not a fal endpoint: the clip is drawn frame by frame with Pillow and
    # encoded with ffmpeg, so the per-video cost is zero. It lives in this table
    # so the studio can pick it and every cost path reports $0 instead of a
    # hidden charge. ``content.render_kinetic`` is the only caller.
    'kinetic-typography': {
        'endpoint': '',
        'label': 'Kinetic typography (rendered in code, $0)',
        'provider': 'kinetic',
        'renderer': 'kinetic',
        'durations': (20,),
        'aspect_ratios': ('9:16',),
        'per_second_usd': 0.0,
        'docs': '',
        'note': '19.7 s, 1080x1920, seven scenes: hook, filmstrip, chat, refraction, '
                'questions, equation, sign-off. Deterministic, no API call.',
    },
    'kling-3-pro': {
        'endpoint': 'fal-ai/kling-video/v3/pro/text-to-video',
        'label': 'Kling 3.0 Pro',
        'provider': 'kling',
        'durations': tuple(range(3, 16)),
        'aspect_ratios': ('16:9', '9:16', '1:1'),
        'per_second_usd': 0.14,
        'docs': 'https://fal.ai/models/fal-ai/kling-video/v3/pro/text-to-video/api',
    },
}
DEFAULT_MODEL = 'minimax-h3-max-turbo'
TERMINAL = ('completed', 'failed', 'canceled', 'submit_failed')
# Statuses that release their reservation because fal.ai did not bill the job.
RELEASED = ('failed', 'canceled', 'submit_failed')
MEDIA_HOSTS = ('fal.media', 'storage.googleapis.com', 'fal.run')
PAGE_SIZE = 12
PRICE_CHECKED = '2026-10-27'


def _number(name, default, minimum, maximum):
    raw = os.environ.get(name, '')
    if not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        raise s.WorkflowError('Operational spending settings are misconfigured.', 503) from None
    if value != value or value < minimum or value > maximum:
        raise s.WorkflowError('Operational spending settings are misconfigured.', 503)
    return value


def limits():
    return {
        'spend_limit_usd': _number('VIDEO_SPEND_LIMIT_USD', 5.0, 0.0, 10000.0),
        'max_job_usd': _number('VIDEO_MAX_JOB_USD', 1.0, 0.0, 10000.0),
        'jobs_per_hour': int(_number('VIDEO_JOBS_PER_HOUR', 6, 1, 60)),
    }


def month_start(now=None):
    parts = time.gmtime(now if now is not None else s.now())
    return calendar.timegm((parts.tm_year, parts.tm_mon, 1, 0, 0, 0, 0, 0, 0))


def webhook_url():
    """Public callback URL, or None when the deployment cannot advertise one."""
    if os.environ.get('VIDEO_WEBHOOK_ENABLED', 'true').strip().lower() == 'false':
        return None
    try:
        return settings.public_origin().rstrip('/') + '/api/video/fal-webhook'
    except ValueError:
        return None


def _model(name):
    entry = MODELS.get(name)
    if not entry:
        raise s.WorkflowError('Choose a supported video model.', 400, field='model')
    return entry


def _text(data, key, minimum, maximum, field=None):
    value = data.get(key, '')
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise s.WorkflowError('Enter text for ' + (field or key) + '.', 400, field=field or key)
    value = value.replace('\r\n', '\n').strip()
    if len(value) < minimum:
        raise s.WorkflowError('The ' + (field or key) + ' is too short.', 400, field=field or key)
    if len(value) > maximum:
        raise s.WorkflowError('The ' + (field or key) + ' is too long (maximum ' + str(maximum) + ' characters).', 400, field=field or key)
    if any(ord(c) < 32 and c not in '\n\t' for c in value) or '\x7f' in value:
        raise s.WorkflowError('The ' + (field or key) + ' contains unsupported control characters.', 400, field=field or key)
    return value


def validate(data):
    if not isinstance(data, dict):
        raise s.WorkflowError('Invalid request.', 400)
    name = data.get('model') or DEFAULT_MODEL
    entry = _model(name)
    prompt = _text(data, 'prompt', 10, 2000, 'prompt')
    negative = _text(data, 'negative_prompt', 0, 300, 'negative prompt') if data.get('negative_prompt') else ''
    try:
        duration = int(data.get('duration_seconds', entry['durations'][0]))
    except (TypeError, ValueError):
        raise s.WorkflowError('Choose a supported duration.', 400, field='duration_seconds') from None
    if duration not in entry['durations']:
        raise s.WorkflowError('Choose a supported duration for this model.', 400, field='duration_seconds')
    aspect = data.get('aspect_ratio') or entry['aspect_ratios'][0]
    if aspect not in entry['aspect_ratios']:
        raise s.WorkflowError('Choose a supported aspect ratio.', 400, field='aspect_ratio')
    resolution = data.get('resolution') or entry.get('default_resolution', '')
    if entry.get('resolutions'):
        if resolution not in entry['resolutions']:
            raise s.WorkflowError('Choose a supported resolution.', 400, field='resolution')
    else:
        resolution = ''
    key = data.get('client_key') or ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', str(key)):
        raise s.WorkflowError('Refresh the page and try again (invalid request key).', 400, field='client_key')
    return {'model': name, 'prompt': prompt, 'negative_prompt': negative,
            'duration_seconds': duration, 'aspect_ratio': aspect, 'client_key': key,
            'resolution': resolution}


def _price(name, resolution=''):
    """Return a price dict with a source label, or None when cost is unknowable."""
    entry = _model(name)
    prices = entry.get('resolution_prices')
    if prices:
        # Resolution-dependent pricing: budget on the *list* price, never the
        # promotional rate, so an expiring discount cannot overspend the limit.
        unit = prices.get(resolution or entry.get('default_resolution'))
        if not unit:
            return None
        return {'per_second': unit, 'source': 'pinned_price_table',
                'checked': PRICE_CHECKED, 'docs': entry['docs'],
                'promotional': entry.get('promo_prices', {}).get(resolution or entry.get('default_resolution')),
                'promo_ends': entry.get('promo_ends', '')}
    live = fal.pricing(entry['endpoint'])
    if live:
        live['checked'] = 'live'
        return live
    return {'per_second': entry['per_second_usd'], 'source': 'pinned_price_table',
            'checked': PRICE_CHECKED, 'docs': entry['docs']}


def estimate(price, duration):
    if 'per_second' in price:
        return round(price['per_second'] * duration, 4)
    return round(price.get('per_video', 0.0), 4)


def _lock(db):
    # Serializes budget checks and job inserts across workers and instances.
    db.execute("INSERT INTO resource_locks VALUES ('video-budget') ON CONFLICT(name) DO NOTHING")
    db.execute("UPDATE resource_locks SET name=name WHERE name='video-budget'")


def _spent(db, now=None):
    row = db.execute(
        'SELECT COALESCE(SUM(cost_usd),0) AS total FROM video_jobs WHERE created_at>=? AND status NOT IN (?,?,?)',
        (month_start(now),) + RELEASED).fetchone()
    return round(float(row['total'] or 0), 6)


def budget(now=None):
    limit = limits()['spend_limit_usd']
    with s.database() as db:
        spent = _spent(db, now)
    return {'limit_usd': round(limit, 2), 'spent_usd': round(spent, 4),
            'remaining_usd': round(max(0.0, limit - spent), 4),
            'window': 'calendar month (UTC)', 'month_start': month_start(now),
            'max_job_usd': round(limits()['max_job_usd'], 2)}


def _ensure_ready():
    if not fal.configured():
        raise s.WorkflowError('FAL_KEY is not configured on the server. Add it in the hosting environment (server-side only) and redeploy.', 503)
    storage = settings.storage_status()
    if not storage['durable'] and settings.environment() not in ('local', 'test'):
        raise s.WorkflowError('Async video jobs need durable PostgreSQL. Set DATABASE_URL and STRICT_PERSISTENT_DB=true before generating.', 503)


def _payload(fields, entry):
    if entry.get('provider') == 'minimax':
        # Schema: prompt (required), duration seconds (number), resolution,
        # prompt_expansion_mode (required), aspect_ratio.
        return {'prompt': fields['prompt'], 'duration': float(fields['duration_seconds']),
                'resolution': fields.get('resolution') or entry.get('default_resolution'),
                'aspect_ratio': fields['aspect_ratio'],
                'prompt_expansion_mode': 'balanced',
                'enable_safety_checker': True}
    body = {'prompt': fields['prompt'], 'duration': str(fields['duration_seconds']),
            'aspect_ratio': fields['aspect_ratio'], 'enable_safety_checker': True}
    if fields['negative_prompt']:
        body['negative_prompt'] = fields['negative_prompt']
    if 'v3' in entry['endpoint']:
        body['generate_audio'] = False
    return body


def submit(data, actor='operator', *, retried_from='', attempt=1, idea_id=''):
    fields = validate(data)
    entry = _model(fields['model'])
    if entry.get('renderer', 'fal') != 'fal':
        raise s.WorkflowError('This model is rendered in code by the content pipeline; '
                              'it is not submitted to fal.ai.', 400, field='model')
    rules = limits()
    _ensure_ready()
    s.rate_limit('video-submit:' + s.digest(str(actor)), rules['jobs_per_hour'], 3600)
    price = _price(fields['model'], fields['resolution'])
    if not price:
        raise s.WorkflowError('Pricing could not be established, so the spending limit cannot be enforced. Generation was blocked.', 503)
    cost = estimate(price, fields['duration_seconds'])
    if cost <= 0:
        raise s.WorkflowError('Pricing could not be established, so the spending limit cannot be enforced. Generation was blocked.', 503)
    if cost > rules['max_job_usd']:
        raise s.WorkflowError('This job would cost $' + f'{cost:.2f}' + ', above the per-job cap of $' + f"{rules['max_job_usd']:.2f}" + '. Lower the duration or raise VIDEO_MAX_JOB_USD.', 400)

    now = s.now()
    identifier = str(uuid.uuid4())
    with s.database() as db:
        existing = db.execute('SELECT * FROM video_jobs WHERE client_key=?', (fields['client_key'],)).fetchone()
        if existing:
            return {'job': public(existing), 'deduplicated': True}
        _lock(db)
        spent = _spent(db)
        if round(spent + cost, 6) > rules['spend_limit_usd'] + 1e-9:
            raise s.WorkflowError('The spending limit would be exceeded: $' + f'{spent:.2f}' + ' of $' + f"{rules['spend_limit_usd']:.2f}" + ' is committed this month. No generation was submitted.', 409)
        db.execute(
            'INSERT INTO video_jobs (id,client_key,model,endpoint,prompt,negative_prompt,duration_seconds,aspect_ratio,'
            'status,attempts,retried_from,unit_price_usd,cost_usd,cost_basis,created_by,created_at,updated_at,idea_id,resolution) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (identifier, fields['client_key'], fields['model'], entry['endpoint'], fields['prompt'],
             fields['negative_prompt'], fields['duration_seconds'], fields['aspect_ratio'], 'reserved',
             int(attempt), retried_from, price.get('per_second', price.get('per_video', 0.0)),
             cost, price['source'], str(actor)[:100], now, now, idea_id, fields['resolution']))

    try:
        response = fal.submit(entry['endpoint'], _payload(fields, entry), webhook_url=webhook_url())
    except fal.FalError as error:
        status = 'unknown' if error.ambiguous else 'submit_failed'
        message = ('Submission outcome unknown: the request may have reached fal.ai. Check the fal.ai dashboard before retrying; the cost stays reserved until resolved.'
                   if error.ambiguous else str(error))
        with s.database() as db:
            db.execute('UPDATE video_jobs SET status=?, error_message=?, cost_usd=?, updated_at=? WHERE id=?',
                       (status, message[:500], 0.0 if status == 'submit_failed' else cost, s.now(), identifier))
        raise s.WorkflowError(message, error.status) from None

    with s.database() as db:
        db.execute('UPDATE video_jobs SET status=?, fal_request_id=?, status_url=?, response_url=?, cancel_url=?, '
                   'queue_position=?, updated_at=? WHERE id=?',
                   ('queued', response['request_id'], response['status_url'], response['response_url'],
                    response['cancel_url'], 0, s.now(), identifier))
        row = db.execute('SELECT * FROM video_jobs WHERE id=?', (identifier,)).fetchone()
    return {'job': public(row), 'deduplicated': False}


def _get(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f-]{36}', identifier):
        raise s.WorkflowError('Job not found.', 404)
    with s.database() as db:
        row = db.execute('SELECT * FROM video_jobs WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise s.WorkflowError('Job not found.', 404)
    return row


def _media_url(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        return ''
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ''
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not host or parsed.username or parsed.password:
        return ''
    if not any(host == allowed or host.endswith('.' + allowed) for allowed in MEDIA_HOSTS):
        return ''
    return value


def _result_video(result):
    if not isinstance(result, dict):
        return ''
    video = result.get('video')
    if isinstance(video, dict):
        return _media_url(video.get('url'))
    videos = result.get('videos')
    if isinstance(videos, list) and videos and isinstance(videos[0], dict):
        return _media_url(videos[0].get('url'))
    return ''


def _update(identifier, **columns):
    columns['updated_at'] = s.now()
    order = list(columns)
    with s.database() as db:
        db.execute('UPDATE video_jobs SET ' + ', '.join(key + '=?' for key in order) + ' WHERE id=?',
                   tuple(columns[key] for key in order) + (identifier,))


def sync(identifier):
    """Refresh one job from fal.ai. Safe to call repeatedly and concurrently."""
    job = _get(identifier)
    if job['status'] in TERMINAL:
        return public(job)
    if job['status'] == 'reserved':
        if s.now() - job['updated_at'] > 600:
            _update(identifier, status='unknown',
                    error_message='Submission was interrupted and the outcome is unknown. Check the fal.ai dashboard before retrying.')
            return public(_get(identifier))
        return public(job)
    if not job['fal_request_id'] or not job['status_url']:
        _update(identifier, status='unknown', error_message='No fal.ai request id was stored; check the fal.ai dashboard.')
        return public(_get(identifier))
    try:
        body = fal.status(job['status_url'])
    except fal.FalError as error:
        _update(identifier, error_message='Status check failed: ' + str(error)[:400])
        raise s.WorkflowError(str(error), error.status) from None
    if body['status'] == 'COMPLETED':
        if body.get('error'):
            _update(identifier, status='failed', cost_usd=0.0, queue_position=-1,
                    error_message=str(body.get('error'))[:500] or 'fal.ai reported a failed generation.')
            return public(_get(identifier))
        try:
            result = fal.result(job['response_url'])
        except fal.FalError as error:
            _update(identifier, status='retrieving', queue_position=-1,
                    error_message='fal.ai finished but the result could not be read yet: ' + str(error))
            return public(_get(identifier))
        video = _result_video(result)
        if not video:
            _update(identifier, status='failed', cost_usd=0.0, queue_position=-1,
                    error_message='fal.ai completed without a usable video URL; nothing was displayed or stored.')
            return public(_get(identifier))
        content_type = ''
        if isinstance(result.get('video'), dict) and isinstance(result['video'].get('content_type'), str):
            content_type = result['video']['content_type'][:100]
        _update(identifier, status='completed', video_url=video, video_content_type=content_type,
                queue_position=-1, error_message='', completed_at=s.now())
        return public(_get(identifier))
    state = 'in_progress' if body['status'] == 'IN_PROGRESS' else 'queued'
    position = body.get('queue_position')
    _update(identifier, status=state, queue_position=position if isinstance(position, int) and 0 <= position < 100000 else -1)
    return public(_get(identifier))


def jobs(offset='0'):
    try:
        start = int(offset)
    except (TypeError, ValueError):
        raise s.WorkflowError('Invalid page.', 400) from None
    if not 0 <= start <= 10000:
        raise s.WorkflowError('Invalid page.', 400)
    with s.database() as db:
        rows = db.execute('SELECT * FROM video_jobs ORDER BY created_at DESC, id LIMIT ? OFFSET ?',
                          (PAGE_SIZE + 1, start)).fetchall()
    return {'jobs': [public(row) for row in rows[:PAGE_SIZE]], 'has_more': len(rows) > PAGE_SIZE, 'offset': start}


def retry(data, actor):
    job = _get(data.get('id'))
    if job['status'] not in ('failed', 'canceled', 'submit_failed'):
        raise s.WorkflowError('Only failed or canceled jobs can be retried.', 409)
    attempt = int(job['attempts']) + 1
    key = (job['client_key'] + '-r' + str(attempt))[:64]
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', key):
        key = ('r' + s.digest(job['client_key'] + str(attempt)))[:32]
    return submit({'prompt': job['prompt'], 'negative_prompt': job['negative_prompt'], 'model': job['model'],
                   'duration_seconds': job['duration_seconds'], 'aspect_ratio': job['aspect_ratio'],
                   'resolution': row_field(job, 'resolution'), 'client_key': key}, actor,
                  retried_from=job['id'], attempt=attempt, idea_id=row_field(job, 'idea_id'))


def cancel(data):
    job = _get(data.get('id'))
    if job['status'] in TERMINAL:
        raise s.WorkflowError('This job has already finished.', 409)
    if not job['cancel_url']:
        raise s.WorkflowError('This job has no cancellable fal.ai request.', 409)
    code, body = fal.cancel(job['cancel_url'])
    if code == 200:
        _update(job['id'], status='canceled', cost_usd=0.0, queue_position=-1, error_message='Canceled before processing.')
        return {'job': public(_get(job['id'])), 'message': 'Canceled before fal.ai processed it.'}
    if code == 202:
        _update(job['id'], status='canceling', error_message='Cancellation requested; fal.ai may still complete and bill this job.')
        return {'job': public(_get(job['id'])), 'message': 'Cancellation requested. The job may still complete.'}
    return {'job': sync(job['id']), 'message': 'fal.ai reported that the request already finished.'}


def webhook(headers, raw_body):
    ok, reason = fal.verify_webhook(headers, raw_body)
    if not ok:
        raise s.WorkflowError('Webhook signature rejected: ' + reason, 403)
    try:
        body = json.loads(raw_body.decode('utf-8'))
    except (UnicodeError, ValueError):
        raise s.WorkflowError('Invalid webhook payload.', 400) from None
    if not isinstance(body, dict):
        raise s.WorkflowError('Invalid webhook payload.', 400)
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not request_id:
        return {'received': True, 'matched': False}
    with s.database() as db:
        row = db.execute('SELECT id FROM video_jobs WHERE fal_request_id=?', (request_id,)).fetchone()
    if not row:
        return {'received': True, 'matched': False}
    try:
        job = sync(row['id'])
    except fal.FalError:
        # Ask fal.ai to redeliver later instead of acknowledging a state we
        # could not confirm; polling in the dashboard remains available.
        raise s.WorkflowError('Result pending; fal.ai should redeliver.', 503) from None
    return {'received': True, 'matched': True, 'status': job['status']}


def public(row):
    label = MODELS.get(row['model'], {}).get('label', row['model'])
    return {
        'id': row['id'], 'model': row['model'], 'model_label': label, 'prompt': row['prompt'],
        'duration_seconds': row['duration_seconds'], 'aspect_ratio': row['aspect_ratio'],
        'status': row['status'], 'queue_position': row['queue_position'],
        'fal_request_id': row['fal_request_id'] or '', 'video_url': row['video_url'] or '',
        'video_content_type': row['video_content_type'] or '', 'error': row['error_message'] or '',
        'attempts': row['attempts'], 'retried_from': row['retried_from'] or '',
        'resolution': row_field(row, 'resolution'), 'idea_id': row_field(row, 'idea_id'),
        'cost_usd': round(float(row['cost_usd'] or 0), 4), 'currency': row['currency'],
        'cost_basis': row['cost_basis'], 'created_at': row['created_at'],
        'updated_at': row['updated_at'], 'completed_at': row['completed_at'],
        'billable': row['status'] not in RELEASED,
    }


ACTIVE = ('reserved', 'queued', 'in_progress', 'retrieving', 'canceling')


def row_field(row, key, default=''):
    """Read a column from a sqlite3.Row or a psycopg dict row."""
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else value


def find(identifier):
    """Return one job row, or None (used by the pipeline)."""
    with s.database() as db:
        return db.execute('SELECT * FROM video_jobs WHERE id=?', (identifier,)).fetchone()


def active_jobs(limit=25):
    placeholders = ','.join('?' for _ in ACTIVE)
    with s.database() as db:
        return db.execute('SELECT id FROM video_jobs WHERE status IN (' + placeholders + ') '
                          'ORDER BY updated_at LIMIT ?', ACTIVE + (int(limit),)).fetchall()


def sync_all(limit=25):
    """Poll every active job once. Returns {job_id: status} for the pipeline."""
    results, errors = {}, {}
    for row in active_jobs(limit):
        identifier = row['id']
        try:
            results[identifier] = sync(identifier)['status']
        except (s.WorkflowError, fal.FalError) as error:
            errors[identifier] = str(error)
    return {'synced': results, 'errors': errors}


def status_payload():
    entry_models = []
    for name, entry in MODELS.items():
        entry_models.append({'id': name, 'label': entry['label'], 'endpoint': entry['endpoint'],
                             'durations': list(entry['durations']), 'aspect_ratios': list(entry['aspect_ratios']),
                             'resolutions': list(entry.get('resolutions', ())),
                             'default_resolution': entry.get('default_resolution', ''),
                             'resolution_prices': entry.get('resolution_prices', {}),
                             'promo_prices': entry.get('promo_prices', {}),
                             'promo_ends': entry.get('promo_ends', ''),
                             'documented_per_second_usd': entry['per_second_usd'], 'docs': entry['docs']})
    return {
        'configured': fal.configured(), 'key_variable': 'FAL_KEY',
        'storage': settings.storage_status(), 'budget': budget(),
        'models': entry_models, 'default_model': DEFAULT_MODEL,
        'webhook_configured': bool(webhook_url()),
        'price_checked': PRICE_CHECKED,
        'pricing_note': 'Budget uses the live fal.ai pricing API when reachable, otherwise the reviewed table below. fal.ai billing is authoritative.',
    }
