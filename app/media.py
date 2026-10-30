"""Durable public media for scheduled posts.

Buffer fetches the video file **when the post publishes**, which can be weeks
after it was scheduled, so a fal CDN URL is not good enough (CDN retention is
configurable and can expire). Finished, captioned clips are therefore copied
into PostgreSQL behind an unguessable token and served from this application's
own HTTPS origin.

Storage cost is small for this workload: a 10-second 1080x1920 clip at
CRF 20 is roughly 2-5 MB, so 40 clips is well under 250 MB. Keep an eye on the
PostgreSQL plan, and use ``prune`` to remove media that is no longer scheduled.
"""
import hashlib
import os
import secrets
import time

from app import suppliers as s

SCHEMA = '''
CREATE TABLE IF NOT EXISTS media_assets (
 id TEXT PRIMARY KEY,
 token TEXT NOT NULL UNIQUE,
 idea_id TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL DEFAULT 'video',
 content_type TEXT NOT NULL DEFAULT 'video/mp4',
 bytes BIGINT NOT NULL DEFAULT 0,
 sha256 TEXT NOT NULL DEFAULT '',
 storage TEXT NOT NULL DEFAULT 'postgres',
 body BLOB,
 external_url TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS media_assets_idea ON media_assets(idea_id);
'''

MAX_BYTES = 64 * 1024 * 1024


def _public_base():
    from app import settings
    try:
        return settings.public_origin().rstrip('/')
    except ValueError:
        return ''


def store(data, *, idea_id='', content_type='video/mp4', kind='video'):
    """Persist bytes and return {'id', 'token', 'url', 'bytes', 'sha256'}."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise s.WorkflowError('The rendered video is empty.', 500)
    if len(data) > MAX_BYTES:
        raise s.WorkflowError('The rendered video is too large to store (limit 64 MB).', 500)
    identifier = str(__import__('uuid').uuid4())
    token = secrets.token_urlsafe(24)
    digest = hashlib.sha256(bytes(data)).hexdigest()
    with s.database() as db:
        db.execute('INSERT INTO media_assets (id,token,idea_id,kind,content_type,bytes,sha256,storage,body,'
                   'external_url,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (identifier, token, str(idea_id)[:64], kind, content_type, len(data), digest,
                    'postgres', bytes(data), '', s.now()))
    base = _public_base()
    return {'id': identifier, 'token': token, 'bytes': len(data), 'sha256': digest,
            'url': (base + '/media/' + token + '.mp4') if base else ''}


def record_external(url, *, idea_id='', kind='video', content_type='video/mp4'):
    """Track a third-party URL (used when a host returns a stable public file)."""
    if not url.startswith('https://'):
        raise s.WorkflowError('Only HTTPS media URLs are accepted.', 400)
    identifier = str(__import__('uuid').uuid4())
    token = secrets.token_urlsafe(24)
    with s.database() as db:
        db.execute('INSERT INTO media_assets (id,token,idea_id,kind,content_type,bytes,sha256,storage,body,'
                   'external_url,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (identifier, token, str(idea_id)[:64], kind, content_type, 0, '',
                    'external', None, url, s.now()))
    return {'id': identifier, 'token': token, 'url': url, 'bytes': 0, 'sha256': ''}


def get(token):
    if not isinstance(token, str) or not 16 <= len(token) <= 64:
        return None
    with s.database() as db:
        row = db.execute('SELECT * FROM media_assets WHERE token=?', (token,)).fetchone()
    return row


def public_base():
    """Configured public origin, or '' when it cannot be trusted."""
    return _public_base()


def url_from_row(row, base=''):
    """Build the public URL from an already-fetched media_assets row."""
    if not row:
        return ''
    if row['external_url']:
        return row['external_url']
    origin = (base or '').rstrip('/') or _public_base()
    return (origin + '/media/' + row['token'] + '.mp4') if origin else ''


def url_for(asset_id, base=''):
    """Absolute public URL for a stored asset, or '' if it cannot be served."""
    if not asset_id:
        return ''
    with s.database() as db:
        row = db.execute('SELECT token, external_url FROM media_assets WHERE id=?', (asset_id,)).fetchone()
    return url_from_row(row, base)


def stats():
    with s.database() as db:
        row = db.execute('SELECT COUNT(*) AS n, COALESCE(SUM(bytes),0) AS total FROM media_assets').fetchone()
    return {'assets': row['n'] if row else 0, 'bytes': row['total'] if row else 0,
            'limit_bytes': MAX_BYTES}


def prune(older_than_days=45):
    """Delete media that is not referenced by a scheduled or published post."""
    cutoff = s.now() - int(older_than_days) * 86400
    with s.database() as db:
        rows = db.execute(
            'SELECT id FROM media_assets WHERE created_at<? AND id NOT IN '
            "(SELECT media_asset_id FROM content_ideas WHERE media_asset_id IS NOT NULL AND status IN ('ready_to_publish','scheduled','published'))",
            (cutoff,)).fetchall()
        for row in rows:
            db.execute('DELETE FROM media_assets WHERE id=?', (row['id'],))
    return len(rows)
