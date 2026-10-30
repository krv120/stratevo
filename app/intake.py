"""Private customer inquiries, supplier review and transactional owner notifications."""
import json
import os
import re
import uuid
from app import suppliers as s

SCHEMA = '''
CREATE TABLE IF NOT EXISTS customer_inquiries (
 id TEXT PRIMARY KEY, submission_digest TEXT NOT NULL UNIQUE, payload_digest TEXT NOT NULL,
 created_at BIGINT NOT NULL, status TEXT NOT NULL CHECK(status IN ('new','contacted','qualified','closed')),
 payload TEXT NOT NULL, consent_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS inquiry_status_date ON customer_inquiries(status,created_at);
CREATE TABLE IF NOT EXISTS supplier_reviews (
 account_id TEXT PRIMARY KEY REFERENCES market_accounts(id),
 status TEXT NOT NULL CHECK(status IN ('new','contacted','reviewed','declined')), updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_jobs (
 id TEXT PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('customer','supplier')),
 entity_id TEXT NOT NULL, summary TEXT NOT NULL, created_at BIGINT NOT NULL,
 outbox_id TEXT REFERENCES outbox(id), UNIQUE(entity_type,entity_id)
);
'''
TABLES = ('customer_inquiries','supplier_reviews','notification_jobs')
CONSENT_VERSION = 'inquiry-2026-10-12'
SECRET = re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{24,}|-----BEGIN .*PRIVATE KEY-----')


def recipient(db=None):
    from app.mail_policy import admin_recipient
    return admin_recipient(db) or None


def enqueue(db, kind, entity_id, summary):
    """Same transaction as the record: a mail failure cannot lose the inquiry."""
    db.execute('INSERT INTO notification_jobs VALUES (?,?,?,?,?,NULL) ON CONFLICT(entity_type,entity_id) DO NOTHING',
               (str(uuid.uuid4()),kind,entity_id,summary[:500],s.now()))
    from app.mail_policy import log_event
    row=db.execute('SELECT payload FROM customer_inquiries WHERE id=?',(entity_id,)).fetchone() if kind=='customer' else db.execute('SELECT private_profile FROM market_accounts WHERE id=?',(entity_id,)).fetchone()
    payload=json.loads(row['payload'] if kind=='customer' else row['private_profile']) if row else {'summary':summary}
    payload.pop('license_pdf',None)
    if kind=='supplier':payload['products']=[json.loads(r['public_payload']) for r in db.execute('SELECT public_payload FROM market_products WHERE owner_id=? ORDER BY created_at DESC LIMIT 50',(entity_id,)).fetchall()]
    log_event(db,'buyer_inquiry' if kind=='customer' else 'supplier_submitted',entity_id,payload)
    queue_pending(db,kind,entity_id)


def queue_pending(db, kind=None, entity_id=None):
    from app.controls import capacity
    capacity(db,'lock')
    destination=recipient(db)
    from app import mail_policy
    if not destination and mail_policy.transport()=='webhook':destination='admin-inbox@example.invalid'
    if not destination:return 0
    try:base=s.public_base()
    except s.WorkflowError:
        from app.settings import canonical
        base=canonical()
    query='SELECT id,entity_type,entity_id,summary FROM notification_jobs WHERE outbox_id IS NULL'
    args=()
    if kind:query+=' AND entity_type=? AND entity_id=?';args=(kind,entity_id)
    query+=' ORDER BY created_at LIMIT 25'
    count=0
    for job in db.execute(query,args).fetchall():
        # Lock/claim the row before inserting mail, avoiding duplicate jobs on PostgreSQL.
        locked=db.execute('UPDATE notification_jobs SET created_at=created_at WHERE id=? AND outbox_id IS NULL RETURNING id',(job['id'],)).fetchone()
        if not locked:continue
        body=('A '+job['entity_type']+' submission was saved.\nReference: '+job['entity_id']+'\n'+job['summary']+
              '\n\nSign in to review private details: '+base+'/admin#'+job['entity_type']+'-'+job['entity_id']+
              '\n\nThis notification is not supplier verification, a quote or a commercial commitment.')
        notification=db.execute('SELECT payload_json FROM admin_notifications WHERE entity_id=?',(job['entity_id'],)).fetchone()
        if notification:body+='\n\nSubmitted private details:\n'+json.dumps(json.loads(notification['payload_json']),indent=2,ensure_ascii=False)
        try:mail=s.queue(db,destination,'STRATEVO — new '+job['entity_type']+' submission',body)
        except s.WorkflowError as error:
            if error.status==503:break  # Retain the durable notification intent until space/configuration recovers.
            raise
        db.execute('UPDATE notification_jobs SET outbox_id=? WHERE id=?',(mail,job['id']));mail_policy.bind_notification(db,job['entity_type'],job['entity_id'],mail);count+=1
    return count


