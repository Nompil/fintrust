'use strict';
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);

(async()=>{
 const origin=process.argv[2],out=process.argv[3],base=process.argv[4]||'',role=process.argv[5]||'Read-only/Auditor',entry=base?base+'/':'/release1';
 const exe=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(require('node:fs').existsSync);
 const browser=await chromium.launch({executablePath:exe,headless:true,args:['--disable-background-networking']});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 let authorize=null,tokenForm=null,logout=null,refreshes=0,authorizations=0,creations=0,creationReceipt=null;
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.origin===origin){
   assert.ok(!base||url.pathname.startsWith(base+'/'),'Request escaped API Gateway stage: '+url.pathname);
   if(url.pathname===base+'/v1/accounts')return route.fulfill({status:200,contentType:'application/json',body:'{"data":[]}'});
   if(url.pathname===base+'/v1/administration')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({data:{identity:'Cognito',contract_version:'test',live_deployment:'Mocked browser verification'}})});
   if(url.pathname===base+'/v1/administration/users')return route.fulfill({status:200,contentType:'application/json',body:'{"data":[]}'});
   if(url.pathname===base+'/v1/user-provisioning'){
    if(route.request().method()==='POST'){
     const body=route.request().postDataJSON();creations++;
     assert.deepEqual(Object.keys(body).sort(),['accounts','display_name','email','notes','request_id','role','username']);
     assert.equal(body.username,'new-analyst');assert.equal(body.role,'Risk/Compliance Analyst');
     assert.deepEqual(body.accounts,['20000000-0000-4000-8000-000000000001']);
     creationReceipt={...body,state:'INVITATION_REQUESTED'};
    }
    assert.ok(creationReceipt);
    return route.fulfill({status:route.request().method()==='POST'?201:200,contentType:'application/json',body:JSON.stringify({data:creationReceipt})});
   }
   if(url.pathname===base+'/v1/release1/overview')return route.fulfill({status:503,contentType:'application/json',body:'{"error":"verification read is intentionally unavailable"}'});
   return route.continue();
  }
  if(url.pathname==='/oauth2/authorize'){
   authorizations++;
   authorize=url;
   const callback=new URL(origin+entry);callback.searchParams.set('code','synthetic-code');callback.searchParams.set('state',url.searchParams.get('state'));
   return route.fulfill({status:200,contentType:'text/html',body:`<!doctype html><a id="continue" href="${callback}">Continue sign-in</a>`});
  }
  if(url.pathname==='/oauth2/token'){
   const posted=new URLSearchParams(route.request().postData()||'');
   if(posted.get('grant_type')==='refresh_token'){
    refreshes++;assert.equal(posted.get('refresh_token'),'synthetic-refresh-token');
    return route.fulfill({status:200,contentType:'application/json',body:'{"token_type":"Bearer","access_token":"synthetic-refreshed-access-token","expires_in":300}'});
   }
   tokenForm=new URLSearchParams(route.request().postData()||'');
   assert.equal(tokenForm.get('grant_type'),'authorization_code');
   assert.equal(tokenForm.get('code'),'synthetic-code');
   const verifier=tokenForm.get('code_verifier');
   assert.ok(verifier&&verifier.length>=43);
   assert.equal(crypto.createHash('sha256').update(verifier).digest('base64url'),authorize.searchParams.get('code_challenge'));
   return route.fulfill({status:200,contentType:'application/json',body:'{"token_type":"Bearer","access_token":"synthetic-access-token","expires_in":300,"refresh_token":"synthetic-refresh-token"}'});
  }
  if(url.pathname==='/logout'){
   logout=url;
   return route.fulfill({status:200,contentType:'text/html',body:'Signed out'});
  }
  return route.abort();
 });
 try{
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+entry);
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
  assert.equal(await page.locator('#identity').innerText(),role==='Admin'?'admin01 | Administrator':'auditor01 | Auditor');
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('imbokodo.oauth.state')),null);
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('imbokodo.oauth.verifier')),null);
  assert.equal(await page.evaluate(()=>localStorage.length),0);
  await page.evaluate(async()=>{cloudSession.expiresAt=Date.now()+1000;await Promise.all([request('/v1/session'),request('/v1/session')]);});
  assert.equal(refreshes,1);
  assert.equal(await page.locator('#workspace').isVisible(),true);
  await page.reload();
  await page.getByRole('link',{name:'Continue sign-in'}).waitFor();
  assert.equal(authorizations,2);
  await page.getByRole('link',{name:'Continue sign-in'}).click();
  await page.locator('#workspace').waitFor({state:'visible'});
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('imbokodo.signed-in')),'1');
  if(role==='Admin'){
   await page.locator('#navigation').getByRole('button',{name:'Users',exact:true}).click();
   await page.getByRole('button',{name:'Add User',exact:true}).click();
   const form=page.locator('#cloud-user-create-form');
   assert.equal(await form.locator('input[type=password]').count(),0);
   await form.locator('[name=username]').fill('new-analyst');await form.locator('[name=display_name]').fill('New Analyst');
   await form.locator('[name=email]').fill('owned-test@example.test');await form.locator('[name=notes]').fill('Approved scoped analyst access');
   await form.locator('input[type=checkbox]').first().check();
   await page.screenshot({path:out+'/cloud-admin-create-user.png',fullPage:true});
   await form.getByRole('button',{name:'Create user and request invitation',exact:true}).click();
   await form.getByText(/INVITATION REQUESTED/).waitFor();assert.equal(creations,1);
   await form.getByRole('button',{name:'Create another user',exact:true}).click();
   assert.equal(await page.locator('#cloud-user-create-form [name=username]').inputValue(),'');
   assert.equal(creations,1);
  }else assert.equal(await page.locator('#navigation').getByRole('button',{name:'Users',exact:true}).count(),0);
  await page.locator('#switch-user').click();
  await page.waitForURL(url=>url.pathname==='/logout');
  assert.ok(logout);
  assert.equal(logout.searchParams.get('client_id'),'synthetic-client-id');
  assert.equal(logout.searchParams.get('logout_uri'),'https://workbench.example.test/release1');
  assert.equal(await page.locator('#workspace').isVisible(),false);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:out+'/cognito-signed-out.png',fullPage:true});
  process.stdout.write('Cognito PKCE authorize/callback/token exchange, app role session, memory-only token, single-flight refresh, reload reauthorization and Switch user/logout: PASS\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
