"""Public supplier introductions, private contacts and owner-authorized recovery."""
import json
import re
import secrets
import uuid
from app import suppliers as s, marketplace, normalization, controls, mail_policy, operations

FOCUSES=('industrial','packaging','consumer','food','textiles','electronics','custom')
LABELS=dict(zip(FOCUSES,('Industrial Components','Packaging & Materials','Consumer Products','Food & Ingredients','Textiles & Apparel','Electronics & Hardware','Custom Manufacturing')))
SCHEMA='''
CREATE TABLE IF NOT EXISTS supplier_directory (
 id TEXT PRIMARY KEY REFERENCES market_accounts(id) ON DELETE CASCADE,
 public_payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('published','withdrawn','hidden')),
 revision BIGINT NOT NULL DEFAULT 1, created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS directory_date ON supplier_directory(status,created_at,id);
'''
CONTACT=re.compile(r'(?:https?://|www\.)[^\s<>]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?<!\w)(?:[\w-]+\.)+[a-z]{2,63}(?:/[^\s<>]*)?|(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)',re.I)


def scrub(value,profile):
    from app.privacy import normalized
    text=CONTACT.sub('[contact removed]',normalized(value))
    for key in ('contact','email','phone','website','country','city'):
        private=profile.get(key,'').strip()
        if private:
            text=re.sub(r'(?<!\w)'+re.escape(normalized(private))+r'(?!\w)','[private detail removed]',text,flags=re.I)
    return text


def validate(data):
    if data.get('consent') is not True:raise s.WorkflowError('Please agree to the Terms and Privacy Policy.',field='consent')
    company=s.field(data,'company',minimum=2,maximum=120)
    focus=s.field(data,'focus',maximum=30)
    if focus not in FOCUSES:raise s.WorkflowError('Choose your focus area.',field='focus')
    description=s.field(data,'description',minimum=20,maximum=2000)
    specialty=s.field(data,'specialty',minimum=0,maximum=160)
    profile={'contact':s.field(data,'contact',minimum=2,maximum=120),'email':s.email_address(data),
             'phone':s.field(data,'phone',minimum=0,maximum=80),'country':s.field(data,'country',minimum=0,maximum=100),
             'city':s.field(data,'city',minimum=0,maximum=100),'website':normalization.website(data.get('website',''))}
    public={'company':scrub(company,profile),'focus':focus,'focus_label':LABELS[focus],
            'specialty':scrub(specialty,profile),'description':scrub(description,profile)}
    if not public['company'].replace('[contact removed]','').replace('[private detail removed]','').strip():
        raise s.WorkflowError('Use a business name rather than a private contact name or address.',field='company')
    profile.update(company=public['company'],capabilities=public['description'],categories=[focus],license_pdf='')
    return profile,public


def projection(row):
    value=json.loads(row['public_payload'])
    # Allowlist only; new private fields can never leak through future schema changes.
    return {'id':row['id'],**{key:value.get(key,'') for key in ('company','focus','focus_label','specialty','description')}}


def register(data):
    s.rate_limit('directory-register',30,3600)
    profile,public=validate(data)
    key=data.get('submission_key')
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,100}',key):raise s.WorkflowError('Reload the form before registering.',field='submission_key')
    fingerprint=s.digest(json.dumps({'private':profile,'public':public},sort_keys=True));mail=None
    with s.database() as db:
        controls.capacity(db,'lock')
        prior=db.execute('SELECT * FROM market_publications WHERE submission_digest=?',(s.digest(key),)).fetchone()
        if prior:
            if prior['payload_digest']!=fingerprint:raise s.WorkflowError('This request was used for different information. Reload your account before retrying.',409)
            if prior['created_at']<s.now()-86400:raise s.WorkflowError('Recovery link expired. Request a supplier sign-in email.',410)
            identifier=prior['account_id']
            if controls.suspended(db,identifier):raise s.WorkflowError('Account access is restricted. Contact STRATEVO.',403)
            row=db.execute('SELECT * FROM supplier_directory WHERE id=?',(identifier,)).fetchone()
            if not row:raise s.WorkflowError('This submission cannot be recovered automatically. Please contact STRATEVO.',409)
        else:
            if db.execute('SELECT id FROM market_accounts WHERE email=?',(profile['email'],)).fetchone():
                raise s.WorkflowError('Registration could not create an account. If you registered previously, use Supplier Sign In.',409,field='email')
            controls.capacity(db,'account')
            identifier=str(uuid.uuid4())
            db.execute('INSERT INTO market_accounts VALUES (?,?,?,?,NULL)',(identifier,profile['email'],json.dumps(profile),s.now()))
            db.execute('INSERT INTO market_publications VALUES (?,?,?,?)',(identifier,s.digest(key),fingerprint,s.now()))
            db.execute("INSERT INTO supplier_directory VALUES (?,?,'published',1,?)",(identifier,json.dumps(public),s.now()))
            operations.upsert_supplier(db,identifier,profile)
            try:
                s.public_base();mail=marketplace.issue(db,{'id':identifier,'email':profile['email']})
            except s.WorkflowError as error:
                if error.status!=503:raise
            from app.intake import enqueue
            enqueue(db,'supplier',identifier,'Supplier focus: '+public['focus_label'])
            row=db.execute('SELECT * FROM supplier_directory WHERE id=?',(identifier,)).fetchone()
        token=s.session(db,'publisher',identifier)
    if mail and mail_policy.transport() not in ('admin_inbox','webhook'):
        try:s.send_email_queue(limit=1,message_id=mail)
        except Exception:pass
    notification=mail_policy.dispatch_entity('supplier',identifier)
    return {'published':row['status']=='published','supplier':projection(row),'supplier_id':identifier,
            'email_notification_status':notification,'message':'Registration saved. Your supplier listing is available in the Marketplace.' if row['status']=='published' else 'Your account exists. Open your account to check the listing status.',
            '_session':token,'redirect':'/supplier/account','storage':__import__('app.settings',fromlist=['storage_status']).storage_status()}


