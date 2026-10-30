// Full local audit. External provider replies are mocked, not a live-AI certification.
const {chromium:playwright}=require('../private/browser/node_modules/playwright');
const {default:AxeBuilder}=require('../private/browser/node_modules/@axe-core/playwright');
const fs=require('node:fs'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
fs.mkdirSync('private/audit-20261012',{recursive:true});
const base='http://127.0.0.1:8002',email=`audit-${Date.now()}@example.invalid`;
function saved(){return JSON.parse(execFileSync('python3',['-c',`import sqlite3,json,sys
c=sqlite3.connect('private/browser-test.sqlite3');c.row_factory=sqlite3.Row
rows=[dict(r) for r in c.execute('SELECT * FROM customer_inquiries') if json.loads(r['payload'])['email']==sys.argv[1]]
for r in rows:r['payload']=json.loads(r['payload'])
print(json.dumps(rows))`,email],{encoding:'utf8'}));}
(async()=>{
 const {default:chromium,inflate,setupLambdaEnvironment}=await import('../private/browser/node_modules/@sparticuz/chromium/build/index.js');await inflate(require('node:path').resolve('private/browser/node_modules/@sparticuz/chromium/bin/al2023.tar.br'));setupLambdaEnvironment(require('node:os').tmpdir()+'/al2023/lib');
 const browser=await playwright.launch({executablePath:await chromium.executablePath(),args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 try{
 let context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});let page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/ai?category=packaging');assert.match(await page.locator('#question').inputValue(),/packaging/);await page.goto(base+'/ai');
 let calls=0,captured=[];
 await page.route('**/api/chat',async route=>{calls++;captured.push(route.request().postDataJSON());if(calls===1)return route.fulfill({status:502,contentType:'application/json',body:JSON.stringify({error:'TEST ONLY transient provider failure'})});return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({mode:'model',message:'TEST ONLY: What dimensions, material and print requirements do you need? <img src=x onerror=alert(1)>',references:[]})});});
 await page.locator('#send').click();assert.equal(calls,0);
 const prompt='I want to source custom packaging from China. My target quantity is 500 units. What information do you need from me to evaluate suitable suppliers?';
 await page.locator('#question').fill(prompt);await page.locator('#question').press('Enter');await page.locator('#retry-chat').waitFor();await page.locator('#retry-chat').click();await page.locator('#messages').getByText('TEST ONLY: What dimensions',{exact:false}).waitFor();assert.equal(await page.locator('#messages img').count(),0);assert.equal(await page.locator('.message.user').count(),1);assert.equal(captured[0].messages[0].content,prompt);
 await page.locator('#question').fill('Recycled cardboard, private label, delivered to Greece in three months.');await page.locator('#question').press('Enter');await page.locator('#send').waitFor({state:'visible'});await page.waitForFunction(()=>!document.getElementById('send').disabled);assert.equal(captured[2].messages.length,3);
 await page.locator('#ai-inquiry').click();await page.waitForURL('**/inquiry?from=ai');assert.match(await page.locator('#lead-requirements').inputValue(),/500 units/);assert.doesNotMatch(await page.locator('#lead-requirements').inputValue(),/TEST ONLY/);assert.equal(await page.evaluate(()=>sessionStorage.getItem('stratevo-inquiry-draft')),null);
 console.log('PASS mobile AI empty input, transient error/retry, no duplicate user bubble, safe literal output, follow-up history, user-only inquiry handoff (provider mocked)');
 await page.locator('#lead-product').fill('Custom printed packaging');await page.locator('#lead-quantity').fill('500 boxes');await page.locator('#lead-destination').fill('Greece');await page.locator('#lead-name').fill('TEST Buyer');await page.locator('#lead-email').fill(email);await page.locator('[name=consent]').check();
 let leadCalls=0;
 await page.route('**/api/inquiries',async route=>{leadCalls++;if(leadCalls===1){const response=await route.fetch();assert.equal(response.status(),200);return route.abort('failed');}return route.continue();});
 await page.getByRole('button',{name:'Send sourcing inquiry',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#inquiry-form button[type=submit]').disabled);assert.equal(saved().length,1);assert.equal(await page.locator('#inquiry-success').isVisible(),false);
 await page.locator('#lead-product').fill('Edited uncertain attempt');await page.getByRole('button',{name:'Send sourcing inquiry',exact:true}).click();await page.locator('#inquiry-restore').waitFor();await page.locator('#inquiry-restore').click();assert.equal(await page.locator('#lead-product').inputValue(),'Custom printed packaging');await page.getByRole('button',{name:'Send sourcing inquiry',exact:true}).click();await page.locator('#inquiry-success').waitFor();assert.equal(saved().length,1);const id=saved()[0].id;assert.equal(saved()[0].payload.marketing_consent,false);assert.equal(saved()[0].payload.source,'ai');
 const jobs=execFileSync('python3',['-c',`import sqlite3,sys
c=sqlite3.connect('private/browser-test.sqlite3');print(c.execute("SELECT COUNT(*) FROM notification_jobs j JOIN outbox o ON o.id=j.outbox_id WHERE j.entity_type='customer' AND j.entity_id=? AND o.recipient='owner@example.invalid'",(sys.argv[1],)).fetchone()[0])`,id],{encoding:'utf8'}).trim();assert.equal(jobs,'1');
 assert.equal((await context.request.get(base+'/api/admin/inquiries')).status(),401);
 console.log('PASS genuine local inquiry save, response-loss recovery, exact-once record/outbox intent, no marketing and anonymous inbox denial; SMTP delivery not tested');
 await page.goto(base+'/admin');const config=JSON.parse(fs.readFileSync('private/browser-config.json'));await page.locator('#admin-password').fill(config.TEST_ADMIN_PASSWORD);await page.getByRole('button',{name:'Sign in securely'}).click();await page.locator('#load-inquiries').waitFor();await page.locator('#load-inquiries').click();const record=page.locator('#customer-'+id);await record.waitFor();await record.locator('select').selectOption('qualified');await record.getByRole('button',{name:'Save inquiry status'}).click();await page.getByText('Inquiry status updated.',{exact:true}).waitFor();await page.locator('#inquiry-filter').selectOption('qualified');await record.waitFor();assert.equal(saved()[0].status,'qualified');
 await page.locator('#retry-owner-mail').click();await page.locator('#notification-summary').getByText('owner notifications requeued',{exact:false}).waitFor();
 console.log('PASS private manager inbox, source/details visibility, status update/filtering and owner-notification retry action');
 // Verify the actual application abort timer by advancing the browser clock, not waiting a minute.
 await page.goto(base+'/ai');await page.unroute('**/api/chat');await page.clock.install();await page.route('**/api/chat',()=>{});await page.locator('#question').fill('Timeout test only');await page.locator('#send').click();await page.clock.fastForward(61000);await page.locator('#messages').getByText('The service took too long',{exact:false}).waitFor();assert.equal(await page.locator('#send').isDisabled(),false);await page.locator('#clear').click();assert.equal(await page.locator('#question').inputValue(),'');await page.unroute('**/api/chat');
 console.log('PASS AI abort timeout and recovered input/new-chat state (clock advanced)');
 const state=await context.storageState();await context.close();context=await browser.newContext({storageState:state,reducedMotion:'reduce'});page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const routes=['/','/ai','/supplier','/marketplace','/inquiry','/privacy','/terms','/admin','/access','/portal','/supplier/account'];
 const axe=[];const links=new Set();const timings=[];
 for(const route of routes){await page.goto(base+route);await page.locator('h1').waitFor();assert.equal(await page.locator('h1').count(),1);const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();axe.push({route,violations:result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
  for(const href of await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href'))))if(href.startsWith('/'))links.add(href.split('#')[0]);
  timings.push({route,...await page.evaluate(()=>{const n=performance.getEntriesByType('navigation')[0];return {domContentLoadedMs:Math.round(n.domContentLoadedEventEnd),transferBytes:n.transferSize};})});
 }
 for(const link of links){const response=await context.request.get(base+link);assert.equal(response.status(),200,link);}
 for(const width of [320,390,768,1440,1920]){await page.setViewportSize({width,height:960});for(const route of routes){await page.goto(base+route);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,route+' '+width);}}
 await page.goto(base+'/inquiry');await page.reload();await page.goto(base+'/privacy');await page.goBack();assert.equal(new URL(page.url()).pathname,'/inquiry');await page.goForward();assert.equal(new URL(page.url()).pathname,'/privacy');
 fs.writeFileSync('private/audit-20261012/accessibility.json',JSON.stringify(axe,null,2));fs.writeFileSync('private/audit-20261012/local-timings.json',JSON.stringify(timings,null,2));
 const violations=axe.flatMap(r=>r.violations.map(v=>({route:r.route,...v})));console.log('Accessibility findings:',JSON.stringify(violations));assert.deepEqual(violations,[]);
 assert.deepEqual(errors,[]);console.log(`PASS ${routes.length} routes, ${links.size} internal link targets, 320/390/768/1440/1920 layouts, direct refresh/back/forward and zero JS exceptions`);
 await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/inquiry');await page.screenshot({path:'private/audit-20261012/inquiry-desktop.png',fullPage:true});
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
