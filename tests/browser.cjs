// Run against the isolated SQLite test server (port 8002), never the public preview.
// Email tokens are read from its test outbox; AI responses are explicitly mocked.
const { chromium: playwright } = require('../private/browser/node_modules/playwright');
const { execFileSync } = require('node:child_process');
const fs=require('node:fs'),assert=require('node:assert/strict');
const base='http://127.0.0.1:8002',runId=Date.now(),email=`browser-${runId}@example.invalid`,marker=`Browser ${runId.toString(36)}`,company=`PRIVATE Browser Manufacturing ${runId}`;
function token(){return execFileSync('python3',['-c',`import sqlite3,sys
c=sqlite3.connect('private/browser-test.sqlite3')
rows=c.execute('SELECT body FROM outbox WHERE recipient=? ORDER BY rowid DESC',(sys.argv[1],)).fetchall()
print(next(r[0].split('#market_token=')[1].split()[0] for r in rows if '#market_token=' in r[0]))`,email],{encoding:'utf8'}).trim();}
(async()=>{
 const {default:chromium,inflate,setupLambdaEnvironment}=await import('../private/browser/node_modules/@sparticuz/chromium/build/index.js');
 await inflate(require('node:path').resolve('private/browser/node_modules/@sparticuz/chromium/bin/al2023.tar.br'));
 setupLambdaEnvironment(require('node:os').tmpdir()+'/al2023/lib');
 const browser=await playwright.launch({executablePath:await chromium.executablePath(),args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'],headless:true});
 try{
 const errors=[];
 const user=await browser.newContext({viewport:{width:1440,height:1000}}),page=await user.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('.hero-actions .blue-button').first().click();
 await page.locator('dialog.ai-dialog[open]').waitFor();
 assert.equal(await page.locator('dialog.ai-dialog').evaluate(e=>Math.round(e.getBoundingClientRect().width)),1440);
 const ai=page.frameLocator('dialog.ai-dialog iframe');await ai.locator('#question').waitFor();assert.equal(await ai.locator('input[type=password]').count(),0);
 await ai.locator('#question').fill('What is photosynthesis?');await ai.locator('#send').click();await ai.locator('#messages').getByText('AI conversation is not connected on this deployment yet.',{exact:false}).waitFor();
 assert.equal(await ai.locator('#question').inputValue(),'What is photosynthesis?');
 await page.route('**/api/chat',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({mode:'model',message:'TEST ONLY: Plants use light to turn water and carbon dioxide into sugars.',references:[]})}));
 await ai.locator('#question').press('Enter');await ai.locator('#messages').getByText('TEST ONLY: Plants use light',{exact:false}).waitFor();
 await ai.locator('#question').press('Escape');await page.locator('dialog.ai-dialog[open]').waitFor({state:'hidden'});
 await page.locator('.hero-actions .blue-button').first().click();await ai.locator('#messages').getByText('TEST ONLY: Plants use light',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Close AI conversation'}).click();
 console.log('PASS full-screen public AI, no credential fields, honest disconnected state, mocked general answer, Enter/Escape and retained chat');
 await page.locator('.header-actions .supplier-link').click();const supplier=page.frameLocator('dialog.supplier-dialog iframe');await supplier.locator('#market-register').waitFor();
 await supplier.getByLabel('Registered company name').fill(company);await supplier.getByLabel('Contact person').fill('PRIVATE Test Contact');await supplier.locator('#email').fill(email);await supplier.getByLabel('Business registration country').fill('Greece');await supplier.getByLabel('Business registration / license number').fill('PRIVATE-BROWSER-LICENSE');
 await supplier.locator('#market-license').setInputFiles({name:'business-license.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nBrowser test only\n%%EOF')});
 await supplier.getByLabel('Product name',{exact:true}).fill(marker+' mounting bracket');await supplier.getByLabel('Category',{exact:true}).selectOption('industrial');await supplier.getByLabel('Product specifications and description').fill('An aluminium bracket for mounting equipment, with four drilled holes.');await supplier.getByLabel('Advertised minimum order quantity').fill('100');await supplier.getByLabel('Advertised price per unit').fill('2.50');
 const photo=execFileSync('.venv/bin/python',['-c',"from PIL import Image; import io,sys; b=io.BytesIO(); Image.new('RGB',(64,48),'blue').save(b,format='PNG'); sys.stdout.buffer.write(b.getvalue())"]);
 await supplier.locator('#product-image').setInputFiles({name:'test-product.png',mimeType:'image/png',buffer:photo});
 await supplier.locator('[name=content_consent]').check();await supplier.locator('[name=consent]').check();
 await supplier.getByRole('button',{name:'Confirm email & publish'}).click();assert.equal(await supplier.locator('#whatsapp').evaluate(e=>e.validity.valid),false);
 await supplier.getByLabel('WeChat (or provide WhatsApp)').fill('PRIVATE-BROWSER-WECHAT');await supplier.getByRole('button',{name:'Confirm email & publish'}).click();await supplier.locator('#market-register-success').waitFor();
 let listing=await (await user.request.get(base+'/api/marketplace?q='+encodeURIComponent(marker))).json();assert.equal(listing.total,0);
 console.log('PASS supplier popup, private details/product form, either-contact validation and invisible unconfirmed listing');
 await page.getByRole('button',{name:'Close supplier form'}).click();await page.goto(base+'/access#market_token='+token());await page.getByRole('button',{name:'Continue securely'}).click();await page.waitForURL('**/supplier/account');await page.locator('#market-account').waitFor();
 listing=await (await user.request.get(base+'/api/marketplace?q='+encodeURIComponent(marker))).json();assert.equal(listing.total,1);const pid=listing.products[0].id;
 for(const privateText of ['PRIVATE Browser','PRIVATE Test',email,'PRIVATE-BROWSER'])assert.equal(JSON.stringify(listing).includes(privateText),false);
 await page.goto(base+'/marketplace');await page.getByRole('heading',{name:marker+' mounting bracket',exact:true}).waitFor();assert.equal(await page.locator('.product-card img').first().evaluate(e=>e.complete&&e.naturalWidth>0),true);assert.equal(await page.getByRole('link',{name:'Inquire via STRATEVO'}).first().getAttribute('href'),'https://app.minup.io/book/stratevo');
 await page.locator('#market-query').fill('missing-product-xyz');await page.getByRole('button',{name:'Find products'}).click();await page.getByRole('heading',{name:'No products to display yet.'}).waitFor();
 console.log('PASS test-outbox confirmation automatically publishes, redirects to supplier account, displays photo, filters products and retains private identity');
 await page.goto(base+'/supplier/account');await page.locator('#market-account').waitFor();await page.getByRole('button',{name:'Withdraw product'}).first().click();await page.getByText('Listing status: withdrawn',{exact:true}).waitFor();assert.equal((await (await user.request.get(base+'/api/marketplace?q='+encodeURIComponent(marker))).json()).total,0);assert.equal((await user.request.get(base+'/api/marketplace/image/'+pid)).status(),404);
 await page.locator('#market-add [name=title]').fill(marker+' replacement bracket');await page.locator('#market-add [name=category]').selectOption('industrial');await page.locator('#market-add [name=description]').fill('Replacement aluminium bracket with revised hole dimensions.');await page.locator('#market-add [name=moq]').fill('50');await page.locator('#market-add [name=content_consent]').check();await page.getByRole('button',{name:'Publish product'}).click();await page.locator('#market-add-status').getByText('Product published to the Marketplace.').waitFor();
 console.log('PASS authenticated supplier withdrawal, inaccessible withdrawn photo and automatic additional-product publication');
 const manager=await browser.newContext(),admin=await manager.newPage();admin.on('pageerror',e=>errors.push(e.message));await admin.goto(base+'/admin');const config=JSON.parse(fs.readFileSync('private/browser-config.json'));await admin.locator('#admin-password').fill(config.TEST_ADMIN_PASSWORD);await admin.getByRole('button',{name:'Sign in securely'}).click();await admin.locator('#admin-workspace').waitFor();await admin.locator('#load-market-admin').click();await admin.locator('#market-admin-records').getByRole('heading',{name:company,exact:true}).waitFor();await admin.locator('#market-admin-records > .form-panel').filter({has:admin.getByRole('heading',{name:company,exact:true})}).getByRole('button',{name:'Remove listing'}).first().click();await admin.getByText('Listing removed from the public Marketplace.',{exact:true}).waitFor();assert.equal((await (await user.request.get(base+'/api/marketplace?q='+encodeURIComponent(marker))).json()).total,0);
 console.log('PASS manager-only private registry and post-publication removal; no publication approval step');
 for(const width of [320,390,768,1568]){
   await page.setViewportSize({width,height:920});
   for(const route of ['/','/marketplace','/supplier','/ai','/supplier/account']){await page.goto(base+route);await page.locator('h1').waitFor();const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,`${route} overflows at ${width}`);}
 }
 await page.setViewportSize({width:390,height:844});await page.goto(base);await page.locator('.menu-toggle').click();await page.locator('#main-nav').getByRole('link',{name:'Are you a supplier?',exact:true}).click();await page.locator('dialog.supplier-dialog[open]').waitFor();await page.frameLocator('dialog.supplier-dialog iframe').locator('#company').waitFor();assert.equal(await page.frameLocator('dialog.supplier-dialog iframe').locator('body').evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);await page.getByRole('button',{name:'Close supplier form'}).click();await page.locator('.menu-toggle').click();await page.locator('#main-nav').getByRole('link',{name:'Marketplace',exact:true}).click();await page.waitForURL('**/marketplace');
 await page.emulateMedia({reducedMotion:'reduce'});await page.goto(base);assert.equal(await page.locator('#constellation').evaluate(e=>getComputedStyle(e).display),'none');
 await page.screenshot({path:'private/checks/home-mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/marketplace');await page.screenshot({path:'private/checks/marketplace-desktop.png',fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS 320/390/768/1568 layouts, mobile popup and Marketplace navigation, reduced motion and zero JS exceptions');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
