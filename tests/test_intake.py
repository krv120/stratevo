import json
import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, Mock
from app import intake, suppliers as s, marketplace as m, seo, agent
import test_marketplace as fixtures
application = fixtures.application


def inquiry(**changes):
    return {'submission_key':secrets.token_hex(24),'name':'TEST Buyer','email':'buyer@example.invalid','business':'Synthetic Buyer','product':'Custom packaging','quantity':'500 boxes','destination':'Greece','requirements':'Recycled cardboard packaging with custom print and no confirmed dimensions yet.','budget':'Not decided','timeline':'Within three months','contact':'','source':'form','consent':True,**changes}


class IntakeTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.MarketplaceTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MarketplaceTests.tearDownClass.__func__)
    setUp = fixtures.MarketplaceTests.setUp
    http = fixtures.MarketplaceTests.http
    def test_customer_persistence_notification_separation_and_idempotency(self):
        data=inquiry()
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':'owner@example.invalid'}):
            first=intake.submit(data);second=intake.submit(data)
        self.assertEqual(first,second)
        with s.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM customer_inquiries').fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM market_accounts').fetchone()['n'],0)
            mail=db.execute('SELECT * FROM outbox').fetchone();self.assertEqual(mail['recipient'],'owner@example.invalid');self.assertIn(first['id'],mail['body']);self.assertNotIn('buyer@example.invalid',mail['body'])
        record=intake.list_inquiries()['inquiries'][0];self.assertFalse(record['details']['marketing_consent']);self.assertEqual(record['notification'],'queued');self.assertNotIn('submission_key',json.dumps(record))

    def test_invalid_input_never_saved(self):
        for changes in [{'email':'invalid'},{'name':''},{'requirements':'tiny'},{'product':'x'*201},{'consent':False},{'destination':''},{'website_confirm':'spam'},{'source':'supplier'},{'submission_key':'short'}]:
            with self.subTest(changes=changes),self.assertRaises(s.WorkflowError):intake.submit(inquiry(**changes))
        with s.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM customer_inquiries').fetchone()['n'],0)

    def test_parallel_retry_one_record_and_one_mail(self):
        data=inquiry()
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':'owner@example.invalid'}),ThreadPoolExecutor(max_workers=6) as pool:
            responses=list(pool.map(lambda _:intake.submit(data),range(6)))
        self.assertEqual(len({r['id'] for r in responses}),1)
        with s.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM outbox').fetchone()['n'],1)
        with self.assertRaises(s.WorkflowError) as error:intake.submit({**data,'product':'Different request'})
        self.assertEqual(error.exception.status,409)

    def test_missing_destination_recovers_without_losing_inquiry(self):
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':''}):result=intake.submit(inquiry())
        self.assertTrue(result['saved']);self.assertEqual(intake.list_inquiries()['inquiries'][0]['notification'],'awaiting_configuration')
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':'owner@example.invalid'}):
            with s.database() as db:self.assertEqual(intake.queue_pending(db),1)
            with s.database() as db:self.assertEqual(intake.queue_pending(db),0)
        self.assertEqual(intake.list_inquiries()['inquiries'][0]['notification'],'queued')

    def test_smtp_failure_preserves_record_and_can_retry(self):
        with patch.dict(os.environ,{'MAIL_DELIVERY_ENABLED':'true','NOTIFICATION_EMAIL':'owner@example.invalid','SMTP_HOST':'smtp.invalid','MAIL_FROM':'sender@example.invalid'}):
            result=intake.submit(inquiry())
            with patch('app.suppliers.smtplib.SMTP',side_effect=OSError('DO NOT EXPOSE')):sent=s.send_email_queue(limit=1)
            self.assertEqual(sent,{'sent':0,'failed':1})
            self.assertEqual(intake.list_inquiries()['inquiries'][0]['id'],result['id']);self.assertEqual(intake.list_inquiries()['inquiries'][0]['notification'],'retry_pending')
            with s.database() as db:db.execute('UPDATE outbox SET claimed_until=0')
            with patch('app.suppliers.smtplib.SMTP'):self.assertEqual(s.send_email_queue(limit=1)['sent'],1)
        self.assertEqual(intake.list_inquiries()['inquiries'][0]['notification'],'smtp_accepted')

    def test_outbox_transaction_failure_rolls_back_record(self):
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':'owner@example.invalid'}),patch('app.suppliers.queue',side_effect=RuntimeError('db unavailable')):
            with self.assertRaises(RuntimeError):intake.submit(inquiry())
        with s.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM customer_inquiries').fetchone()['n'],0)

    def test_supplier_notifies_owner_without_customer_record_and_optional_files(self):
        data=application(license_pdf='',license_number='',whatsapp='',wechat='');data['product']['moq']=None
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':'owner@example.invalid'}):m.register(data);m.register(data)
        with s.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM notification_jobs').fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM customer_inquiries').fetchone()['n'],0)
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM outbox').fetchone()['n'],2)
        account=m.admin_accounts()['accounts'][0];self.assertFalse(account['has_license']);self.assertEqual(account['review_status'],'new')
        intake.update({'id':account['id'],'status':'reviewed'},supplier=True)
        self.assertEqual(m.admin_accounts()['accounts'][0]['review_status'],'reviewed');self.assertEqual(m.listings()['total'],0)

    def test_inquiry_http_auth_origin_and_real_save(self):
        for path in ['/inquiry','/privacy','/terms','/intake.js','/robots.txt','/sitemap.xml']:self.assertEqual(self.http(path)[0],200)
        self.assertEqual(self.http('/api/inquiries',inquiry(),origin='https://evil.invalid')[0],403)
        self.assertEqual(self.http('/api/inquiries',[])[0],400)
        self.assertEqual(self.http('/api/admin/inquiries')[0],401)
        self.assertEqual(self.http('/api/admin/inquiry-status',{'id':'x','status':'closed'})[0],401)
        self.assertEqual(self.http('/api/admin/notifications')[0],401)
        self.assertEqual(self.http('/api/inquiries',inquiry())[0],200)
        self.assertEqual(self.http('/api/inquiries')[0],404)
        with patch('app.server.intake.submit',side_effect=RuntimeError('SECRET DATABASE ERROR')):
            code,body,_=self.http('/api/inquiries',inquiry());self.assertEqual(code,503);self.assertNotIn(b'SECRET',body)

    def test_private_admin_inbox_status_filter_and_pagination(self):
        result=intake.submit(inquiry());intake.update({'id':result['id'],'status':'qualified'})
        self.assertEqual(intake.list_inquiries('new')['inquiries'],[]);self.assertEqual(len(intake.list_inquiries('qualified')['inquiries']),1)
        with s.database() as db:session=s.session(db,'admin',None)
        code,body,_=self.http('/api/admin/inquiries?status=qualified',cookie='stratevo_session='+session);self.assertEqual(code,200);self.assertIn('buyer@example.invalid',body.decode())
        with self.assertRaises(s.WorkflowError):intake.update({'id':result['id'],'status':'invented'})
        with self.assertRaises(s.WorkflowError):intake.list_inquiries('all',-1)

    def test_owner_retry_does_not_revive_verification_links(self):
        with patch.dict(os.environ,{'NOTIFICATION_EMAIL':'owner@example.invalid'}):intake.submit(inquiry())
        with s.database() as db:
            verification=s.queue(db,'other@example.invalid','Access link','TEST ONLY expired link')
            db.execute('UPDATE outbox SET attempts=5,claimed_until=0')
        intake.retry_failed()
        with s.database() as db:
            self.assertEqual(db.execute('SELECT attempts FROM outbox WHERE id=?',(verification,)).fetchone()['attempts'],5)
            self.assertEqual(db.execute('SELECT o.attempts FROM outbox o JOIN notification_jobs j ON j.outbox_id=o.id').fetchone()['attempts'],0)
        self.assertEqual(self.http('/api/admin/retry-notifications',{})[0],401)

    def test_header_like_addresses_and_accidental_keys_rejected(self):
        for email in ['Name <x@example.invalid>','x,y@example.invalid','x@example.invalid;evil','x..y@example.invalid']:
            with self.assertRaises(s.WorkflowError):s.email_address({'email':email})
        with self.assertRaises(s.WorkflowError):intake.submit(inquiry(requirements='Here is a key: '+'sk-'+'x'*40))

    def test_client_disconnect_does_not_attempt_error_response(self):
        from app.server import Handler
        for stage,error in [('body',BrokenPipeError()),('headers',ConnectionResetError())]:
            with self.subTest(stage=stage):
                handler=Handler.__new__(Handler);handler.path='/';handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock();handler.wfile=Mock()
                if stage=='body':handler.wfile.write.side_effect=error
                else:handler.end_headers.side_effect=error
                handler.send(200,{'saved':True})
                self.assertTrue(handler.close_connection);self.assertEqual(handler.send_response.call_count,1)

    def test_noindex_canonical_sitemap_and_etag(self):
        with patch.dict(os.environ,{'SITE_INDEXABLE':'false','CANONICAL_BASE_URL':'https://stratevo.online'}):
            _,body,headers=self.http('/inquiry');self.assertIn(b'rel="canonical" href="https://stratevo.online/inquiry"',body);self.assertIn('noindex',headers['X-Robots-Tag']);self.assertIn('Disallow: /',seo.robots())
        with patch.dict(os.environ,{'APP_ENV':'production','SITE_INDEXABLE':'true','SITE_LAUNCH_APPROVED':'true','PUBLIC_ORIGIN_VERIFIED':'true'}):
            self.assertIn('<loc>https://stratevo.online/</loc>',seo.sitemap());self.assertNotIn('/admin',seo.sitemap());self.assertNotIn('/inquiry</loc>',seo.sitemap());self.assertFalse(seo.indexable('/supplier/account'))
        _,_,headers=self.http('/intake.js');self.assertIn('ETag',headers);self.assertIn('must-revalidate',headers['Cache-Control'])
        with patch.dict(os.environ,{'CANONICAL_BASE_URL':'https://evil.invalid/path'}):self.assertEqual(self.http('/')[0],503)

    def test_invalid_output_limit_gives_safe_config_error(self):
        with patch.dict(os.environ,{'AI_MAX_OUTPUT_TOKENS':'broken'}),patch('app.agent.urllib.request.build_opener') as network:
            with self.assertRaises(agent.ProviderError) as error:agent.provider_request([{'role':'user','content':'hi'}])
            self.assertEqual(error.exception.code,'configuration');network.assert_not_called()

if __name__=='__main__':unittest.main()

class VercelIntakeTests(unittest.TestCase):
    def test_ephemeral_inquiry_save_is_disclosed_and_idempotent(self):
        import tempfile
        from pathlib import Path
        from app import connections, settings
        from unittest.mock import patch
        import os
        payload={'submission_key':'test-only-inquiry-key-123456789012345','name':'Synthetic Buyer','business':'','product':'Synthetic packaging','requirements':'Synthetic integration test requirements only.','destination':'Greece','quantity':'100 pieces','budget':'','timeline':'','contact':'','email':'test@example.invalid','source':'assessment','consent':True,'website_confirm':''}
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'VERCEL':'1','APP_ENV':'production'},clear=True),patch.object(connections,'RUNTIME_SQLITE',Path(folder)/'runtime.sqlite3'):
            first=intake.submit(payload);second=intake.submit(payload)
            self.assertEqual(first['id'],second['id']);self.assertTrue(first['saved'])
            self.assertEqual(first['storage']['mode'],'ephemeral_fallback')
            self.assertIn('Temporary',first['message'])
