"""Local stand-in for the fal.ai queue, pricing and JWKS endpoints.

Used only by tests to exercise the real HTTP client, database writes, budget
logic and webhook verification without spending money or reaching the network.
A passing test here is contract evidence, not proof of a real generation.
"""
import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

STUB = None
KP_SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')


def public_key_b64():
    from app import ed25519
    return base64.urlsafe_b64encode(ed25519.public_key_for_tests(KP_SEED)).rstrip(b'=').decode()


class StubServer:
    def __init__(self, key='test-key-0123456789abcdef'):
        self.key = key
        self.submissions = []
        self.states = {}
        self.errors = {}
        self.results = {}
        self.cancel_status = 200
        # The pricing endpoint reports one unit price per endpoint. Resolution
        # dependent models are priced from the reviewed table in app.video.
        self.default_pricing = {'fal-ai/kling-video/v2.5-turbo/pro/text-to-video': 0.07,
                                'fal-ai/kling-video/v3/pro/text-to-video': 0.14,
                                'minimax/h3-max-turbo/text-to-video': 0.04}
        self.pricing = dict(self.default_pricing)
        self.pricing_fail = False
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        global STUB
        STUB = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def complete(self, request_id, url='https://v3.fal.media/files/test/clip.mp4', error=None):
        self.states[request_id] = 'COMPLETED'
        if error:
            self.errors[request_id] = error
        else:
            self.results[request_id] = {'video': {'url': url, 'content_type': 'video/mp4', 'file_size': 1234}}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        return self.headers.get('Authorization') == 'Key ' + STUB.key

    def _read(self):
        length = int(self.headers.get('Content-Length', '0'))
        return json.loads(self.rfile.read(length) or b'{}')

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith(('/fal-ai/', '/minimax/')):
            if not self._authorized():
                return self._send(401, {'detail': 'invalid key'})
            payload = self._read()
            request_id = 'req-%d' % (len(STUB.submissions) + 1)
            STUB.submissions.append({'path': parsed.path, 'query': parse_qs(parsed.query),
                                     'payload': payload, 'request_id': request_id})
            STUB.states[request_id] = 'IN_QUEUE'
            owner_app = '/'.join(parsed.path.strip('/').split('/')[:2])
            base = STUB.base + '/' + owner_app
            return self._send(200, {'request_id': request_id,
                                    'status_url': base + '/requests/' + request_id + '/status',
                                    'response_url': base + '/requests/' + request_id,
                                    'cancel_url': base + '/requests/' + request_id + '/cancel',
                                    'queue_position': 0})
        return self._send(404, {'detail': 'not found'})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/v1/models/pricing':
            if STUB.pricing_fail:
                return self._send(500, {'error': {'message': 'pricing unavailable'}})
            endpoint = parse_qs(parsed.query).get('endpoint_id', [''])[0]
            price = STUB.pricing.get(endpoint)
            if price is None:
                return self._send(200, {'prices': [], 'has_more': False, 'next_cursor': None})
            return self._send(200, {'prices': [{'endpoint_id': endpoint, 'unit_price': price,
                                                'unit': 'second', 'currency': 'USD'}],
                                    'has_more': False, 'next_cursor': None})
        if parsed.path == '/.well-known/jwks.json':
            return self._send(200, {'keys': [{'kty': 'OKP', 'crv': 'Ed25519', 'x': public_key_b64()}]})
        if '/requests/' in parsed.path:
            if not self._authorized():
                return self._send(401, {'detail': 'invalid key'})
            parts = parsed.path.strip('/').split('/')
            if parts[-1] == 'status':
                request_id = parts[-2]
                body = {'status': STUB.states.get(request_id, 'COMPLETED'), 'request_id': request_id}
                # fal.ai reports failures on the queue status itself.
                if body['status'] == 'COMPLETED' and request_id in STUB.errors:
                    body['error'] = STUB.errors[request_id]
                    body['error_type'] = 'content_policy_violation'
                return self._send(200, body)
            request_id = parts[-1]
            if request_id in STUB.errors:
                return self._send(400, {'detail': STUB.errors[request_id]})
            return self._send(200, STUB.results.get(request_id, {'video': {'url': 'https://v3.fal.media/files/test/clip.mp4'}}))
        return self._send(404, {'detail': 'not found'})

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path.endswith('/cancel'):
            if not self._authorized():
                return self._send(401, {'detail': 'invalid key'})
            return self._send(STUB.cancel_status, {'status': 'OK' if STUB.cancel_status == 200 else 'CANCELLATION_REQUESTED'})
        return self._send(404, {'detail': 'not found'})


def signed_headers(body, user_id='user-test', timestamp=None, key_seed=KP_SEED, request_id=None):
    from app import ed25519
    import hashlib
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    identifier = request_id or 'req-1'
    message = '\n'.join((identifier, user_id, stamp, hashlib.sha256(body).hexdigest())).encode()
    signature = ed25519.sign_for_tests(key_seed, message).hex()
    return {'X-Fal-Webhook-Request-Id': identifier, 'X-Fal-Webhook-User-Id': user_id,
            'X-Fal-Webhook-Timestamp': stamp, 'X-Fal-Webhook-Signature': signature}
