"""Fresh real PostgreSQL automatic migrations + pooled URL aliases; isolated, never production."""
import os
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pgserver
from app import catalog, connections, marketplace, suppliers, controls
from test_marketplace import application

with tempfile.TemporaryDirectory(dir='private') as folder:
    server=pgserver.get_server(Path(folder)/'postgres')
    try:
        uri=server.get_uri().replace('postgresql://','postgres://')
        uri+=('&' if '?' in uri else '?')+'pgbouncer=true&connection_limit=2&supa=base'
        with patch.dict(os.environ,{'POSTGRES_URL':uri,'PUBLIC_BASE_URL':'https://example.invalid'},clear=True):
            connections._READY.clear()
            # First query, without initialize() or manual migrations: all tables must exist.
            with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(lambda _:catalog.count(),range(4)))==[0]*4
            with suppliers.database() as db:
                assert db.execute('SELECT COUNT(*) AS n FROM schema_migrations').fetchone()['n']==5
                assert db.raw.prepare_threshold is None
                for _ in range(20):db.execute('SELECT COUNT(*) AS n FROM market_accounts').fetchone()
            print('PASS cold PostgreSQL initialization via POSTGRES_URL, all five migrations, concurrent startup and repeated non-prepared queries')
            payload=application(submission_key='synthetic-postgres-attempt-key-1234567890')
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:marketplace.register(payload,immediate=True),range(2)))
            assert all(r[0]['published'] for r in results)
            assert marketplace.listings()['total']==1
            token=results[0][0]['_session'];owner=marketplace.identity(token)['id']
            assert marketplace.mine(token)['email_confirmed'] is False
            try:
                with suppliers.database() as db:
                    db.execute("UPDATE market_products SET visibility='hidden'")
                    raise RuntimeError('synthetic rollback')
            except RuntimeError:pass
            assert marketplace.listings()['total']==1
            controls.suspension({'id':owner,'suspended':True,'reason':'Synthetic test suspension'},'test-admin')
            assert marketplace.listings()['total']==0
            # Reapply every migration after data exists; existing records must survive.
            connections._READY.clear()
            with suppliers.database() as db:
                db.execute('DELETE FROM schema_migrations')
            connections._READY.clear()
            with suppliers.database() as db:
                assert db.execute('SELECT COUNT(*) AS n FROM market_accounts').fetchone()['n']==1
                assert db.execute('SELECT COUNT(*) AS n FROM schema_migrations').fetchone()['n']==5
                assert db.execute("SELECT relrowsecurity FROM pg_class WHERE relname='market_publications'").fetchone()['relrowsecurity']
            print('PASS PostgreSQL exact-retry immediate publication, management sessions, rollback, suspension and nondestructive migration reapplication')
    finally:server.cleanup()
