"""Do not deliver obsolete authentication links. Metadata contains no raw tokens."""
import re
from app import suppliers as s

SUBJECTS={'STRATEVO — verify your application email','STRATEVO — approved supplier access','STRATEVO — confirm your supplier email'}


def state(db,identifier,status):
    db.execute('INSERT INTO mail_state VALUES (?,?,?) ON CONFLICT(outbox_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at',(identifier,status,s.now()))


def obsolete(db,message):
    if message['subject'] not in SUBJECTS:return False
    found=re.search(r'#(market_token|token)=([A-Za-z0-9_-]{40,100})(?:\s|$)',message['body'])
    token=None
    if found:
        if found[1]=='market_token':
            token=db.execute('SELECT t.expires_at,t.used_at,t.owner_id FROM market_tokens t WHERE digest=?',(s.digest(found[2]),)).fetchone()
            if token:
                from app.controls import suspended
                if suspended(db,token['owner_id']):token=None
        else:token=db.execute('SELECT expires_at,used_at FROM tokens WHERE digest=?',(s.digest(found[2]),)).fetchone()
    expired=token and token['expires_at']<=s.now()
    if not token or token['used_at'] is not None or expired:
        state(db,message['id'],'expired' if expired else 'cancelled')
        db.execute("UPDATE outbox SET body='',attempts=5,claimed_until=0 WHERE id=?",(message['id'],))
        record_attempt(db,message['id'],'failed','Access link expired, was consumed or was revoked; delivery was cancelled.')
        return True
    return False

# Real transports. Provider acceptance is NOT proof of inbox delivery.
import html
import json
import os
import smtplib
import ssl
import urllib.request
import uuid
from email.message import EmailMessage
from urllib.parse import urlsplit


def transport():
    if os.environ.get('MAIL_DELIVERY_ENABLED','').lower()=='false':return 'admin_inbox'
    if os.environ.get('RESEND_API_KEY'):return 'resend'
    if os.environ.get('SENDGRID_API_KEY'):return 'sendgrid'
    if os.environ.get('SMTP_HOST'):return 'smtp'
    if os.environ.get('NOTIFICATION_WEBHOOK_URL'):return 'webhook'
    return 'admin_inbox'


def admin_recipient(db=None):
    if db:
        row=db.execute("SELECT value FROM platform_settings WHERE name='admin_email'").fetchone()
        if row:return row['value']
    else:
        with s.database() as connection:return admin_recipient(connection)
    value=next((os.environ[n].strip() for n in ('ADMIN_NOTIFICATION_EMAIL','ADMIN_EMAIL','NOTIFY_EMAIL','NOTIFICATION_EMAIL','SMTP_USER') if os.environ.get(n,'').strip()),'')
    try:return s.email_address({'email':value})
    except s.WorkflowError:return ''


