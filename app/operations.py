"""Private operations metadata; no unauthenticated registry or browser persistence."""
import json
import uuid
from app import suppliers as s

SCHEMA='''
CREATE TABLE IF NOT EXISTS suppliers (
 id TEXT PRIMARY KEY REFERENCES market_accounts(id) ON DELETE CASCADE,
 contact_email TEXT NOT NULL, contact_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',
 full_metadata TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', source TEXT NOT NULL DEFAULT 'user_submission',
 featured INTEGER NOT NULL DEFAULT 0, verification_note TEXT NOT NULL DEFAULT '', created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS platform_settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_notifications (
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, event_type TEXT NOT NULL, recipient TEXT NOT NULL,
 subject TEXT NOT NULL, body_preview TEXT NOT NULL, payload_json TEXT NOT NULL,
 delivery_status TEXT NOT NULL DEFAULT 'queued_in_admin_inbox', error_message TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL, read_at BIGINT, outbox_id TEXT REFERENCES outbox(id) ON DELETE SET NULL,
 UNIQUE(entity_id,event_type)
);
CREATE INDEX IF NOT EXISTS notifications_date ON admin_notifications(created_at,id);
CREATE TABLE IF NOT EXISTS notification_attempts (
 id TEXT PRIMARY KEY, notification_id TEXT REFERENCES admin_notifications(id) ON DELETE CASCADE,
 transport TEXT NOT NULL, delivery_status TEXT NOT NULL, error_message TEXT NOT NULL, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS discovered_leads (
 id TEXT PRIMARY KEY, query TEXT NOT NULL, lead_type TEXT NOT NULL, company_name TEXT NOT NULL,
 country TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
 created_at BIGINT NOT NULL, actor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS discovered_leads_date ON discovered_leads(created_at,id);
'''
TABLES=('suppliers','platform_settings','admin_notifications','notification_attempts','discovered_leads')


def upsert_supplier(db,identifier,profile,created_at=None):
    previous=db.execute('SELECT full_metadata FROM suppliers WHERE id=?',(identifier,)).fetchone()
    profile={**(json.loads(previous['full_metadata']) if previous else {}),**profile}
    db.execute('INSERT INTO suppliers(id,contact_email,contact_name,phone,full_metadata,created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET contact_email=excluded.contact_email,contact_name=excluded.contact_name,phone=excluded.phone,full_metadata=excluded.full_metadata',
               (identifier,profile['email'],profile['contact'],profile.get('phone',''),json.dumps(profile),created_at or s.now()))


def page_number(value):
    try:n=int(value)
    except (ValueError,TypeError):raise s.WorkflowError('Invalid page.') from None
    if not 0<=n<=100000:raise s.WorkflowError('Invalid page.')
    return n


def supplier_rows(offset=0,query=''):
    offset=page_number(offset)
    if len(query)>100:raise s.WorkflowError('Search is too long.')
    with s.database() as db:
        pattern='%'+query.lower().replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        rows=db.execute("SELECT a.id,a.private_profile,a.created_at,a.verified_at,p.full_metadata,p.status,p.source,p.featured,p.verification_note FROM market_accounts a LEFT JOIN suppliers p ON p.id=a.id WHERE LOWER(a.private_profile) LIKE ? ESCAPE '!' ORDER BY a.created_at DESC,a.id LIMIT 26 OFFSET ?",(pattern,offset)).fetchall()
        result=[]
        for row in rows[:25]:
            profile=json.loads(row['full_metadata'] or row['private_profile']);profile.pop('license_pdf',None)
            result.append({'id':row['id'],'created_at':row['created_at'],'profile':profile,'status':row['status'] or 'new','source':row['source'] or 'user_submission','featured':bool(row['featured']),'verification_note':row['verification_note'] or '', 'email_confirmed':row['verified_at'] is not None})
    return {'suppliers':result,'has_more':len(rows)>25,'offset':offset,'notice':'NEW SUBMISSION is self-reported, not independent business verification. Seed research remains in the separate private research panel.'}


def supplier_action(data,actor):
    from app import controls, marketplace, mail_policy
    identifier=s.field(data,'id',maximum=40);action=data.get('action')
    if action not in ('verify','feature','edit'):raise s.WorkflowError('Unsupported action.')
    notice=None
    with s.database() as db:
        row=db.execute('SELECT * FROM market_accounts WHERE id=?',(identifier,)).fetchone()
        if not row:raise s.WorkflowError('Supplier not found.',404)
        profile=json.loads(row['private_profile']);upsert_supplier(db,identifier,profile)
        if action=='verify':
            note=s.field(data,'evidence',minimum=20,maximum=2000)
            db.execute("UPDATE suppliers SET status='reviewed',verification_note=? WHERE id=?",(note,identifier))
        elif action=='feature':
            if not isinstance(data.get('featured'),bool):raise s.WorkflowError('Choose featured or not featured.')
            db.execute('UPDATE suppliers SET featured=? WHERE id=?',(int(data['featured']),identifier))
        else:
            changes=data.get('profile')
            if not isinstance(changes,dict):raise s.WorkflowError('Provide profile fields.')
            # Changing email/ownership is not a simple administrative edit.
            allowed={'company','contact','country','city','phone','website','capabilities','categories','certifications','materials','regions','lead_time','employees','founded_year'}
            if set(changes)-allowed:raise s.WorkflowError('Unsupported profile field.')
            profile=marketplace.private_profile({**profile,**changes,'consent':True})
            db.execute('UPDATE market_accounts SET private_profile=? WHERE id=?',(json.dumps(profile),identifier));upsert_supplier(db,identifier,profile)
            notice=mail_policy.log_event(db,'supplier_published',identifier+':update:'+str(uuid.uuid4()),profile)
        controls.event(db,actor,'supplier_'+action,identifier)
    if notice:mail_policy.dispatch_notice(notice)
    return {'message':'Supplier updated. Review notes are not certification or automatic publication approval.'}


def lead_rows(offset=0,status='all'):
    offset=page_number(offset)
    if status not in ('all','new','contacted','qualified','rejected'):raise s.WorkflowError('Invalid lead status.')
    with s.database() as db:
        rows=db.execute('SELECT * FROM discovered_leads WHERE (?=\'all\' OR status=?) ORDER BY created_at DESC,id LIMIT 26 OFFSET ?',(status,status,offset)).fetchall()
    return {'leads':[{**dict(r),'lead':json.loads(r['payload_json'])} for r in rows[:25]],'has_more':len(rows)>25,'offset':offset}


def update_lead(data,actor):
    status=data.get('status');identifier=s.field(data,'id',maximum=40)
    if status not in ('new','contacted','qualified','rejected'):raise s.WorkflowError('Invalid lead status.')
    with s.database() as db:
        if db.execute('UPDATE discovered_leads SET status=? WHERE id=?',(status,identifier)).rowcount!=1:raise s.WorkflowError('Lead not found.',404)
        from app.controls import event
        event(db,actor,'lead_status',identifier)
    return {'message':'Lead status saved. Qualification is a staff decision, not AI verification.'}
