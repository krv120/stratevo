"""Server-side fal.ai REST client (standard library only).

Only this module talks to fal.ai, and only with the server-held ``FAL_KEY``.
The key is read from the process environment at call time, is never returned in
a response, never written to the database and never logged. Queue URLs returned
by fal.ai are re-validated before use so a tampered response cannot turn the
poller into an SSRF primitive.
"""
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

QUEUE_BASE = 'https://queue.fal.run'
PRICING_URL = 'https://api.fal.ai/v1/models/pricing'
JWKS_URL = 'https://rest.fal.ai/.well-known/jwks.json'
TIMEOUT = 20
MAX_RESPONSE_BYTES = 1_000_000
PRICING_TTL = 6 * 60 * 60
PRICING_FAILURE_TTL = 10 * 60
JWKS_TTL = 24 * 60 * 60

_PRICING_CACHE = {}
_JWKS_CACHE = {'keys': [], 'fetched_at': 0}


class FalError(Exception):
    """A fal.ai failure that is safe to surface to an authenticated operator."""

    def __init__(self, message, status=502, retryable=True, ambiguous=False, code=None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        # Upstream HTTP status when fal.ai actually answered (None for transport errors).
        self.code = code
        # True when the request may have reached fal.ai even though we saw an
        # error (timeout/connection reset). Such jobs must not be auto-retried
        # or refunded because they may have been queued and billed.
        self.ambiguous = ambiguous


def endpoint_key():
    """Return the configured key without ever echoing it. Placeholder values are rejected."""
    value = (os.environ.get('FAL_KEY') or '').strip()
    if not value or value.lower() in ('replace_me', 'your_key', 'changeme', 'todo'):
        return ''
    if len(value) < 20 or any(c.isspace() or ord(c) < 32 for c in value):
        return ''
    return value


def configured():
    return bool(endpoint_key())


def _headers(extra=None):
    value = endpoint_key()
    if not value:
        raise FalError('FAL_KEY is not configured on the server. Add it as a hosting environment variable and redeploy.', 503, retryable=False)
    headers = {'Authorization': 'Key ' + value, 'Accept': 'application/json',
               'User-Agent': 'stratevo-content-studio/1'}
    headers.update(extra or {})
    return headers


def _decode_body(raw, label):
    try:
        return json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError):
        raise FalError('fal.ai returned an unreadable ' + label + ' response.', 502) from None


