"""Private rights operations and opt-in retention. Defaults never delete business records."""
import json
import os
from app import suppliers as s, controls, settings


def _record(db,kind,identifier):
    if kind=='customer':row=db.execute('SELECT * FROM customer_inquiries WHERE id=?',(identifier,)).fetchone()
    elif kind=='supplier':row=db.execute('SELECT * FROM market_accounts WHERE id=?',(identifier,)).fetchone()
    elif kind=='legacy':row=db.execute('SELECT * FROM applications WHERE id=?',(identifier,)).fetchone()
    else:raise s.WorkflowError('Choose customer, supplier or legacy.')
    if not row:raise s.WorkflowError('Record not found.',404)
    return dict(row)


def export(kind,identifier):
    with s.database() as db:
        row=_record(db,kind,identifier)
        if kind=='customer':return {'id':row['id'],'created_at':row['created_at'],'status':row['status'],'details':json.loads(row['payload']),'consent_version':row['consent_version']}
        profile=json.loads(row['private_profile']) if kind=='supplier' else row
        profile={k:v for k,v in profile.items() if k not in ('license_pdf','private_profile')}
        products=[dict(r) for r in db.execute('SELECT id,public_payload,visibility,created_at FROM market_products WHERE owner_id=? ORDER BY created_at,id',(identifier,)).fetchall()] if kind=='supplier' else []
        directory=db.execute('SELECT public_payload,status,revision FROM supplier_directory WHERE id=?',(identifier,)).fetchone() if kind=='supplier' else None
        return {'id':identifier,'directory':dict(directory) if directory else None,'products':products,'profile':profile,'document_included':False,'notice':'Documents require a separate authorized, secure review; no access tokens are exported.'}


def _mail_ids(db,kind,identifier,row):
    ids=[r['outbox_id'] for r in db.execute('SELECT outbox_id FROM notification_jobs WHERE entity_type=? AND entity_id=?',(kind,identifier)).fetchall() if r['outbox_id']]
    if kind in ('supplier','legacy'):
        email=row['email']
        if kind=='supplier':
            rows=db.execute("SELECT id FROM outbox WHERE recipient=? AND subject IN ('STRATEVO — confirm your supplier email','STRATEVO — listing removal','STRATEVO — listing review decision')",(email,)).fetchall()
        else:
            rows=db.execute("SELECT id FROM outbox WHERE recipient=? AND subject IN ('STRATEVO — verify your application email','STRATEVO — approved supplier access','STRATEVO — application decision')",(email,)).fetchall()
        ids += [r['id'] for r in rows]
    ids += [r['outbox_id'] for r in db.execute('SELECT outbox_id FROM admin_notifications WHERE entity_id=? OR entity_id LIKE ?',(identifier,identifier+':update:%')).fetchall() if r['outbox_id']]
    for identifier in set(ids):
        # Lock before reading the lease; concurrent SMTP claiming cannot race erasure.
        message=db.execute('UPDATE outbox SET created_at=created_at WHERE id=? RETURNING claimed_until,sent_at',(identifier,)).fetchone()
        if message and message['sent_at'] is None and message['claimed_until']>s.now():raise s.WorkflowError('A related email is being processed. Retry deletion after the worker lease expires.',409)
    return set(ids)


