// Requires playwright and @sparticuz/chromium installed in private/browser.
// Run only against the isolated test database/server configured by the setup instructions.
const { chromium: playwright } = require('../private/browser/node_modules/playwright');

const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const base='http://127.0.0.1:8002';
const testEmail=`browser-${Date.now()}@example.invalid`;
function emailToken(email) {
 return execFileSync('python3',['-c', `import sqlite3,sys
c=sqlite3.connect('private/browser-test.sqlite3')
rows=c.execute('SELECT body FROM outbox WHERE recipient=? ORDER BY rowid DESC',(sys.argv[1],)).fetchall()
print(next(r[0].split('#token=')[1].split()[0] for r in rows if '#token=' in r[0]))`,email],{encoding:'utf8'}).trim();
}
(async()=>{
 const { default: chromium } = await import('../private/browser/node_modules/@sparticuz/chromium/build/index.js');
 const browser=await playwright.launch({executablePath:await chromium.executablePath(),args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'],headless:true});
 const errors=[];
 const user=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await user.newPage();page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base);await page.getByRole('heading',{name:'find a stronger route from brief to supply.'}).waitFor();
 await page.screenshot({path:'private/home-desktop.png',fullPage:true});
 console.log('PASS desktop homepage');
 const unauthorized=await user.request.get(base+'/api/admin/applications');assert.equal(unauthorized.status(),401);
 await page.goto(base+'/supplier');
 await page.getByLabel('Registered company name').fill('Browser Test Manufacturing');
 await page.getByLabel('Contact person').fill('Test Applicant');
 await page.getByLabel('Business email',{exact:true}).fill(testEmail);
 await page.getByLabel('Country / region of registration').fill('Greece');
 await page.getByLabel('Main product category').fill('Lighting');
 assert.match(await page.getByLabel('WhatsApp (optional if WeChat provided)',{exact:true}).evaluate(el=>el.validationMessage),/WhatsApp or WeChat/);
 await page.getByLabel('WeChat (optional if WhatsApp provided)',{exact:true}).fill('test-wechat');
 assert.equal(await page.getByLabel('WhatsApp (optional if WeChat provided)',{exact:true}).evaluate(el=>el.validationMessage),'');
 await page.getByLabel('WeChat (optional if WhatsApp provided)',{exact:true}).fill('');
 await page.getByLabel('WhatsApp (optional if WeChat provided)',{exact:true}).fill('+300000000000');
 await page.getByLabel('Products and capabilities').fill('Browser test only: lighting research and product manufacturing. No real supplier data.');
 await page.getByLabel('Business registration / license number').fill('BROWSER-TEST-ONLY');
 await page.getByLabel('Business license PDF').setInputFiles({name:'bad.txt',mimeType:'text/plain',buffer:Buffer.from('test-only invalid document')});
 await page.locator('#license-file-status').filter({hasText:'Choose a PDF document'}).waitFor();
 await page.getByLabel('Business license PDF').setInputFiles({name:'test-license.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\n% browser fixture only\n%%EOF')});
 await page.getByRole('checkbox').check();
 await page.getByRole('button',{name:'Submit for email verification'}).click();
 await page.locator('#application-status').filter({hasText:'verification email will be sent'}).waitFor();
 await page.locator('#application-success').waitFor({state:'visible'});
 assert.equal(await page.locator('#application-form').isVisible(),false);
 console.log('PASS supplier contact/document validation, application submission and next-step confirmation');
 await page.goto(base+'/access#token='+emailToken(testEmail));
 assert.equal(new URL(page.url()).hash,'');
 await page.getByRole('button',{name:'Continue securely'}).click();
 await page.locator('#consume-status').filter({hasText:'Email verified'}).waitFor();
 console.log('PASS explicit email verification (token extracted from test-only outbox; SMTP not exercised)');
 const admin=await browser.newContext({viewport:{width:1440,height:1000}}); const manager=await admin.newPage();manager.on('pageerror',error=>errors.push(error.message));
 await manager.goto(base+'/admin');await manager.getByLabel('Manager password').fill('browser-test-manager-password');
 await manager.getByRole('button',{name:'Sign in securely'}).click();
 await manager.locator('#admin-workspace').waitFor({state:'visible'});
 const card=manager.locator('.application-card').filter({hasText:testEmail});await card.waitFor();
 await manager.screenshot({path:'private/admin-desktop.png',fullPage:true});
 const download=await admin.request.get(await card.getByText('Download private license PDF').getAttribute('href').then(path=>base+path));
 assert.equal(download.status(),200);assert.match(download.headers()['content-disposition'],/attachment/);
 manager.on('dialog',dialog=>dialog.accept());
 await card.getByRole('button',{name:'Approve & queue access email'}).click();
 await manager.locator('#admin-status').filter({hasText:'Application approved'}).waitFor();
 await manager.getByLabel('Application status',{exact:true}).selectOption('approved');
 await manager.locator('.application-card').filter({hasText:testEmail}).waitFor();
 await manager.getByRole('button',{name:'Load private research'}).click();
 await manager.locator('#research-status').filter({hasText:'imported research rows'}).waitFor();
 assert.equal((await admin.request.get(base+'/api/agent/status')).status(),200);
 console.log('PASS manager login, private license download, approval, queue filtering and private research access');
 await manager.getByRole('button',{name:'Test AI connection'}).click();
 await manager.locator('#connection-test-status').filter({hasText:'Set AI_API_KEY'}).waitFor();
 await manager.locator('.application-card').filter({hasText:testEmail}).getByRole('link',{name:'Open supplier profile'}).click();
 await manager.locator('#profile').filter({hasText:'Browser Test Manufacturing'}).waitFor();
 assert.equal(await manager.getByRole('button',{name:'Sign out',exact:true}).isVisible(),false);
 console.log('PASS manager-only profile and missing-key connection diagnostics');

 await manager.goto(base+'/ai');
 await manager.locator('.qualification summary').click();
 await manager.getByLabel('1 / Product keywords (English index)').fill('Christmas tree');
 await manager.getByLabel('2 / Target volume').fill('100');
 await manager.getByLabel('Volume unit',{exact:true}).fill('pieces');
 await manager.getByLabel('3 / Ideal supplier location').fill('any');
 await manager.getByLabel('4 / Required certifications').fill('none');
 await manager.getByRole('button',{name:'Check supplied research'}).click();
 await manager.locator('#match-status').filter({hasText:'human needs to verify'}).waitFor();
 assert.equal(await manager.locator('#results .result').count(),0);
 const qualification = await admin.request.post(base+'/api/catalog/match',{data:{product:'tree'}});
 assert.equal((await qualification.json()).status,'needs_qualification');
 console.log('PASS qualified matching form, honest no-match handoff and incomplete-brief gate');
 await manager.getByLabel('Research source').selectOption('online');
 await manager.getByRole('button',{name:'Check supplied research'}).click();
 await manager.locator('#match-status').filter({hasText:'No online search was performed'}).waitFor();
 await manager.getByRole('button',{name:'New chat'}).click();
 assert.equal(await manager.locator('#match-status').textContent(),'');
 assert.match(await manager.locator('#results').textContent(),/cleared/);
 console.log('PASS disabled online-search disclosure and stale research reset');
 await manager.route('**/api/chat',route=>route.fulfill({status:502,contentType:'application/json',body:JSON.stringify({error:'The AI provider is rate-limited or out of quota.'})}));
 await manager.getByRole('button',{name:'Prepare an RFQ',exact:true}).click();
 await manager.getByRole('button',{name:'Send message'}).click();
 await manager.locator('#messages').filter({hasText:'rate-limited'}).waitFor();
 assert.equal(await manager.locator('#question').inputValue(),'What should I include in an RFQ?');
 assert.equal(await manager.locator('#send').isEnabled(),true);
 assert.equal(await manager.locator('#chat-progress').textContent(),'');
 await manager.unroute('**/api/chat');
 console.log('PASS mocked AI provider error, retained question and reset loading state');


 await page.goto(base+'/access#token='+emailToken(testEmail));
 await page.getByRole('button',{name:'Continue securely'}).click();
 await page.waitForURL('**/portal');
 await page.locator('#profile').filter({hasText:'Browser Test Manufacturing'}).waitFor();
 assert.equal((await user.request.get(base+'/api/admin/applications')).status(),403);
 console.log('PASS approved supplier login and admin-role denial');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/supplier#sign-in');
 assert.equal((await user.request.get(base+'/api/supplier/me')).status(),401);
 console.log('PASS supplier logout revokes server session');
 const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const phone=await mobile.newPage();phone.on('pageerror',error=>errors.push(error.message));
 for(const route of ['/','/supplier','/admin','/access','/portal','/ai']){
   await phone.goto(base+route);await phone.waitForLoadState('networkidle');
   assert.ok(await phone.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`Overflow on ${route}`);
   if(route==='/')await phone.screenshot({path:'private/home-mobile.png',fullPage:true});
   if(route==='/supplier')await phone.screenshot({path:'private/supplier-mobile.png',fullPage:true});
 }
 console.log('PASS six routes at 390px mobile viewport; no horizontal overflow');
 await phone.goto(base+'/');await phone.getByRole('button',{name:'Menu'}).click();
 await phone.getByRole('navigation').getByRole('link',{name:'Are you a supplier?',exact:true}).click();
 await phone.waitForURL('**/supplier');
 for(const width of [320,768,1568]){
   await phone.setViewportSize({width,height:900});
   for(const route of ['/','/supplier','/ai']){await phone.goto(base+route);await phone.evaluate(()=>document.fonts.ready);assert.ok(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow ${width} ${route}`);}
 }
 await phone.emulateMedia({reducedMotion:'reduce'});await phone.goto(base+'/');
 assert.equal(await phone.locator('#constellation').evaluate(el=>getComputedStyle(el).display),'none');
 console.log('PASS mobile supplier navigation, 320/768/1568px layouts and reduced-motion mode');
 assert.deepEqual(errors,[]);console.log('PASS no browser JavaScript errors');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
