"""One-shot integration tests against bundled real PostgreSQL, not a mock.
Install pgserver and psycopg into private/postgres-tools before running.
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
            db.execute('CREATE ROLE anon; CREATE ROLE authenticated;')
            db.execute(Path('migrations/001_private_platform.sql').read_text())
            db.execute(Path('migrations/002_private_discovery.sql').read_text())
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
