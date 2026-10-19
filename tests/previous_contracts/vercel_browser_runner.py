"""Run a browser against the real Vercel adapter, isolated storage and synthetic credentials.
Usage: PYTHONPATH=. .venv/bin/python tests/vercel_browser_runner.py [--postgres]
This emulates a worker; it is not a deployed Vercel/load-balancer certification.
"""
import base64
from contextlib import ExitStack
import json
import os
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from api.index import handler
from app import connections, suppliers, admin_auth

with tempfile.TemporaryDirectory(dir='private') as folder:
    pg=None
    certificate=Path(folder)/'certificate.pem';key=Path(folder)/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-keyout',str(key),'-out',str(certificate)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    config={'APP_ENV':'production','VERCEL':'1','VERCEL_ENV':'production',
            'PUBLIC_BASE_URL':'https://stratevo.online','PUBLIC_ORIGIN_VERIFIED':'true',
            'SMTP_HOST':'','MAIL_DELIVERY_ENABLED':'false'}
    if '--postgres' in sys.argv:
        import pgserver
        pg=pgserver.get_server(Path(folder)/'postgres')
        config['POSTGRES_URL']=pg.get_uri()
    if '--engine' in sys.argv:config.update(OPENAI_API_KEY='synthetic-test-only',RESEND_API_KEY='synthetic-test-only',MAIL_DELIVERY_ENABLED='true',MAIL_FROM='sender@example.invalid',ADMIN_NOTIFICATION_EMAIL='owner@example.invalid')
    password=secrets.token_urlsafe(24);seed=base64.b32encode(secrets.token_bytes(24)).decode()
    config['ADMIN_ACCOUNTS_JSON']=json.dumps([{'id':'fixture-admin','password_hash':suppliers.hash_password(password),'totp_secret':seed}])
    try:
        # Preserve PATH/HOME for browser dependencies, but remove all external provider/DB/mail config.
        with patch.dict(os.environ,{**{k:os.environ[k] for k in ('PATH','HOME') if k in os.environ},**config},clear=True),patch.object(connections,'RUNTIME_SQLITE',Path(folder)/'runtime.sqlite3'):
            server=ThreadingHTTPServer(('127.0.0.1',0),handler)
            tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(certificate,key)
            server.socket=tls.wrap_socket(server.socket,server_side=True)
            base='https://127.0.0.1:'+str(server.server_port)
            os.environ['PUBLIC_BASE_URL']=base
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                env={**os.environ,'TEST_BASE_URL':base,
                     'TEST_ADMIN_PASSWORD':password,'TEST_ADMIN_OTP':admin_auth.code(seed,suppliers.now()//30),
                     'TEST_STORAGE_MODE':'postgres' if pg else 'ephemeral_fallback'}
                with ExitStack() as stack:
                    if '--engine' in sys.argv:
                        candidate={'company_name':'SYNTHETIC Test Research Company','country':'Test country','city_region':'Test region','website_url':'https://example.com/','source_urls':['https://example.com/'],'specialties_and_capabilities':['Synthetic fixture only'],'certifications':[],'fit_score':60,'ai_rationale':'Synthetic test, not a real lead recommendation.'}
                        stack.enter_context(patch('app.ai_providers.grounded',return_value={'status':'searched','text':json.dumps({'leads':[candidate]}),'sources':['https://example.com/']}))
                        stack.enter_context(patch('app.agent.provider_request',return_value={'content':json.dumps({'summary':'SYNTHETIC improved machining capability summary for testing only.','keywords':['machining'],'suggested_checks':['Request certification scope evidence.'],'buyer_match_preview':'Synthetic buyer sector; not confirmed demand.'})}))
                        stack.enter_context(patch('app.mail_policy.send',return_value='synthetic_test_acceptance'))
                    subprocess.run(['node','tests/engine_browser.cjs' if '--engine' in sys.argv else 'tests/vercel_browser.cjs'],env=env,check=True,timeout=120)
            finally:server.shutdown();server.server_close();thread.join()
    finally:
        if pg:pg.cleanup()
