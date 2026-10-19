'use strict';
const {chromium:pw}=require('../private/browser/node_modules/playwright');
const {default:AxeBuilder}=require('../private/browser/node_modules/@axe-core/playwright');
const assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const {default:c,inflate,setupLambdaEnvironment}=await import('../private/browser/node_modules/@sparticuz/chromium/build/index.js');
 await inflate(path.resolve('private/browser/node_modules/@sparticuz/chromium/bin/al2023.tar.br'));setupLambdaEnvironment(require('os').tmpdir()+'/al2023/lib');
 const browser=await pw.launch({executablePath:await c.executablePath(),args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 try{
  // HTTPS loopback uses an isolated self-signed test certificate. Production cookies stay Secure.
  const context=await browser.newContext({viewport:{width:390,height:844},ignoreHTTPSErrors:true,extraHTTPHeaders:{'X-Vercel-Forwarded-For':'203.0.113.23'}});
  const page=await context.newPage(),base=process.env.TEST_BASE_URL,errors=[];page.on('pageerror',e=>errors.push(e.message));
  const health=await (await context.request.get(base+'/api/health')).json();assert.equal(health.storage.mode,process.env.TEST_STORAGE_MODE);
  await page.goto(base+'/supplier.html');await page.locator('#market-register').waitFor();
  if(process.env.TEST_STORAGE_MODE==='ephemeral_fallback')await page.locator('[data-storage-status]').filter({hasText:'Temporary instance-local storage'}).waitFor();
  await page.locator('#company').fill('SYNTHETIC Private Test Works');await page.locator('#contact').fill('SYNTHETIC Person');await page.locator('#email').fill('browser-synthetic@example.invalid');await page.locator('#country').fill('Greece');await page.locator('#city').fill('Rethymno');
  await page.locator('#product-title').fill('Synthetic test bracket');await page.locator('#product-category').selectOption('industrial');await page.locator('#product-description').fill('Synthetic browser test product, not a genuine supplier offer.');await page.locator('[name=content_consent]').check();await page.locator('[name=consent]').check();
  await page.getByRole('button',{name:'Review product'}).click();await page.locator('#market-review').waitFor();
  assert.equal((await new AxeBuilder({page}).analyze()).violations.length,0);
  let calls=0,keys=[];await page.route('**/api/marketplace/register',async route=>{calls++;keys.push(route.request().postDataJSON().submission_key);const headers=route.request().headers();if(calls===1){const response=await route.fetch({headers});assert.equal(response.status(),200);await route.abort('connectionfailed');}else{const response=await route.fetch({headers});await route.fulfill({response});}});
  await page.getByRole('button',{name:'Confirm and Publish',exact:true}).click();await page.locator('#market-review-status').getByText('Your details are retained.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Confirm and Publish',exact:true}).click();await page.locator('#market-register-success').waitFor({timeout:10000}).catch(async e=>{console.error('Publication status:',await page.locator('#market-review-status').textContent());throw e;});assert.equal(calls,2);assert.equal(keys[0],keys[1]);
  let market=await (await context.request.get(base+'/api/marketplace')).json();assert.equal(market.total,1);assert.equal(JSON.stringify(market).includes('Private Test Works'),false);
  await page.getByRole('link',{name:'Manage your products'}).click();await page.locator('#market-account').waitFor();await page.locator('#market-account-status').getByText('Email not yet confirmed.',{exact:false}).waitFor();
  await page.goto(base+'/portal');await page.waitForURL('**/supplier/account');await page.locator('#market-account').waitFor();
  await page.getByRole('button',{name:'Withdraw product',exact:true}).click();await page.getByText('Listing status: withdrawn',{exact:true}).waitFor();
  market=await (await context.request.get(base+'/api/marketplace')).json();assert.equal(market.total,0);
  await page.goto(base+'/inquiry');await page.locator('#lead-product').fill('Synthetic test packaging');await page.locator('#lead-quantity').fill('100 pieces');await page.locator('#lead-destination').fill('Greece');await page.locator('#lead-requirements').fill('Synthetic test only; no real buyer or commercial request.');await page.locator('#lead-name').fill('SYNTHETIC Buyer');await page.locator('#lead-email').fill('buyer@example.invalid');await page.locator('[name=consent]').check();await page.getByRole('button',{name:'Send sourcing inquiry',exact:true}).click();await page.locator('#inquiry-success').waitFor();if(process.env.TEST_STORAGE_MODE==='ephemeral_fallback')await page.locator('#inquiry-result').getByText('Temporary',{exact:false}).waitFor();
  const login=await context.request.post(base+'/api/admin/login',{data:{username:'fixture-admin',password:process.env.TEST_ADMIN_PASSWORD,otp:process.env.TEST_ADMIN_OTP}});assert.equal(login.status(),200);
  assert.equal((await context.request.get(base+'/api/admin/inquiries')).status(),200);
  assert.equal((await context.request.get(base+'/api/admin/marketplace')).status(),200);
  await page.goto(base+'/assessment');await page.locator('h1').waitFor();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
  assert.deepEqual(errors,[]);
  console.log('PASS actual Vercel adapter '+process.env.TEST_STORAGE_MODE+': mobile review/axe, response-loss idempotent publication, secure management session, portal redirect, withdrawal, inquiry, production MFA/admin and no page exceptions');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
