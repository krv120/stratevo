"""Durable resource ceilings, moderation, privacy-safe operational events."""
import json
import os
import uuid
from contextlib import contextmanager
from app import suppliers as s

SCHEMA = '''
CREATE TABLE IF NOT EXISTS processing_slots (id TEXT PRIMARY KEY, expires_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS resource_locks (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS account_controls (account_id TEXT PRIMARY KEY REFERENCES market_accounts(id), suspended INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', updated_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS security_events (id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, created_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS listing_reports (id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES market_products(id), reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','reviewed')), created_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS mail_state (outbox_id TEXT PRIMARY KEY REFERENCES outbox(id) ON DELETE CASCADE, status TEXT NOT NULL, updated_at BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_session_meta (digest TEXT PRIMARY KEY REFERENCES sessions(digest) ON DELETE CASCADE, actor TEXT NOT NULL, credential_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_totp (actor TEXT PRIMARY KEY, counter BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS event_date ON security_events(created_at);
CREATE INDEX IF NOT EXISTS outbox_pending ON outbox(sent_at,claimed_until,attempts);
CREATE INDEX IF NOT EXISTS account_date ON market_accounts(created_at,id);
CREATE INDEX IF NOT EXISTS product_visibility_date ON market_products(visibility,created_at,id);
CREATE INDEX IF NOT EXISTS inquiry_date ON customer_inquiries(created_at,id);
'''
TABLES=('processing_slots','resource_locks','account_controls','security_events','listing_reports','mail_state','admin_session_meta','admin_totp')


def limit(name,default,maximum):
    try:value=int(os.environ.get(name,str(default)))
    except ValueError:raise s.WorkflowError('A resource limit is misconfigured.',503) from None
    if not 1<=value<=maximum:raise s.WorkflowError('A resource limit is misconfigured.',503)
    return value


def capacity(db, kind, image_bytes=0):
    # A single row lock serializes checks and inserts across all workers/backends.
    db.execute("INSERT INTO resource_locks VALUES ('storage') ON CONFLICT(name) DO NOTHING")
    db.execute("UPDATE resource_locks SET name=name WHERE name='storage'")
    if kind=='account':
        n=db.execute('SELECT COUNT(*) AS n FROM market_accounts').fetchone()['n']
        pending=db.execute('SELECT COUNT(*) AS n FROM market_accounts WHERE verified_at IS NULL AND NOT EXISTS (SELECT 1 FROM market_publications mp WHERE mp.account_id=market_accounts.id)').fetchone()['n']
        if n>=limit('MAX_SUPPLIER_ACCOUNTS',2000,100000) or pending>=limit('MAX_PENDING_SUPPLIERS',500,10000):raise s.WorkflowError('Supplier registration capacity has been reached. Contact STRATEVO through the inquiry form.',503)
    if kind=='mail':
        if db.execute('SELECT COUNT(*) AS n FROM outbox').fetchone()['n']>=limit('MAX_OUTBOX_RECORDS',10000,100000):raise s.WorkflowError('Email queue storage is at capacity.',503)
    if kind=='inquiry':
        n=db.execute('SELECT COUNT(*) AS n FROM customer_inquiries').fetchone()['n']
        if n>=limit('MAX_STORED_INQUIRIES',10000,1000000):raise s.WorkflowError('Inquiry storage is temporarily at capacity. Please use the booking route.',503)
    if kind in ('account','product'):
        n=db.execute('SELECT COUNT(*) AS n FROM market_products').fetchone()['n']
        size=db.execute('SELECT COALESCE(SUM(LENGTH(image)),0) AS n FROM market_products').fetchone()['n']
        if n>=limit('MAX_STORED_PRODUCTS',20000,100000) or size+image_bytes>limit('MAX_IMAGE_STORAGE_BYTES',268435456,2147483648):raise s.WorkflowError('Product storage is at capacity. Please retry after the operator reviews storage.',503)


def event(db, actor, action, entity_id=''):
    db.execute('INSERT INTO security_events VALUES (?,?,?,?,?)',(str(uuid.uuid4()),actor[:100],action[:80],entity_id[:100],s.now()))


