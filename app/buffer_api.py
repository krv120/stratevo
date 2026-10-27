"""Buffer public GraphQL API client (api.buffer.com).

Facts this module depends on, verified against developers.buffer.com on
2026-10-27:

* One endpoint, ``POST https://api.buffer.com``, GraphQL, ``Authorization:
  Bearer <personal API key>``. There is no SDK and no OAuth needed for a single
  account: a personal key from publish.buffer.com/settings/api is enough.
* ``createPost`` targets **one channel per call**. Scheduling uses
  ``schedulingType: automatic`` with ``mode: customScheduled`` and ``dueAt`` in
  ISO-8601 UTC (or ``addToQueue`` to use the channel's own slots).
* Video is attached as ``assets: [{ video: { url } }]`` — Buffer fetches the
  file from a **public HTTPS URL** at publish time, so the URL must outlive the
  scheduling window. No media upload endpoint exists.
* TikTok metadata supports ``isAiGenerated``; Instagram metadata requires
  ``type`` (reel/post/story) and ``shouldShareToFeed``.
* Errors arrive inside HTTP 200 as ``errors[]`` or as a ``MutationError`` union
  member, so both must be inspected before anything is called scheduled.

Nothing here ever claims a post is scheduled: the caller only stores a
``confirmed`` state when Buffer returns a post id.
"""
import json
import os
import urllib.error
import urllib.request

API_URL = 'https://api.buffer.com'
TIMEOUT = 30
MAX_RESPONSE = 512 * 1024

CHANNELS_QUERY = '''
query Channels($input: ChannelsInput!) {
  channels(input: $input) {
    id
    name
    service
    descriptor
    displayName
    externalLink
    isDisconnected
    isLocked
    isQueuePaused
    organizationId
  }
}
'''

ACCOUNT_QUERY = '''
query Account {
  account {
    id
    email
    timezone
    organizations { id name }
  }
}
'''

CREATE_POST = '''
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess {
      post { id text dueAt status channelId assets { id mimeType source } }
    }
    ... on MutationError { message }
  }
}
'''

POST_QUERY = '''
query Post($input: PostInput!) {
  post(input: $input) { id status dueAt channelId sentAt }
}
'''


class BufferError(Exception):
    def __init__(self, message, status=502, retryable=True, code=None):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.code = code


def api_key():
    value = (os.environ.get('BUFFER_API_KEY') or '').strip()
    if not value or len(value) < 20 or any(ch.isspace() for ch in value):
        return ''
    return value


def configured():
    return bool(api_key())


def enabled():
    return configured() and os.environ.get('PUBLISHING_ENABLED', 'false').strip().lower() == 'true'


