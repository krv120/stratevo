"""Opt-in live web discovery via Brave Search. Never follows supplier URLs.

Search titles/snippets/URLs are private evidence, never buyer/model text.
Search results are discovery candidates, not verified supplier matches.
"""
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from app import catalog
from app.matching import validate, BOOKING
from app.privacy import buyer_safe


def configured():
    return os.environ.get('ONLINE_DISCOVERY_ENABLED') == 'true' and bool(os.environ.get('BRAVE_SEARCH_API_KEY'))


def initialize(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS discovery_evidence (id TEXT PRIMARY KEY, searched_at TEXT NOT NULL, evidence TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS discovery_budget (day TEXT PRIMARY KEY, calls INTEGER NOT NULL)')
    if os.environ.get('DATABASE_URL'):
        for table in ('discovery_evidence','discovery_budget'):
            connection.execute('ALTER TABLE ' + table + ' ENABLE ROW LEVEL SECURITY')
            connection.execute('REVOKE ALL ON ' + table + ' FROM PUBLIC')
            for role in ('anon','authenticated'):
                if connection.execute('SELECT 1 FROM pg_roles WHERE rolname=?',(role,)).fetchone():
                    connection.execute('REVOKE ALL ON ' + table + ' FROM ' + role)



def reserve(db):
    limit = max(1, min(int(os.environ.get('ONLINE_DISCOVERY_DAILY_LIMIT', '50')), 1000))
    connection = catalog.connect(db)
    try:
        with connection:
            initialize(connection)
            row = connection.execute('INSERT INTO discovery_budget(day,calls) VALUES (?,1) ON CONFLICT(day) DO UPDATE SET calls=discovery_budget.calls+1 WHERE discovery_budget.calls < ? RETURNING calls', (datetime.now(timezone.utc).date().isoformat(), limit)).fetchone()
            return bool(row)
    finally:
        connection.close()


def provider_search(query):
    request = urllib.request.Request('https://api.search.brave.com/res/v1/web/search?' + urlencode({'q':query, 'count':10}), headers={'Accept':'application/json', 'X-Subscription-Token':os.environ['BRAVE_SEARCH_API_KEY']})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):return None
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:raise ValueError('Search response too large')
        result = json.loads(raw)
    rows = result.get('web', {}).get('results', [])
    if not isinstance(rows, list):raise ValueError('Unexpected search response')
    return rows[:10]


def discover(requirement, db=catalog.DB, search_fn=None):
    missing = validate(requirement)
    if missing:
        return {'status':'needs_qualification', 'matches':[], 'message':'Before searching online, provide product, volume and unit, supplier location (or any), and certifications (or explicitly none). Missing: ' + ', '.join(missing)}
    if not configured():
        return {'status':'not_configured','matches':[], 'message':'Online discovery is not connected. An operator must enable it and configure a server-side search API key. No online search was performed.'}
    if not reserve(db):
        return {'status':'budget_exhausted','matches':[], 'message':'The online search daily limit has been reached. No additional search was performed. Arrange human review: ' + BOOKING}
    # Do not send the buyer's target price, volume, contact data or entire chat.
    query = requirement['product'].strip() + ' manufacturer supplier'
    if requirement['location'].strip().casefold() != 'any':query += ' ' + requirement['location'].strip()
    query += ' ' + ' '.join(requirement['certifications'])
    try:
        rows = (search_fn or provider_search)(query[:1000])
        if not isinstance(rows, list):raise ValueError('Unexpected search response')
    except Exception:
        return {'status':'search_unavailable','matches':[], 'message':'The online search service could not return results. No supplier match has been established. Try again or arrange human review: ' + BOOKING}
    now = datetime.now(timezone.utc).isoformat()
    leads, evidence, seen = [], [], set()
    for row in rows[:10]:
        if not isinstance(row, dict) or not isinstance(row.get('url'), str):continue
        try:
            parsed = urlsplit(row['url'])
            host = parsed.hostname
            if parsed.scheme not in ('https','http') or not host or parsed.username or parsed.password:continue
        except ValueError:continue
        domain = host.lower().removeprefix('www.')
        if domain in seen:continue
        seen.add(domain)
        reference = 'W-' + hashlib.sha256((row['url']+now).encode()).hexdigest()[:16]
        evidence.append((reference,now,json.dumps({'query':query[:1000],'provider':'brave','url':row['url'],'title':str(row.get('title',''))[:2000],'snippet':str(row.get('description',''))[:6000],'status':'unverified_search_candidate'})))
        # No model summarization of raw snippets: prevents names/links/instructions leaking.
        leads.append({'reference':reference, 'description':'Online research candidate — human review required', 'advertised_price':None, 'advertised_moq':None, 'verification_status':'unverified_search_candidate', 'matrix':{'category':buyer_safe(requirement['product']), 'location':'Unknown','lead_time_days':None,'certifications_verified':[], 'target_price':None}, 'moq_match':'Unknown — no verified MOQ evidence', 'why_fit':'A search result was returned for the product-focused supplier query; relevance, supplier identity and all commercial requirements still require human review.', 'searched_at':now})
        if len(leads)==3:break
    connection = catalog.connect(db)
    try:
        with connection:
            for item in evidence:connection.execute('INSERT INTO discovery_evidence VALUES (?,?,?)',item)
    finally:
        connection.close()
    message = ('Online search returned candidate pages, not a qualified supplier shortlist. Raw sources are private. No MOQ, location or certification match has been verified.' if leads else 'Online search returned no usable candidate pages. No supplier match has been established.') + ' Arrange a scoping call: ' + BOOKING
    return {'status':'online_research' if leads else 'no_match', 'matches':leads,'message':message,'searched_at':now}


def owner_evidence(db=catalog.DB):
    connection=catalog.connect(db)
    try:
        with connection:
            initialize(connection)
            rows=connection.execute('SELECT id,searched_at,evidence FROM discovery_evidence ORDER BY searched_at DESC LIMIT 100').fetchall()
        return [{'reference':row[0],'searched_at':row[1],**json.loads(row[2])} for row in rows]
    finally:connection.close()
