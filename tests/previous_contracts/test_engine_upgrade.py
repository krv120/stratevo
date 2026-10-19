"""Synthetic provider/transport contract tests, NOT proof of live provider or inbox delivery."""
import json
import os
import unittest
import urllib.error
from unittest.mock import patch,MagicMock
from app import agent,settings,ai_providers,marketplace as market,suppliers as s,mail_policy,intake,discovery,operations,admin_auth
import test_marketplace as fixtures
from test_marketplace import application
from test_intake import inquiry

class ProviderTests(unittest.TestCase):
    def test_admin_setup_missing_invalid_and_ready(self):
        import base64
        import secrets
        password = secrets.token_urlsafe(32)
        seed = base64.b32encode(secrets.token_bytes(20)).decode()
        cases = [({}, 'missing'), ({'ADMIN_PASSWORD': 'short'}, 'invalid'),
                 ({'ADMIN_PASSWORD': password}, 'invalid'),
                 ({'ADMIN_PASSWORD': password, 'ADMIN_TOTP_SECRET': 'invalid seed'}, 'invalid'),
                 ({'ADMIN_PASSWORD': password, 'ADMIN_TOTP_SECRET': seed}, 'ready'),
                 ({'ADMIN_ACCOUNTS_JSON': '{}'}, 'invalid')]
        for values, expected in cases:
            with self.subTest(state=expected), patch.dict(os.environ, {'APP_ENV': 'production', **values}, clear=True):
                result = admin_auth.setup_status()
                self.assertEqual(result['state'], expected)
                self.assertEqual(result['configured'], expected == 'ready')
                self.assertNotIn(password, json.dumps(result))
                self.assertNotIn(seed, json.dumps(result))

    def test_key_aliases_defaults_and_priority(self):
        for variable,provider in [('OPENAI_API_KEY','openai'),('STRATEVO_AI_API_KEY','openai'),('AI_API_KEY','openai'),('GEMINI_API_KEY','gemini'),('GOOGLE_API_KEY','gemini'),('ANTHROPIC_API_KEY','anthropic'),('PERPLEXITY_API_KEY','perplexity'),('OPENROUTER_API_KEY','openrouter'),('GROQ_API_KEY','groq')]:
            with self.subTest(variable=variable),patch.dict(os.environ,{variable:'synthetic-key'},clear=True):
                config=settings.ai_configuration();self.assertEqual(config['provider'],provider);self.assertTrue(agent.configured());self.assertTrue(config['model'])
        with patch.dict(os.environ,{'OPENAI_API_KEY':'first','GEMINI_API_KEY':'second'},clear=True):self.assertEqual(settings.ai_configuration()['key'],'first')
        for prefix,provider in [('sk-ant-','anthropic'),('AIza','gemini'),('pplx-','perplexity'),('sk-or-','openrouter'),('gsk_','groq')]:
            with patch.dict(os.environ,{'STRATEVO_AI_API_KEY':prefix+'synthetic'},clear=True):self.assertEqual(settings.ai_configuration()['provider'],provider)

    def test_explicit_provider_and_legacy_openai_default(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic','AI_BASE_URL':'https://api.openai.com/v1'},clear=True):self.assertIn('googleapis',settings.ai_configuration()['base'])
        with patch.dict(os.environ,{'AI_API_KEY':'synthetic','AI_PROVIDER':'groq'},clear=True):self.assertEqual(settings.ai_configuration()['provider'],'groq')

    def test_fenced_json_and_native_adapters(self):
        self.assertEqual(ai_providers.parse_json('```json\n{"leads":[]}\n```'),{'leads':[]})
        for variable,response in [('GEMINI_API_KEY',{'candidates':[{'content':{'parts':[{'text':'synthetic reply'}]}}]}),('ANTHROPIC_API_KEY',{'content':[{'type':'text','text':'synthetic reply'}]})]:
            with patch.dict(os.environ,{variable:'synthetic'},clear=True),patch('app.ai_providers.post',return_value=response) as post:
                self.assertEqual(agent.provider_request([{'role':'user','content':'hello'}],tools=False)['content'],'synthetic reply')
                self.assertIn(':generateContent' if variable=='GEMINI_API_KEY' else '/messages',post.call_args.args[0])

    def test_grounding_is_not_assumed_from_chat_key(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'synthetic'},clear=True):self.assertEqual(ai_providers.grounded('test')['status'],'grounding_not_configured')

    def test_transport_header_timeout_and_safe_errors(self):
        response=MagicMock();response.__enter__.return_value=response;response.read.return_value=b'{"ok":true}'
        with patch('app.ai_providers.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response;ai_providers.post('https://example.com',{},{});call=opener.return_value.open.call_args
            self.assertEqual(call.kwargs['timeout'],25);self.assertEqual(call.args[0].get_header('User-agent'),'Stratevo-AI-Engine/2.0')
            opener.return_value.open.side_effect=urllib.error.HTTPError('https://example.com',401,'PRIVATE KEY DETAIL',{},None)
            with self.assertRaises(agent.ProviderError) as error:ai_providers.post('https://example.com',{}, {})
            self.assertNotIn('PRIVATE',str(error.exception))

    def test_perplexity_chat_does_not_send_unsupported_function_tools(self):
        response=MagicMock();response.__enter__.return_value=response
        response.read.return_value=b'{"choices":[{"message":{"content":"Synthetic reply"}}]}'
        with patch.dict(os.environ,{'PERPLEXITY_API_KEY':'synthetic'},clear=True),patch('app.agent.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response
            agent.provider_request([{'role':'user','content':'hello'}])
            payload=json.loads(opener.return_value.open.call_args.args[0].data)
            self.assertEqual(payload['model'],'sonar-pro');self.assertNotIn('tools',payload)

    def test_openai_bounded_model_fallback(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic','AI_MODEL':'invalid-model'},clear=True),patch('app.agent.urllib.request.build_opener') as opener,patch('app.ai_providers.post',return_value={'choices':[{'message':{'content':'fallback'}}]}) as fallback:
            opener.return_value.open.side_effect=urllib.error.HTTPError('https://api.openai.com',404,'not found',{},None)
            self.assertEqual(agent.provider_request([{'role':'user','content':'hi'}])['content'],'fallback')
            self.assertEqual(fallback.call_args.args[1]['model'],'gpt-4.1-mini')

class EngineTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.MarketplaceTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.MarketplaceTests.tearDownClass.__func__)
    setUp=fixtures.MarketplaceTests.setUp
    http=fixtures.MarketplaceTests.http

    def admin_cookie(self):
        with s.database() as db:return 'stratevo_session='+s.session(db,'admin','fixture-owner')

    def test_public_setup_does_not_unlock_private_registry(self):
        with patch.dict(os.environ, {'ADMIN_ACCOUNTS_JSON': '', 'ADMIN_TOKEN': '', 'STRATEVO_ADMIN_TOKEN': '', 'ADMIN_PASSWORD': '', 'ADMIN_TOTP_SECRET': ''}):
            status, body, _ = self.http('/api/admin/setup')
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['state'], 'missing')
            self.assertEqual(self.http('/api/admin/suppliers')[0], 401)
            self.assertEqual(self.http('/api/admin/notifications')[0], 401)

    def test_supplier_normalization_immediate_inbox_and_private_registry(self):
        data=application(website='example.com',phone='+30 (210) 123 4567',certifications='ISO 9001, RoHS',materials='aluminium;steel',employees='10–50',lead_time='2–4 weeks',founded_year=2001,capabilities='Precision machining and industrial bracket production.')
        data['product']['moq']='1,000 pcs'
        status,body,headers=self.http('/api/suppliers',data);self.assertEqual(status,200);result=json.loads(body)
        self.assertTrue(result['published']);self.assertEqual(result['supplier']['moq'],1000);self.assertIn('supplier_id',result)
        self.assertEqual(result['email_notification_status'],'queued_in_admin_inbox')
        self.assertNotIn('access_token',result);self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertEqual(self.http('/api/admin/suppliers')[0],401)
        cookie=self.admin_cookie();status,body,_=self.http('/api/admin/suppliers',cookie=cookie);self.assertEqual(status,200)
        profile=json.loads(body)['suppliers'][0]['profile'];self.assertEqual(profile['website'],'https://example.com');self.assertEqual(profile['materials'],['aluminium','steel'])
        status,body,_=self.http('/api/admin/notifications',cookie=cookie);self.assertEqual(status,200);self.assertTrue(any(r['event_type']=='supplier_published' for r in json.loads(body)['notifications']))
        public=json.dumps(market.listings());self.assertNotIn(data['email'],public);self.assertNotIn(data['company'],public)

    def test_invalid_fields_return_location_and_no_record(self):
        for changes,field in [({'website':'javascript:bad'},'website'),({'founded_year':'9999'},'founded_year'),({'company':''},'company')]:
            status,body,_=self.http('/api/suppliers',application(**changes));self.assertEqual(status,400);self.assertEqual(json.loads(body)['field'],field)
        self.assertEqual(market.listings()['total'],0)

    def test_inquiry_dispatch_and_persistent_attempt_log(self):
        with patch.dict(os.environ,{'ADMIN_NOTIFICATION_EMAIL':'owner@example.invalid','RESEND_API_KEY':'synthetic','MAIL_FROM':'sender@example.invalid','MAIL_DELIVERY_ENABLED':'true'}),patch('app.mail_policy.send',return_value='resend') as sender:
            status,body,_=self.http('/api/inquiries',inquiry());self.assertEqual(status,200);self.assertEqual(json.loads(body)['email_notification_status'],'sent')
            self.assertEqual(sender.call_args.args[0],'owner@example.invalid');self.assertIn('buyer@example.invalid',sender.call_args.args[2])
        with s.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM notification_attempts').fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT delivery_status FROM admin_notifications').fetchone()['delivery_status'],'sent')

    def test_provider_failure_does_not_undo_inquiry(self):
        with patch.dict(os.environ,{'ADMIN_EMAIL':'owner@example.invalid','SMTP_HOST':'smtp.example.invalid','MAIL_FROM':'sender@example.invalid','MAIL_DELIVERY_ENABLED':'true'}),patch('app.mail_policy.send',side_effect=RuntimeError('secret failure detail')):
            status,body,_=self.http('/api/inquiries',inquiry());self.assertEqual(status,200);self.assertTrue(json.loads(body)['saved']);self.assertEqual(json.loads(body)['email_notification_status'],'failed');self.assertNotIn('secret',body.decode())
        row=mail_policy.inbox()['notifications'][0];self.assertNotIn('secret',row['error_message'])

    def test_recipient_update_requires_admin_and_read_counter(self):
        self.assertEqual(self.http('/api/admin/notifications/config',{'email':'owner@example.invalid'})[0],401)
        cookie=self.admin_cookie();self.assertEqual(self.http('/api/admin/notifications/config',{'email':'owner@example.invalid'},cookie=cookie)[0],200)
        self.assertEqual(mail_policy.admin_recipient(),'owner@example.invalid')
        intake.submit(inquiry());row=mail_policy.inbox()['notifications'][0]
        self.assertEqual(self.http('/api/admin/notifications/read',{'id':row['id']},cookie=cookie)[0],200)
        self.assertEqual(mail_policy.inbox()['unread'],0)

    def test_grounded_candidates_saved_but_unsupported_urls_dropped(self):
        candidate={'company_name':'SYNTHETIC Test Company','country':'Greece','city_region':'Test','website_url':'https://example.com/company','source_urls':['https://example.com/company'],'specialties_and_capabilities':['Synthetic test capability'],'certifications':[],'fit_score':72,'ai_rationale':'Synthetic test evidence only.'}
        result={'status':'searched','text':'```json\n'+json.dumps({'leads':[candidate,{**candidate,'company_name':'UNSUPPORTED','website_url':'https://unsupported.example.org'}]})+'\n```','sources':['https://example.com/company']}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic'}),patch('app.ai_providers.grounded',return_value=result):
            status,body,_=self.http('/api/leads/find',{'query':'synthetic brackets','geography':'','lead_type':'buyer_lead'});self.assertEqual(status,200);data=json.loads(body);self.assertEqual(len(data['external_leads']),1)
        self.assertEqual(data['external_leads'][0]['verification_status'],'source_backed_unverified')
        self.assertEqual(len(operations.lead_rows()['leads']),1)
        self.assertEqual(self.http('/api/admin/leads')[0],401)

    def test_no_citations_never_fabricates_a_lead(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic'}),patch('app.ai_providers.grounded',return_value={'status':'searched','text':json.dumps({'leads':[{'company_name':'Unsupported Company','website_url':'https://example.com'}]}),'sources':[]}):
            result=discovery.find_leads({'query':'synthetic request','geography':''})
        self.assertEqual(result['external_leads'],[])
        self.assertEqual(operations.lead_rows()['leads'],[])

    def test_enrichment_is_reviewable_and_not_automatically_verified(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic'}),patch('app.agent.provider_request',return_value={'content':'```json\n'+json.dumps({'summary':'Synthetic improved capability summary.','keywords':['machining'],'suggested_checks':['Ask whether ISO 9001 evidence exists.'],'buyer_match_preview':'Possible sector, not an actual buyer.'})+'\n```'}):
            status,body,_=self.http('/api/supplier/enhance',{'summary':'Synthetic machining capabilities for a test.'})
            self.assertEqual(status,200);self.assertIn('not evidence',json.loads(body)['notice'])
        self.assertEqual(market.listings()['total'],0)

    def test_profile_edit_verification_feature_and_guarded_delete(self):
        result,_=market.register(application(),immediate=True);identifier=result['supplier_id'];cookie=self.admin_cookie()
        self.assertEqual(self.http('/api/admin/suppliers/action',{'id':identifier,'action':'feature','featured':True},cookie=cookie)[0],200)
        self.assertEqual(self.http('/api/admin/suppliers/action',{'id':identifier,'action':'verify','evidence':'Synthetic evidence note; no certification asserted.'},cookie=cookie)[0],200)
        self.assertEqual(operations.supplier_rows()['suppliers'][0]['status'],'reviewed')
        self.assertEqual(self.http('/api/admin/suppliers/action',{'id':identifier,'action':'edit','profile':{'website':'example.com'}},cookie=cookie)[0],200)
        self.assertEqual(self.http('/api/admin/delete',{'id':identifier,'kind':'supplier','confirm':identifier},cookie=cookie)[0],403)
        with patch.dict(os.environ,{'RIGHTS_ERASURE_APPROVED':'true'}):self.assertEqual(self.http('/api/admin/delete',{'id':identifier,'kind':'supplier','confirm':identifier},cookie=cookie)[0],200)
        self.assertEqual(operations.supplier_rows()['suppliers'],[])
        self.assertEqual(mail_policy.inbox()['notifications'],[])

    def test_supplier_updates_only_own_profile_and_logs_notice(self):
        first,_=market.register(application(),immediate=True)
        second,_=market.register(application('second-owner@example.invalid'),immediate=True)
        cookie='stratevo_session='+first['_session']
        self.assertEqual(self.http('/api/marketplace/profile',{'id':second['supplier_id'],'profile':{'website':'example.com'}},cookie=cookie)[0],200)
        self.assertEqual(market.mine(first['_session'])['profile']['website'],'https://example.com')
        self.assertEqual(market.mine(second['_session'])['profile']['website'],'')
        self.assertTrue(any(':update:' in row['entity_id'] for row in mail_policy.inbox()['notifications']))

    def test_unknown_browser_cache_is_not_blindly_imported(self):
        self.assertEqual(self.http('/api/suppliers/sync',{'records':[{'email':'someone@example.invalid'}]})[0],409)
        self.assertEqual(market.listings()['total'],0)

class MailTransportTests(unittest.TestCase):
    def test_resend_and_sendgrid_real_request_contracts(self):
        for key,host in [('RESEND_API_KEY','api.resend.com'),('SENDGRID_API_KEY','api.sendgrid.com')]:
            with patch.dict(os.environ,{key:'synthetic','MAIL_FROM':'sender@example.invalid'},clear=True),patch('app.mail_policy.urllib.request.build_opener') as opener:
                response=MagicMock();response.__enter__.return_value=response;response.status=202;opener.return_value.open.return_value=response
                mail_policy.send('owner@example.invalid','Test','<unsafe>','test-message')
                req=opener.return_value.open.call_args.args[0];self.assertIn(host,req.full_url);self.assertIn(b'&lt;unsafe&gt;',req.data);self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],8)

    def test_smtp_ssl_and_starttls(self):
        for port in ('465','587'):
            with patch.dict(os.environ,{'SMTP_HOST':'smtp.example.invalid','SMTP_USER':'sender@example.invalid','SMTP_PASSWORD':'synthetic','SMTP_PORT':port},clear=True),patch('app.mail_policy.smtplib.SMTP') as plain,patch('app.mail_policy.smtplib.SMTP_SSL') as secure:
                mail_policy.send('owner@example.invalid','Test','Text','fixture')
                smtp=(secure if port=='465' else plain).return_value.__enter__.return_value
                smtp.login.assert_called_once();smtp.send_message.assert_called_once()
                if port=='587':smtp.starttls.assert_called_once()
                else:plain.assert_not_called()

    def test_webhook_never_receives_supplier_login_tokens(self):
        with patch.dict(os.environ,{'NOTIFICATION_WEBHOOK_URL':'https://hooks.slack.com/services/synthetic'},clear=True),patch('app.mail_policy.urllib.request.build_opener') as opener:
            with self.assertRaises(s.WorkflowError):mail_policy.send('owner@example.invalid','Login','Sensitive token','id',authentication=True)
            opener.assert_not_called()

class AdminAliasTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.MarketplaceTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.MarketplaceTests.tearDownClass.__func__)
    setUp=fixtures.MarketplaceTests.setUp
    http=fixtures.MarketplaceTests.http

    def test_alias_login_requires_mfa_in_production_and_rotates(self):
        import base64
        seed=base64.b32encode(b'synthetic-owner-auth-seed').decode()
        secret='synthetic-admin-secret-not-a-real-key'
        with patch.dict(os.environ,{'ADMIN_TOKEN':secret,'ADMIN_ACCOUNTS_JSON':'','ADMIN_TOTP_SECRET':seed}):
            result,session=s.admin_login({'username':'owner','password':secret,'otp':admin_auth.code(seed,s.now()//30)})
            self.assertEqual(s.authenticate(session,'admin')['actor'],'owner')
            with patch.dict(os.environ,{'ADMIN_TOKEN':'rotated-synthetic-secret-value-only'}):
                with self.assertRaises(s.WorkflowError):s.authenticate(session,'admin')
        with patch.dict(os.environ,{'APP_ENV':'production','ADMIN_TOKEN':secret,'ADMIN_ACCOUNTS_JSON':'','ADMIN_TOTP_SECRET':''}):
            with self.assertRaises(s.WorkflowError):admin_auth.accounts()

    def test_no_default_admin_access_and_setup_is_secret_free(self):
        status,body,_=self.http('/api/admin/setup');self.assertEqual(status,200);self.assertNotIn('pbkdf2',body.decode())
        self.assertEqual(self.http('/api/admin/suppliers')[0],401)

    def test_exact_registration_retry_does_not_call_ai_twice(self):
        payload=application(submission_key='synthetic-registry-retry-key-1234567890')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic'}),patch('app.discovery.find_leads',return_value={'status':'searched','external_leads':[]}) as find:
            self.assertEqual(self.http('/api/suppliers',payload)[0],200)
            self.assertEqual(self.http('/api/suppliers',payload)[0],200)
            self.assertEqual(find.call_count,1)