def send(recipient,subject,body,identifier,*,authentication=False):
    chosen=transport()
    if chosen=='admin_inbox':raise s.WorkflowError('Notification delivery is not configured.',503)
    markup='<html><body><h2>'+html.escape(subject)+'</h2><pre style="white-space:pre-wrap">'+html.escape(body)+'</pre></body></html>'
    sender=os.environ.get('MAIL_FROM') or os.environ.get('SMTP_USER','')
    if chosen!='webhook':sender=s.email_address({'email':sender})
    if chosen=='smtp':
        message=EmailMessage();message['From']=sender;message['To']=recipient;message['Subject']=subject;message['Message-ID']='<'+identifier+'@'+sender.split('@')[-1]+'>'
        message.set_content(body);message.add_alternative(markup,subtype='html')
        port=int(os.environ.get('SMTP_PORT','587'));context=ssl.create_default_context()
        connection=smtplib.SMTP_SSL(os.environ['SMTP_HOST'],port,timeout=8,context=context) if port==465 else smtplib.SMTP(os.environ['SMTP_HOST'],port,timeout=8)
        with connection as smtp:
            if port!=465:smtp.starttls(context=context)
            if os.environ.get('SMTP_USER'):smtp.login(os.environ['SMTP_USER'],os.environ.get('SMTP_PASSWORD',''))
            smtp.send_message(message)
        return chosen
    headers={'Content-Type':'application/json','User-Agent':'Stratevo-Notifications/2.0'}
    if chosen=='resend':
        url='https://api.resend.com/emails';headers.update(Authorization='Bearer '+os.environ['RESEND_API_KEY'],**{'Idempotency-Key':identifier})
        payload={'from':sender,'to':[recipient],'subject':subject,'text':body,'html':markup}
    elif chosen=='sendgrid':
        url='https://api.sendgrid.com/v3/mail/send';headers['Authorization']='Bearer '+os.environ['SENDGRID_API_KEY']
        payload={'personalizations':[{'to':[{'email':recipient}]}],'from':{'email':sender},'subject':subject,'content':[{'type':'text/plain','value':body},{'type':'text/html','value':markup}]}
    else:
        if authentication:raise s.WorkflowError('Authentication links require an email transport, not a webhook.',503)
        url=os.environ['NOTIFICATION_WEBHOOK_URL'];parsed=urlsplit(url)
        # Owner-controlled integration URL only, never accepted from an HTTP payload.
        from app.discovery import safe_web_url
        if not safe_web_url(url) or parsed.scheme!='https':raise s.WorkflowError('Invalid notification webhook configuration.',503)
        if parsed.hostname=='hooks.slack.com':payload={'text':subject+'\n'+body[:3000]}
        elif parsed.hostname in ('discord.com','discordapp.com'):payload={'content':(subject+'\n'+body)[:1900],'allowed_mentions':{'parse':[]}}
        else:payload={'id':identifier,'recipient':recipient,'subject':subject,'text':body,'html':markup}
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=8) as response:
        if not 200<=response.status<300:raise s.WorkflowError('Notification provider did not accept the message.',502)
        response.read(65536)
    return chosen


def log_event(db,event_type,entity_id,payload):
    # Inbox entry is committed with the business record even when no email destination exists.
    identifier=str(uuid.uuid4());recipient=admin_recipient(db)
    subject='STRATEVO — '+event_type.replace('_',' ')
    db.execute('INSERT INTO admin_notifications(id,entity_id,event_type,recipient,subject,body_preview,payload_json,created_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(entity_id,event_type) DO NOTHING',
               (identifier,entity_id,event_type,recipient,subject,subject,json.dumps(payload),s.now()))
    row=db.execute('SELECT id,outbox_id FROM admin_notifications WHERE entity_id=? AND event_type=?',(entity_id,event_type)).fetchone()
    if (event_type=='ai_lead_alert' or ':update:' in entity_id) and not row['outbox_id'] and (recipient or transport()=='webhook'):
        from app.settings import canonical
        body=json.dumps(payload,indent=2,ensure_ascii=False)+'\n\nPrivate manager: '+canonical()+'/admin'
        try:mail=s.queue(db,recipient or 'admin-inbox@example.invalid',subject,body)
        except s.WorkflowError:pass
        else:db.execute('UPDATE admin_notifications SET outbox_id=? WHERE id=?',(mail,row['id']))
    return row['id']


def bind_notification(db,kind,entity_id,outbox_id):
    event='buyer_inquiry' if kind=='customer' else 'supplier_published'
    db.execute('UPDATE admin_notifications SET outbox_id=?,recipient=? WHERE entity_id=? AND event_type=?',(outbox_id,admin_recipient(db),entity_id,event))


