'use strict';
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);

(async()=>{
 const origin=process.argv[2],out=process.argv[3];
 const exe=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(require('node:fs').existsSync);
 const browser=await chromium.launch({executablePath:exe,headless:true,args:['--disable-background-networking']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 let authorize=null,tokenForm=null,logout=null;
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.origin===origin){
   if(url.pathname==='/v1/accounts')return route.fulfill({status:200,contentType:'application/json',body:'{"data":[]}'});
   if(url.pathname==='/v1/release1/overview')return route.fulfill({status:503,contentType:'application/json',body:'{"error":"verification read is intentionally unavailable"}'});
   return route.continue();
  }
  if(url.pathname==='/oauth2/authorize'){
   authorize=url;
   const callback=new URL(origin+'/release1');callback.searchParams.set('code','synthetic-code');callback.searchParams.set('state',url.searchParams.get('state'));
   return route.fulfill({status:200,contentType:'text/html',body:`<!doctype html><a id="continue" href="${callback}">Continue sign-in</a>`});
  }
  if(url.pathname==='/oauth2/token'){
   tokenForm=new URLSearchParams(route.request().postData()||'');
   assert.equal(tokenForm.get('grant_type'),'authorization_code');
   assert.equal(tokenForm.get('code'),'synthetic-code');
   const verifier=tokenForm.get('code_verifier');
   assert.ok(verifier&&verifier.length>=43);
   assert.equal(crypto.createHash('sha256').update(verifier).digest('base64url'),authorize.searchParams.get('code_challenge'));
   return route.fulfill({status:200,contentType:'application/json',body:'{"token_type":"Bearer","access_token":"synthetic-access-token"}'});
  }
  if(url.pathname==='/logout'){
   logout=url;
   return route.fulfill({status:200,contentType:'text/html',body:'Signed out'});
  }
  return route.abort();
 });
 try{
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/release1');
  await page.waitForFunction(()=>document.querySelector('#signin')?.textContent.includes('Imbokodo'));
  await page.getByRole('button',{name:'Sign in with Imbokodo'}).click();
  await page.getByRole('link',{name:'Continue sign-in'}).waitFor();
  assert.equal(authorize.searchParams.get('response_type'),'code');
  assert.equal(authorize.searchParams.get('code_challenge_method'),'S256');
  assert.equal(authorize.searchParams.get('scope'),'openid email profile');
  assert.ok((authorize.searchParams.get('state')||'').length>=40);
  await page.getByRole('link',{name:'Continue sign-in'}).click();
  await page.locator('#workspace').waitFor({state:'visible'});
  assert.ok(tokenForm);
  assert.equal(await page.locator('#switch-user').isVisible(),true);
  assert.equal(await page.locator('#identity').innerText(),'auditor01 | Auditor');
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('imbokodo.oauth.state')),null);
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('imbokodo.oauth.verifier')),null);
  assert.equal(await page.evaluate(()=>localStorage.length),0);
  await page.locator('#switch-user').click();
  await page.waitForURL(url=>url.pathname==='/logout');
  assert.ok(logout);
  assert.equal(logout.searchParams.get('client_id'),'synthetic-client-id');
  assert.equal(logout.searchParams.get('logout_uri'),'https://workbench.example.test/release1');
  assert.equal(await page.locator('#workspace').isVisible(),false);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:out+'/cognito-signed-out.png',fullPage:true});
  process.stdout.write('Cognito PKCE authorize/callback/token exchange, app role session, memory-only token and Switch user/logout: PASS\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