def _request(url, *, method='GET', payload=None, timeout=TIMEOUT, label='API'):
    data = None
    headers = _headers({'Content-Type': 'application/json'} if payload is not None else None)
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as error:
        try:
            detail = error.read(4096)
        except Exception:
            detail = b''
        message = ''
        try:
            parsed = json.loads(detail.decode('utf-8'))
            if isinstance(parsed, dict):
                message = str(parsed.get('detail') or parsed.get('message') or parsed.get('error') or '')[:300]
        except (UnicodeError, ValueError):
            pass
        if error.code in (401, 403):
            raise FalError('fal.ai rejected the API key. Check FAL_KEY in the hosting secret manager; no generation was charged.', 502, retryable=False, code=error.code) from None
        if error.code == 429:
            raise FalError('fal.ai rate-limited the request. Try again shortly.', 429, code=error.code) from None
        if error.code in (400, 404, 422):
            raise FalError('fal.ai rejected the request' + (': ' + message if message else '.'), 502, retryable=False, code=error.code) from None
        raise FalError('fal.ai returned HTTP ' + str(error.code) + (': ' + message if message else '') + '.', 502, retryable=True, ambiguous=method == 'POST', code=error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise FalError('fal.ai could not be reached from this server (' + label + ').',
                       503, retryable=True, ambiguous=method == 'POST') from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FalError('fal.ai returned an oversized response.', 502)
    response = _decode_body(raw, label)
    if not isinstance(response, dict):
        raise FalError('fal.ai returned an unexpected ' + label + ' response.', 502)
    return status, response


def _trusted_queue_url(value):
    """Queue URLs must stay on the configured fal host over the configured scheme."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return ''
    base = urllib.parse.urlsplit(QUEUE_BASE)
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return ''
    if (parsed.scheme != base.scheme or parsed.hostname != base.hostname
            or parsed.username or parsed.password or parsed.fragment
            or not parsed.path.startswith('/')):
        return ''
    return value


def submit(model, payload, webhook_url=None):
    """Submit an asynchronous job and return the identifiers fal.ai will need later."""
    url = QUEUE_BASE.rstrip('/') + '/' + model
    if webhook_url:
        url += '?' + urllib.parse.urlencode({'fal_webhook': webhook_url})
    _, body = _request(url, method='POST', payload=payload, label='submit')
    request_id = body.get('request_id')
    if not isinstance(request_id, str) or not request_id or len(request_id) > 200:
        raise FalError('fal.ai did not return a request id.', 502, retryable=True, ambiguous=True)
    status_url = _trusted_queue_url(body.get('status_url'))
    response_url = _trusted_queue_url(body.get('response_url'))
    cancel_url = _trusted_queue_url(body.get('cancel_url'))
    # Older queue responses omit the helper URLs; derive them from the
    # documented owner/app rule only when the host still matches.
    owner_app = '/'.join(model.split('/')[:2])
    status_url = status_url or _trusted_queue_url(QUEUE_BASE.rstrip('/') + '/' + owner_app + '/requests/' + request_id + '/status')
    response_url = response_url or _trusted_queue_url(QUEUE_BASE.rstrip('/') + '/' + owner_app + '/requests/' + request_id)
    cancel_url = cancel_url or _trusted_queue_url(QUEUE_BASE.rstrip('/') + '/' + owner_app + '/requests/' + request_id + '/cancel')
    if not status_url or not response_url:
        raise FalError('fal.ai returned untrusted queue URLs; the job was not tracked.', 502)
    return {'request_id': request_id, 'status_url': status_url,
            'response_url': response_url, 'cancel_url': cancel_url}


def status(status_url):
    if not _trusted_queue_url(status_url):
        raise FalError('Stored fal.ai status URL is not trusted.', 502, retryable=False)
    _, body = _request(status_url, label='status')
    state = body.get('status')
    if state not in ('IN_QUEUE', 'IN_PROGRESS', 'COMPLETED'):
        raise FalError('fal.ai returned an unknown queue status.', 502)
    return body


def result(response_url):
    if not _trusted_queue_url(response_url):
        raise FalError('Stored fal.ai result URL is not trusted.', 502, retryable=False)
    _, body = _request(response_url, label='result', timeout=30)
    return body


def cancel(cancel_url):
    """Return (http_status, body). 400/404 mean "already finished" / "not found"."""
    if not _trusted_queue_url(cancel_url):
        raise FalError('Stored fal.ai cancel URL is not trusted.', 502, retryable=False)
    try:
        return _request(cancel_url, method='PUT', payload={}, label='cancel')
    except FalError as error:
        if error.code == 400:
            return 400, {'status': 'ALREADY_COMPLETED'}
        if error.code == 404:
            return 404, {'status': 'NOT_FOUND'}
        raise


def pricing(model):
    """Live unit price for a model, or None when it cannot be determined safely.

    Uses fal's documented Platform API. Results are cached; failures are cached
    briefly so a pricing outage cannot amplify into request floods.
    """
    cached = _PRICING_CACHE.get(model)
    if cached and time.time() - cached[1] < (PRICING_TTL if cached[0] else PRICING_FAILURE_TTL):
        return cached[0]
    query = urllib.parse.urlencode({'endpoint_id': model})
    try:
        _, body = _request(PRICING_URL + '?' + query, label='pricing', timeout=10)
        prices = body.get('prices')
        found = None
        for row in prices if isinstance(prices, list) else []:
            if not isinstance(row, dict) or row.get('endpoint_id') != model:
                continue
            try:
                amount = float(row['unit_price'])
                unit = str(row['unit']).strip().lower()
                currency = str(row['currency']).strip().upper()
            except (KeyError, TypeError, ValueError):
                continue
            if currency != 'USD' or amount < 0:
                continue
            if unit in ('second', 'seconds', 's', 'per_second'):
                found = {'per_second': amount, 'source': 'fal_pricing_api'}
            elif unit in ('video', 'videos', 'per_video', 'output'):
                found = {'per_video': amount, 'source': 'fal_pricing_api'}
            if found:
                break
    except FalError:
        found = None
    _PRICING_CACHE[model] = (found, time.time())
    return found


def _jwks(force=False):
    fetched = time.time() - _JWKS_CACHE['fetched_at']
    if not force and _JWKS_CACHE['keys'] and fetched < JWKS_TTL:
        return _JWKS_CACHE['keys']
    request = urllib.request.Request(JWKS_URL, headers={'Accept': 'application/json',
                                                        'User-Agent': 'stratevo-content-studio/1'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read(300_000).decode('utf-8'))
    except Exception:
        # Keep serving a previously fetched key set rather than failing open.
        return _JWKS_CACHE['keys']
    keys = [row for row in (body.get('keys') or []) if isinstance(row, dict) and isinstance(row.get('x'), str)]
    if keys:
        _JWKS_CACHE.update({'keys': keys, 'fetched_at': time.time()})
        return keys
    return _JWKS_CACHE['keys']


def _b64url(value):
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_webhook(headers, raw_body):
    """Validate fal.ai's Ed25519 webhook signature.

    Returns (ok, reason). Any missing header, stale timestamp or unverifiable
    signature is rejected; the caller must not trust the body before this
    returns True.
    """
    from app import ed25519

    def header(name):
        for candidate in (name, name.lower(), name.upper()):
            value = headers.get(candidate) if hasattr(headers, 'get') else None
            if value:
                return str(value).strip()
        return ''

    request_id = header('X-Fal-Webhook-Request-Id')
    user_id = header('X-Fal-Webhook-User-Id')
    timestamp = header('X-Fal-Webhook-Timestamp')
    signature = header('X-Fal-Webhook-Signature')
    if not all((request_id, user_id, timestamp, signature)):
        return False, 'missing signature headers'
    if len(request_id) > 200 or len(user_id) > 200 or len(timestamp) > 20 or len(signature) > 256:
        return False, 'malformed signature headers'
    try:
        stamp = int(timestamp)
    except ValueError:
        return False, 'invalid timestamp'
    if abs(int(time.time()) - stamp) > 300:
        return False, 'stale timestamp'
    try:
        signature_bytes = bytes.fromhex(signature)
    except ValueError:
        return False, 'signature is not hexadecimal'
    message = '\n'.join((request_id, user_id, timestamp,
                         hashlib.sha256(raw_body).hexdigest())).encode('utf-8')
    for force in (False, True):
        keys = _jwks(force=force)
        for row in keys:
            try:
                candidate = _b64url(row['x'])
            except Exception:
                continue
            if ed25519.verify(candidate, message, signature_bytes):
                return True, 'verified'
        if not keys:
            break
    return False, 'signature did not verify'
