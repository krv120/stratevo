"""Named environment-provisioned administrators, optional TOTP, immediate revocation.
No self-registration, public reset or seed-return endpoint exists.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import struct
from app import suppliers as s, settings


def accounts():
    raw=os.environ.get('ADMIN_ACCOUNTS_JSON','')
    if not raw:return {}
    try:
        rows=json.loads(raw)
        if not isinstance(rows,list) or not 1<=len(rows)<=20:raise ValueError()
        result={}
        for row in rows:
            identifier=row['id']
            if not re.fullmatch('[A-Za-z0-9_-]{3,60}',identifier) or identifier in result:raise ValueError()
            if not re.fullmatch(r'pbkdf2_sha256\$600000\$[a-f0-9]{32}\$[a-f0-9]{64}',row['password_hash']):raise ValueError()
            secret=row.get('totp_secret','')
            if secret and len(base64.b32decode(secret,casefold=True))<20:raise ValueError()
            if settings.environment()=='production' and not secret:raise ValueError()
            result[identifier]=row
        return result
    except Exception:raise s.WorkflowError('Administrator account configuration is invalid.',503) from None


def code(secret,counter):
    raw=hmac.new(base64.b32decode(secret,casefold=True),struct.pack('>Q',counter),hashlib.sha1).digest()
    offset=raw[-1]&15
    return str((struct.unpack('>I',raw[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)


def login(data):
    configured=accounts()
    if not configured:
        if settings.environment()=='production':raise s.WorkflowError('Named administrator accounts with MFA must be configured.',503)
        return None
    username=data.get('username')
    row=configured.get(username) if isinstance(username,str) else None
    password=s.field(data,'password',maximum=300)
    # Use a valid dummy hash when the name is unknown to keep password work comparable.
    template=row or next(iter(configured.values()))
    _,rounds,salt,expected=template['password_hash'].split('$')
    actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),int(rounds)).hex()
    if not row or not hmac.compare_digest(actual,expected) or row.get('disabled'):raise s.WorkflowError('Sign-in failed.',401)
    secret=row.get('totp_secret','');counter=None
    if secret:
        supplied=s.field(data,'otp',minimum=6,maximum=6)
        for step in (s.now()//30-1,s.now()//30,s.now()//30+1):
            if step>=0 and hmac.compare_digest(code(secret,step),supplied):counter=step
        if counter is None:raise s.WorkflowError('Sign-in failed.',401)
    with s.database() as db:
        if counter is not None:
            claimed=db.execute('INSERT INTO admin_totp VALUES (?,?) ON CONFLICT(actor) DO UPDATE SET counter=excluded.counter WHERE admin_totp.counter<excluded.counter RETURNING counter',(row['id'],counter)).fetchone()
            if not claimed:raise s.WorkflowError('This authentication code was already used. Wait for the next code.',401)
        token=s.session(db,'admin',row['id'])
        db.execute('INSERT INTO admin_session_meta VALUES (?,?,?)',(s.digest(token),row['id'],version(row)))
        from app.controls import event
        event(db,row['id'],'admin_login')
    return {'role':'admin'},token


def version(row):return s.digest(row['password_hash']+'|'+row.get('totp_secret',''))


def validate(db,raw):
    row=db.execute('SELECT actor,credential_version FROM admin_session_meta WHERE digest=?',(s.digest(raw),)).fetchone()
    configured=accounts()
    if not row:
        if configured or settings.environment()=='production':raise s.WorkflowError('Administrator session has been revoked.',403)
        return 'legacy-owner'
    account=configured.get(row['actor'])
    if not account or account.get('disabled') or not hmac.compare_digest(version(account),row['credential_version']):raise s.WorkflowError('Administrator session has been revoked.',403)
    return row['actor']
