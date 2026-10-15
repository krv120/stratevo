"""Shared persistence, email/session services and legacy supplier workflow."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
import uuid
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

PRIVATE = Path(__file__).resolve().parents[1] / 'private'
DATABASE = Path(os.environ.get('SUPPLIER_SQLITE_PATH', str(PRIVATE / 'suppliers.sqlite3'))).resolve()
SCHEMA = '''
CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, company TEXT NOT NULL, contact TEXT NOT NULL,
 email TEXT UNIQUE NOT NULL, country TEXT NOT NULL, category TEXT NOT NULL,
 capabilities TEXT NOT NULL, whatsapp TEXT NOT NULL, wechat TEXT NOT NULL,
 license_number TEXT NOT NULL, license_pdf TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending_email','pending','approved','rejected')),
 created_at BIGINT NOT NULL, reviewed_at BIGINT, review_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tokens (
 digest TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
 purpose TEXT NOT NULL, expires_at BIGINT NOT NULL, used_at BIGINT
);
CREATE TABLE IF NOT EXISTS sessions (
 digest TEXT PRIMARY KEY, role TEXT NOT NULL, application_id TEXT,
 expires_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL, action TEXT NOT NULL,
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, recipient TEXT NOT NULL, subject TEXT NOT NULL,
 body TEXT NOT NULL, created_at BIGINT NOT NULL, sent_at BIGINT,
 attempts INTEGER NOT NULL DEFAULT 0, claimed_until BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rate_limits (
 bucket TEXT PRIMARY KEY, started_at BIGINT NOT NULL, hits INTEGER NOT NULL
);
'''

class WorkflowError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class DB:
    def __init__(self, raw, postgres):
        self.raw, self.postgres = raw, postgres
    def execute(self, sql, args=()):
        return self.raw.execute(sql.replace('?', '%s') if self.postgres else sql, args)


@contextmanager
def database():
    from app import connections
    try:raw,postgres=connections.open_database(DATABASE,dictionaries=True)
    except ValueError:raise WorkflowError('Storage configuration is invalid. Check strict storage mode and deployment settings.',503) from None
    try:
        if not postgres:raw.execute('BEGIN IMMEDIATE')
        yield DB(raw, postgres)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def initialize():
    # database() initializes all workflow, research and usage-control tables before yielding.
    with database():pass


def now(): return int(time.time())
def digest(value): return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password, salt=None):
    if len(password) < 16:
        raise ValueError('Use an admin password of at least 16 characters')
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f'pbkdf2_sha256$600000${salt}${value}'


def verify_password(password):
    configured = os.environ.get('ADMIN_PASSWORD_HASH', '')
    try:
        algorithm, rounds, salt, expected = configured.split('$')
        if algorithm != 'pbkdf2_sha256' or rounds != '600000': return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def rate_limit(bucket, limit, seconds):
    # Durable global buckets are conservative. Add trusted edge per-client limits in production.
    denied = False
    with database() as db:
        from app.controls import capacity
        capacity(db,'lock')
        if not db.execute('SELECT bucket FROM rate_limits WHERE bucket=?',(bucket,)).fetchone():
            db.execute('DELETE FROM rate_limits WHERE started_at<?',(now()-172800,))
            if db.execute('SELECT COUNT(*) AS n FROM rate_limits').fetchone()['n']>=10000:raise WorkflowError('Usage-control capacity reached. Try again later.',429)
        db.execute('INSERT INTO rate_limits(bucket, started_at, hits) VALUES (?,?,0) ON CONFLICT(bucket) DO NOTHING', (bucket, now()))
        db.execute('UPDATE rate_limits SET started_at=?, hits=0 WHERE bucket=? AND started_at<=?', (now(), bucket, now()-seconds))
        row = db.execute('UPDATE rate_limits SET hits=hits+1 WHERE bucket=? RETURNING hits', (bucket,)).fetchone()
        denied = row['hits'] > limit
    if denied: raise WorkflowError('Too many attempts. Please try again later.', 429)


def public_base():
    from app.settings import public_origin
    try:return public_origin()
    except ValueError:raise WorkflowError('A verified public email-link origin is not configured.',503) from None


def field(data, key, minimum=1, maximum=200):
    value = data.get(key, '')
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise WorkflowError(f'Check the {key.replace("_", " ")} field.')
    value = value.strip()
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise WorkflowError('Invalid text characters.')
    return value


def email_address(data):
    email = field(data, 'email', maximum=254).casefold()
    local, _, domain = email.partition('@')
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", email) or len(local)>64 or local.startswith('.') or local.endswith('.') or '..' in local:
        raise WorkflowError('Enter a valid email address.')
    return email


def queue(db, email, subject, body):
    from app.controls import capacity
    capacity(db,'mail')
    message_id=str(uuid.uuid4())
    db.execute('INSERT INTO outbox(id,recipient,subject,body,created_at) VALUES (?,?,?,?,?)', (message_id, email, subject, body, now()))
    return message_id


def issue_token(db, application, purpose):
    raw = secrets.token_urlsafe(32)
    db.execute('UPDATE tokens SET used_at=? WHERE application_id=? AND purpose=? AND used_at IS NULL', (now(), application['id'], purpose))
    lifetime = 86400 if purpose == 'verify' else 1800
    db.execute('INSERT INTO tokens(digest,application_id,purpose,expires_at) VALUES (?,?,?,?)', (digest(raw), application['id'], purpose, now()+lifetime))
    link = public_base() + '/access#token=' + raw
    subject = 'STRATEVO — verify your application email' if purpose == 'verify' else 'STRATEVO — approved supplier access'
    body = ('Confirm your email to submit your application for manual review.' if purpose == 'verify' else 'Your application is approved. Use this single-use link to access your supplier account.')
    queue(db, application['email'], subject, f'{body}\n\n{link}\n\nThis link expires in {24 if purpose == "verify" else 0.5} hours. If you did not request this, ignore this email. Access does not certify your business or create a contract.')


def apply(data):
    rate_limit('applications', 30, 3600)
    public_base()
    company = field(data, 'company')
    contact = field(data, 'contact')
    email = email_address(data)
    country = field(data, 'country', maximum=100)
    category = field(data, 'category', maximum=150)
    capabilities = field(data, 'capabilities', minimum=20, maximum=4000)
    whatsapp = field(data, 'whatsapp', minimum=0, maximum=60)
    wechat = field(data, 'wechat', minimum=0, maximum=100)
    if not whatsapp and not wechat: raise WorkflowError('Provide WhatsApp or WeChat. You do not need both.')
    license_number = field(data, 'license_number', maximum=150)
    if data.get('consent') is not True: raise WorkflowError('Confirm the application privacy notice.')
    encoded = field(data, 'license_pdf', maximum=2800000)
    try: document = base64.b64decode(encoded, validate=True)
    except Exception: raise WorkflowError('Upload a valid PDF license.')
    if not document.startswith(b'%PDF-') or not 20 <= len(document) <= 2*1024*1024:
        raise WorkflowError('License must be a PDF no larger than 2 MB.')
    # Signature/size checks are not malware scanning. Documents are attachment-only.
    application_id = str(uuid.uuid4())
    with database() as db:
        exists = db.execute('SELECT id FROM applications WHERE email=?', (email,)).fetchone()
        if not exists:
            inserted = db.execute('INSERT INTO applications(id,company,contact,email,country,category,capabilities,whatsapp,wechat,license_number,license_pdf,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(email) DO NOTHING RETURNING id', (application_id,company,contact,email,country,category,capabilities,whatsapp,wechat,license_number,encoded,'pending_email',now())).fetchone()
            if inserted:
                issue_token(db, {'id':application_id,'email':email}, 'verify')
    return {'message':'If this email is eligible, a verification email will be sent. Existing applicants can use the access form to request another link.'}


def request_access(data):
    rate_limit('access-email', 20, 3600)
    public_base()
    email = email_address(data)
    with database() as db:
        application = db.execute('SELECT id,email,status FROM applications WHERE email=?', (email,)).fetchone()
        if application and application['status'] in ('approved', 'pending_email'):
            issue_token(db, application, 'login' if application['status']=='approved' else 'verify')
    return {'message':'If your application is eligible, an email link will be sent. Pending applications require manager review; rejected applications do not have platform access.'}


def session(db, role, application_id=None):
    raw = secrets.token_urlsafe(32)
    db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (digest(raw), role, application_id, now()+28800))
    return raw


def consume(data):
    rate_limit('consume-link', 100, 3600)
    raw = field(data, 'token', minimum=40, maximum=100)
    with database() as db:
        token = db.execute('UPDATE tokens SET used_at=? WHERE digest=? AND used_at IS NULL AND expires_at>? RETURNING application_id,purpose', (now(), digest(raw), now())).fetchone()
        if not token: raise WorkflowError('This link has expired or was already used. Request another link.', 410)
        application = db.execute('SELECT id,status FROM applications WHERE id=?', (token['application_id'],)).fetchone()
        if token['purpose']=='verify' and application['status']=='pending_email':
            db.execute("UPDATE applications SET status='pending' WHERE id=? AND status='pending_email'", (application['id'],))
            db.execute('INSERT INTO audit VALUES (?,?,?,?)', (str(uuid.uuid4()), application['id'], 'email_verified', now()))
            return {'message':'Email verified. Your application is awaiting manager review, normally 1–3 business days.', 'status':'pending'}, None
        if token['purpose']=='login' and application['status']=='approved':
            return {'message':'Signed in.', 'status':'approved', 'redirect':'/portal'}, session(db, 'supplier', application['id'])
        raise WorkflowError('This application does not have access.', 403)


def admin_login(data):
    rate_limit('admin-login', 10, 900)
    from app.admin_auth import login
    named=login(data)
    if named is not None:return named
    password = field(data, 'password', maximum=300)
    if not verify_password(password): raise WorkflowError('Sign-in failed.', 401)
    with database() as db: token = session(db, 'admin')
    return {'role':'admin'}, token


def authenticate(raw, role=None):
    if not raw: raise WorkflowError('Please sign in.', 401)
    with database() as db:
        result = db.execute('SELECT role,application_id FROM sessions WHERE digest=? AND expires_at>?', (digest(raw), now())).fetchone()
        if not result or (role and result['role']!=role): raise WorkflowError('Access denied.', 403)
        if result['role']=='supplier':
            app = db.execute('SELECT status FROM applications WHERE id=?', (result['application_id'],)).fetchone()
            if not app or app['status']!='approved': raise WorkflowError('Supplier access is not approved.', 403)
        identity=dict(result)
        if result['role']=='admin':
            from app.admin_auth import validate
            identity['actor']=validate(db,raw)
        if result['role']=='publisher':
            from app.controls import suspended
            if suspended(db,result['application_id']):raise WorkflowError('This supplier account is suspended.',403)
        return identity


def logout(raw):
    with database() as db: db.execute('DELETE FROM sessions WHERE digest=?', (digest(raw or ''),))
    return {'message':'Signed out.'}


def applications():
    with database() as db:
        rows = db.execute('SELECT id,company,contact,email,country,category,capabilities,whatsapp,wechat,license_number,status,created_at,reviewed_at,review_note FROM applications ORDER BY created_at DESC LIMIT 200').fetchall()
        total = db.execute('SELECT COUNT(*) AS total FROM applications').fetchone()['total']
        queued = db.execute('SELECT COUNT(*) AS total FROM outbox WHERE sent_at IS NULL').fetchone()['total']
    return {'applications':[dict(row) for row in rows], 'total':total, 'queued_emails':queued, 'smtp_configured':bool(os.environ.get('SMTP_HOST') and os.environ.get('MAIL_FROM'))}


def review(data):
    aid = field(data, 'id', maximum=50)
    decision = field(data, 'decision', maximum=20)
    note = field(data, 'note', minimum=0, maximum=2000)
    if decision not in ('approved','rejected'): raise WorkflowError('Choose approve or reject.')
    if decision == 'rejected' and not note: raise WorkflowError('Add a rejection reason for the supplier.')
    if decision == 'approved': public_base()
    with database() as db:
        app = db.execute('SELECT id,email,status FROM applications WHERE id=?', (aid,)).fetchone()
        if not app: raise WorkflowError('Application not found.', 404)
        cursor = db.execute("UPDATE applications SET status=?,reviewed_at=?,review_note=? WHERE id=? AND status='pending'", (decision,now(),note,aid))
        if cursor.rowcount != 1: raise WorkflowError('Only email-verified pending applications can be reviewed. Refresh the queue.', 409)
        db.execute('INSERT INTO audit VALUES (?,?,?,?)', (str(uuid.uuid4()),aid,decision,now()))
        if decision=='approved': issue_token(db, app, 'login')
        else: queue(db, app['email'], 'STRATEVO — application decision', 'Your application was not approved.\n\nManager reason:\n' + note + '\n\nNo platform access has been granted.')
    return {'message':f'Application {decision}. ' + ('Private supplier profile is available now. ' if decision == 'approved' else '') + 'Notification queued; delivery depends on the configured email service.', 'profile_url':('/portal?application=' + aid) if decision == 'approved' else None}


def license_document(aid):
    with database() as db: row = db.execute('SELECT license_pdf FROM applications WHERE id=?', (aid,)).fetchone()
    if not row: raise WorkflowError('Application not found.',404)
    return base64.b64decode(row['license_pdf'])


def approved_profile(application_id):
    with database() as db:
        row = db.execute("SELECT company,contact,email,country,category,capabilities,whatsapp,wechat,status,reviewed_at FROM applications WHERE id=? AND status='approved'", (application_id,)).fetchone()
    if not row: raise WorkflowError('Approved supplier profile not found.',404)
    return {'application':dict(row)}


def profile(identity):
    # Supplier identity comes from the authenticated session, never request parameters.
    return approved_profile(identity['application_id'])


def send_email_queue(limit=10, message_id=None):
    """At-least-once delivery: SMTP cannot offer atomic exactly-once delivery."""
    from app.intake import queue_pending
    from app import mail_policy
    if os.environ.get('MAIL_DELIVERY_ENABLED','false')!='true':raise WorkflowError('Email delivery is disabled; saved jobs remain queued.',503)
    limit=max(1,min(int(limit),10))
    with database() as db: queue_pending(db)
    host, sender = os.environ.get('SMTP_HOST'), os.environ.get('MAIL_FROM')
    if not host or not sender: raise WorkflowError('SMTP is not configured. Emails remain queued.',503)
    sender=email_address({'email':sender})
    sent, failed = 0, 0
    for _ in range(limit):
        with database() as db:
            query = 'SELECT id FROM outbox WHERE sent_at IS NULL AND claimed_until<? AND attempts<5'
            args = [now()]
            if message_id:
                query += ' AND id=?';args.append(message_id)
            row = db.execute(query+' ORDER BY created_at LIMIT 1', tuple(args)).fetchone()
            if not row: break
            claimed = db.execute('UPDATE outbox SET claimed_until=?,attempts=attempts+1 WHERE id=? AND sent_at IS NULL AND claimed_until<? RETURNING id,recipient,subject,body', (now()+120,row['id'],now())).fetchone()
            if not claimed: continue
            if mail_policy.obsolete(db,claimed):continue
            mail_policy.state(db,claimed['id'],'sending')
        try:rate_limit('smtp-delivery',60,3600)
        except WorkflowError:
            with database() as db:
                db.execute('UPDATE outbox SET attempts=attempts-1,claimed_until=? WHERE id=?',(now()+60,claimed['id']))
                mail_policy.state(db,claimed['id'],'rate_limited')
            break
        try:
            message = EmailMessage()
            message['From'], message['To'], message['Subject'] = sender, claimed['recipient'], claimed['subject']
            message['Message-ID'] = '<'+claimed['id']+'@'+sender.split('@')[-1]+'>'
            message.set_content(claimed['body'])
            with smtplib.SMTP(host, int(os.environ.get('SMTP_PORT','587')), timeout=8) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if os.environ.get('SMTP_USER'): smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                smtp.send_message(message)
            with database() as db:
                db.execute("UPDATE outbox SET sent_at=?,body='' WHERE id=?", (now(),claimed['id']))
                mail_policy.state(db,claimed['id'],'smtp_accepted')
            sent += 1
        except Exception:
            failed += 1  # Never expose provider errors or email contents in logs.
            with database() as db:
                row=db.execute('SELECT attempts FROM outbox WHERE id=?',(claimed['id'],)).fetchone()
                mail_policy.state(db,claimed['id'],'exhausted' if row and row['attempts']>=5 else 'retry_pending')
    return {'sent':sent,'failed':failed}


if __name__ == '__main__':
    import argparse
    import getpass
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init','hash-password','send-mail'])
    args = parser.parse_args()
    if args.command == 'hash-password': print(hash_password(getpass.getpass('New admin password (16+ characters): ')))
    elif args.command == 'init': initialize(); print('Supplier tables initialized.')
    else: print(json.dumps(send_email_queue()))