def _call(query, variables=None):
    key = api_key()
    if not key:
        raise BufferError('BUFFER_API_KEY is not configured on the server.', 503, retryable=False)
    body = json.dumps({'query': query, 'variables': variables or {}}).encode()
    request = urllib.request.Request(API_URL, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
        'Accept': 'application/json', 'User-Agent': 'stratevo-content-studio/1'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise BufferError('Buffer rejected the API key. Check BUFFER_API_KEY in the hosting secret manager.', 502, retryable=False, code=error.code) from None
        if error.code == 429:
            raise BufferError('Buffer rate-limited the request. The worker will retry.', 429, code=429) from None
        raise BufferError('Buffer returned HTTP ' + str(error.code) + '.', 502, code=error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise BufferError('Buffer could not be reached from this worker.', 503) from None
    if len(raw) > MAX_RESPONSE:
        raise BufferError('Buffer returned an oversized response.', 502)
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeError, ValueError):
        raise BufferError('Buffer returned an unreadable response.', 502) from None
    if not isinstance(payload, dict):
        raise BufferError('Buffer returned an unexpected response.', 502)
    errors = payload.get('errors')
    if errors:
        message = ''
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            message = str(errors[0].get('message') or '')[:300]
        raise BufferError('Buffer rejected the request' + (': ' + message if message else '.'), 502, retryable=False)
    data = payload.get('data')
    if not isinstance(data, dict):
        raise BufferError('Buffer returned no data.', 502)
    return data


def account():
    return _call(ACCOUNT_QUERY)['account']


def channels(organization_id):
    rows = _call(CHANNELS_QUERY, {'input': {'organizationId': organization_id}})['channels']
    result = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        result.append({'id': row.get('id'), 'name': row.get('name'), 'service': str(row.get('service') or '').lower(),
                       'descriptor': row.get('descriptor'), 'display_name': row.get('displayName'),
                       'external_link': row.get('externalLink'),
                       'is_disconnected': bool(row.get('isDisconnected')),
                       'is_locked': bool(row.get('isLocked')),
                       'queue_paused': bool(row.get('isQueuePaused'))})
    return result


def publishable_channels():
    """Channels that can receive an automatic TikTok/Instagram video post."""
    data = account()
    organizations = data.get('organizations') or []
    if not organizations:
        raise BufferError('No Buffer organization is available for this key.', 409, retryable=False)
    rows = []
    for organization in organizations:
        for channel in channels(organization['id']):
            rows.append({**channel, 'organization_id': organization['id']})
    allowed = []
    for channel in rows:
        if channel['service'] not in ('tiktok', 'instagram'):
            continue
        if channel['is_disconnected'] or channel['is_locked']:
            continue
        allowed.append(channel)
    return allowed


def _post_input(*, text, channel_id, due_at=None, video_url, platform, first_comment='', thumbnail_ms=1500):
    payload = {'text': text, 'channelId': channel_id, 'schedulingType': 'automatic',
               'assets': [{'video': {'url': video_url, 'metadata': {'thumbnailOffset': int(thumbnail_ms)}}}]}
    if due_at:
        payload['mode'] = 'customScheduled'
        payload['dueAt'] = due_at
    else:
        payload['mode'] = 'addToQueue'
    if platform == 'tiktok':
        payload['metadata'] = {'tiktok': {'isAiGenerated': True}}
    elif platform == 'instagram':
        payload['metadata'] = {'instagram': {'type': 'reel', 'shouldShareToFeed': False,
                                            **({'firstComment': first_comment} if first_comment else {})}}
    return payload


def public_media_url(url):
    """Buffer must be able to fetch the file with no credentials.

    Production requires HTTPS on a real host. Local/test loops accept plain
    HTTP on a loopback address so the pipeline can be exercised end to end.
    """
    from urllib.parse import urlsplit
    parsed = urlsplit(str(url or ''))
    if parsed.scheme == 'https' and parsed.hostname:
        return True
    if parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1') \
            and os.environ.get('APP_ENV') in ('local', 'test'):
        return True
    return False


def create_post(*, text, channel_id, video_url, platform, due_at=None, first_comment=''):
    """Create one post. Returns the Buffer post id and dueAt, or raises."""
    if not text or not channel_id or not video_url:
        raise BufferError('A post needs text, a channel and a public video URL.', 400, retryable=False)
    if not public_media_url(video_url):
        raise BufferError('Buffer only accepts public HTTPS media URLs.', 400, retryable=False)
    data = _call(CREATE_POST, {'input': _post_input(text=text, channel_id=channel_id, due_at=due_at,
                                                    video_url=video_url, platform=platform,
                                                    first_comment=first_comment)})
    result = data.get('createPost')
    if not isinstance(result, dict):
        raise BufferError('Buffer returned no post result.', 502)
    if result.get('__typename') == 'MutationError' or 'message' in result and not result.get('post'):
        raise BufferError('Buffer refused the post: ' + str(result.get('message') or 'unknown error')[:300],
                          422, retryable=False)
    post = result.get('post')
    if not isinstance(post, dict) or not post.get('id'):
        raise BufferError('Buffer did not confirm a post id; nothing was recorded as scheduled.', 502)
    return {'id': post['id'], 'due_at': post.get('dueAt'), 'status': post.get('status'),
            'channel_id': post.get('channelId'), 'text': post.get('text')}


def post(post_id):
    data = _call(POST_QUERY, {'input': {'id': post_id}})
    row = data.get('post')
    if not isinstance(row, dict):
        raise BufferError('Buffer returned no post.', 502)
    return row
