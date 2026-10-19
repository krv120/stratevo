"""Actual isolated PostgreSQL verification; never connects to a production database."""
import json
import os
from pathlib import Path
import secrets
import tempfile
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import pgserver
from app import connections, suppliers as s, directory, controls, maintenance
from test_directory import application

Path('private').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir='private') as folder:
    server=pgserver.get_server(Path(folder)/'postgres')
    try:
        with patch.dict(os.environ,{'APP_ENV':'test','POSTGRES_URL':server.get_uri(),'PUBLIC_BASE_URL':'https://www.stratevo.online','MAIL_DELIVERY_ENABLED':'false','ADMIN_PASSWORD':secrets.token_urlsafe(24)},clear=True):
            connections._READY.clear()
            with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(lambda _:directory.public()['total'],range(4)))==[0]*4
            with s.database() as db:
                assert db.execute('SELECT count(*) AS n FROM schema_migrations').fetchone()['n']==7
                assert db.raw.prepare_threshold is None
                for _ in range(12):assert db.execute('SELECT count(*) AS n FROM supplier_directory').fetchone()['n']==0
            print('PASS concurrent cold bootstrap, seven migrations and repeated non-prepared queries')
            data=application();
            with ThreadPoolExecutor(max_workers=3) as pool:result=list(pool.map(lambda _:directory.register(data),range(3)))
            assert len({v['supplier_id'] for v in result})==1 and directory.public()['total']==1
            owner=result[0];print('PASS exact-retry registration is one record under concurrent PostgreSQL requests')
            raw=json.dumps(directory.public());assert data['email'] not in raw and data['phone'] not in raw and data['contact'] not in raw
            print('PASS public contact projection and private staff persistence')
            directory.update(owner['_session'],{**data,'revision':1,'company':'Updated Synthetic Works'})
            assert directory.public()['suppliers'][0]['company']=='Updated Synthetic Works'
            try:directory.update(owner['_session'],{**data,'revision':1});raise AssertionError('stale edit accepted')
            except s.WorkflowError as e:assert e.status==409
            print('PASS owned edits publish atomically and reject stale versions')
            directory.moderate({'id':owner['supplier_id'],'note':'Synthetic test moderation review.'},'fixture-owner')
            assert directory.public()['total']==0 and directory.sync(owner['_session'],{'id':owner['supplier_id']})['supplier'] is None
            print('PASS staff removal cannot be resurrected by synchronization')
            connections._READY.clear();s.initialize();assert directory.mine(owner['_session'])['status']=='hidden'
            print('PASS schema reapplication preserves account, session and moderation state')
            with s.database() as db:
                db.execute('CREATE ROLE directory_fixture_reader')
                db.execute('GRANT USAGE ON SCHEMA stratevo_private TO directory_fixture_reader')
                db.execute('GRANT SELECT ON supplier_directory,market_accounts,admin_notifications TO directory_fixture_reader')
                db.execute('SET LOCAL ROLE directory_fixture_reader')
                for table in ('supplier_directory','market_accounts','admin_notifications'):
                    assert db.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
            print('PASS RLS denies client role rows even after accidental SELECT grants')
            with patch.dict(os.environ,{'RIGHTS_ERASURE_APPROVED':'true'}):maintenance.erase({'kind':'supplier','id':owner['supplier_id'],'confirm':owner['supplier_id']},'fixture-owner')
            with s.database() as db:
                for table in ('supplier_directory','market_accounts','suppliers','market_tokens'):
                    assert db.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
            print('PASS approved privacy erasure cascades through directory and private metadata')
    finally:server.cleanup()
