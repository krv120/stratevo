"""HTTP routes for operations and grounded lead finding. All registry routes require admin auth."""
import json
import os
from urllib.parse import urlparse,parse_qs
from app import suppliers as s, operations, mail_policy, agent, discovery, public_ai, admin_auth

GETS={'/api/admin/suppliers','/api/admin/notifications','/api/admin/leads','/api/admin/setup'}
POSTS={'/api/leads/find','/api/public-ai/leads','/api/assessment/leads','/api/admin/leads/find','/api/supplier/enhance','/api/admin/suppliers/action','/api/admin/notifications/read','/api/admin/notifications/config','/api/admin/notifications/test','/api/admin/leads/status','/api/suppliers/sync'}


def get(handler,route):
    try:
        if route=='/api/admin/setup':
            ready=bool(os.environ.get('ADMIN_ACCOUNTS_JSON') or any(os.environ.get(n) for n in ('ADMIN_TOKEN','STRATEVO_ADMIN_TOKEN','ADMIN_PASSWORD')))
            return handler.send(200,{'configured':ready,'message':'Configure ADMIN_ACCOUNTS_JSON, or a strong ADMIN_TOKEN / STRATEVO_ADMIN_TOKEN / ADMIN_PASSWORD plus ADMIN_TOTP_SECRET in hosting secrets. Alias login name: owner. Production requires MFA; there is no default or public access mode.'})
        s.authenticate(handler.session_token(),'admin')
        query=parse_qs(urlparse(handler.path).query);offset=query.get('offset',['0'])[0]
        if route=='/api/admin/suppliers':result=operations.supplier_rows(offset,query.get('q',[''])[0])
        elif route=='/api/admin/notifications':
            from app.intake import delivery_overview
            result={**delivery_overview(),**mail_policy.inbox(offset)}
        else:result=operations.lead_rows(offset,query.get('status',['all'])[0])
        return handler.send(200,result)
    except s.WorkflowError as error:return handler.send(error.status,{'error':str(error)})
    except Exception:return handler.send(503,{'error':'Operations storage is unavailable.'})


def post(handler,route):
    if not handler.origin_allowed():return handler.send(403,{'error':'Origin not allowed'})
    try:
        actor='public'
        if route.startswith('/api/admin/'):
            actor=s.authenticate(handler.session_token(),'admin')['actor']
        if handler.headers.get('Content-Type','').split(';')[0]!='application/json':return handler.send(415,{'error':'JSON required'})
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=20000:return handler.send(413,{'error':'Request size is invalid.'})
        handler.connection.settimeout(15);data=json.loads(handler.rfile.read(length))
        if not isinstance(data,dict):raise s.WorkflowError('Expected a JSON object.')
        if route.endswith('/leads') or route.endswith('/leads/find') or route=='/api/leads/find':
            public_ai.throttle(handler.client_ip())
            from app.ai_providers import budget
            with budget(40):result=discovery.find_leads(data,actor)
        elif route=='/api/supplier/enhance':public_ai.throttle(handler.client_ip());result=agent.enhance_profile(data)
        elif route=='/api/admin/suppliers/action':result=operations.supplier_action(data,actor)
        elif route=='/api/admin/notifications/config':result=mail_policy.configure(data,actor)
        elif route=='/api/admin/notifications/test':result=mail_policy.test_notification(actor)
        elif route=='/api/admin/leads/status':result=operations.update_lead(data,actor)
        elif route=='/api/admin/notifications/read':
            with s.database() as db:db.execute('UPDATE admin_notifications SET read_at=? WHERE id=?',(s.now(),s.field(data,'id',maximum=40)))
            result={'message':'Notification marked read.'}
        else:
            # This repository never cached business records in localStorage. Blindly importing unknown
            # browser values would trust unvalidated ownership and leak data across accounts.
            return handler.send(409,{'error':'No legacy browser-cache schema exists in this application. Review any external export and submit each record through the normal validated form; never upload arbitrary browser storage.'})
        return handler.send(200,result)
    except s.WorkflowError as error:return handler.send(error.status,{'error':str(error),'field':error.field})
    except agent.ProviderError as error:return handler.send(502,{'error':str(error),'code':error.code})
    except (ValueError,TypeError,UnicodeError):return handler.send(400,{'error':'Invalid request fields.'})
    except Exception:return handler.send(503,{'error':'The operation could not be completed. No live result or email delivery is implied.'})
