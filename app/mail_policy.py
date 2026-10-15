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
        return True
    return False
