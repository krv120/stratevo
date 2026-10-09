"""STRATEVO HTTP adapter; persistent workflow lives in app.suppliers."""
import hmac
import json
import os
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

from app.agent import configured, reply
from app.catalog import count, search, owner_records
from app import suppliers, connections
from app.matching import match
from app.discovery import discover, configured as discovery_configured, owner_evidence

ROOT = Path(__file__).resolve().parents[1]
HISTORY = defaultdict(deque)
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Avoid logging queries, conversation text or credentials.

    def send(self, code, body, content_type='application/json; charset=utf-8', headers=None):
        data = json.dumps(body).encode() if isinstance(body, dict) else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', (headers or {}).get('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'"))
        for key, value in (headers or {}).items():
            if key.lower() == 'content-security-policy': continue
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

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
        if route.startswith('/api/admin/') or route.startswith('/api/supplier/'):
            return self.workflow_get(route)
        if route == '/api/health':
            return self.send(200, {'ok': True, 'application': 'stratevo', 'deployment': 'development' if not os.environ.get('DATABASE_URL') else 'configured'})
        if route == '/api/agent/status':
            if not self.authorized():
                return self.send(401, {'error': 'Owner access required'})
            return self.send(200, {'provider_configured': connections.status()['ai_configured'], 'online_discovery_configured': discovery_configured(), 'research_rows': count(), 'production_connected': False})
        files = {'/': ('home.html', 'text/html; charset=utf-8'), '/supplier': ('supplier.html','text/html; charset=utf-8'), '/admin': ('admin.html','text/html; charset=utf-8'), '/access': ('access.html','text/html; charset=utf-8'), '/portal': ('portal.html','text/html; charset=utf-8'), '/site.js': ('site.js','application/javascript'), '/site.css': ('site.css','text/css'), '/ai': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'application/javascript'), '/style.css': ('style.css', 'text/css')}
        if route not in files:
            return self.send(404, {'error': 'Not found'})
        name, mime = files[route]
        return self.send(200, (ROOT / 'web' / name).read_bytes(), mime)

    def origin_allowed(self):
        # Check scheme as well as authority; reject opaque/non-web origins and
        # browser-declared cross-site requests even if Origin was omitted.
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return False
        origin = self.headers.get('Origin')
        if not origin:
            return True  # Non-browser integrations still require authentication.
        try:
            parsed = urlparse(origin)
            if parsed.scheme not in ('https','http') or parsed.netloc != self.headers.get('Host') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                return False
            canonical = urlparse(os.environ.get('PUBLIC_BASE_URL',''))
            if canonical.netloc == parsed.netloc and canonical.scheme == 'https' and parsed.scheme != 'https':
                return False
            return True
        except ValueError:
            return False

    def do_POST(self):
        route = urlparse(self.path).path
        if route.startswith('/api/admin/') or route.startswith('/api/supplier/'):
            return self.workflow_post(route)
        if route not in ('/api/chat', '/api/catalog/search', '/api/catalog/match', '/api/catalog/discover'):
            return self.send(404, {'error': 'Not found'})
        if not self.authorized():
            return self.send(401, {'error': 'Owner access required; enter your preview token'})
        # No CORS grant; reject cross-origin browser requests even with a token.
        if not self.origin_allowed():
            return self.send(403, {'error': 'Origin not allowed'})
        with LOCK:
            bucket = HISTORY['owner']
            now = time.monotonic()
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= 20:
                return self.send(429, {'error': 'Too many requests; wait one minute'})
            bucket.append(now)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                return self.send(413, {'error': 'Request body too large or missing'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'JSON required'})
            self.connection.settimeout(10)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected JSON object')
            if route == '/api/catalog/discover':
                return self.send(200, discover(data))
            if route == '/api/catalog/match':
                return self.send(200, match(data))
            if route == '/api/catalog/search':
                query = data.get('query')
                if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
                    raise ValueError('Search must contain 1–300 characters')
                return self.send(200, {'results': search(query), 'notice': 'Unverified owner research, not a quotation'})
            # Validate separately so malformed user input is 400, provider issues 502.
            from app.agent import validate_messages
            messages = validate_messages(data.get('messages'))
        except (ValueError, TypeError, UnicodeError):
            return self.send(400, {'error': 'Invalid request. Check message or search length.'})
        except Exception:
            return self.send(503, {'error':'Research service is temporarily unavailable. Please retry later.'})
        try:
            return self.send(200, reply(messages))
        except Exception:
            return self.send(502, {'error': 'The AI provider could not answer. Try again or use catalog search. No order was placed.'})


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
                if route == '/api/admin/connections':
                    return self.send(200, connections.status())
                if route.startswith('/api/admin/supplier-profile/'):
                    return self.send(200, suppliers.approved_profile(route.rsplit('/',1)[-1]))
                if route == '/api/admin/discovery':
                    return self.send(200, {'records':owner_evidence(), 'notice':'Private search evidence; not verified suppliers.'})
                if route == '/api/admin/research':
                    return self.send(200, {'records':owner_records(), 'total':count(), 'pending_rows':None, 'import_completeness':'unknown', 'notice':'Research is not approved supplier membership. Supplier identities here are manager-only.'})
                if route == '/api/admin/applications':
                    return self.send(200, suppliers.applications())
                if route.startswith('/api/admin/license/'):
                    document = suppliers.license_document(route.rsplit('/',1)[-1])
                    return self.send(200, document, 'application/octet-stream', {'Content-Disposition':'attachment; filename="business-license.pdf"', 'Content-Security-Policy':"sandbox; default-src 'none'"})
            elif route == '/api/supplier/me':
                identity = suppliers.authenticate(self.session_token(), 'supplier')
                return self.send(200, suppliers.profile(identity))
            return self.send(404, {'error':'Not found'})
        except suppliers.WorkflowError as error:
            return self.send(error.status, {'error':str(error)})
        except Exception:
            return self.send(503, {'error':'Supplier service is temporarily unavailable.'})

    def workflow_post(self, route):
        allowed = ('/api/supplier/apply','/api/supplier/request-access','/api/supplier/consume','/api/supplier/logout','/api/admin/login','/api/admin/logout','/api/admin/review','/api/admin/send-mail','/api/admin/check-connection')
        if route not in allowed: return self.send(404, {'error':'Not found'})
        if not self.origin_allowed():
            return self.send(403, {'error':'Origin not allowed'})
        if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            return self.send(415, {'error':'JSON required'})
        try:
            # Review/send endpoints check the session before processing request bodies.
            if route.startswith('/api/admin/') and route not in ('/api/admin/login','/api/admin/logout'):
                suppliers.authenticate(self.session_token(), 'admin')
            maximum = 2900000 if route == '/api/supplier/apply' else 12000
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= maximum: return self.send(413, {'error':'Request is too large or empty.'})
            self.connection.settimeout(15)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict): raise ValueError()
            if route == '/api/supplier/apply': result = suppliers.apply(data)
            elif route == '/api/supplier/request-access': result = suppliers.request_access(data)
            elif route == '/api/supplier/consume':
                result, token = suppliers.consume(data)
                return self.send(200, result, headers=self.session_cookie(token) if token else None)
            elif route == '/api/admin/login':
                result, token = suppliers.admin_login(data)
                return self.send(200, result, headers=self.session_cookie(token))
            elif route.endswith('/logout'):
                return self.send(200, suppliers.logout(self.session_token()), headers=self.session_cookie(''))
            elif route == '/api/admin/check-connection': result = connections.check(data.get('service'))
            elif route == '/api/admin/review': result = suppliers.review(data)
            elif route == '/api/admin/send-mail': result = suppliers.send_email_queue(limit=1)
            return self.send(200, result)
        except suppliers.WorkflowError as error:
            return self.send(error.status, {'error':str(error)})
        except (ValueError, TypeError, UnicodeError):
            return self.send(400, {'error':'Invalid request.'})
        except Exception:
            return self.send(503, {'error':'Supplier service is temporarily unavailable. Please retry later.'})


if __name__ == '__main__':
    suppliers.initialize()
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8000'))), Handler).serve_forever()
