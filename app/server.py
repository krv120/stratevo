"""STRATEVO HTTP adapter; persistent workflow lives in app.suppliers."""
import hmac
import ipaddress
import hashlib
import gzip
import json
import ssl
import re
import os
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from app import suppliers, connections, marketplace, intake, seo, settings, controls, maintenance
from app import engine_http, mail_policy, listings, directory_http, release

ROOT = Path(__file__).resolve().parents[1]
HISTORY = defaultdict(deque)
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Avoid logging queries, conversation text or credentials.

    def send(self, code, body, content_type='application/json; charset=utf-8', headers=None):
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        headers=dict(headers or {})
        # Compress only public static assets. Private JSON/HTML, tokens and documents never enter this path.
        if content_type in ('text/css','application/javascript') and code==200:
            headers['Vary']='Accept-Encoding'
            accepted=[part.strip().split(';',1) for part in self.headers.get('Accept-Encoding','').lower().split(',')]
            if len(data)>=1024 and any(parts[0]=='gzip' and (len(parts)==1 or parts[1].strip() not in ('q=0','q=0.0','q=0.00','q=0.000')) for parts in accepted):
                data=gzip.compress(data,compresslevel=6,mtime=0);headers['Content-Encoding']='gzip'
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Stratevo-Release', release.RELEASE)
        self.send_header('Cache-Control', (headers or {}).get('Cache-Control','no-store'))
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        if not seo.indexable(urlparse(self.path).path):self.send_header('X-Robots-Tag','noindex, nofollow')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        csp=(headers or {}).get('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'")
        if os.environ.get('ALLOW_PREVIEW_EMBEDDING','false').lower()!='true':csp+="; frame-ancestors 'self'"
        self.send_header('Content-Security-Policy',csp)
        for key, value in (headers or {}).items():
            if key.lower() in ('content-security-policy','cache-control'): continue
            self.send_header(key, value)
        try:
            self.end_headers()
            if getattr(self,'command','GET')!='HEAD':self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError):
            # Navigation/abort closed the client socket. Do not attempt a second response.
            self.close_connection = True

    def send_error(self, code, message=None, explain=None):
        return self.send(405 if code==501 else code,{'error':'Method not allowed' if code==501 else 'Request rejected'})

    def do_HEAD(self):
        if urlparse(self.path).path=='/api/jobs/mail':return self.send(405,{'error':'Use GET or POST for the authenticated worker'})
        return self.do_GET()

    def mail_job(self):
        secret=os.environ.get('CRON_SECRET','')
        supplied=self.headers.get('Authorization','')
        if len(secret)<32 or not hmac.compare_digest(supplied.encode(),('Bearer '+secret).encode()):return self.send(401,{'error':'Worker authorization required'})
        try:return self.send(200,suppliers.send_email_queue(limit=1))
        except suppliers.WorkflowError as error:return self.send(error.status,{'error':str(error),'field':getattr(error,'field',None)})
        except Exception:return self.send(503,{'error':'Worker unavailable; saved jobs remain queued'})

    def authorized(self):
        token = os.environ.get('APP_ACCESS_TOKEN', '')
        supplied = self.headers.get('Authorization', '')
        if token and hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode()):
            return True
        if not self.session_token():
            return False
        try:
            suppliers.authenticate(self.session_token(), 'admin')
            return True
        except Exception:
            return False

    def do_GET(self):
        route = urlparse(self.path).path
        if route == '/api/version':return self.send(200,release.identity())
        if settings.environment()=='production' and self.headers.get('Host','').split(':')[0].lower()=='stratevo.online':
            return self.send(308,b'',headers={'Location':settings.canonical()+self.path})
        if route in directory_http.GETS:return directory_http.get(self,route)
        if route in engine_http.GETS:return engine_http.get(self,route)
        aliases={'/home':'/','/supplier.html':'/supplier','/supplier-account':'/supplier/account','/supplier-account.html':'/supplier/account','/marketplace.html':'/marketplace','/inquiry.html':'/inquiry','/assessment.html':'/assessment','/rfq':'/assessment','/supplier-portal':'/supplier/account','/business-information':'/terms#operator'}
        if route in aliases:return self.send(308,b'',headers={'Location':aliases[route]})
        if route=='/api/jobs/mail':return self.mail_job()
        if route.startswith('/api/marketplace/') or route == '/api/marketplace':
            return self.market_get(route)
        if route.startswith('/api/admin/') or route.startswith('/api/supplier/'):
            return self.workflow_get(route)
        if route in ('/robots.txt','/sitemap.xml'):
            try:return self.send(200,(seo.robots() if route=='/robots.txt' else seo.sitemap()).encode(),'text/plain; charset=utf-8' if route=='/robots.txt' else 'application/xml; charset=utf-8')
            except ValueError:return self.send(503,{'error':'Site metadata configuration is invalid.'})
        if route == '/api/health':
            try:
                with suppliers.database() as db:db.execute('SELECT COUNT(*) AS n FROM resource_locks').fetchone()
                return self.send(200,{'ok':True,'database':'reachable','storage':settings.storage_status(),'mail':'not_probed'})
            except Exception:return self.send(503,{'ok':False,'database':'unavailable','mail':'not_probed'})
        pages={'/':'home','/supplier':'supplier','/admin':'admin','/access':'access','/portal':'portal','/marketplace':'marketplace','/supplier/account':'supplier-account','/inquiry':'inquiry','/assessment':'assessment','/methodology':'methodology','/privacy':'privacy','/cookies':'cookies','/terms':'terms'}
        files={route:(name+'.html','text/html; charset=utf-8') for route,name in pages.items()}
        for name in ('site','market','manager','operations','storage','navigation','ui','comparison'):
            files['/'+name+'.js']=(name+'.js','application/javascript')
        files.update({'/site.css':('site.css','text/css'),'/favicon.svg':('favicon.svg','image/svg+xml'),'/images/stratevo-social.jpg':('images/stratevo-social.jpg','image/jpeg'),'/fonts/inter-latin.woff2':('fonts/inter-latin.woff2','font/woff2'),'/fonts/inter-greek.woff2':('fonts/inter-greek.woff2','font/woff2')})
        if route not in files:
            if route.startswith('/api/'):return self.send(404, {'error': 'Not found'})
            try:body=re.sub(r'<!--SEO-START-->.*?<!--SEO-END-->',lambda _:seo.metadata('/404'),settings.render_public((ROOT/'web'/'404.html').read_text()),flags=re.S)
            except ValueError:return self.send(503,{'error':'Site configuration is invalid.'})
            return self.send(404,body.encode(),'text/html; charset=utf-8')
        name, mime = files[route]
        body=(ROOT/'web'/name).read_bytes()
        if mime.startswith('text/html'):
            try:body=re.sub(r'<!--SEO-START-->.*?<!--SEO-END-->',lambda _:seo.metadata(route),settings.render_public(body.decode()),flags=re.S).encode()
            except ValueError:return self.send(503,{'error':'Site metadata configuration is invalid.'})
            return self.send(200,body,mime)
        etag='W/"'+hashlib.sha256(body).hexdigest()+'"'
        headers={'ETag':etag,'Vary':'Accept-Encoding','Cache-Control':'public, max-age=86400' if mime=='font/woff2' else 'public, max-age=0, must-revalidate'}
        if self.headers.get('If-None-Match')==etag:return self.send(304,b'',mime,headers)
        return self.send(200,body,mime,headers)

    def client_ip(self):
        # Vercel overwrites these edge headers. Never trust them on arbitrary/self-hosted proxies.
        if os.environ.get('VERCEL')=='1':
            candidate=self.headers.get('X-Vercel-Forwarded-For') or self.headers.get('X-Forwarded-For','')
            try:return str(ipaddress.ip_address(candidate.strip()))
            except ValueError:pass  # Ambiguous chains are deliberately not trusted.
        return self.client_address[0]

    def origin_allowed(self):
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return False
        value=self.headers.get('Origin')
        if not value:return True  # Non-browser clients still need authentication/public quotas.
        try:
            parsed=urlparse(value)
            if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:return False
            if settings.environment() in ('local','test') and not os.environ.get('VERCEL'):
                configured=urlparse(os.environ.get('PUBLIC_BASE_URL',''))
                return parsed.scheme in ('http','https') and parsed.netloc==self.headers.get('Host') and not (configured.netloc==parsed.netloc and configured.scheme=='https' and parsed.scheme!='https')
            allowed={'https://stratevo.online','https://www.stratevo.online'}
            # Deployment origins come only from Vercel's server environment,
            # never a browser Host or forwarding header. No wildcard trust.
            if os.environ.get('VERCEL')=='1':
                for name in ('VERCEL_URL','VERCEL_BRANCH_URL','VERCEL_PROJECT_PRODUCTION_URL'):
                    host=os.environ.get(name,'').lower()
                    if re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.vercel\.app',host):allowed.add('https://'+host)
            configured=os.environ.get('PUBLIC_BASE_URL','').strip().rstrip('/')
            if configured and settings.origin('PUBLIC_BASE_URL')==configured:allowed.add(configured)
            return parsed.scheme=='https' and value in allowed
        except ValueError:return False

    def do_POST(self):
        route = urlparse(self.path).path
        if route in directory_http.POSTS:return directory_http.post(self,route)
        if route in engine_http.POSTS:return engine_http.post(self,route)
        if route=='/api/suppliers':return self.market_post('/api/marketplace/register')
        if route=='/api/jobs/mail':return self.mail_job()
        if route == '/api/inquiries':
            return self.inquiry_post()
        if route.startswith('/api/marketplace/'):
            return self.market_post(route)
        if route.startswith('/api/admin/') or route.startswith('/api/supplier/'):
            return self.workflow_post(route)
        return self.send(404, {'error':'Not found'})


    def inquiry_post(self):
        if not self.origin_allowed():return self.send(403,{'error':'Origin not allowed'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send(415,{'error':'JSON required'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=24000:return self.send(413,{'error':'Inquiry is too large or empty.'})
            suppliers.rate_limit('inquiry-client:'+suppliers.digest(self.client_ip()),10,3600)
            self.connection.settimeout(10)
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError()
            result=intake.submit(data)
            result['email_notification_status']=mail_policy.dispatch_entity('customer',result['id'])
            result['email_notification_transport']=mail_policy.transport()
            return self.send(200,result)
        except suppliers.WorkflowError as error:return self.send(error.status,{'error':str(error),'field':getattr(error,'field',None)})
        except (ValueError,TypeError,UnicodeError):return self.send(400,{'error':'Invalid inquiry. Check the form fields.'})
        except Exception:return self.send(503,{'error':'We could not confirm that your inquiry was saved. Keep your details and retry the same submission; duplicate retries are protected.'})

    def market_get(self, route):
        try:
            suppliers.rate_limit('marketplace-reads',1200,60)
            if route == '/api/marketplace':
                query=parse_qs(urlparse(self.path).query)
                result=marketplace.listings(query.get('q',[''])[0],query.get('category',[''])[0],query.get('offset',['0'])[0])
                return self.send(200,result)
            if route == '/api/marketplace/export':
                account=marketplace.identity(self.session_token())
                return self.send(200,maintenance.export('supplier',account['id']))
            if route == '/api/marketplace/me':
                return self.send(200,marketplace.mine(self.session_token()))
            if route.startswith('/api/marketplace/own-image/'):
                return self.send(200,listings.own_photo(self.session_token(),route.rsplit('/',1)[-1]),'image/jpeg')
            if route.startswith('/api/marketplace/image/'):
                return self.send(200,marketplace.photo(route.rsplit('/',1)[-1]),'image/jpeg',{'Content-Security-Policy':"sandbox; default-src 'none'"})
            return self.send(404,{'error':'Not found'})
        except suppliers.WorkflowError as error:
            return self.send(error.status,{'error':str(error),'field':getattr(error,'field',None)})
        except Exception:
            return self.send(503,{'error':'Marketplace is temporarily unavailable. Please try again later.'})

    def market_post(self, route):
        allowed=('/api/marketplace/edit','/api/marketplace/profile','/api/marketplace/register','/api/marketplace/request-access','/api/marketplace/consume','/api/marketplace/products','/api/marketplace/withdraw','/api/marketplace/logout','/api/marketplace/report')
        if route not in allowed:return self.send(404,{'error':'Not found'})
        if not self.origin_allowed():return self.send(403,{'error':'Origin not allowed'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send(415,{'error':'JSON required'})
        try:
            maximum=750000 if route in ('/api/marketplace/register','/api/marketplace/products','/api/marketplace/edit') else 20000 if route=='/api/marketplace/profile' else 12000
            if route in ('/api/marketplace/products','/api/marketplace/withdraw','/api/marketplace/profile','/api/marketplace/edit'):
                marketplace.identity(self.session_token())
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=maximum:return self.send(413,{'error':'Request is too large or empty.'})
            self.connection.settimeout(15)
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError()
            message_id=None
            response_headers=None
            if route=='/api/marketplace/register':
                suppliers.rate_limit('register-client:'+suppliers.digest(self.client_ip()),10,3600)
                result,message_id=marketplace.register(data,immediate=True)
                token=result.pop('_session',None)
                if token:response_headers=self.session_cookie(token)
            elif route=='/api/marketplace/profile':
                from app import operations
                account=marketplace.identity(self.session_token());suppliers.rate_limit('profile-edit:'+account['id'],10,3600)
                result=operations.supplier_action({'id':account['id'],'action':'edit','profile':data.get('profile')},'supplier:'+account['id'])
            elif route=='/api/marketplace/request-access':result,message_id=marketplace.request_access(data)
            elif route=='/api/marketplace/consume':
                result,token=marketplace.consume(data)
                return self.send(200,result,headers=self.session_cookie(token))
            elif route=='/api/marketplace/products':result=listings.add(self.session_token(),data)
            elif route=='/api/marketplace/edit':result=listings.edit(self.session_token(),data)
            elif route=='/api/marketplace/report':result=controls.report(data)
            elif route=='/api/marketplace/withdraw':result=marketplace.withdraw(self.session_token(),data)
            elif route=='/api/marketplace/logout':
                return self.send(200,suppliers.logout(self.session_token()),headers=self.session_cookie(''))
            # Run before the response: serverless runtimes can freeze background workers.
            # A failed attempt stays in the outbox for the mail worker; responses never enumerate accounts.
            if message_id and mail_policy.transport() not in ('admin_inbox','webhook'):
                try:suppliers.send_email_queue(limit=1,message_id=message_id)
                except Exception:pass
            if route=='/api/marketplace/register' and result.get('submitted'):
                result['email_notification_status']=mail_policy.dispatch_entity('supplier',result['supplier_id'])
                result['email_notification_transport']=mail_policy.transport()
            return self.send(200,result,headers=response_headers)
        except suppliers.WorkflowError as error:
            return self.send(error.status,{'error':str(error),'field':getattr(error,'field',None)})
        except (ValueError,TypeError,UnicodeError):
            return self.send(400,{'error':'Invalid request.'})
        except Exception:
            return self.send(503,{'error':'Supplier service is temporarily unavailable. Please try again later.'})

    def session_token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            return cookie['stratevo_session'].value if 'stratevo_session' in cookie else ''
        except Exception:
            return ''

    def session_cookie(self, token):
        secure = '; Secure' if os.environ.get('COOKIE_SECURE','true') != 'false' else ''
        return {'Set-Cookie':f'stratevo_session={token}; HttpOnly; SameSite=Lax; Path=/api; Max-Age={28800 if token else 0}{secure}'}

    def workflow_get(self, route):
        try:
            if route.startswith('/api/admin/'):
                suppliers.authenticate(self.session_token(), 'admin')
                if route.startswith('/api/admin/product-image/'):
                    import base64
                    with suppliers.database() as db:row=db.execute('SELECT image FROM market_products WHERE id=?',(route.rsplit('/',1)[-1],)).fetchone()
                    if not row or not row['image']:return self.send(404,{'error':'Photo not found'})
                    return self.send(200,base64.b64decode(row['image']),'image/jpeg')
                if route == '/api/admin/inquiries':
                    query=parse_qs(urlparse(self.path).query)
                    return self.send(200,intake.list_inquiries(query.get('status',['all'])[0],query.get('offset',['0'])[0]))
                if route == '/api/admin/reports':return self.send(200,controls.reports(parse_qs(urlparse(self.path).query).get('offset',['0'])[0]))
                if route == '/api/admin/notifications':return self.send(200,intake.delivery_overview())
                if route == '/api/admin/marketplace':
                    return self.send(200,marketplace.admin_accounts(parse_qs(urlparse(self.path).query).get('offset',['0'])[0]))
                if route.startswith('/api/admin/market-license/'):
                    return self.send(200,marketplace.license_document(route.rsplit('/',1)[-1]),'application/octet-stream',{'Content-Disposition':'attachment; filename="business-license.pdf"','Content-Security-Policy':"sandbox; default-src 'none'"})
                if route.startswith('/api/admin/supplier-profile/'):
                    return self.send(200,suppliers.approved_profile(route.rsplit('/',1)[-1]))
                if route == '/api/admin/applications':
                    return self.send(200, suppliers.applications())
                if route.startswith('/api/admin/license/'):
                    document = suppliers.license_document(route.rsplit('/',1)[-1])
                    return self.send(200, document, 'application/octet-stream', {'Content-Disposition':'attachment; filename="business-license.pdf"', 'Content-Security-Policy':"sandbox; default-src 'none'"})
            elif route == '/api/supplier/me':
                identity = suppliers.authenticate(self.session_token())
                if identity['role']=='publisher':
                    marketplace.identity(self.session_token())
                    return self.send(200,{'redirect':'/supplier/account'})
                if identity['role']!='supplier':raise suppliers.WorkflowError('Supplier access required.',403)
                return self.send(200, suppliers.profile(identity))
            return self.send(404, {'error':'Not found'})
        except suppliers.WorkflowError as error:
            return self.send(error.status, {'error':str(error),'field':getattr(error,'field',None)})
        except Exception:
            return self.send(503, {'error':'Supplier service is temporarily unavailable.'})

    def workflow_post(self, route):
        allowed = ('/api/supplier/apply','/api/supplier/request-access','/api/supplier/consume','/api/supplier/logout','/api/admin/login','/api/admin/logout','/api/admin/review','/api/admin/send-mail','/api/admin/hide-product','/api/admin/inquiry-status','/api/admin/supplier-status','/api/admin/retry-notifications','/api/admin/suspend','/api/admin/report-reviewed','/api/admin/export','/api/admin/correct','/api/admin/delete','/api/admin/revoke-sessions')
        if route not in allowed: return self.send(404, {'error':'Not found'})
        if not self.origin_allowed():
            return self.send(403, {'error':'Origin not allowed'})
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.send(415, {'error':'JSON required'})
        try:
            # Review/send endpoints check the session before processing request bodies.
            if route.startswith('/api/admin/') and route not in ('/api/admin/login','/api/admin/logout'):
                identity=suppliers.authenticate(self.session_token(), 'admin')
            maximum = 2900000 if route == '/api/supplier/apply' else 12000
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= maximum: return self.send(413, {'error':'Request is too large or empty.'})
            self.connection.settimeout(15)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict): raise ValueError()
            if route == '/api/supplier/apply':
                return self.send(410, {'error':'Use the supplier registration form to submit products for review.'})
            elif route == '/api/supplier/request-access': result = suppliers.request_access(data)
            elif route == '/api/supplier/consume':
                result, token = suppliers.consume(data)
                return self.send(200, result, headers=self.session_cookie(token) if token else None)
            elif route == '/api/admin/login':
                suppliers.rate_limit('admin-login-ip:'+suppliers.digest(self.client_ip()),10,900)
                result, token = suppliers.admin_login(data)
                return self.send(200, result, headers=self.session_cookie(token))
            elif route.endswith('/logout'):
                return self.send(200, suppliers.logout(self.session_token()), headers=self.session_cookie(''))
            elif route == '/api/admin/suspend':result=controls.suspension(data,identity['actor'])
            elif route == '/api/admin/report-reviewed':result=controls.review_report(data,identity['actor'])
            elif route == '/api/admin/export':result=maintenance.export(data.get('kind'),suppliers.field(data,'id',maximum=40))
            elif route == '/api/admin/correct':result=maintenance.correct(data,identity['actor'])
            elif route == '/api/admin/delete':result=maintenance.erase(data,identity['actor'])
            elif route == '/api/admin/revoke-sessions':
                actor=suppliers.field(data,'actor',maximum=60)
                with suppliers.database() as db:
                    db.execute('DELETE FROM sessions WHERE digest IN (SELECT digest FROM admin_session_meta WHERE actor=?)',(actor,))
                    controls.event(db,identity['actor'],'admin_sessions_revoked',actor)
                result={'message':'Existing sessions revoked. Disable or rotate the account to prevent new logins.'}
            elif route == '/api/admin/retry-notifications':result=intake.retry_failed()
            elif route == '/api/admin/inquiry-status':result=intake.update(data)
            elif route == '/api/admin/supplier-status':result=intake.update(data,supplier=True)
            elif route == '/api/admin/hide-product': result = marketplace.moderate(data)
            elif route == '/api/admin/review': result = suppliers.review(data)
            elif route == '/api/admin/send-mail': result = suppliers.send_email_queue(limit=1)
            if route.startswith('/api/admin/') and route not in ('/api/admin/login','/api/admin/logout','/api/admin/delete'):
                with suppliers.database() as db:controls.event(db,identity['actor'],route.rsplit('/',1)[-1],str(data.get('id',''))[:100])
            return self.send(200, result)
        except suppliers.WorkflowError as error:
            return self.send(error.status, {'error':str(error),'field':getattr(error,'field',None)})
        except (ValueError, TypeError, UnicodeError):
            return self.send(400, {'error':'Invalid request.'})
        except Exception:
            return self.send(503, {'error':'Supplier service is temporarily unavailable. Please retry later.'})


if __name__ == '__main__':
    suppliers.initialize()
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8000'))), Handler).serve_forever()
