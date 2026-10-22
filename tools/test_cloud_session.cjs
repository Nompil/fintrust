'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {ImbokodoCloudSession}=require('../frontend/js/release1-session.js');
const cfg={domain:'https://owned-test.auth.af-south-1.amazoncognito.com',client_id:'test-client'};
const tokens=(access='first')=>({token_type:'Bearer',access_token:access,refresh_token:'synthetic-refresh',expires_in:300});
test('five-minute access token refreshes before expiry; concurrent reads share one refresh',async()=>{
 let now=0,calls=0,release;
 const session=new ImbokodoCloudSession(cfg,async(url,options)=>{
  calls++;assert.equal(options.body.get('grant_type'),'refresh_token');assert.equal(options.credentials,'omit');
  await new Promise(resolve=>release=resolve);return {ok:true,json:async()=>tokens('second')};
 },()=>now);
 session.accept(tokens());assert.equal(await session.access(),'first');now=260000;
 const a=session.access(),b=session.access();release();
 assert.deepEqual(await Promise.all([a,b]),['second','second']);assert.equal(calls,1);
});
test('logout during refresh never restores credentials',async()=>{
 let now=0,release;
 const session=new ImbokodoCloudSession(cfg,async()=>{await new Promise(resolve=>release=resolve);return {ok:true,json:async()=>tokens('late')};},()=>now);
 session.accept(tokens());now=260000;const pending=session.access();session.clear();release();
 await assert.rejects(pending,error=>error.staleSession===true);assert.equal(session.token,'');assert.equal(session.refreshToken,'');
});
test('network failure is retryable and does not erase the valid refresh session',async()=>{
 let now=0,calls=0;
 const session=new ImbokodoCloudSession(cfg,async()=>{if(++calls===1)throw Error('synthetic network outage');return {ok:true,json:async()=>tokens('recovered')};},()=>now);
 session.accept(tokens());now=260000;
 await assert.rejects(session.access());assert.equal(session.refreshToken,'synthetic-refresh');assert.equal(await session.access(),'recovered');
});
test('revoked refresh token is classified as expired, with no automatic mutation retry',async()=>{
 let now=0,calls=0;
 const session=new ImbokodoCloudSession(cfg,async()=>{calls++;return {ok:false,status:400};},()=>now);
 session.accept(tokens());now=260000;await assert.rejects(session.access(),error=>error.sessionExpired===true);assert.equal(calls,1);
});
test('malformed token responses cannot replace an existing token',()=>{
 const session=new ImbokodoCloudSession(cfg);session.accept(tokens());
 assert.throws(()=>session.accept({token_type:'Bearer',access_token:'bad',expires_in:-1}));assert.equal(session.token,'first');
});
