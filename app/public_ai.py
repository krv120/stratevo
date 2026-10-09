"""Password-free chat with shared durable request/concurrency bounds."""
import hashlib
import hmac
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from app import suppliers as s

SCHEMA = '''
CREATE TABLE IF NOT EXISTS public_ai_budget (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS public_ai_slots (id TEXT PRIMARY KEY, expires_at BIGINT NOT NULL);
'''


def enabled():return os.environ.get('PUBLIC_AI_ENABLED','true').lower()=='true'


def positive_setting(name,default,maximum):
    try:return max(1,min(int(os.environ.get(name,str(default))),maximum))
    except (TypeError,ValueError):return default


def throttle(address):
    # Do not trust client-supplied forwarding headers. Shared proxies can share this limit.
    secret=os.environ.get('ADMIN_PASSWORD_HASH') or os.environ.get('APP_ACCESS_TOKEN') or 'stratevo-rate-limit'
    key=hmac.new(secret.encode(),address.encode(),hashlib.sha256).hexdigest()[:24]
    s.rate_limit('public-chat-global',60,60)
    s.rate_limit('public-chat-client:'+key,positive_setting('PUBLIC_AI_PER_MINUTE',10,60),60)


@contextmanager
def reserve():
    day=datetime.now(timezone.utc).date().isoformat()
    limit=positive_setting('PUBLIC_AI_DAILY_LIMIT',100,10000)
    concurrent=positive_setting('PUBLIC_AI_CONCURRENCY',3,20)
    lease=secrets.token_hex(16)
    with s.database() as db:
        budget=db.execute('INSERT INTO public_ai_budget VALUES (?,1) ON CONFLICT(day) DO UPDATE SET calls=public_ai_budget.calls+1 WHERE public_ai_budget.calls<? RETURNING calls',(day,limit)).fetchone()
        if not budget:raise s.WorkflowError('The daily AI request allowance has been reached. Please try again tomorrow or book a human sourcing call.',429)
        # The daily-budget row lock serializes concurrent reservations on PostgreSQL.
        db.execute('DELETE FROM public_ai_slots WHERE expires_at<=?',(s.now(),))
        if db.execute('SELECT COUNT(*) AS n FROM public_ai_slots').fetchone()['n']>=concurrent:
            raise s.WorkflowError('The AI is busy with other conversations. Please try again shortly.',429)
        db.execute('INSERT INTO public_ai_slots VALUES (?,?)',(lease,s.now()+90))
        # Bound historical rate-limit and budget metadata; never retain conversation text.
        db.execute('DELETE FROM rate_limits WHERE started_at<?',(s.now()-172800,))
        db.execute('DELETE FROM public_ai_budget WHERE day<?',((datetime.now(timezone.utc).date()).replace(day=1).isoformat(),))
    try:yield
    finally:
        with s.database() as db:db.execute('DELETE FROM public_ai_slots WHERE id=?',(lease,))
