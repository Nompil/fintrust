"use strict";
// Tokens remain in memory. A pending refresh cannot resurrect a signed-out session.
class ImbokodoCloudSession {
 constructor(config, fetcher=fetch, clock=()=>Date.now()) {
  this.config=config;this.fetcher=fetcher.bind(globalThis);this.clock=clock;this.clear();
 }
 clear(){this.epoch=(this.epoch||0)+1;this.token="";this.refreshToken="";this.expiresAt=0;this.pending=null;}
 accept(result){
  if(result.token_type!=="Bearer"||typeof result.access_token!=="string"||!result.access_token||!Number.isFinite(result.expires_in)||result.expires_in<=0||result.expires_in>86400)throw Error("Invalid sign-in response");
  this.token=result.access_token;this.expiresAt=this.clock()+result.expires_in*1000;
  if(typeof result.refresh_token==="string"&&result.refresh_token)this.refreshToken=result.refresh_token;
 }
 async access(){
  if(!this.token)throw Object.assign(Error("Sign in required"),{sessionExpired:true});
  if(this.clock()<this.expiresAt-45000)return this.token;
  if(this.pending)return this.pending;
  if(!this.refreshToken)throw Object.assign(Error("Sign in required"),{sessionExpired:true});
  const epoch=this.epoch,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
  const operation=(async()=>{
   try{
    const body=new URLSearchParams({grant_type:"refresh_token",client_id:this.config.client_id,refresh_token:this.refreshToken});
    const response=await this.fetcher(this.config.domain+"/oauth2/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body,credentials:"omit",cache:"no-store",signal:controller.signal});
    if(epoch!==this.epoch)throw Object.assign(Error("Session changed"),{staleSession:true});
    if(!response.ok){const error=Error("Session refresh unavailable");error.sessionExpired=response.status===400||response.status===401;throw error;}
    const result=await response.json();
    if(epoch!==this.epoch)throw Object.assign(Error("Session changed"),{staleSession:true});
    this.accept(result);return this.token;
   }finally{clearTimeout(timer);}
  })();
  const pending=operation.finally(()=>{if(this.pending===pending)this.pending=null;});
  this.pending=pending;return pending;
 }
}
if(typeof module!=="undefined")module.exports={ImbokodoCloudSession};
