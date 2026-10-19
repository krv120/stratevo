import os
import unittest
from unittest.mock import patch
from app import connections


class ConnectionTests(unittest.TestCase):
    @patch.dict(os.environ,{'AI_API_KEY':'','AI_MODEL':'','BRAVE_SEARCH_API_KEY':''})
    def test_missing_config_does_not_call_provider(self):
        with patch('app.connections.suppliers.rate_limit'),patch('app.connections.agent.provider_request') as provider:
            self.assertFalse(connections.check('ai')['ok'])
            provider.assert_not_called()

    @patch.dict(os.environ,{'AI_API_KEY':'SECRET-KEY','AI_MODEL':'test','AI_BASE_URL':'https://example.invalid/v1'})
    def test_success_requires_response_and_does_not_echo_provider(self):
        with patch('app.connections.suppliers.rate_limit'),patch('app.connections.agent.provider_request',return_value={'content':'PRIVATE PROVIDER RESPONSE'}):
            result=connections.check('ai')
        self.assertTrue(result['ok'])
        self.assertNotIn('PRIVATE',str(result))
        self.assertNotIn('SECRET',str(connections.status()))

    @patch.dict(os.environ,{'AI_API_KEY':'SECRET-KEY','AI_MODEL':'test','AI_BASE_URL':'https://example.invalid/v1'})
    def test_failure_does_not_leak_error_body(self):
        with patch('app.connections.suppliers.rate_limit'),patch('app.connections.agent.provider_request',side_effect=RuntimeError('SECRET-KEY')):
            result=connections.check('ai')
        self.assertFalse(result['ok'])
        self.assertNotIn('SECRET',str(result))

    def test_search_check_reports_actual_result_status(self):
        with patch('app.connections.suppliers.rate_limit'),patch('app.connections.discovery.discover',return_value={'status':'search_unavailable','message':'Provider unavailable'}):
            self.assertFalse(connections.check('search')['ok'])

if __name__=='__main__':unittest.main()
