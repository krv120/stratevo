"""Shared transactional storage bootstrap and secret-free connection diagnostics."""
import os
from app import agent, discovery, suppliers, intake



def status():
    try:
        ai_ready = agent.configured()
    except ValueError:
        ai_ready = False
    try:ai_config=settings.ai_configuration()
    except ValueError:ai_config={'key':'','provider':'invalid'}
    live_search=bool(ai_config['key'] and (ai_config['provider'] in ('openai','gemini','anthropic','perplexity') or os.environ.get('BRAVE_SEARCH_API_KEY')))
    return {'storage':settings.storage_status(),'ai_configured':ai_ready,'ai_provider':ai_config['provider'],'search_configured':live_search,
            'email_configured':__import__('app.mail_policy',fromlist=['transport']).transport()!='admin_inbox',
            'owner_notification_configured':bool(intake.recipient()),
            'notice':'Configured is not a connection test. Keys are read from server environment variables; redeploy or restart after changing them.'}


def check(service):
    if service not in ('ai','search'):
        raise suppliers.WorkflowError('Choose ai or search.')
    suppliers.rate_limit('connection-check',5,300)
    if service == 'ai':
        if not status()['ai_configured']:
            return {'ok':False,'message':'Set AI_API_KEY, AI_MODEL and a valid HTTPS AI_BASE_URL, then redeploy.'}
        try:
            answer = agent.provider_request([{'role':'user','content':'Connection test. Reply with OK only.'}],tools=False)
            if not isinstance(answer.get('content'),str) or not answer['content'].strip():
                raise ValueError('Empty answer')
        except agent.ProviderError as error:
            return {'ok':False,'message':str(error),'code':error.code}
        except Exception:
            return {'ok':False,'message':'AI connection failed. Check the endpoint, model access, key, provider billing and hosting outbound access. Secret/provider error details are not shown.'}
        return {'ok':True,'message':'The configured model returned a response. Test a full sourcing conversation next; this basic check does not validate tool calling or answer quality.'}
    result = discovery.find_leads({'query':'cardboard packaging manufacturers','geography':'','lead_type':'supplier_lead'},'admin-connection-test')
    return {'ok':result['status']=='searched', 'message':result['message']}


# One storage boundary for workflow, catalog, discovery and rate limits.
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
        for path in sorted(MIGRATIONS.glob('00[1-5]_*.sql')):
            text=path.read_text();digest=hashlib.sha256(text.encode()).hexdigest()
            row=raw.execute('SELECT digest FROM schema_migrations WHERE name=%s',(path.name,)).fetchone()
            previous=(row['digest'] if isinstance(row,dict) else row[0]) if row else None
            if previous!=digest:
                # Files remain independently runnable; the worker owns the encompassing transaction.
                text=re.sub(r'^\s*(?:BEGIN|COMMIT);\s*$', '', text, flags=re.M)
                raw.execute(text,prepare=False)
                raw.execute('INSERT INTO schema_migrations VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET digest=excluded.digest',(path.name,digest))
        if len(list(MIGRATIONS.glob('00[1-5]_*.sql')))!=5:raise RuntimeError('Required migrations missing from deployment')
        raw.execute('ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY')
        raw.execute('REVOKE ALL ON schema_migrations FROM PUBLIC')
        for role in ('anon','authenticated'):
            if raw.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                raw.execute('REVOKE ALL ON ALL TABLES IN SCHEMA stratevo_private FROM '+role)
    else:
        from app import suppliers, marketplace, public_ai, intake, controls, operations
        raw.execute('BEGIN IMMEDIATE')
        schema=suppliers.SCHEMA+marketplace.SCHEMA+public_ai.SCHEMA+intake.SCHEMA+controls.SCHEMA+operations.SCHEMA
        schema+="""
CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, batch TEXT NOT NULL, fingerprint TEXT NOT NULL, original TEXT NOT NULL, public_summary TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED, description);
CREATE TABLE IF NOT EXISTS discovery_evidence (id TEXT PRIMARY KEY, searched_at TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discovery_budget (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
"""
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
