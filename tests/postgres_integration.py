"""One-shot integration tests against bundled real PostgreSQL, not a mock.
Install requirements.txt and pgserver in a virtual environment; run with PYTHONPATH=.:tests.
"""
import base64
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pgserver
import psycopg
from app import suppliers, catalog, discovery
from catalog_fixture import write_fixture

with tempfile.TemporaryDirectory(dir='private') as directory:
    server=pgserver.get_server(Path(directory)/'postgres')
    try:
        url=server.get_uri()
        os.environ['DATABASE_URL']=url
        os.environ['PUBLIC_BASE_URL']='https://example.invalid'
        with psycopg.connect(url) as db:
            db.execute(Path('migrations/001_private_platform.sql').read_text())
            db.execute(Path('migrations/002_private_discovery.sql').read_text())
            db.execute(Path('migrations/003_public_ai_marketplace.sql').read_text())
            db.execute('CREATE ROLE anon; CREATE ROLE authenticated;')
            db.execute(Path('migrations/001_private_platform.sql').read_text())
            db.execute(Path('migrations/002_private_discovery.sql').read_text())
            db.execute(Path('migrations/003_public_ai_marketplace.sql').read_text())
        suppliers.initialize()
        fixture = write_fixture(Path(directory)/'synthetic-fixture.json')
        assert catalog.import_json(fixture)==60
        catalog.import_json(fixture)
        assert catalog.count()==60
        assert len(catalog.search('7.5ft warm white tree'))>0
        assert catalog.search('nonexistentxyz')==[]
        print('PASS PostgreSQL migration, idempotent catalog import and full-text search')
        os.environ['ONLINE_DISCOVERY_ENABLED']='true'
        os.environ['BRAVE_SEARCH_API_KEY']='test-only'
        req={'product':'test boxes','volume':10,'unit':'pieces','location':'any','certifications':[]}
        found=discovery.discover(req,search_fn=lambda q:[{'url':'https://fixture.example/test','title':'TEST ONLY','description':'Fixture only'}])
        assert len(found['matches'])==1
        assert len(discovery.owner_evidence())==1
        print('PASS PostgreSQL private discovery storage and persisted budget')

        data=dict(company='Postgres Test',contact='Test Person',email='pg@example.invalid',country='Greece',category='Lighting',capabilities='Example-only lighting capability for PostgreSQL integration.',whatsapp='+300000000000',wechat='',license_number='TEST-PG',license_pdf=base64.b64encode(b'%PDF-1.4\n% Test fixture only\n%%EOF').decode(),consent=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            submissions=list(pool.map(suppliers.apply,[data,data]))
        assert submissions[0]==submissions[1]
        with suppliers.database() as db:
            assert db.execute('SELECT COUNT(*) AS n FROM applications').fetchone()['n']==1
            assert db.execute('SELECT COUNT(*) AS n FROM outbox').fetchone()['n']==1
        print('PASS PostgreSQL concurrent duplicate application is non-enumerating with one verification email')
        with suppliers.database() as db:
            row=db.execute('SELECT id FROM applications').fetchone()
            body=db.execute('SELECT body FROM outbox').fetchone()['body']
        suppliers.consume({'token':body.split('#token=')[1].split()[0]})
        def decide(decision):
            try: suppliers.review({'id':row['id'],'decision':decision,'note':'Test review'}); return 200
            except suppliers.WorkflowError as e: return e.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(decide,['approved','approved']))
        assert sorted(outcomes)==[200,409], outcomes
        with suppliers.database() as db:
            mail=db.execute("SELECT body FROM outbox WHERE subject='STRATEVO — approved supplier access'").fetchall()
            assert len(mail)==1
        _,token=suppliers.consume({'token':mail[0]['body'].split('#token=')[1].split()[0]})
        identity=suppliers.authenticate(token,'supplier')
        assert suppliers.profile(identity)['application']['status']=='approved'
        suppliers.logout(token)
        print('PASS PostgreSQL verification, concurrent approval conflict, single access email, login and logout')
        from app import marketplace, public_ai
        from test_marketplace import application, product, token_for
        import json
        with ThreadPoolExecutor(max_workers=4) as pool:
            submissions=list(pool.map(lambda _:marketplace.register(application('market-pg@example.invalid')),range(4)))
        assert len([item for item in submissions if item[1]])==1
        assert marketplace.listings()['total']==0
        email_token=token_for('market-pg@example.invalid')
        def verify(_):
            try:return marketplace.consume({'token':email_token})[1]
            except suppliers.WorkflowError:return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            sessions=list(pool.map(verify,range(4)))
        assert len([s for s in sessions if s])==1
        session=next(s for s in sessions if s)
        assert marketplace.listings()['total']==1
        assert 'Private Example Works' not in json.dumps(marketplace.listings())
        marketplace.add_product(session,product(title='Second PG product'))
        pid=marketplace.listings()['products'][0]['id']
        marketplace.withdraw(session,{'id':pid})
        assert marketplace.listings()['total']==1
        assert len(marketplace.mine(session)['products'])==2
        print('PASS PostgreSQL concurrent registration, single-use confirmation, automatic publication, private projection and ownership')
        os.environ['PUBLIC_AI_DAILY_LIMIT']='3'
        os.environ['PUBLIC_AI_CONCURRENCY']='20'
        def reserve(_):
            try:
                with public_ai.reserve():pass
                return True
            except suppliers.WorkflowError:return False
        with ThreadPoolExecutor(max_workers=8) as pool:outcomes=list(pool.map(reserve,range(8)))
        assert sum(outcomes)==3,outcomes
        with suppliers.database() as db:assert db.execute('SELECT COUNT(*) AS n FROM public_ai_slots').fetchone()['n']==0
        print('PASS PostgreSQL atomic shared public AI daily budget and concurrency lease cleanup')
        for table in ('market_accounts','market_products','market_tokens','public_ai_budget','public_ai_slots'):
            with psycopg.connect(url) as db:
                db.execute('GRANT USAGE ON SCHEMA stratevo_private TO anon')
                db.execute('GRANT SELECT ON stratevo_private.'+table+' TO anon')
                db.execute('SET ROLE anon')
                assert db.execute('SELECT COUNT(*) FROM stratevo_private.'+table).fetchone()[0]==0
                db.rollback()
        print('PASS PostgreSQL RLS protection of all marketplace and public AI internal tables')
        for role in ['anon','authenticated']:
            with psycopg.connect(url) as db:
                db.execute('SET ROLE '+role)
                try:
                    db.execute('SELECT * FROM stratevo_private.applications')
                    raise AssertionError('Client role accessed private applications')
                except psycopg.errors.InsufficientPrivilege:
                    db.rollback()
        # Even an accidental SELECT grant must not expose rows: enabled RLS has no client policies.
        with psycopg.connect(url) as db:
            db.execute('GRANT USAGE ON SCHEMA stratevo_private TO anon')
            db.execute('GRANT SELECT ON stratevo_private.applications TO anon')
            db.execute('SET ROLE anon')
            assert db.execute('SELECT COUNT(*) FROM stratevo_private.applications').fetchone()[0]==0
            db.rollback()
        with psycopg.connect(url) as db:
            db.execute('GRANT USAGE ON SCHEMA stratevo_private TO anon')
            db.execute('GRANT SELECT ON stratevo_private.discovery_evidence TO anon')
            db.execute('SET ROLE anon')
            assert db.execute('SELECT COUNT(*) FROM stratevo_private.discovery_evidence').fetchone()[0]==0
            db.rollback()
        print('PASS anon/authenticated role denial and RLS protection of applications and discovery evidence')
    finally:
        os.environ.pop('DATABASE_URL',None)
        server.cleanup()
