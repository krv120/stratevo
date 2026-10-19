"""Private supplier management, notifications and versioned listing reviews."""
import json
from urllib.parse import urlparse,parse_qs
from app import suppliers as s, operations, mail_policy, admin_auth, listings

GETS={'/api/admin/suppliers','/api/admin/notifications','/api/admin/setup','/api/admin/products'}
POSTS={'/api/admin/suppliers/action','/api/admin/notifications/read','/api/admin/notifications/config','/api/admin/notifications/test','/api/admin/products/review'}


def get(handler,route):
    try:
        if route=='/api/admin/setup':return handler.send(200,admin_auth.setup_status())
        s.authenticate(handler.session_token(),'admin')
        query=parse_qs(urlparse(handler.path).query);offset=query.get('offset',['0'])[0]
        if route=='/api/admin/suppliers':result=operations.supplier_rows(offset,query.get('q',[''])[0])
        elif route=='/api/admin/products':result=listings.review_queue(offset)
        else:
            from app.intake import delivery_overview
            result={**delivery_overview(),**mail_policy.inbox(offset)}
        return handler.send(200,result)
    except s.WorkflowError as error:return handler.send(error.status,{'error':str(error)})
    except Exception:return handler.send(503,{'error':'Records are temporarily unavailable. Please retry.'})


def post(handler,route):
    if not handler.origin_allowed():return handler.send(403,{'error':'Origin not allowed'})
    try:
        actor=s.authenticate(handler.session_token(),'admin')['actor']
        s.rate_limit('manager-actions:'+actor,100,60)
        if handler.headers.get('Content-Type','').split(';')[0]!='application/json':return handler.send(415,{'error':'JSON required'})
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=20000:return handler.send(413,{'error':'Request size is invalid.'})
        handler.connection.settimeout(15);data=json.loads(handler.rfile.read(length))
        if not isinstance(data,dict):raise s.WorkflowError('Expected a JSON object.')
        if route=='/api/admin/suppliers/action':result=operations.supplier_action(data,actor)
        elif route=='/api/admin/products/review':result=listings.decide(data,actor)
        elif route=='/api/admin/notifications/config':result=mail_policy.configure(data,actor)
        elif route=='/api/admin/notifications/test':result=mail_policy.test_notification(actor)
        else:
            with s.database() as db:db.execute('UPDATE admin_notifications SET read_at=? WHERE id=?',(s.now(),s.field(data,'id',maximum=40)))
            result={'message':'Notification marked read.'}
        return handler.send(200,result)
    except s.WorkflowError as error:return handler.send(error.status,{'error':str(error),'field':error.field})
    except (ValueError,TypeError,UnicodeError):return handler.send(400,{'error':'Invalid request fields.'})
    except Exception:return handler.send(503,{'error':'The operation could not be completed. Reload the record before retrying.'})
