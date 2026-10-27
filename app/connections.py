"""Shared transactional database initialization; no outbound discovery services."""
import os
# One storage boundary for supplier records, inquiries and rate limits.
import hashlib
import re
import sqlite3
import threading
from pathlib import Path
from app import settings

RUNTIME_SQLITE = Path('/tmp/stratevo_runtime.sqlite3')
_MIGRATION_LOCK = threading.Lock()
_READY = set()
MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'


def sqlite_path(local_path):
    if settings.ephemeral_storage():return RUNTIME_SQLITE
    from app import suppliers
    path=Path(local_path).resolve()
    if not path.is_relative_to(suppliers.PRIVATE.resolve()):raise ValueError('Local database must be inside private/')
    return path


def _initialize(raw, postgres):
    if postgres:
        # Transaction-scoped lock prevents concurrent cold-start DDL races across workers.
        raw.execute('SELECT pg_advisory_xact_lock(738420126)')
        raw.execute('CREATE SCHEMA IF NOT EXISTS stratevo_private')
        raw.execute('SET LOCAL search_path TO stratevo_private')
        raw.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, digest TEXT NOT NULL)')
        for path in sorted(MIGRATIONS.glob('00[1-8]_*.sql')):
            text=path.read_text();digest=hashlib.sha256(text.encode()).hexdigest()
            row=raw.execute('SELECT digest FROM schema_migrations WHERE name=%s',(path.name,)).fetchone()
            previous=(row['digest'] if isinstance(row,dict) else row[0]) if row else None
            if previous!=digest:
                # Files remain independently runnable; the worker owns the encompassing transaction.
                text=re.sub(r'^\s*(?:BEGIN|COMMIT);\s*$', '', text, flags=re.M)
                raw.execute(text,prepare=False)
                raw.execute('INSERT INTO schema_migrations VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET digest=excluded.digest',(path.name,digest))
        if len(list(MIGRATIONS.glob('00[1-8]_*.sql')))!=8:raise RuntimeError('Required migrations missing from deployment')
        raw.execute('ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY')
        raw.execute('REVOKE ALL ON schema_migrations FROM PUBLIC')
        for role in ('anon','authenticated'):
            if raw.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                raw.execute('REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM '+role)
    else:
        from app import suppliers, marketplace, intake, controls, operations
        raw.execute('BEGIN IMMEDIATE')
        schema=suppliers.SCHEMA+marketplace.SCHEMA+intake.SCHEMA+controls.SCHEMA+operations.SCHEMA
        from app import listings, directory, video
        schema+=listings.SCHEMA+directory.SCHEMA+video.SCHEMA
        # Upgrade legacy outbox shapes before dependent indexes are created.
        exists=raw.execute("SELECT 1 FROM sqlite_master WHERE name='outbox'").fetchone()
        if exists:
            columns={r[1] for r in raw.execute('PRAGMA table_info(outbox)')}
            for column in ('attempts','claimed_until'):
                if column not in columns:raw.execute('ALTER TABLE outbox ADD COLUMN '+column+' BIGINT NOT NULL DEFAULT 0')
        for statement in schema.split(';'):
            if statement.strip():raw.execute(statement)
    raw.commit()


def open_database(local_path, *, dictionaries=False):
    settings.database_guard()
    url=settings.database_url()
    if url:
        import psycopg
        from psycopg.rows import dict_row, tuple_row
        raw=psycopg.connect(url,row_factory=dict_row if dictionaries else tuple_row,
                            connect_timeout=10,prepare_threshold=None,autocommit=False)
        key=('postgres',hashlib.sha256(url.encode()).hexdigest())
    else:
        path=sqlite_path(local_path)
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        # Atomic creation with private permissions; never follow an unexpected symlink.
        fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        os.fchmod(fd,0o600);os.close(fd)
        raw=sqlite3.connect(path,timeout=15)
        raw.create_function('LOWER',1,lambda v:v.lower() if isinstance(v,str) else v,deterministic=True)
        raw.execute('PRAGMA foreign_keys=ON')
        key=('sqlite',str(path),path.stat().st_ino)
    try:
        with _MIGRATION_LOCK:
            if key not in _READY:
                _initialize(raw,bool(url));_READY.add(key)
        if url:raw.execute('SET LOCAL search_path TO stratevo_private')
        elif dictionaries:raw.row_factory=sqlite3.Row
        return raw,bool(url)
    except Exception:
        raw.rollback();raw.close();raise
