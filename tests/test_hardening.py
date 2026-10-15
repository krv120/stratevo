"""Synthetic regression tests; SMTP is mocked, never sends mail."""
import base64
import json
import os
import urllib.request
import urllib.error
from unittest.mock import patch
import unittest
import test_marketplace as fixtures
from test_marketplace import application, token_for, product
from app import suppliers as s, marketplace as m, controls, maintenance, admin_auth, settings

class HardeningTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.MarketplaceTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.MarketplaceTests.tearDownClass.__func__)
    setUp=fixtures.MarketplaceTests.setUp
    http=fixtures.MarketplaceTests.http
    def test_unscanned_upload_disabled(self):
        with self.assertRaises(s.WorkflowError) as error:m.register(application(license_pdf=base64.b64encode(b'%PDF-test').decode()))
        self.assertEqual(error.exception.status,503)
        self.assertEqual(m.admin_accounts()['accounts'],[])

    def test_expired_mail_not_sent(self):
        m.register(application())
        with s.database() as db:db.execute('UPDATE market_tokens SET expires_at=0')
        with patch.dict(os.environ,{'MAIL_DELIVERY_ENABLED':'true','SMTP_HOST':'smtp.invalid','MAIL_FROM':'sender@example.invalid'}),patch('app.suppliers.smtplib.SMTP') as smtp:
            self.assertEqual(s.send_email_queue()['sent'],0);smtp.assert_not_called()
        with s.database() as db:self.assertEqual(db.execute('SELECT status FROM mail_state').fetchone()['status'],'expired')

    def test_consumed_mail_not_sent(self):
        m.register(application());m.consume({'token':token_for('account@example.invalid')})
        with patch.dict(os.environ,{'MAIL_DELIVERY_ENABLED':'true','SMTP_HOST':'smtp.invalid','MAIL_FROM':'sender@example.invalid'}),patch('app.suppliers.smtplib.SMTP') as smtp:
            s.send_email_queue();smtp.assert_not_called()

    def test_suspend_revoke_hide_restore_does_not_publish(self):
        m.register(application());_,session=m.consume({'token':token_for('account@example.invalid')});owner=m.identity(session)['id']
        controls.suspension({'id':owner,'suspended':True,'reason':'Synthetic test review'},'test-admin')
        self.assertEqual(m.listings()['total'],0)
        with self.assertRaises(s.WorkflowError):m.identity(session)
        controls.suspension({'id':owner,'suspended':False,'reason':'Synthetic restoration'},'test-admin')
        self.assertEqual(m.listings()['total'],0)

    def test_storage_capacity(self):
        with patch.dict(os.environ,{'MAX_PENDING_SUPPLIERS':'1'}):
            m.register(application())
            with self.assertRaises(s.WorkflowError) as error:m.register(application('another@example.invalid'))
            self.assertEqual(error.exception.status,503)
        self.assertEqual(len(m.admin_accounts()['accounts']),1)

    def test_report_and_review(self):
        m.register(application());m.consume({'token':token_for('account@example.invalid')});identifier=m.listings()['products'][0]['id']
        controls.report({'id':identifier,'reason':'Synthetic inaccurate listing report'})
        report=controls.reports()['reports'][0];controls.review_report({'id':report['id']},'test-admin')
        self.assertEqual(controls.reports()['reports'][0]['status'],'reviewed')
        self.assertEqual(m.listings()['total'],1)

    def test_named_admin_totp_replay_and_rotation(self):
        secret=base64.b32encode(b'synthetic-testing-only-seed').decode();password='synthetic-test-password-123'
        row={'id':'test-admin','password_hash':s.hash_password(password),'totp_secret':secret}
        with patch.dict(os.environ,{'ADMIN_ACCOUNTS_JSON':json.dumps([row])}):
            code=admin_auth.code(secret,s.now()//30)
            _,session=s.admin_login({'username':row['id'],'password':password,'otp':code})
            self.assertEqual(s.authenticate(session,'admin')['actor'],'test-admin')
            with self.assertRaises(s.WorkflowError):s.admin_login({'username':row['id'],'password':password,'otp':code})
            row['disabled']=True
            with patch.dict(os.environ,{'ADMIN_ACCOUNTS_JSON':json.dumps([row])}):
                with self.assertRaises(s.WorkflowError):s.authenticate(session,'admin')

    def test_export_and_guarded_erase(self):
        m.register(application());owner=m.admin_accounts()['accounts'][0]['id']
        self.assertNotIn('license_pdf',maintenance.export('supplier',owner)['profile'])
        with self.assertRaises(s.WorkflowError):maintenance.erase({'kind':'supplier','id':owner,'confirm':owner},'test-admin')
        with patch.dict(os.environ,{'RIGHTS_ERASURE_APPROVED':'true'}):maintenance.erase({'kind':'supplier','id':owner,'confirm':owner},'test-admin')
        self.assertEqual(m.admin_accounts()['accounts'],[])
        with s.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM outbox').fetchone()['n'],0)

    def test_retention_opt_in(self):
        m.register(application())
        with s.database() as db:db.execute('UPDATE market_accounts SET created_at=0')
        self.assertEqual(maintenance.prune()['pending_suppliers'],0)
        with patch.dict(os.environ,{'RETENTION_DAYS_PENDING_SUPPLIERS':'1','RETENTION_APPLY_APPROVED':'true'}):
            self.assertEqual(maintenance.prune()['pending_suppliers'],1)
            self.assertEqual(len(m.admin_accounts()['accounts']),1)
            maintenance.prune(True)
        self.assertEqual(m.admin_accounts()['accounts'],[])

    def test_health_failure_and_json_methods(self):
        with patch('app.suppliers.database',side_effect=RuntimeError('secret database detail')):
            status,_,body=self.http('/api/health');self.assertEqual(status,503);self.assertNotIn('secret',str(body))
        request=urllib.request.Request(self.base+'/api/health',method='PATCH')
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,405);self.assertIn('application/json',error.exception.headers['Content-Type'])

    def test_environment_contact_guards(self):
        self.assertEqual(settings.contact(),'')
        with patch.dict(os.environ,{'APP_ENV':'production','DATABASE_URL':'','COOKIE_SECURE':'false'}):
            with self.assertRaises(ValueError):settings.database_guard()
        with patch.dict(os.environ,{'APP_ENV':'staging','PUBLIC_ORIGIN_VERIFIED':'false'}):
            with self.assertRaises(ValueError):settings.public_origin()

    def test_mail_worker_requires_secret(self):
        self.assertEqual(self.http('/api/jobs/mail')[0],401)
        self.assertEqual(self.http('/api/jobs/mail',{})[0],401)

    def test_sql_pagination_beyond_old_cutoff(self):
        m.register(application());m.consume({'token':token_for('account@example.invalid')})
        with s.database() as db:
            row=dict(db.execute('SELECT * FROM market_products').fetchone())
            for i in range(2001):db.execute('INSERT INTO market_products VALUES (?,?,?,?,?,?)',('fixture-'+str(i),row['owner_id'],row['public_payload'],'','published',i))
        self.assertEqual(m.listings()['total'],2002)
        self.assertEqual(len(m.listings(offset=1992)['products']),10)
        self.assertEqual(m.listings(query='%')['total'],0)

    def test_admin_registry_pagination(self):
        m.register(application())
        with s.database() as db:
            row=dict(db.execute('SELECT * FROM market_accounts').fetchone())
            for i in range(25):db.execute('INSERT INTO market_accounts VALUES (?,?,?,?,?)',('fixture-'+str(i),'fixture-'+str(i)+'@example.invalid',row['private_profile'],i,None))
        self.assertTrue(m.admin_accounts()['has_more']);self.assertEqual(len(m.admin_accounts(25)['accounts']),1)

    def test_atomic_storage_ceiling(self):
        from concurrent.futures import ThreadPoolExecutor
        def register(email):
            try:m.register(application(email));return True
            except s.WorkflowError:return False
        with patch.dict(os.environ,{'MAX_PENDING_SUPPLIERS':'1'}),ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(register,['a@example.invalid','b@example.invalid'])),1)

    def test_public_model_cannot_invent_qualification_for_lookup(self):
        from app import agent
        with patch.object(agent,'configured',return_value=True),patch.object(agent,'match') as match:
            result=agent.reply([{'role':'user','content':'find boxes'}],public=True,request_fn=lambda _: {'tool_calls':[{'function':{'name':'match_catalog','arguments':'{"product":"boxes","volume":100,"unit":"pieces","location":"Greece","certifications":[]}'}}]})
            match.assert_not_called();self.assertEqual(result['references'],[])

    def test_erasure_waits_for_inflight_mail(self):
        m.register(application());owner=m.admin_accounts()['accounts'][0]['id']
        with s.database() as db:db.execute('UPDATE outbox SET claimed_until=?',(s.now()+120,))
        with patch.dict(os.environ,{'RIGHTS_ERASURE_APPROVED':'true'}):
            with self.assertRaises(s.WorkflowError) as error:maintenance.erase({'kind':'supplier','id':owner,'confirm':owner},'test-admin')
            self.assertEqual(error.exception.status,409)
        self.assertEqual(len(m.admin_accounts()['accounts']),1)

    def test_image_processing_lease_expires_and_releases(self):
        with patch.dict(os.environ,{'IMAGE_PROCESSING_CONCURRENCY':'1'}):
            with controls.image_slot():
                with self.assertRaises(s.WorkflowError):
                    with controls.image_slot():pass
            with controls.image_slot():pass
        with s.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM processing_slots').fetchone()['n'],0)

    def test_unapproved_indexing_stays_off(self):
        from app import seo
        with patch.dict(os.environ,{'SITE_INDEXABLE':'true','SITE_LAUNCH_APPROVED':'false'}):self.assertFalse(seo.indexable('/'))

    def test_aggregate_metrics_no_transcript(self):
        from app import public_ai
        with public_ai.measure():public_ai.usage({'prompt_tokens':30,'completion_tokens':10})
        data=public_ai.metrics()['days'][0]
        self.assertEqual((data['successes'],data['failures'],data['input_tokens'],data['output_tokens']),(1,0,30,10))
        self.assertNotIn('messages',data)

    def test_full_mail_queue_does_not_erase_inquiry(self):
        from app import intake
        from test_intake import inquiry
        m.register(application())
        with patch.dict(os.environ,{'MAX_OUTBOX_RECORDS':'1','NOTIFICATION_EMAIL':'owner@example.invalid'}):
            result=intake.submit(inquiry());self.assertTrue(result['saved'])
        with s.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM customer_inquiries').fetchone()['n'],1)
            self.assertIsNone(db.execute("SELECT outbox_id FROM notification_jobs WHERE entity_type='customer'").fetchone()['outbox_id'])

    def test_unicode_case_insensitive_product_search(self):
        m.register(application(product=product(title='ΠΡΟΪΟΝ ΣΤΗΡΙΞΗΣ')))
        m.consume({'token':token_for('account@example.invalid')})
        self.assertEqual(m.listings(query='προϊον')['total'],1)

