import json
import os
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch
from app import agent


class ReferenceUpdateTests(unittest.TestCase):
    def test_home_uses_reference_content_and_real_routes(self):
        home=Path('web/home.html').read_text()
        for phrase in ['find a stronger route','from brief to supply.','NON-CONTRACTING PREVIEW','THE BRIEF','Ask STRATEVO','/reference.css','/visual.js']:
            self.assertIn(phrase,home)
        self.assertNotIn('Find the right fit.',home)
        self.assertIn('href="/marketplace"',home)

    def test_supplier_sections_and_success_are_present(self):
        html=Path('web/supplier.html').read_text()
        self.assertEqual(html.count('<fieldset>'),2)
        for value in ['id="market-register-success"','id="market-license"','WhatsApp','not published or sent to the AI','id="market-register-status"','no manager approval']:
            self.assertIn(value,html)

    @patch.dict(os.environ,{'AI_API_KEY':'TEST ONLY','AI_MODEL':'gemini-2.5-flash','AI_BASE_URL':'https://generativelanguage.googleapis.com/v1beta/openai','AI_REASONING_EFFORT':''})
    def test_gemini_default_reasoning_budget_and_output_headroom(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]}'
        with patch.dict(os.environ):
            os.environ.pop('AI_MAX_OUTPUT_TOKENS',None)
            with patch('app.agent.urllib.request.build_opener') as opener:
                opener.return_value.open.return_value=Response()
                agent.provider_request([{'role':'user','content':'hello'}],tools=False)
                payload=json.loads(opener.return_value.open.call_args.args[0].data)
                self.assertEqual(payload['reasoning_effort'],'low')
                self.assertEqual(payload['max_tokens'],4096)
                self.assertNotIn('tools',payload)

    @patch.dict(os.environ,{'AI_API_KEY':'TEST ONLY','AI_MODEL':'test','AI_BASE_URL':'https://example.invalid/v1','AI_REASONING_EFFORT':''})
    def test_provider_http_errors_are_actionable_and_do_not_leak(self):
        for code,expected in [(400,'configuration'),(401,'authentication'),(403,'access_denied'),(404,'model_not_found'),(429,'provider_quota'),(500,'provider_unavailable')]:
            with self.subTest(code=code),patch('app.agent.urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect=urllib.error.HTTPError('https://example.invalid',code,'SECRET BODY',{},None)
                with self.assertRaises(agent.ProviderError) as caught:agent.provider_request([{'role':'user','content':'hello'}])
                self.assertEqual(caught.exception.code,expected)
                self.assertNotIn('SECRET',str(caught.exception))

    @patch.dict(os.environ,{'AI_API_KEY':'TEST ONLY','AI_MODEL':'test','AI_BASE_URL':'https://example.invalid/v1','AI_REASONING_EFFORT':''})
    def test_timeout_and_network_failures_are_distinct(self):
        for error,code in [(TimeoutError(),'provider_timeout'),(urllib.error.URLError('SECRET'), 'provider_network')]:
            with patch('app.agent.urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(agent.ProviderError) as caught:agent.provider_request([{'role':'user','content':'hi'}])
                self.assertEqual(caught.exception.code,code)
                self.assertNotIn('SECRET',str(caught.exception))

    @patch.dict(os.environ,{'AI_API_KEY':'TEST ONLY','AI_MODEL':'test','AI_BASE_URL':'https://example.invalid/v1','AI_REASONING_EFFORT':'invalid'})
    def test_invalid_reasoning_setting_does_not_call_provider(self):
        with patch('app.agent.urllib.request.build_opener') as opener:
            with self.assertRaises(agent.ProviderError):agent.provider_request([{'role':'user','content':'hi'}])
            opener.assert_not_called()

if __name__=='__main__':unittest.main()
