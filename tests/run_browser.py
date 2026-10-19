"""Run current browser journeys on real HTTPS Vercel adapter and isolated storage."""
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from api.index import handler
from vercel_rewrite import RewrittenHandler
from app import connections

Path('private/audit').mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir='private') as folder,ExitStack() as stack:
    folder=Path(folder)
    cert=folder/'certificate.pem';key=folder/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    password=secrets.token_urlsafe(24)
    config={**{k:os.environ[k] for k in ('PATH','HOME') if k in os.environ},'APP_ENV':'production','VERCEL':'1','VERCEL_ENV':'production','PUBLIC_ORIGIN_VERIFIED':'true','COOKIE_SECURE':'true','ADMIN_PASSWORD':password,'MAIL_DELIVERY_ENABLED':'false'}
    pg=None
    try:
        if '--postgres' in sys.argv:
            import pgserver
            pg=pgserver.get_server(folder/'postgres');config['POSTGRES_URL']=pg.get_uri()
        stack.enter_context(patch.dict(os.environ,config,clear=True))
        stack.enter_context(patch.object(connections,'RUNTIME_SQLITE',folder/'runtime.sqlite3'))
        server=ThreadingHTTPServer(('127.0.0.1',0),RewrittenHandler if '--rewrite' in sys.argv else handler)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key);server.socket=tls.wrap_socket(server.socket,server_side=True)
        base='https://127.0.0.1:'+str(server.server_port);os.environ['PUBLIC_BASE_URL']=base
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            env={**os.environ,'TEST_BASE':base,'TEST_ADMIN_PASSWORD':password,'TEST_STORAGE_MODE':'postgres' if pg else 'ephemeral_fallback','TEST_CAPTURE':'false' if pg else 'true'}
            subprocess.run(['node','tests/current_browser.cjs'],env=env,check=True,timeout=180)
        finally:server.shutdown();server.server_close();thread.join()
    finally:
        if pg:pg.cleanup()
