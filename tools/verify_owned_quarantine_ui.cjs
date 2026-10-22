const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);
(async()=>{const origin=process.argv[2],out=process.argv[3];if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Loopback required');
const exe=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
const browser=await chromium.launch({executablePath:exe,headless:true,args:['--disable-background-networking']});try{
const context=await browser.newContext({viewport:{width:1366,height:950}});await context.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());const p=await context.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto(origin+'/release1');await p.locator('#token').fill('2'.repeat(64));await p.locator('#signin').click();await p.locator('#workspace').waitFor({state:'visible'});
await p.locator('#navigation').getByRole('button',{name:'Quarantined Rows',exact:true}).click();await p.locator('#content').getByRole('button',{name:'View issue',exact:true}).first().click();
await p.locator('#investigation-drawer').getByText('analyst01',{exact:true}).first().waitFor();
if(await p.getByRole('button',{name:'Correct and resubmit',exact:true}).count()||await p.locator('#correction-account-id').count())throw Error('Account editing is exposed');
await p.getByLabel('Record a source-review note',{exact:true}).fill('Ask source owner to confirm the missing account reference');
await p.getByRole('button',{name:'Save source-review note',exact:true}).click();
await p.locator('#investigation-drawer').getByRole('cell',{name:'Ask source owner to confirm the missing account reference',exact:true}).waitFor();
await p.getByRole('button',{name:'Reject row',exact:true}).click();await p.locator('#notes').fill('Source replacement required; do not infer a bank account');await p.locator('#submit-action').click();
await p.locator('#investigation-drawer').getByText('Rejected — no ledger entry. Original evidence retained.',{exact:true}).waitFor();
await p.screenshot({path:path.join(out,'own-upload-source-review-rejection.png'),fullPage:true});
if(errors.length)throw Error(errors.join(';'));fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({status:'PASSED',local_only:true,checks:['own upload detail','financial editor absent','source-review note retained','rejection recorded','original unknown account retained'],page_errors:errors},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
