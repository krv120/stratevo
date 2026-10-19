"""Versioned supplier product edits and staff publication review."""
import base64
import json
import secrets
import uuid
from app import suppliers as s, marketplace as market, controls, mail_policy

SCHEMA = '''
CREATE TABLE IF NOT EXISTS listing_reviews (
 product_id TEXT PRIMARY KEY REFERENCES market_products(id) ON DELETE CASCADE,
 revision BIGINT NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','approved','rejected','withdrawn')),
 rights_confirmed_at BIGINT NOT NULL, updated_at BIGINT NOT NULL,
 review_note TEXT NOT NULL DEFAULT '', reviewed_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS listing_review_status ON listing_reviews(status,updated_at);
CREATE TABLE IF NOT EXISTS listing_requests (
 request_digest TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES market_accounts(id) ON DELETE CASCADE,
 payload_digest TEXT NOT NULL, product_id TEXT NOT NULL REFERENCES market_products(id) ON DELETE CASCADE
);
'''


def create_pending(db, owner, payload, image):
    identifier=str(uuid.uuid4())
    db.execute('INSERT INTO market_products VALUES (?,?,?,?,?,?)',(identifier,owner,json.dumps(payload),image,'hidden',s.now()))
    db.execute('INSERT INTO listing_reviews(product_id,rights_confirmed_at,updated_at) VALUES (?,?,?)',(identifier,s.now(),s.now()))
    return identifier


def revision(data):
    value=data.get('revision')
    if type(value) is not int or value<0:raise s.WorkflowError('Reload the listing before saving.',409)
    return value


def notify(db, owner, identifier, event):
    profile=json.loads(db.execute('SELECT private_profile FROM market_accounts WHERE id=?',(owner,)).fetchone()['private_profile'])
    profile.pop('license_pdf',None)
    return mail_policy.log_event(db,event,owner+':update:'+str(uuid.uuid4()),{'supplier':profile,'product_id':identifier})


def add(raw,data):
    account=market.identity(raw)
    s.rate_limit('product-submit:'+account['id'],20,3600)
    payload,image=market.product_data(data,json.loads(account['private_profile']))
    key=data.get('request_key')
    if not isinstance(key,str) or not 32<=len(key)<=100:raise s.WorkflowError('Reload the form before submitting.',field='request_key')
    digest=s.digest(account['id']+':'+key)
    fingerprint=s.digest(json.dumps({'payload':payload,'image':image},sort_keys=True))
    notice=None
    with s.database() as db:
        controls.capacity(db,'lock')
        if controls.suspended(db,account['id']):raise s.WorkflowError('This account is suspended.',403)
        previous=db.execute('SELECT * FROM listing_requests WHERE request_digest=?',(digest,)).fetchone()
        if previous:
            if previous['payload_digest']!=fingerprint:raise s.WorkflowError('This request was used for different details. Reload your listings.',409)
            identifier=previous['product_id']
        else:
            controls.capacity(db,'product',len(image))
            n=db.execute('SELECT COUNT(*) AS n FROM market_products WHERE owner_id=?',(account['id'],)).fetchone()['n']
            if n>=500:raise s.WorkflowError('Listing limit reached. Contact STRATEVO.',409)
            identifier=create_pending(db,account['id'],payload,image)
            db.execute('INSERT INTO listing_requests VALUES (?,?,?,?)',(digest,account['id'],fingerprint,identifier))
            notice=notify(db,account['id'],identifier,'product_submitted')
    if notice:mail_policy.dispatch_notice(notice)
    return {'id':identifier,'submitted':True,'message':'Submitted for review. Your product is not public until approved.'}


