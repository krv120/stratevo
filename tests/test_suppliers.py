import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import suppliers as s

PDF = base64.b64encode(b'%PDF-1.4\n% Test-only placeholder, not a real license\n%%EOF').decode()
DATA = dict(company='Test Manufacturing', contact='Example Person',email='supplier@example.invalid',country='Greece',category='Lighting',capabilities='Test-only lighting products and sample manufacturing capability.',whatsapp='+300000000000',wechat='',license_number='TEST-ONLY-123',license_pdf=PDF,consent=True)

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(dir=s.PRIVATE)
        self.db=patch.object(s,'DATABASE',Path(self.directory.name)/'suppliers.sqlite3');self.db.start()
        self.env=patch.dict(os.environ, {'DATABASE_URL':'','PUBLIC_BASE_URL':'https://example.invalid','ADMIN_PASSWORD_HASH':s.hash_password('test-manager-password-only'),'SMTP_HOST':''});self.env.start()
        s.initialize()
    def tearDown(self):
        self.env.stop();self.db.stop();self.directory.cleanup()
    def last_token(self):
        with s.database() as db: row=db.execute('SELECT body FROM outbox ORDER BY created_at DESC, id DESC').fetchall()
        return next(r['body'].split('#token=')[1].split()[0] for r in row if '#token=' in r['body'])
    def id(self):
        with s.database() as db: return db.execute('SELECT id FROM applications').fetchone()['id']
    def state(self):
        with s.database() as db: return db.execute('SELECT status FROM applications').fetchone()['status']
    def verified(self):
        s.apply(DATA); token=self.last_token(); result,_=s.consume({'token':token});self.assertEqual(result['status'],'pending')
    def test_apply_contact_requirement(self):
        with self.assertRaises(s.WorkflowError):s.apply({**DATA,'whatsapp':'','wechat':''})
        s.apply({**DATA,'whatsapp':'','wechat':'wechat-example'})
        self.assertEqual(self.state(),'pending_email')
    def test_pdf_validation(self):
        with self.assertRaises(s.WorkflowError):s.apply({**DATA,'license_pdf':base64.b64encode(b'<script>bad</script>').decode()})
    def test_consent_required(self):
        with self.assertRaises(s.WorkflowError):s.apply({**DATA,'consent':False})
    def test_duplicate_does_not_overwrite(self):
        first=s.apply(DATA);second=s.apply({**DATA,'company':'attacker replacement'})
        self.assertEqual(first,second)
        with s.database() as db:self.assertEqual(db.execute('SELECT company FROM applications').fetchone()['company'],DATA['company'])
    def test_email_verification_single_use(self):
        s.apply(DATA);token=self.last_token();s.consume({'token':token})
        with self.assertRaises(s.WorkflowError):s.consume({'token':token})
        self.assertEqual(self.state(),'pending')
    def test_expired_link(self):
        s.apply(DATA);token=self.last_token()
        with s.database() as db:db.execute('UPDATE tokens SET expires_at=0')
        with self.assertRaises(s.WorkflowError):s.consume({'token':token})
        self.assertEqual(self.state(),'pending_email')
    def test_cannot_approve_unverified(self):
        s.apply(DATA)
        with self.assertRaises(s.WorkflowError):s.review({'id':self.id(),'decision':'approved'})
    def test_full_approval_flow(self):
        self.verified()
        with s.database() as db:db.execute('DELETE FROM outbox')
        s.review({'id':self.id(),'decision':'approved'})
        result,token=s.consume({'token':self.last_token()})
        self.assertEqual(result['status'],'approved')
        identity=s.authenticate(token,'supplier')
        self.assertEqual(s.profile(identity)['application']['email'],DATA['email'])
        with self.assertRaises(s.WorkflowError):s.authenticate(token,'admin')
        s.logout(token)
        with self.assertRaises(s.WorkflowError):s.authenticate(token)
    def test_profile_available_immediately_on_approval(self):
        self.verified()
        with self.assertRaises(s.WorkflowError):s.approved_profile(self.id())
        result=s.review({'id':self.id(),'decision':'approved'})
        self.assertEqual(result['profile_url'],'/portal?application='+self.id())
        self.assertEqual(s.approved_profile(self.id())['application']['company'],DATA['company'])
        self.assertNotIn('license_pdf',s.approved_profile(self.id())['application'])

    def test_login_response_directs_supplier_to_own_page(self):
        self.verified()
        with s.database() as db:db.execute('DELETE FROM outbox')
        s.review({'id':self.id(),'decision':'approved'})
        result,token=s.consume({'token':self.last_token()})
        self.assertEqual(result['redirect'],'/portal')
        self.assertEqual(s.profile(s.authenticate(token,'supplier'))['application']['email'],DATA['email'])

    def test_rejection_does_not_grant_access(self):
        self.verified();s.review({'id':self.id(),'decision':'rejected','note':'Missing required capability evidence'})
        self.assertEqual(self.state(),'rejected')
        with s.database() as db:count=db.execute('SELECT COUNT(*) AS n FROM tokens').fetchone()['n']
        s.request_access({'email':DATA['email']})
        with s.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM tokens').fetchone()['n'],count)
    def test_review_race_conflict(self):
        self.verified();s.review({'id':self.id(),'decision':'approved'})
        with self.assertRaises(s.WorkflowError) as error:s.review({'id':self.id(),'decision':'rejected','note':'second decision'})
        self.assertEqual(error.exception.status,409)
    def test_admin_password_and_hash_only(self):
        self.assertNotIn('test-manager-password-only',os.environ['ADMIN_PASSWORD_HASH'])
        with self.assertRaises(s.WorkflowError):s.admin_login({'password':'wrong'})
        result,token=s.admin_login({'password':'test-manager-password-only'})
        self.assertEqual(s.authenticate(token,'admin')['role'],'admin')
        with s.database() as db:self.assertNotIn(token,str([dict(row) for row in db.execute('SELECT * FROM sessions').fetchall()]))
    def test_unknown_access_non_enumerating(self):
        a=s.request_access({'email':'unknown@example.invalid'})
        s.apply(DATA)
        b=s.request_access({'email':DATA['email']})
        self.assertEqual(a,b)
    def test_missing_smtp_keeps_outbox(self):
        s.apply(DATA)
        with self.assertRaises(s.WorkflowError):s.send_email_queue()
        self.assertEqual(s.applications()['queued_emails'],1)
    def test_license_not_in_list(self):
        s.apply(DATA)
        self.assertNotIn('license_pdf',s.applications()['applications'][0])
        self.assertTrue(s.license_document(self.id()).startswith(b'%PDF'))
    def test_bad_public_origin_fails_closed(self):
        with patch.dict(os.environ,{'PUBLIC_BASE_URL':'http://attacker.invalid'}):
            with self.assertRaises(s.WorkflowError):s.apply(DATA)
    def test_attempt_limit(self):
        for _ in range(3):s.rate_limit('test',3,60)
        with self.assertRaises(s.WorkflowError) as error:s.rate_limit('test',3,60)
        self.assertEqual(error.exception.status,429)

    def test_mail_success_clears_body(self):
        s.apply(DATA)
        with patch.dict(os.environ,{'SMTP_HOST':'mail.example.invalid','MAIL_FROM':'sender@example.invalid'}), patch('app.suppliers.smtplib.SMTP') as smtp:
            result=s.send_email_queue()
            self.assertEqual(result,{'sent':1,'failed':0})
            smtp.return_value.__enter__.return_value.starttls.assert_called_once()
            smtp.return_value.__enter__.return_value.send_message.assert_called_once()
        with s.database() as db:self.assertEqual(db.execute('SELECT body FROM outbox').fetchone()['body'],'')
    def test_mail_failure_preserves_queue(self):
        s.apply(DATA)
        with patch.dict(os.environ,{'SMTP_HOST':'mail.example.invalid','MAIL_FROM':'sender@example.invalid'}), patch('app.suppliers.smtplib.SMTP',side_effect=OSError('private provider detail')):
            self.assertEqual(s.send_email_queue(),{'sent':0,'failed':1})
        self.assertEqual(s.applications()['queued_emails'],1)
    def test_http_session_cookie_origin_and_manager_gate(self):
        import json, threading, urllib.request, urllib.error
        from http.server import ThreadingHTTPServer
        from app.server import Handler
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,data=None,cookie='',origin=None):
            headers={'Content-Type':'application/json','Cookie':cookie}
            if origin:headers['Origin']=origin
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
            try:response=urllib.request.urlopen(req)
            except urllib.error.HTTPError as error:response=error
            with response:return response.status,response.headers,response.read()
        try:
            self.assertEqual(request('/api/admin/connections')[0],401)
            self.assertEqual(request('/api/admin/check-connection',{'service':'ai'})[0],401)
            self.assertEqual(request('/api/admin/supplier-profile/fake')[0],401)
            self.assertEqual(request('/api/admin/research')[0],401)
            self.assertEqual(request('/api/admin/license/fake')[0],401)
            self.assertEqual(request('/api/admin/login',{'password':'test-manager-password-only'},origin='https://evil.invalid')[0],403)
            status,headers,_=request('/api/admin/login',{'password':'test-manager-password-only'})
            self.assertEqual(status,200)
            cookie=headers['Set-Cookie']
            self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=Lax',cookie)
            cookie=cookie.split(';')[0]
            self.assertEqual(request('/api/admin/applications',cookie=cookie)[0],200)
            self.assertEqual(request('/api/admin/research',cookie=cookie)[0],200)
            self.assertEqual(request('/api/supplier/me',cookie=cookie)[0],403)
            self.assertEqual(request('/api/agent/status',cookie=cookie)[0],200)
            self.assertEqual(request('/api/admin/connections',cookie=cookie)[0],200)
            self.verified()
            self.assertEqual(request('/api/admin/supplier-profile/'+self.id(),cookie=cookie)[0],404)
            s.review({'id':self.id(),'decision':'approved'})
            self.assertEqual(request('/api/admin/supplier-profile/'+self.id(),cookie=cookie)[0],200)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