def public(query='',focus='',offset=0):
    from app.operations import page_number
    offset=page_number(offset)
    if not isinstance(query,str) or len(query)>100 or focus not in ('',*FOCUSES):raise s.WorkflowError('Check your search filters.')
    with s.database() as db:
        # Public payload only is searched; private contacts are never a searchable index.
        term='%'+query.lower().replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        category="(d.public_payload::jsonb->>'focus')" if db.postgres else "json_extract(d.public_payload,'$.focus')"
        where="d.status='published' AND NOT EXISTS(SELECT 1 FROM account_controls c WHERE c.account_id=d.id AND c.suspended=1) AND LOWER(d.public_payload) LIKE ? ESCAPE '!'"
        args=[term]
        if focus:where+=' AND '+category+'=?';args.append(focus)
        total=db.execute('SELECT COUNT(*) AS n FROM supplier_directory d WHERE '+where,tuple(args)).fetchone()['n']
        rows=db.execute('SELECT d.* FROM supplier_directory d WHERE '+where+' ORDER BY d.created_at DESC,d.id LIMIT 24 OFFSET ?',tuple(args+[offset])).fetchall()
    return {'suppliers':[projection(r) for r in rows],'total':total,'has_more':offset+len(rows)<total,'offset':offset}


def mine(raw):
    account=marketplace.identity(raw)
    with s.database() as db:row=db.execute('SELECT * FROM supplier_directory WHERE id=?',(account['id'],)).fetchone()
    return {'profile':{k:v for k,v in json.loads(account['private_profile']).items() if k!='license_pdf'},
            'supplier':projection(row) if row else None,'status':row['status'] if row else 'not_listed',
            'revision':row['revision'] if row else 0,'email_confirmed':account['verified_at'] is not None}


def update(raw,data):
    account=marketplace.identity(raw)
    s.rate_limit('directory-edit:'+account['id'],20,3600)
    profile,public=validate({**data,'email':account['email']})
    if type(data.get('revision')) is not int:raise s.WorkflowError('Reload your account first.',409)
    with s.database() as db:
        controls.capacity(db,'lock')
        if controls.suspended(db,account['id']):raise s.WorkflowError('Account access is restricted.',403)
        row=db.execute('SELECT * FROM supplier_directory WHERE id=?',(account['id'],)).fetchone()
        if row and row['status']=='hidden':raise s.WorkflowError('This listing was removed by staff. Contact STRATEVO for review.',403)
        if (row['revision'] if row else 0)!=data['revision']:raise s.WorkflowError('Your listing has changed. Reload it before saving.',409)
        db.execute("INSERT INTO supplier_directory VALUES (?,?,'published',1,?) ON CONFLICT(id) DO UPDATE SET public_payload=excluded.public_payload,status='published',revision=supplier_directory.revision+1",(account['id'],json.dumps(public),s.now()))
        db.execute('UPDATE market_accounts SET private_profile=? WHERE id=?',(json.dumps(profile),account['id']))
        operations.upsert_supplier(db,account['id'],profile)
        notice=mail_policy.log_event(db,'supplier_updated',account['id']+':update:'+str(uuid.uuid4()),profile)
    mail_policy.dispatch_notice(notice)
    return {'message':'Your listing and private profile have been updated.','supplier':mine(raw)['supplier']}


def withdraw(raw):
    account=marketplace.identity(raw)
    with s.database() as db:
        controls.capacity(db,'lock')
        db.execute("UPDATE supplier_directory SET status='withdrawn',revision=revision+1 WHERE id=? AND status!='hidden'",(account['id'],))
    return {'message':'Your listing has been withdrawn.'}


def sync(raw,data):
    """Reconcile public cache only against an authenticated, existing server record.

    Never resurrect deleted/moderated data or trust browser data as ownership proof.
    """
    account=marketplace.identity(raw)
    if data.get('id')!=account['id']:raise s.WorkflowError('This backup does not belong to your account.',403)
    with s.database() as db:row=db.execute('SELECT * FROM supplier_directory WHERE id=?',(account['id'],)).fetchone()
    if not row:raise s.WorkflowError('The server record is unavailable. A browser backup cannot restore private account ownership. Contact STRATEVO.',409)
    return {'supplier':projection(row) if row['status']=='published' else None,'status':row['status'],'reconciled':True}


def moderate(data,actor):
    identifier=s.field(data,'id',maximum=40);note=s.field(data,'note',minimum=10,maximum=2000)
    with s.database() as db:
        controls.capacity(db,'lock')
        changed=db.execute("UPDATE supplier_directory SET status='hidden',revision=revision+1 WHERE id=?",(identifier,))
        if not changed.rowcount:raise s.WorkflowError('Listing not found.',404)
        controls.event(db,actor,'supplier_listing_removed',identifier)
        notice=mail_policy.log_event(db,'listing_removed',identifier+':update:'+str(uuid.uuid4()),{'id':identifier,'reason':note})
        email=db.execute('SELECT email FROM market_accounts WHERE id=?',(identifier,)).fetchone()['email']
        try:s.queue(db,email,'STRATEVO — listing removal','Your listing was removed.\nReason: '+note+'\nRequest a review: info@stratevo.store. Include your listing reference: '+identifier)
        except s.WorkflowError:pass
    mail_policy.dispatch_notice(notice)
    return {'message':'Listing removed. A decision email is queued when capacity permits.'}