def record_attempt(db,outbox_id,status,error=''):
    row=db.execute('SELECT id FROM admin_notifications WHERE outbox_id=?',(outbox_id,)).fetchone()
    if row:
        db.execute('UPDATE admin_notifications SET delivery_status=?,error_message=?,read_at=NULL WHERE id=?',(status,error,row['id']))
    db.execute('INSERT INTO notification_attempts VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),row['id'] if row else None,transport(),status,error,s.now()))


def dispatch_entity(kind,identifier):
    event='buyer_inquiry' if kind=='customer' else 'supplier_published'
    try:
        with s.database() as db:
            from app.intake import queue_pending
            queue_pending(db,kind,identifier)
            row=db.execute('SELECT outbox_id FROM admin_notifications WHERE entity_id=? AND event_type=?',(identifier,event)).fetchone()
        if row and row['outbox_id'] and transport()!='admin_inbox':s.send_email_queue(limit=1,message_id=row['outbox_id'])
        with s.database() as db:row=db.execute('SELECT delivery_status FROM admin_notifications WHERE entity_id=? AND event_type=?',(identifier,event)).fetchone()
        return row['delivery_status'] if row else 'queued_in_admin_inbox'
    except Exception:return 'queued_in_admin_inbox'  # Record already committed; never turn a saved form into a failure.


def inbox(offset=0):
    from app.operations import page_number
    offset=page_number(offset)
    with s.database() as db:
        rows=db.execute('SELECT * FROM admin_notifications ORDER BY created_at DESC,id LIMIT 26 OFFSET ?',(offset,)).fetchall()
        unread=db.execute('SELECT COUNT(*) AS n FROM admin_notifications WHERE read_at IS NULL').fetchone()['n']
        recipient=admin_recipient(db)
    return {'notifications':[dict(r) for r in rows[:25]],'unread':unread,'has_more':len(rows)>25,'offset':offset,'transport':transport(),'recipient':recipient,'notice':'Sent means transport accepted; inbox arrival is not confirmed. Webhook acceptance is not email delivery.'}


def configure(data,actor):
    destination=s.email_address({'email':data.get('email','')})
    with s.database() as db:
        db.execute("INSERT INTO platform_settings VALUES ('admin_email',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(destination,))
        from app.controls import event
        event(db,actor,'notification_destination_changed')
    return {'message':'Admin notification destination saved. New and unassigned messages use this address; previously addressed mail is not silently retargeted.'}


def test_notification(actor):
    s.rate_limit('notification-test',3,3600)
    with s.database() as db:
        identifier=str(uuid.uuid4());log_event(db,'ai_lead_alert',identifier,{'test':True,'requested_by':actor})
        recipient=admin_recipient(db)
        if not recipient and transport()!='webhook':return {'message':'Test recorded in admin inbox. Configure a recipient and transport first.'}
        mail=s.queue(db,recipient or 'admin-inbox@example.invalid','STRATEVO — requested notification test','Operator-requested delivery test; contains no supplier or buyer data.')
        db.execute('UPDATE admin_notifications SET outbox_id=? WHERE entity_id=?',(mail,identifier))
    if transport()!='admin_inbox':s.send_email_queue(limit=1,message_id=mail)
    return {'message':'Test attempted. Inspect the notification inbox status; provider acceptance is not proof of inbox arrival.'}


def dispatch_notice(identifier):
    try:
        with s.database() as db:row=db.execute('SELECT outbox_id FROM admin_notifications WHERE id=?',(identifier,)).fetchone()
        if row and row['outbox_id'] and transport()!='admin_inbox':s.send_email_queue(limit=1,message_id=row['outbox_id'])
    except Exception:pass  # Committed notice stays in the inbox and queued outbox for recovery.


def audit_auth_mail(db,identifier,email,owner):
    db.execute('INSERT INTO admin_notifications(id,entity_id,event_type,recipient,subject,body_preview,payload_json,created_at,outbox_id) VALUES (?,?,?,?,?,?,?,?,?)',
      (str(uuid.uuid4()),identifier,'supplier_access',email,'STRATEVO — supplier email access','Single-use access email; credentials are not copied into the notification inbox.',json.dumps({'supplier_id':owner,'kind':'supplier_access'}),s.now(),identifier))