class VercelConfigurationTests(unittest.TestCase):
    def test_url_priority_normalization_pooler_hints_and_tls(self):
        with patch.dict(os.environ,{},clear=True):
            for variable in reversed(settings.DATABASE_VARIABLES):
                os.environ[variable]='postgres://user:encoded%40password@db.example.invalid/db?pgbouncer=true&connection_limit=2&supa=base&sslmode=disable&sslmode=require&application_name=test'
                resolved=settings.database_url()
                self.assertTrue(resolved.startswith('postgresql://'))
                self.assertNotIn('pgbouncer',resolved);self.assertNotIn('connection_limit',resolved);self.assertNotIn('supa=',resolved)
                self.assertIn('sslmode=require',resolved);self.assertNotIn('sslmode=disable',resolved)
                self.assertIn('application_name=test',resolved)
            os.environ['DATABASE_URL']='postgres://primary.invalid/db'
            self.assertIn('primary.invalid',settings.database_url())
            os.environ['DATABASE_URL']='  '
            self.assertIn('db.example.invalid',settings.database_url())

    def test_strict_and_environment_mismatch_still_fail_closed(self):
        with patch.dict(os.environ,{'APP_ENV':'production','VERCEL':'1'},clear=True):
            settings.database_guard()
            self.assertEqual(settings.storage_status()['mode'],'ephemeral_fallback')
            with patch.dict(os.environ,{'STRICT_PERSISTENT_DB':'true'}):
                with self.assertRaises(ValueError):settings.database_guard()
            with patch.dict(os.environ,{'POSTGRES_URL':'postgres://db.invalid/test','DATABASE_ENVIRONMENT':'preview'}):
                with self.assertRaises(ValueError):settings.database_guard()

    def test_pooler_connections_disable_preparation_and_use_transactions(self):
        from app import connections
        from unittest.mock import MagicMock
        raw=MagicMock()
        with patch.dict(os.environ,{'POSTGRES_URL':'postgres://db.invalid/test?pgbouncer=true'},clear=True),patch('psycopg.connect',return_value=raw) as connect,patch('app.connections._initialize'):
            connections.open_database('/unused',dictionaries=True)
            self.assertIsNone(connect.call_args.kwargs['prepare_threshold'])
            self.assertIs(connect.call_args.kwargs['autocommit'],False)
            self.assertEqual(connect.call_args.args[0],'postgresql://db.invalid/test?sslmode=require')
        connections._READY.clear()

    def test_vercel_ip_headers_are_not_trusted_on_arbitrary_hosts(self):
        from app.server import Handler
        handler=object.__new__(Handler);handler.client_address=('127.0.0.1',1)
        handler.headers={'X-Forwarded-For':'203.0.113.8'}
        with patch.dict(os.environ,{},clear=True):self.assertEqual(handler.client_ip(),'127.0.0.1')
        with patch.dict(os.environ,{'VERCEL':'1'},clear=True):
            self.assertEqual(handler.client_ip(),'203.0.113.8')
            handler.headers={'X-Vercel-Forwarded-For':'2001:db8::7','X-Forwarded-For':'203.0.113.8'}
            self.assertEqual(handler.client_ip(),'2001:db8::7')
            handler.headers={'X-Forwarded-For':'spoof, 203.0.113.8'}
            self.assertEqual(handler.client_ip(),'127.0.0.1')

    def test_configured_database_failure_never_silently_switches_storage(self):
        from app import connections
        with patch.dict(os.environ,{'VERCEL':'1','POSTGRES_URL':'postgres://db.invalid/fixture'},clear=True),patch('psycopg.connect',side_effect=RuntimeError('synthetic failure')),patch('app.connections.sqlite3.connect') as sqlite:
            with self.assertRaises(RuntimeError):connections.open_database('/unused')
            sqlite.assert_not_called()

    def test_production_origin_allowlist_rejects_spoof_and_cross_site(self):
        from app.server import Handler
        handler=object.__new__(Handler)
        with patch.dict(os.environ,{'VERCEL':'1','VERCEL_ENV':'production'},clear=True):
            for origin in ('https://stratevo.online','https://www.stratevo.online'):
                handler.headers={'Origin':origin,'Host':'internal-worker.invalid'}
                self.assertTrue(handler.origin_allowed())
            for origin in ('https://evil.invalid','http://stratevo.online','https://stratevo.online.evil.invalid','null'):
                handler.headers={'Origin':origin,'Host':origin.removeprefix('https://')}
                self.assertFalse(handler.origin_allowed())
            handler.headers={'Origin':'https://stratevo.online','Sec-Fetch-Site':'cross-site'}
            self.assertFalse(handler.origin_allowed())