def submit(data):
    s.rate_limit('customer-intake-global',40,3600)
    if s.field(data,'website_confirm',minimum=0,maximum=200):raise s.WorkflowError('Submission could not be accepted.',400)
    key=s.field(data,'submission_key',minimum=32,maximum=100)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{32,100}',key):raise s.WorkflowError('Reload the form and try again.')
    payload={k:s.field(data,k,minimum=minimum,maximum=maximum) for k,minimum,maximum in (
        ('name',1,120),('business',0,160),('product',3,200),('requirements',20,6000),
        ('destination',1,100),('quantity',1,100),('budget',0,150),('timeline',0,150),('contact',0,100))}
    payload['email']=s.email_address(data)
    if data.get('source') not in ('form','assessment'):raise s.WorkflowError('Invalid inquiry source.')
    payload['source']=data['source']
    if data.get('consent') is not True:raise s.WorkflowError('Confirm the inquiry privacy notice.')
    payload['follow_up_requested']=True
    payload['marketing_consent']=False  # No marketing subscription exists.
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False)
    if SECRET.search(raw):raise s.WorkflowError('Remove API keys or private keys from the inquiry.')
    fingerprint=s.digest(raw)
    with s.database() as db:
        # Preserve idempotent retries even when storage has reached its ceiling.
        from app.controls import capacity
        if not db.execute('SELECT id FROM customer_inquiries WHERE submission_digest=?',(s.digest(key),)).fetchone():capacity(db,'inquiry')
        new_id=str(uuid.uuid4())
        row=db.execute('INSERT INTO customer_inquiries VALUES (?,?,?,?,?,?,?) ON CONFLICT(submission_digest) DO NOTHING RETURNING id',
                       (new_id,s.digest(key),fingerprint,s.now(),'new',raw,CONSENT_VERSION)).fetchone()
        if not row:
            existing=db.execute('SELECT id,payload_digest FROM customer_inquiries WHERE submission_digest=?',(s.digest(key),)).fetchone()
            if existing['payload_digest']!=fingerprint:raise s.WorkflowError('This submission key was already used for different details. Start a new inquiry.',409)
            new_id=existing['id']
        else:
            enqueue(db,'customer',new_id,'Product: '+payload['product']+'\nDestination: '+payload['destination']+'\nQuantity: '+payload['quantity'])
    from app.settings import storage_status
    storage=storage_status()
    return {'id':new_id,'saved':True,'storage':storage,'message':storage['warning']+' '+'Your sourcing inquiry is saved. Keep this reference for follow-up. Email notification is queued separately; delivery is not yet confirmed. No order or payment has been created.'}


def notification_state(row):
    if not row.get('outbox_id'):return 'awaiting_configuration'
    if row.get('sent_at'):return 'smtp_accepted'
    if row.get('attempts',0)>=5:return 'failed_attention_required'
    if row.get('attempts',0)>0:return 'retry_pending'
    return 'queued'


def list_inquiries(status='all',offset=0):
    if status not in ('all','new','contacted','qualified','closed'):raise s.WorkflowError('Invalid status.')
    try:offset=int(offset)
    except (ValueError,TypeError):raise s.WorkflowError('Invalid page.') from None
    if not 0<=offset<=100000:raise s.WorkflowError('Invalid page.')
    where='' if status=='all' else ' WHERE c.status=?'
    args=[] if status=='all' else [status]
    with s.database() as db:
        rows=db.execute('SELECT c.*,j.outbox_id,o.sent_at,o.attempts FROM customer_inquiries c LEFT JOIN notification_jobs j ON j.entity_type=\'customer\' AND j.entity_id=c.id LEFT JOIN outbox o ON o.id=j.outbox_id'+where+' ORDER BY c.created_at DESC,c.id LIMIT 26 OFFSET ?',tuple(args+[offset])).fetchall()
    return {'inquiries':[{'id':r['id'],'created_at':r['created_at'],'status':r['status'],'details':json.loads(r['payload']),'consent_version':r['consent_version'],'notification':notification_state(dict(r))} for r in rows[:25]],'has_more':len(rows)>25,'offset':offset}


def update(data, supplier=False):
    identifier=s.field(data,'id',maximum=40)
    states=('new','contacted','reviewed','declined') if supplier else ('new','contacted','qualified','closed')
    status=data.get('status')
    if status not in states:raise s.WorkflowError('Invalid status.')
    with s.database() as db:
        if supplier:
            if not db.execute('SELECT id FROM market_accounts WHERE id=?',(identifier,)).fetchone():raise s.WorkflowError('Record not found.',404)
            db.execute('INSERT INTO supplier_reviews VALUES (?,?,?) ON CONFLICT(account_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at',(identifier,status,s.now()))
        else:
            changed=db.execute('UPDATE customer_inquiries SET status=? WHERE id=?',(status,identifier))
            if changed.rowcount!=1:raise s.WorkflowError('Record not found.',404)
        db.execute('INSERT INTO audit VALUES (?,?,?,?)',(str(uuid.uuid4()),identifier,('supplier-review:' if supplier else 'inquiry:')+status,s.now()))
    return {'message':'Review status updated. Supplier publication is controlled separately.' if supplier else 'Inquiry status updated.'}


def delivery_overview():
    with s.database() as db:
        missing=db.execute('SELECT COUNT(*) AS n FROM notification_jobs WHERE outbox_id IS NULL').fetchone()['n']
        failed=db.execute('SELECT COUNT(*) AS n FROM outbox WHERE sent_at IS NULL AND attempts>=5').fetchone()['n']
        queued=db.execute('SELECT COUNT(*) AS n FROM outbox WHERE sent_at IS NULL AND attempts<5').fetchone()['n']
        states={row['status']:row['n'] for row in db.execute('SELECT status,COUNT(*) AS n FROM mail_state GROUP BY status').fetchall()}
    return {'states':states,'recipient_configured':bool(recipient()),'awaiting_configuration':missing,'queued':queued,'failed':failed,'notice':'SMTP acceptance is not inbox receipt. Unassigned jobs can be waiting for configuration or queue capacity. Configure and monitor the mail worker.'}


def retry_failed():
    """Manager action: retry only exhausted owner alerts, never expired login links."""
    s.rate_limit('owner-notification-retry',5,3600)
    with s.database() as db:
        changed=db.execute('UPDATE outbox SET attempts=0,claimed_until=0 WHERE sent_at IS NULL AND attempts>=5 AND claimed_until<? AND id IN (SELECT outbox_id FROM notification_jobs WHERE outbox_id IS NOT NULL)',(s.now(),))
    return {'message':str(changed.rowcount)+' owner notifications requeued. The mail worker must run; inbox receipt is not confirmed.'}
