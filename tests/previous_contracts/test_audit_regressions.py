import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import agent, catalog, matching
from app.knowledge import context_for, reference_document
from app.privacy import safe_answer
from app.server import Handler


class AuditRegressionTests(unittest.TestCase):
    def test_long_assistant_answer_can_be_followed_up(self):
        history=[{'role':'user','content':'Explain sourcing'},{'role':'assistant','content':'a'*5000},{'role':'user','content':'Explain that more simply'}]
        self.assertEqual(len(agent.validate_messages(history)),3)

    def test_long_user_and_total_context_still_bounded(self):
        with self.assertRaises(ValueError):agent.validate_messages([{'role':'user','content':'a'*4001}])
        history=[]
        for _ in range(4):history += [{'role':'user','content':'x'},{'role':'assistant','content':'a'*16000}]
        history += [{'role':'user','content':'more'}]
        with self.assertRaises(ValueError):agent.validate_messages(history)

    def test_bad_url_fails_closed(self):
        self.assertIn('remain private',safe_answer('Try https://[malformed for more information'))

    def test_origin_scheme_and_cross_site_metadata(self):
        handler=object.__new__(Handler)
        for origin in ['ftp://example.invalid','https://user@example.invalid','null','https://example.invalid/path','https://evil.invalid']:
            handler.headers={'Host':'example.invalid','Origin':origin}
            self.assertFalse(handler.origin_allowed(),origin)
        handler.headers={'Host':'example.invalid','Sec-Fetch-Site':'cross-site'}
        self.assertFalse(handler.origin_allowed())
        handler.headers={'Host':'example.invalid','Origin':'https://example.invalid'}
        self.assertTrue(handler.origin_allowed())
        with patch.dict(os.environ,{'PUBLIC_BASE_URL':'https://example.invalid'}):
            handler.headers={'Host':'example.invalid','Origin':'http://example.invalid'}
            self.assertFalse(handler.origin_allowed())

    def test_unit_aliases_do_not_convert_packages(self):
        for alias in ['PCS',' pc ','pieces','tmx','τεμάχια']:
            self.assertEqual(matching.unit_name(alias),'pieces')
        self.assertNotEqual(matching.unit_name('cartons'),matching.unit_name('pieces'))
        self.assertNotEqual(matching.unit_name('sets'),matching.unit_name('pieces'))

    def test_invalid_currency_type_is_validation_error(self):
        req={'product':'boxes','volume':10,'unit':'pieces','location':'any','certifications':[],'target_price':5,'currency':None}
        with self.assertRaises(ValueError):matching.validate(req)

    def test_import_rejects_boolean_moq_or_lead_time_atomically(self):
        catalog.PRIVATE.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=catalog.PRIVATE) as tmp:
            path=Path(tmp)/'test.json';db=Path(tmp)/'test.sqlite3'
            for bad in [{'advertised_moq':{'quantity':True,'unit':'pcs'}},{'matrix':{'lead_time_days':True}},{'matrix':{'location':42}}]:
                path.write_text(json.dumps({'records':[{'source_row_id':'990-1','description_summary':'TEST ONLY',**bad}]}))
                with self.assertRaises(ValueError):catalog.import_json(path,db)
                self.assertEqual(catalog.count(db),0)

    def test_context_is_curated_relevant_and_bounded(self):
        messages=[{'role':'user','content':'yo pls need 2k pcs kraft boxes, idk certs, ddp asap'}]
        context=context_for(messages)
        self.assertIn('Greeklish',context)
        self.assertIn('2,000',context)
        self.assertIn('not a technical specification',context)
        self.assertIn('LOGISTICS / INCOTERMS',context)
        self.assertLess(len(context),16000)
        self.assertIn('FOOD / INGREDIENTS',reference_document())

    @patch.dict(os.environ,{'AI_API_KEY':'TEST ONLY','AI_MODEL':'test','ONLINE_DISCOVERY_ENABLED':'false'})
    def test_runtime_no_browsing_context_and_slang_are_injected(self):
        def provider(messages):
            self.assertIn('ONLINE DISCOVERY: disabled',messages[0]['content'])
            self.assertIn('Greek / Greeklish',messages[0]['content'])
            return {'content':'What product do you need?'}
        self.assertIn('product',agent.reply([{'role':'user','content':'yo need a supplier asap'}],provider)['message'])

    @patch.dict(os.environ,{'AI_API_KEY':' TEST ONLY ','AI_MODEL':' test ','AI_BASE_URL':' https://generativelanguage.googleapis.com/v1beta/openai/ ','AI_MAX_OUTPUT_TOKENS':'2048','ONLINE_DISCOVERY_ENABLED':'false'})
    def test_gemini_compatible_transport_and_truncation(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'OK'}}]}).encode()
        with patch('app.agent.urllib.request.build_opener') as build:
            build.return_value.open.return_value=Response()
            self.assertEqual(agent.provider_request([{'role':'user','content':'hi'}])['content'],'OK')
            request=build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions')
            data=json.loads(request.data)
            self.assertEqual(data['model'],'test')
            self.assertEqual(data['max_tokens'],2048)
            self.assertEqual(len(data['tools']),1)
        class Truncated(Response):
            def read(self,limit):return json.dumps({'choices':[{'finish_reason':'length','message':{'content':'partial'}}]}).encode()
        with patch('app.agent.urllib.request.build_opener') as build:
            build.return_value.open.return_value=Truncated()
            with self.assertRaises(ValueError):agent.provider_request([{'role':'user','content':'hi'}])

    def test_endpoint_must_be_base_not_completion_url(self):
        with patch.dict(os.environ,{'AI_BASE_URL':'https://example.invalid/v1/chat/completions'}):
            with self.assertRaises(ValueError):agent.configuration()

if __name__=='__main__':unittest.main()
