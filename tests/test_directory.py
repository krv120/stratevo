"""Current supplier directory contracts. External mail transport is mocked only where stated."""
import base64
import json
import os
import re
import secrets
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from app import suppliers as s, directory, marketplace, controls, mail_policy, admin_auth, settings, intake, connections, maintenance
from app.server import Handler


def application(**changes):
    return {'company':'SYNTHETIC Precision Works','focus':'industrial','specialty':'Precision components','description':'We manufacture precision aluminium brackets and steel housings for industrial equipment.',
            'contact':'PRIVATE CONTACT PERSON','email':'supplier@example.invalid','phone':'+30 6980001111','website':'www.example.com','country':'Greece','city':'Private City','consent':True,'submission_key':secrets.token_hex(24),**changes}


class DirectoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s.PRIVATE.mkdir(exist_ok=True)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=s.PRIVATE);self.addCleanup(self.tmp.cleanup)
        self.dbpatch=patch.object(s,'DATABASE',Path(self.tmp.name)/'test.sqlite3');self.dbpatch.start();self.addCleanup(self.dbpatch.stop)
        self.password=secrets.token_urlsafe(24)
        self.env=patch.dict(os.environ,{'APP_ENV':'test','PUBLIC_BASE_URL':self.base,'COOKIE_SECURE':'false','MAIL_DELIVERY_ENABLED':'false','ADMIN_PASSWORD':self.password},clear=True);self.env.start();self.addCleanup(self.env.stop)
        s.initialize()
    def http(self,path,data=None,cookie='',origin=None,headers=None):
        h={'Content-Type':'application/json','Cookie':cookie,**(headers or {})}
        if origin:h['Origin']=origin
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
        try:r=urllib.request.urlopen(request,timeout=10)
        except urllib.error.HTTPError as e:r=e
        with r:return r.status,r.read(),r.headers
    def register(self,**changes):return directory.register(application(**changes))
    def admin(self):return 'stratevo_session='+s.admin_login({'username':'owner','password':self.password})[1]

    def test_single_step_publication_and_private_projection(self):
        data=application();code,body,headers=self.http('/api/suppliers',data);self.assertEqual(code,200)
        result=json.loads(body);self.assertTrue(result['published']);self.assertNotIn('_session',result);self.assertIn('HttpOnly',headers['Set-Cookie'])
        public=directory.public()['suppliers'];self.assertEqual(len(public),1);self.assertEqual(public[0]['company'],data['company'])
        for field in ('email','phone','contact','website','country','city'):
            self.assertNotIn(field,public[0]);self.assertNotIn(data[field],json.dumps(public))
        cookie=headers['Set-Cookie'].split(';')[0];code,body,_=self.http('/api/directory/me',cookie=cookie)
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['profile']['website'],'https://www.example.com')
        self.assertEqual(result['email_notification_status'],'queued_in_admin_inbox')

    def test_required_field_errors_are_specific(self):
        for field,bad in [('company','x'),('description','short'),('focus','unknown'),('contact',''),('email','not-email'),('consent',False)]:
            with self.subTest(field=field):
                code,body,_=self.http('/api/suppliers',application(**{field:bad}));self.assertEqual(code,400);self.assertEqual(json.loads(body)['field'],field)
        self.assertEqual(directory.public()['total'],0)

    def test_optional_private_fields_and_one_consent(self):
        result=self.register(phone='',country='',city='',website='')
        self.assertTrue(result['published']);self.assertNotIn('rights_consent',result)

    def test_website_normalization_and_unsafe_rejection(self):
        from app.normalization import website
        for value in ['example.com','www.example.com','[www.example.com](https://www.example.com)']:self.assertTrue(website(value).startswith('https://'))
        for value in ['javascript:alert(1)','http://localhost','https://user:password@example.com','https://127.0.0.1','https://example .com','https://example.com:99999']:
            with self.subTest(value=value),self.assertRaises(s.WorkflowError):website(value)

    def test_description_and_specialty_scrub_contact_values(self):
        data=application(description='We make steel parts. Email sales@example.store; call +30 6980001111 or visit www.example.com. PRIVATE CONTACT PERSON, Private City.',specialty='Parts at https://example.com/contact')
        result=directory.register(data);raw=json.dumps(directory.public())
        for value in ['sales@example.store','6980001111','www.example.com','https://example.com','PRIVATE CONTACT PERSON','Private City']:self.assertNotIn(value,raw)
        self.assertIn('[contact removed]',result['supplier']['description'])

    def test_company_cannot_publish_private_contact_as_identity(self):
        with self.assertRaises(s.WorkflowError):directory.register(application(company='PRIVATE CONTACT PERSON'))

    def test_retry_is_idempotent_and_payload_mismatch_conflicts(self):
        data=application();a=directory.register(data);b=directory.register(data);self.assertEqual(a['supplier_id'],b['supplier_id']);self.assertEqual(directory.public()['total'],1)
        with self.assertRaises(s.WorkflowError) as error:directory.register({**data,'description':'A changed description which must not create an account.'})
        self.assertEqual(error.exception.status,409)
        with s.database() as db:self.assertEqual(db.execute("SELECT count(*) AS n FROM admin_notifications WHERE event_type='supplier_submitted'").fetchone()['n'],1)

    def test_concurrent_exact_retry_creates_one_record(self):
        data=application()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:directory.register(data),range(2)))
        self.assertEqual(results[0]['supplier_id'],results[1]['supplier_id']);self.assertEqual(directory.public()['total'],1)

    def test_duplicate_email_never_grants_session(self):
        self.register()
        code,body,headers=self.http('/api/suppliers',application(company='Different Company'))
        self.assertEqual(code,409);self.assertNotIn('Set-Cookie',headers);self.assertEqual(directory.public()['suppliers'][0]['company'],'SYNTHETIC Precision Works')

    def test_edit_owner_scoping_revision_and_publication(self):
        owner=self.register();other=self.register(email='other@example.invalid',company='OTHER Works')
        result=directory.update(owner['_session'],{**application(company='Updated Works'), 'id':other['supplier_id'],'revision':1})
        self.assertEqual(result['supplier']['id'],owner['supplier_id']);self.assertEqual(directory.mine(other['_session'])['supplier']['company'],'OTHER Works')
        with self.assertRaises(s.WorkflowError) as error:directory.update(owner['_session'],{**application(),'revision':1})
        self.assertEqual(error.exception.status,409)

    def test_withdraw_and_sync_cannot_resurrect(self):
        owner=self.register();directory.withdraw(owner['_session'])
        self.assertEqual(directory.public()['total'],0);self.assertIsNone(directory.sync(owner['_session'],{'id':owner['supplier_id']})['supplier'])

    def test_moderated_listing_cannot_be_republished_by_owner(self):
        owner=self.register();directory.moderate({'id':owner['supplier_id'],'note':'Synthetic infringement review reason.'},'owner')
        self.assertEqual(directory.public()['total'],0)
        with self.assertRaises(s.WorkflowError) as error:directory.update(owner['_session'],{**application(),'revision':2})
        self.assertEqual(error.exception.status,403)
        self.assertIsNone(directory.sync(owner['_session'],{'id':owner['supplier_id']})['supplier'])

    def test_sync_requires_owner_and_does_not_ingest_arbitrary_contacts(self):
        owner=self.register();other=self.register(email='other@example.invalid',company='OTHER Works')
        self.assertEqual(self.http('/api/suppliers/sync',{'id':owner['supplier_id']})[0],401)
        with self.assertRaises(s.WorkflowError):directory.sync(other['_session'],{'id':owner['supplier_id']})
        result=directory.sync(owner['_session'],{'id':owner['supplier_id'],'company':'UNTRUSTED','email':'attacker@example.invalid'})
        self.assertEqual(result['supplier']['company'],'SYNTHETIC Precision Works')

    def test_signed_out_private_routes_are_denied(self):
        for route in ['/api/directory/me','/api/admin/suppliers','/api/admin/notifications','/api/admin/inquiries']:
            self.assertIn(self.http(route)[0],(401,403))

    def test_cross_origin_and_payload_limits(self):
        self.assertEqual(self.http('/api/suppliers',application(),origin='https://evil.example')[0],403)
        self.assertEqual(self.http('/api/suppliers',{'extra':'x'*20000})[0],413)
        self.assertEqual(self.http('/api/suppliers',[])[0],400)

    def test_search_focus_pagination_and_private_search(self):
        self.register();self.register(email='second@example.invalid',company='SYNTHETIC Textile Works',focus='textiles',specialty='Cotton weaving',description='We manufacture cotton fabrics and woven textile materials.')
        self.assertEqual(directory.public(focus='textiles')['total'],1)
        self.assertEqual(directory.public('supplier@example.invalid')['total'],0)
        self.assertEqual(directory.public('private city')['total'],0)
        self.assertEqual(directory.public('Precision')['total'],1)
        with self.assertRaises(s.WorkflowError):directory.public(offset=-1)

    def test_suspension_hides_directory_and_revokes_session(self):
        owner=self.register();controls.suspension({'id':owner['supplier_id'],'suspended':True,'reason':'Synthetic account review'},'owner')
        self.assertEqual(directory.public()['total'],0)
        with self.assertRaises(s.WorkflowError):directory.mine(owner['_session'])

    def test_erasure_removes_directory_and_private_metadata(self):
        owner=self.register();directory.moderate({'id':owner['supplier_id'],'note':'Synthetic erasure test review.'},'owner')
        with patch.dict(os.environ,{'RIGHTS_ERASURE_APPROVED':'true'}):maintenance.erase({'kind':'supplier','id':owner['supplier_id'],'confirm':owner['supplier_id']},'owner')
        self.assertEqual(directory.public()['total'],0)
        with s.database() as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM suppliers').fetchone()['n'],0)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM market_accounts').fetchone()['n'],0)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM outbox').fetchone()['n'],0)

    def test_admin_password_without_mfa_in_production(self):
        with patch.dict(os.environ,{'APP_ENV':'production','COOKIE_SECURE':'true','PUBLIC_BASE_URL':'https://www.stratevo.online','PUBLIC_ORIGIN_VERIFIED':'true'}),patch.object(connections,'RUNTIME_SQLITE',Path(self.tmp.name)/'prod.sqlite3'):
            self.assertTrue(admin_auth.setup_status()['configured'])
            token=s.admin_login({'username':'owner','password':self.password})[1]
            self.assertEqual(s.authenticate(token,'admin')['actor'],'owner')
            with patch.dict(os.environ,{'ADMIN_PASSWORD':secrets.token_urlsafe(24)}):
                with self.assertRaises(s.WorkflowError):s.authenticate(token,'admin')

    def test_optional_mfa_remains_enforced_when_configured(self):
        seed=base64.b32encode(secrets.token_bytes(20)).decode()
        with patch.dict(os.environ,{'ADMIN_TOTP_SECRET':seed}):
            with self.assertRaises(s.WorkflowError):s.admin_login({'username':'owner','password':self.password})
            otp=admin_auth.code(seed,s.now()//30)
            self.assertTrue(s.admin_login({'username':'owner','password':self.password,'otp':otp})[1])
            with self.assertRaises(s.WorkflowError):s.admin_login({'username':'owner','password':self.password,'otp':otp})

    def test_missing_admin_credentials_never_unlock(self):
        with patch.dict(os.environ,{'ADMIN_PASSWORD':'','APP_ENV':'production'}):
            self.assertFalse(admin_auth.setup_status()['configured'])
            with self.assertRaises(s.WorkflowError):s.admin_login({'password':'anything'})

    def test_admin_registry_and_notification_include_private_details_only_after_login(self):
        owner=self.register();cookie=self.admin()
        for route,key in [('/api/admin/suppliers','suppliers'),('/api/admin/notifications','notifications')]:
            code,body,_=self.http(route,cookie=cookie);self.assertEqual(code,200);self.assertTrue(json.loads(body)[key]);self.assertIn('supplier@example.invalid',body.decode())

    def test_notification_delivery_attempt_uses_real_pipeline_mock_transport(self):
        with patch.dict(os.environ,{'MAIL_DELIVERY_ENABLED':'true','RESEND_API_KEY':'synthetic-test','MAIL_FROM':'sender@example.invalid','ADMIN_NOTIFICATION_EMAIL':'owner@example.invalid'}),patch('app.mail_policy.send',return_value='resend') as sender:
            result=self.register();self.assertEqual(result['email_notification_status'],'sent');self.assertTrue(sender.called)
        with s.database() as db:self.assertGreater(db.execute('SELECT count(*) AS n FROM notification_attempts').fetchone()['n'],0)

    def test_mail_failure_does_not_lose_registration(self):
        with patch.dict(os.environ,{'MAIL_DELIVERY_ENABLED':'true','RESEND_API_KEY':'synthetic-test','MAIL_FROM':'sender@example.invalid','ADMIN_NOTIFICATION_EMAIL':'owner@example.invalid'}),patch('app.mail_policy.send',side_effect=RuntimeError('sensitive provider detail')):
            result=self.register();self.assertTrue(result['published']);self.assertEqual(directory.public()['total'],1)
            self.assertNotIn('sensitive',json.dumps(mail_policy.inbox()))

    def test_email_link_single_use_does_not_change_directory_publication(self):
        owner=self.register()
        with s.database() as db:body=db.execute("SELECT body FROM outbox WHERE recipient='supplier@example.invalid'").fetchone()['body']
        token=re.search(r'#market_token=([^\s]+)',body)[1]
        result,session=marketplace.consume({'token':token});self.assertTrue(session);self.assertEqual(directory.public()['total'],1)
        with self.assertRaises(s.WorkflowError):marketplace.consume({'token':token})

    def test_retired_routes_have_no_active_features(self):
        for route in ['/ai','/api/agent/status','/leads.js','/app.js']:
            self.assertEqual(self.http(route)[0],404)
        for route in ['/api/chat','/api/leads/find','/api/supplier/enhance','/api/catalog/discover']:
            self.assertEqual(self.http(route,{'query':'test'})[0],404)

    def test_seo_pages_have_static_metadata_and_private_noindex(self):
        from bs4 import BeautifulSoup
        descriptions=[]
        for route in ['/','/supplier','/marketplace','/methodology','/assessment','/inquiry','/privacy','/terms','/cookies']:
            code,body,_=self.http(route);self.assertEqual(code,200);html=BeautifulSoup(body,'html.parser')
            self.assertEqual(len(html.select('h1')),1);self.assertEqual(len(html.select('link[rel=canonical]')),1)
            self.assertEqual(html.select_one('link[rel=canonical]')['href'],'https://www.stratevo.online'+route)
            descriptions.append(html.select_one('meta[name=description]')['content']);self.assertTrue(html.select_one('meta[property="og:title"]'))
            self.assertEqual(len(html.select('link[rel=stylesheet]')),1)
        self.assertEqual(len(descriptions),len(set(descriptions)))
        for route in ['/admin','/supplier/account','/access']:
            self.assertIn(b'noindex',self.http(route)[1])

    def test_indexability_requires_approval_and_robots_excludes_private_routes(self):
        from app import seo
        self.assertIn('Disallow: /',seo.robots())
        with patch.dict(os.environ,{'APP_ENV':'production','SITE_LAUNCH_APPROVED':'true','PUBLIC_ORIGIN_VERIFIED':'true','SITE_INDEXABLE':'true'}):
            self.assertTrue(seo.indexable('/'));self.assertFalse(seo.indexable('/admin'));self.assertNotIn('/admin',seo.sitemap())
            self.assertIn('https://www.stratevo.online',seo.sitemap())

    def test_browser_cookie_and_cache_security(self):
        code,body,headers=self.http('/api/suppliers',application());self.assertEqual(code,200)
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Lax',headers['Set-Cookie']);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIn("object-src 'none'",headers['Content-Security-Policy'])

    def test_legacy_inquiries_persist_and_retry_safely(self):
        data={'submission_key':secrets.token_hex(24),'name':'SYNTHETIC Buyer','email':'buyer@example.invalid','business':'','product':'Industrial brackets','requirements':'Synthetic specifications for a new bracket design.','destination':'Greece','quantity':'100','budget':'','timeline':'','contact':'','source':'form','consent':True}
        a=intake.submit(data);b=intake.submit(data);self.assertEqual(a['id'],b['id']);self.assertEqual(len(intake.list_inquiries()['inquiries']),1)

    def test_rate_limit_is_enforced(self):
        for _ in range(3):s.rate_limit('synthetic',3,60)
        with self.assertRaises(s.WorkflowError) as e:s.rate_limit('synthetic',3,60)
        self.assertEqual(e.exception.status,429)

    def test_fresh_schema_initialization_is_idempotent(self):
        connections._READY.clear();s.initialize();connections._READY.clear();s.initialize()
        with s.database() as db:
            for table in ['supplier_directory','market_accounts','listing_reviews','admin_notifications','notification_attempts','customer_inquiries']:
                self.assertEqual(db.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'],0)