def erase_in(db,kind,identifier,actor):
    row=_record(db,kind,identifier);mails=_mail_ids(db,kind,identifier,row)
    for mail in mails:db.execute('DELETE FROM admin_notifications WHERE outbox_id=?',(mail,))
    db.execute('DELETE FROM admin_notifications WHERE entity_id=? OR entity_id LIKE ?',(identifier,identifier+':update:%'))
    db.execute('DELETE FROM notification_jobs WHERE entity_type=? AND entity_id=?',(kind,identifier))
    for mail in mails:db.execute('DELETE FROM outbox WHERE id=?',(mail,))
    if kind=='customer':db.execute('DELETE FROM customer_inquiries WHERE id=?',(identifier,))
    elif kind=='supplier':
        db.execute('DELETE FROM listing_reports WHERE product_id IN (SELECT id FROM market_products WHERE owner_id=?)',(identifier,))
        db.execute('DELETE FROM market_products WHERE owner_id=?',(identifier,))
        db.execute('DELETE FROM market_tokens WHERE owner_id=?',(identifier,))
        db.execute('DELETE FROM supplier_reviews WHERE account_id=?',(identifier,))
        db.execute('DELETE FROM account_controls WHERE account_id=?',(identifier,))
        db.execute("DELETE FROM sessions WHERE role='publisher' AND application_id=?",(identifier,))
        db.execute('DELETE FROM market_accounts WHERE id=?',(identifier,))
    else:
        db.execute('DELETE FROM tokens WHERE application_id=?',(identifier,))
        db.execute("DELETE FROM sessions WHERE role='supplier' AND application_id=?",(identifier,))
        db.execute('DELETE FROM applications WHERE id=?',(identifier,))
    db.execute('DELETE FROM audit WHERE application_id=?',(identifier,))
    db.execute('DELETE FROM security_events WHERE entity_id=?',(identifier,))
    # Deletion event does not retain the erased entity ID or its contact data.
    controls.event(db,actor,'privacy_erasure_'+kind)


def erase(data,actor):
    if os.environ.get('RIGHTS_ERASURE_APPROVED')!='true':raise s.WorkflowError('Erasure is disabled until the operator approves identity verification, backup and deletion procedures.',403)
    identifier=s.field(data,'id',maximum=40);kind=data.get('kind')
    if data.get('confirm')!=identifier:raise s.WorkflowError('Confirm the exact record ID to delete.')
    with s.database() as db:
        controls.capacity(db,'lock');erase_in(db,kind,identifier,actor)
    return {'message':'Live record and related private data deleted. Previously delivered mail and backups need separate controlled deletion handling.'}


def correct(data,actor):
    identifier=s.field(data,'id',maximum=40);changes=data.get('changes');kind=data.get('kind')
    if not isinstance(changes,dict) or not changes:raise s.WorkflowError('Provide correction fields.')
    allowed={'customer':{'name':120,'business':160,'email':254,'contact':100,'destination':100},'supplier':{'company':200,'contact':200,'country':100,'city':100,'whatsapp':60,'wechat':100}}
    if kind not in allowed or set(changes)-set(allowed[kind]):raise s.WorkflowError('Unsupported correction field; supplier email changes require a new verification process.')
    cleaned={k:(s.email_address({'email':v}) if k=='email' else s.field(changes,k,minimum=0 if k in ('business','contact','whatsapp','wechat') and kind=='customer' or k in ('whatsapp','wechat') else 1,maximum=allowed[kind][k])) for k,v in changes.items()}
    with s.database() as db:
        row=_record(db,kind,identifier);payload=json.loads(row['payload'] if kind=='customer' else row['private_profile']);payload.update(cleaned)
        if kind=='customer':db.execute('UPDATE customer_inquiries SET payload=? WHERE id=?',(json.dumps(payload),identifier))
        else:db.execute('UPDATE market_accounts SET private_profile=? WHERE id=?',(json.dumps(payload),identifier))
        controls.event(db,actor,'privacy_correction',identifier)
    return {'message':'Private details corrected. No message was sent to the contact.'}


def days(name):
    value=os.environ.get(name,'').strip()
    if not value:return None
    try:n=int(value)
    except ValueError:raise s.WorkflowError('Invalid retention setting: '+name,503) from None
    if not 1<=n<=36500:raise s.WorkflowError('Invalid retention setting: '+name,503)
    return n