def suspended(db, account):
    row=db.execute('SELECT suspended FROM account_controls WHERE account_id=?',(account,)).fetchone()
    return bool(row and row['suspended'])


def suspension(data, actor):
    identifier=s.field(data,'id',maximum=40);reason=s.field(data,'reason',minimum=5,maximum=500)
    value=data.get('suspended')
    if not isinstance(value,bool):raise s.WorkflowError('Choose suspend or restore.')
    with s.database() as db:
        capacity(db,'lock')
        if not db.execute('SELECT id FROM market_accounts WHERE id=?',(identifier,)).fetchone():raise s.WorkflowError('Account not found.',404)
        db.execute('INSERT INTO account_controls VALUES (?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET suspended=excluded.suspended,reason=excluded.reason,updated_at=excluded.updated_at',(identifier,int(value),reason,s.now()))
        db.execute("DELETE FROM sessions WHERE role='publisher' AND application_id=?",(identifier,))
        db.execute('UPDATE market_tokens SET used_at=? WHERE owner_id=? AND used_at IS NULL',(s.now(),identifier))
        # Do not republish anything on restoration: hidden/withdrawn states stay unchanged.
        if value:db.execute("UPDATE market_products SET visibility='hidden' WHERE owner_id=? AND visibility='published'",(identifier,))
        event(db,actor,'supplier_suspended' if value else 'supplier_restored',identifier)
    return {'message':'Account suspended and public listings removed.' if value else 'Account restored. Previously removed listings remain hidden; request a new access link.'}


def report(data):
    s.rate_limit('listing-reports',20,3600)
    identifier=s.field(data,'id',maximum=40);reason=s.field(data,'reason',minimum=10,maximum=1000)
    with s.database() as db:
        capacity(db,'lock')
        if db.execute('SELECT COUNT(*) AS n FROM listing_reports').fetchone()['n']>=10000:raise s.WorkflowError('Reporting is temporarily at capacity. Use the contact route.',503)
        if not db.execute("SELECT p.id FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE p.id=? AND p.visibility='published' AND (a.verified_at IS NOT NULL OR EXISTS (SELECT 1 FROM market_publications mp WHERE mp.account_id=a.id))",(identifier,)).fetchone():raise s.WorkflowError('Product not found.',404)
        db.execute('INSERT INTO listing_reports VALUES (?,?,?,\'new\',?)',(str(uuid.uuid4()),identifier,reason,s.now()))
    return {'message':'Report saved privately for review. No removal or response time is guaranteed.'}


def reports(offset=0):
    try:offset=int(offset)
    except (ValueError,TypeError):raise s.WorkflowError('Invalid page.') from None
    if not 0<=offset<=100000:raise s.WorkflowError('Invalid page.')
    with s.database() as db:rows=db.execute('SELECT * FROM listing_reports ORDER BY created_at DESC,id LIMIT 26 OFFSET ?',(offset,)).fetchall()
    return {'reports':[dict(r) for r in rows[:25]],'has_more':len(rows)>25,'offset':offset}


def review_report(data,actor):
    identifier=s.field(data,'id',maximum=40)
    with s.database() as db:
        if db.execute("UPDATE listing_reports SET status='reviewed' WHERE id=?",(identifier,)).rowcount!=1:raise s.WorkflowError('Report not found.',404)
        event(db,actor,'report_reviewed',identifier)
    return {'message':'Report marked reviewed. Removing a listing is a separate action.'}


@contextmanager
def image_slot():
    identifier=str(uuid.uuid4())
    with s.database() as db:
        capacity(db,'lock')
        db.execute('DELETE FROM processing_slots WHERE expires_at<=?',(s.now(),))
        if db.execute('SELECT COUNT(*) AS n FROM processing_slots').fetchone()['n']>=limit('IMAGE_PROCESSING_CONCURRENCY',2,4):raise s.WorkflowError('Photo processing is busy. Retry shortly, or submit without a photo.',429)
        db.execute('INSERT INTO processing_slots VALUES (?,?)',(identifier,s.now()+60))
    try:yield
    finally:
        with s.database() as db:db.execute('DELETE FROM processing_slots WHERE id=?',(identifier,))
