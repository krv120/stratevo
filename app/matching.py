"""Conservative, deterministic research matching; no external supplier search."""
import json
import math
import re
from app import catalog
from app.privacy import buyer_safe

BOOKING = 'https://app.minup.io/book/stratevo'
HANDOFF = "The supplied research does not establish a qualifying match. A human needs to verify the missing evidence. Schedule a brief scoping call: " + BOOKING
REQUIRED = ('product', 'volume', 'unit', 'location', 'certifications')


def unit_name(value):
    # Only spelling aliases, never cross-unit or carton-to-piece conversion.
    value = value.strip().casefold()
    return {'pc':'pieces','pcs':'pieces','pce':'pieces','piece':'pieces','temaxia':'pieces','tmx':'pieces','τεμάχια':'pieces','kg':'kilograms','kilogram':'kilograms','set':'sets'}.get(value,value)


def validate(requirement):
    if not isinstance(requirement, dict):
        raise ValueError('Provide a sourcing requirement object')
    missing = [k for k in REQUIRED if k not in requirement or requirement[k] is None or requirement[k] == '']
    if missing:
        return missing
    for key in ('product', 'unit', 'location'):
        if not isinstance(requirement[key], str) or not requirement[key].strip() or len(requirement[key]) > 200:
            raise ValueError('Invalid ' + key)
    volume = requirement['volume']
    if isinstance(volume, bool) or not isinstance(volume, (float, int)) or not math.isfinite(volume) or not 0 < volume <= 1e12:
        raise ValueError('Volume must be a positive finite number')
    certs = requirement['certifications']
    if not isinstance(certs, list) or len(certs) > 20 or any(not isinstance(s, str) or not s.strip() or len(s) > 100 for s in certs):
        raise ValueError('Certifications must be a list; [] means explicitly none required')
    for key in ('lead_time_days', 'target_price'):
        value = requirement.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0):
            raise ValueError('Invalid ' + key)
    if requirement.get('target_price') is not None and (not isinstance(requirement.get('currency'),str) or not re.fullmatch('[A-Z]{3}', requirement['currency'])):
        raise ValueError('Target price requires a three-letter currency')
    return []


def match(requirement, db=catalog.DB):
    missing = validate(requirement)
    if missing:
        return {'status': 'needs_qualification', 'missing': missing, 'matches': [], 'message': 'Before matching, confirm product, target volume and unit, ideal supplier location (or any), and required certifications (or explicitly none). Missing: ' + ', '.join(missing)}
    tokens = re.findall(r'[\w]+', requirement['product'].casefold())
    if not tokens:
        raise ValueError('Provide product keywords')
    if not catalog.count(db):
        return {'status':'no_match','matches':[], 'message':HANDOFF, 'reviewed_product_candidates':0}
    connection = catalog.connect(db)
    try:
        rows = connection.execute('SELECT public_summary FROM records ORDER BY id').fetchall()
    finally:
        connection.close()
    results, candidate_count, seen = [], 0, set()
    gaps = set()
    for (raw,) in rows:
        row = buyer_safe(json.loads(raw))
        words = set(re.findall(r'[\w]+', row['description'].casefold()))
        if not all(token in words for token in tokens):
            continue
        candidate_count += 1
        matrix = row.get('matrix') or {}
        moq = row.get('advertised_moq') or {}
        quantity = moq.get('quantity')
        # No conversion or unit inference: pieces, sets and service weights differ.
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not math.isfinite(quantity) or quantity <= 0 or not isinstance(moq.get('unit'), str) or not moq['unit'] or unit_name(moq['unit']) != unit_name(requirement['unit']):
            gaps.add('Comparable MOQ units or quantity missing');continue
        if quantity > requirement['volume']:
            gaps.add('Advertised MOQ exceeds target volume');continue
        location = matrix.get('location')
        if requirement['location'].strip().casefold() != 'any' and (not isinstance(location, str) or location.casefold() != requirement['location'].strip().casefold()):
            gaps.add('Supplier location missing or does not match');continue
        verified = {s.casefold() for s in matrix.get('certifications_verified', [])}
        if not all(s.casefold() in verified for s in requirement['certifications']):
            gaps.add('Required certification evidence not verified');continue
        lead = matrix.get('lead_time_days')
        if requirement.get('lead_time_days') is not None and (not isinstance(lead, (int, float)) or isinstance(lead,bool) or lead <= 0 or not math.isfinite(lead) or lead > requirement['lead_time_days']):
            gaps.add('Lead time missing or exceeds target');continue
        # This catalog has no confirmed variant-specific prices: never qualify on a range.
        if requirement.get('target_price') is not None:
            gaps.add('No confirmed variant-specific quotation');continue
        signature = row['description'].casefold()
        if signature in seen:continue
        seen.add(signature)
        row['matrix'] = {**matrix, 'location': location or 'Unknown', 'lead_time_days':lead, 'target_price':requirement.get('target_price')}
        row['moq_match'] = 'Yes — advertised MOQ only'
        row['why_fit'] = 'The listing contains all requested product keywords and advertises a MOQ of %s %s within the target volume; supplier identity, variant and claims still need human review.' % (quantity, moq['unit'])
        results.append(row)
    matches = results[:3]
    return {'status':'research_shortlist' if matches else 'no_match', 'matches':matches, 'reviewed_product_candidates':candidate_count, 'evidence_gaps':sorted(gaps), 'message':'Up to three unverified research leads, not verified supplier recommendations. Matching checks product keywords and the supplied constraints; it does not establish technical suitability.' if matches else HANDOFF}


def render(result):
    parts = [result['message']]
    for row in result['matches']:
        matrix = row['matrix']
        parts.append('%s / %s\nLocation: %s\nMOQ Match: %s\nWhy they fit: %s' % (matrix.get('category') or 'Unclassified', row['reference'], matrix['location'], row['moq_match'], row['why_fit']))
    if result.get('evidence_gaps'):
        parts.append('Evidence gaps: ' + '; '.join(result['evidence_gaps']))
    return '\n\n'.join(parts)