def prune(apply=False):
    policies={name:days('RETENTION_DAYS_'+name) for name in ('CLOSED_INQUIRIES','PENDING_SUPPLIERS','DOCUMENTS','OPERATIONS')}
    if apply and os.environ.get('RETENTION_APPLY_APPROVED')!='true':raise s.WorkflowError('Retention application requires explicit operator approval.',403)
    result={'apply':apply,'batch_limit':100,'closed_inquiries':0,'pending_suppliers':0,'documents':0,'operations_policy_enabled':policies['OPERATIONS'] is not None,'skipped_inflight':0}
    with s.database() as db:
        controls.capacity(db,'lock')
        pending=[]
        if policies['CLOSED_INQUIRIES']:
            pending += [('customer',r['id']) for r in db.execute("SELECT id FROM customer_inquiries WHERE status='closed' AND created_at<? ORDER BY created_at LIMIT 100",(s.now()-policies['CLOSED_INQUIRIES']*86400,)).fetchall()]
        if policies['PENDING_SUPPLIERS']:
            threshold=s.now()-policies['PENDING_SUPPLIERS']*86400
            pending += [('supplier',r['id']) for r in db.execute('SELECT id FROM market_accounts WHERE verified_at IS NULL AND NOT EXISTS (SELECT 1 FROM market_publications mp WHERE mp.account_id=market_accounts.id) AND created_at<? ORDER BY created_at LIMIT 100',(threshold,)).fetchall()]
            pending += [('legacy',r['id']) for r in db.execute("SELECT id FROM applications WHERE status='pending_email' AND created_at<? ORDER BY created_at LIMIT 100",(threshold,)).fetchall()]
        for kind,identifier in pending[:100]:
            result['closed_inquiries' if kind=='customer' else 'pending_suppliers']+=1
            if apply:
                # The preflight can fail without changing data; skip active SMTP leases.
                try:_mail_ids(db,kind,identifier,_record(db,kind,identifier))
                except s.WorkflowError as error:
                    if error.status==409:result['skipped_inflight']+=1;continue
                    raise
                erase_in(db,kind,identifier,'retention-worker')
        if policies['DOCUMENTS']:
            threshold=s.now()-policies['DOCUMENTS']*86400
            predicate="COALESCE(private_profile::jsonb->>'license_pdf','')<>''" if db.postgres else "COALESCE(json_extract(private_profile,'$.license_pdf'),'')<>''"
            for row in db.execute('SELECT id,private_profile FROM market_accounts WHERE created_at<? AND '+predicate+' ORDER BY created_at LIMIT 100',(threshold,)).fetchall():
                profile=json.loads(row['private_profile'])
                if profile.get('license_pdf'):
                    result['documents']+=1
                    if apply:profile['license_pdf']='';db.execute('UPDATE market_accounts SET private_profile=? WHERE id=?',(json.dumps(profile),row['id']))
            result['documents']+=db.execute("SELECT COUNT(*) AS n FROM applications WHERE created_at<? AND license_pdf<>''",(threshold,)).fetchone()['n']
            if apply:db.execute("UPDATE applications SET license_pdf='' WHERE created_at<?",(threshold,))
        if apply:
            db.execute('DELETE FROM sessions WHERE expires_at<=?',(s.now(),))
            db.execute('DELETE FROM tokens WHERE expires_at<=? OR used_at IS NOT NULL',(s.now(),))
            db.execute('DELETE FROM market_tokens WHERE expires_at<=? OR used_at IS NOT NULL',(s.now(),))
            db.execute('DELETE FROM rate_limits WHERE started_at<?',(s.now()-172800,))
            if policies['OPERATIONS']:
                threshold=s.now()-policies['OPERATIONS']*86400
                db.execute('DELETE FROM security_events WHERE created_at<?',(threshold,))
                db.execute('DELETE FROM audit WHERE created_at<?',(threshold,))
                db.execute('DELETE FROM listing_reports WHERE created_at<? AND status=\'reviewed\'',(threshold,))
                db.execute('DELETE FROM notification_jobs WHERE outbox_id IN (SELECT id FROM outbox WHERE created_at<? AND sent_at IS NOT NULL)',(threshold,))
                db.execute('DELETE FROM outbox WHERE created_at<? AND sent_at IS NOT NULL',(threshold,))
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Dry-run retention by default; counts only, no PII.')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--environment',required=True,choices=['local','test','preview','staging','production'])
    args=parser.parse_args()
    if args.environment!=settings.environment():raise SystemExit('Environment confirmation mismatch.')
    print(json.dumps(prune(args.apply)))
