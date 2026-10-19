"""HTTP boundary for supplier directory operations."""
import json
from urllib.parse import urlparse,parse_qs
from app import directory, suppliers as s

GETS={'/api/marketplace','/api/suppliers/public','/api/directory/me'}
POSTS={'/api/suppliers','/api/directory/register','/api/directory/update','/api/directory/withdraw','/api/suppliers/sync','/api/admin/directory/hide'}


def get(handler,route):
    try:
        if route=='/api/directory/me':result=directory.mine(handler.session_token())
        else:
            q=parse_qs(urlparse(handler.path).query)
            result=directory.public(q.get('q',[''])[0],q.get('focus',[''])[0],q.get('offset',['0'])[0])
        return handler.send(200,result)
    except s.WorkflowError as e:return handler.send(e.status,{'error':str(e),'field':e.field})
    except Exception:return handler.send(503,{'error':'Supplier records are temporarily unavailable. Please retry.'})


def post(handler,route):
    if not handler.origin_allowed():return handler.send(403,{'error':'Origin not allowed'})
    try:
        actor=None
        if route.startswith('/api/admin/'):
            actor=s.authenticate(handler.session_token(),'admin')['actor']
            s.rate_limit('directory-moderation:'+actor,60,60)
        elif route not in ('/api/suppliers','/api/directory/register'):s.authenticate(handler.session_token(),'publisher')
        if handler.headers.get('Content-Type','').split(';')[0]!='application/json':return handler.send(415,{'error':'JSON required'})
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=16000:return handler.send(413,{'error':'Request size is invalid'})
        handler.connection.settimeout(15)
        data=json.loads(handler.rfile.read(length))
        if not isinstance(data,dict):raise ValueError()
        headers=None
        if route in ('/api/suppliers','/api/directory/register'):
            s.rate_limit('register-ip:'+s.digest(handler.client_ip()),10,3600)
            result=directory.register(data);headers=handler.session_cookie(result.pop('_session'))
        elif route=='/api/directory/update':result=directory.update(handler.session_token(),data)
        elif route=='/api/directory/withdraw':result=directory.withdraw(handler.session_token())
        elif route=='/api/suppliers/sync':result=directory.sync(handler.session_token(),data)
        else:result=directory.moderate(data,actor)
        return handler.send(200,result,headers=headers)
    except s.WorkflowError as e:return handler.send(e.status,{'error':str(e),'field':e.field})
    except (ValueError,TypeError,UnicodeError):return handler.send(400,{'error':'Invalid request fields'})
    except Exception:return handler.send(503,{'error':'We could not confirm completion. Your form is retained; retry unchanged to recover the same registration.'})