def edit(raw,data):
    account=market.identity(raw);identifier=s.field(data,'id',maximum=40);expected=revision(data)
    s.rate_limit('product-edit:'+account['id'],30,3600)
    payload,image=market.product_data(data,json.loads(account['private_profile']))
    remove=data.get('remove_image',False)
    if not isinstance(remove,bool):raise s.WorkflowError('Choose whether to remove the photo.',field='remove_image')
    with s.database() as db:
        controls.capacity(db,'lock')
        if controls.suspended(db,account['id']):raise s.WorkflowError('This account is suspended.',403)
        row=db.execute('SELECT p.*,COALESCE(r.revision,0) AS revision FROM market_products p LEFT JOIN listing_reviews r ON r.product_id=p.id WHERE p.id=? AND p.owner_id=?',(identifier,account['id'])).fetchone()
        if not row:raise s.WorkflowError('Listing not found.',404)
        if row['revision']!=expected:raise s.WorkflowError('This listing changed. Reload it before editing again.',409)
        if image:controls.capacity(db,'product',max(0,len(image)-len(row['image'])))
        replacement='' if remove else image or row['image']
        db.execute("UPDATE market_products SET public_payload=?,image=?,visibility='hidden' WHERE id=?",(json.dumps(payload),replacement,identifier))
        db.execute("INSERT INTO listing_reviews VALUES (?,?, 'pending',?,?, '', '') ON CONFLICT(product_id) DO UPDATE SET revision=excluded.revision,status='pending',rights_confirmed_at=excluded.rights_confirmed_at,updated_at=excluded.updated_at,review_note='',reviewed_by=''",(identifier,expected+1,s.now(),s.now()))
        notice=notify(db,account['id'],identifier,'product_updated')
        controls.event(db,'supplier:'+account['id'],'product_resubmitted',identifier)
    mail_policy.dispatch_notice(notice)
    return {'id':identifier,'revision':expected+1,'submitted':True,'message':'Changes saved and submitted for review. The listing is hidden until approved.'}


def own_photo(raw,identifier):
    account=market.identity(raw)
    with s.database() as db:row=db.execute('SELECT image FROM market_products WHERE id=? AND owner_id=?',(identifier,account['id'])).fetchone()
    if not row or not row['image']:raise s.WorkflowError('Photo not found.',404)
    return base64.b64decode(row['image'])


def review_queue(offset=0):
    from app.operations import page_number
    offset=page_number(offset)
    with s.database() as db:
        rows=db.execute("SELECT p.*,COALESCE(r.revision,0) AS revision,COALESCE(r.status,'legacy') AS review_status,COALESCE(r.review_note,'') AS review_note FROM market_products p LEFT JOIN listing_reviews r ON r.product_id=p.id ORDER BY CASE WHEN r.status='pending' THEN 0 ELSE 1 END,COALESCE(r.updated_at,p.created_at) DESC,p.id LIMIT 26 OFFSET ?",(offset,)).fetchall()
    return {'products':[{**market.public_product(r),'image_url':'/api/admin/product-image/'+r['id'] if r['image'] else None,'owner_id':r['owner_id'],'revision':r['revision'],'visibility':r['visibility'],'review_status':r['review_status'],'review_note':r['review_note']} for r in rows[:25]],'has_more':len(rows)>25,'offset':offset}


def decide(data,actor):
    identifier=s.field(data,'id',maximum=40);expected=revision(data)
    action=data.get('action');note=s.field(data,'note',minimum=10,maximum=2000)
    if action not in ('approve','reject','hide'):raise s.WorkflowError('Choose a review decision.')
    with s.database() as db:
        controls.capacity(db,'lock')
        row=db.execute('SELECT p.*,COALESCE(r.revision,0) AS revision,COALESCE(r.status,\'legacy\') AS review_status FROM market_products p LEFT JOIN listing_reviews r ON r.product_id=p.id WHERE p.id=?',(identifier,)).fetchone()
        if not row:raise s.WorkflowError('Listing not found.',404)
        if row['revision']!=expected:raise s.WorkflowError('The listing changed. Reload and review the current version.',409)
        if action=='approve' and (row['review_status']!='pending' or controls.suspended(db,row['owner_id'])):raise s.WorkflowError('Only a pending listing from an active account can be approved.',409)
        state='approved' if action=='approve' else 'rejected'
        db.execute("UPDATE market_products SET visibility=? WHERE id=?",('published' if action=='approve' else 'hidden',identifier))
        db.execute('INSERT INTO listing_reviews VALUES (?,?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET revision=excluded.revision,status=excluded.status,updated_at=excluded.updated_at,review_note=excluded.review_note,reviewed_by=excluded.reviewed_by',(identifier,expected+1,state,0,s.now(),note,actor))
        controls.event(db,actor,'listing_'+action,identifier)
        notice=notify(db,row['owner_id'],identifier,'listing_reviewed')
        email=db.execute('SELECT email FROM market_accounts WHERE id=?',(row['owner_id'],)).fetchone()['email']
        # A queue capacity/transport failure must not reverse a takedown decision.
        try:
            mail=s.queue(db,email,'STRATEVO — listing review decision','Listing '+identifier+'\nDecision: '+state+'\nReason: '+note+'\n\nYou can edit your listing or request a review at info@stratevo.store. Include the listing reference and any supporting evidence.\nhttps://www.stratevo.online/supplier/account')
        except s.WorkflowError:pass
    mail_policy.dispatch_notice(notice)
    return {'message':'Decision saved. The supplier can see the reason in their account. Email delivery depends on the configured mail service.'}
