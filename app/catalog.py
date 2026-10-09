"""Private research index: SQLite locally, PostgreSQL for deployed persistence."""
import hashlib
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from app.privacy import buyer_safe

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'private'
DB = PRIVATE / 'catalog.sqlite3'


def private_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(PRIVATE.resolve()):
        raise ValueError('Research files must remain inside private/')
    return path


class PostgresConnection:
    def __init__(self):
        import psycopg
        self.raw = psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10)
        self.raw.execute('SET search_path TO stratevo_private')
    def execute(self, sql, args=()):
        return self.raw.execute(sql.replace('?', '%s'), args)
    def __enter__(self): return self
    def __exit__(self, kind, value, trace):
        self.raw.rollback() if kind else self.raw.commit()
    def close(self): self.raw.close()


def connect(path=DB):
    if os.environ.get('DATABASE_URL'):
        return PostgresConnection()
    path = private_path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    os.chmod(path, 0o600)
    connection.executescript('''
      CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY, batch TEXT NOT NULL, fingerprint TEXT NOT NULL,
        original TEXT NOT NULL, public_summary TEXT NOT NULL);
      CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED, description);
    ''')
    return connection


def import_json(path, db=DB):
    path = private_path(path)
    document = json.loads(path.read_text())
    rows = document['records']
    prepared = []
    ids = set()
    for row in rows:
        rid = row['source_row_id']
        description = row['description_summary']
        if not isinstance(rid, str) or not re.fullmatch(r'[0-9]+-[0-9]+', rid) or rid in ids:
            raise ValueError('Invalid or duplicate source row ID')
        ids.add(rid)
        if not isinstance(description, str) or not 1 <= len(description) <= 2000:
            raise ValueError('Invalid description')
        # Public references are opaque; source row IDs and supplier fields stay private.
        public = {
            'reference': 'R-' + hashlib.sha256(rid.encode()).hexdigest()[:16],
            'description': description,
            'advertised_price': row.get('advertised_price'),
            'advertised_moq': row.get('advertised_moq'),
            'verification_status': 'unverified_user_supplied_listing',
            'source_note': 'Owner-provided research summary; not a verified quotation',
        }
        # Explicitly allowlist nested fields, too. Never blindly copy nested input.
        for field, keys in [('advertised_price', ('display', 'min', 'max', 'currency_symbol', 'currency_code', 'unit_basis', 'exact_variant_confirmed')), ('advertised_moq', ('quantity', 'unit'))]:
            value = public[field]
            if value is not None:
                if not isinstance(value, dict):
                    raise ValueError('Invalid pricing/MOQ object')
                public[field] = {key: value.get(key) for key in keys}
                if any(isinstance(v, (dict, list)) for v in public[field].values()):
                    raise ValueError('Nested research fields are not allowed')
        moq = public['advertised_moq']
        if moq:
            quantity = moq.get('quantity')
            unit = moq.get('unit')
            if quantity is not None and (isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not math.isfinite(quantity) or quantity <= 0):
                raise ValueError('MOQ quantity must be a positive finite number or unknown')
            if unit is not None and (not isinstance(unit,str) or not unit.strip() or len(unit)>100):
                raise ValueError('Invalid MOQ unit')
        matrix = row.get('matrix') or {}
        if not isinstance(matrix, dict):
            raise ValueError('Invalid sourcing matrix')
        public['matrix'] = {key: matrix.get(key) for key in ('category', 'location', 'lead_time_days', 'target_price')}
        if any(isinstance(v, (dict, list)) for v in public['matrix'].values()):
            raise ValueError('Invalid matrix scalar')
        for key in ('category','location'):
            value = public['matrix'][key]
            if value is not None and (not isinstance(value,str) or len(value)>200):
                raise ValueError('Invalid matrix text')
        for key in ('lead_time_days','target_price'):
            value = public['matrix'][key]
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0):
                raise ValueError('Invalid matrix numeric value')
        claims = matrix.get('certifications_claimed', [])
        if not isinstance(claims, list) or any(not isinstance(v, str) or len(v) > 100 for v in claims):
            raise ValueError('Invalid certification claims')
        public['matrix']['certifications_claimed'] = claims
        # Imported marketing claims never become verified compliance evidence.
        public['matrix']['certifications_verified'] = []
        public = buyer_safe(public)
        fingerprint = hashlib.sha256(description.casefold().encode()).hexdigest()
        prepared.append((rid, rid.split('-')[0], fingerprint, json.dumps(row), json.dumps(public)))
    connection = connect(db)
    try:
        with connection:
            for item in prepared:
                connection.execute('INSERT INTO records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET batch=excluded.batch,fingerprint=excluded.fingerprint,original=excluded.original,public_summary=excluded.public_summary', item)
                connection.execute('DELETE FROM search WHERE id = ?', (item[0],))
                connection.execute('INSERT INTO search VALUES (?,?)', (item[0], json.loads(item[4])['description']))
    finally:
        connection.close()
    return len(prepared)


def search(query, limit=6, db=DB):
    # FTS syntax is never accepted from the browser/model.
    tokens = re.findall(r'[^\W_]+', query.casefold(), flags=re.UNICODE)[:16]
    tokens = [t for t in tokens if len(t) > 1 and t not in {'the', 'with', 'for', 'and', 'find', 'me', 'want', 'need', 'please', 'show'}]
    if not tokens or (not os.environ.get("DATABASE_URL") and not Path(db).exists()):
        return []
    expression = ' OR '.join('"' + t + '"' for t in tokens)
    connection = connect(db)
    try:
        if os.environ.get('DATABASE_URL'):
            expression = ' | '.join(tokens)
            rows = connection.execute("SELECT records.public_summary FROM search JOIN records ON records.id=search.id WHERE to_tsvector('simple',description) @@ to_tsquery('simple',?) ORDER BY ts_rank(to_tsvector('simple',description),to_tsquery('simple',?)) DESC LIMIT ?", (expression,expression,max(1,min(int(limit),10)))).fetchall()
        else:
            rows = connection.execute('''SELECT records.public_summary FROM search
            JOIN records ON records.id=search.id WHERE search MATCH ?
            ORDER BY bm25(search) LIMIT ?''', (expression, max(1, min(int(limit), 10)))).fetchall()
        # Preserve duplicate rows privately, collapse only identical public summaries in results.
        results, seen = [], set()
        for (value,) in rows:
            item = buyer_safe(json.loads(value))
            signature = json.dumps({k: v for k, v in item.items() if k != 'reference'}, sort_keys=True)
            if signature not in seen:
                seen.add(signature)
                results.append(item)
        return results
    finally:
        connection.close()


def count(db=DB):
    if not os.environ.get("DATABASE_URL") and not Path(db).exists():
        return 0
    connection = connect(db)
    try:
        return connection.execute('SELECT COUNT(*) FROM records').fetchone()[0]
    finally:
        connection.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    args = parser.parse_args()
    print(f'Imported {import_json(args.file)} research rows (not verified suppliers).')


def owner_records(limit=200):
    """Manager-only original summaries; never use this in buyer/model endpoints."""
    if not os.environ.get('DATABASE_URL') and not DB.exists():
        return []
    connection = connect()
    try:
        rows = connection.execute('SELECT original FROM records ORDER BY id LIMIT ?', (max(1,min(limit,200)),)).fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        connection.close()
