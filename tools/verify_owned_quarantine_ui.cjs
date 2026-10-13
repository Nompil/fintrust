const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);
(async()=>{const origin=process.argv[2],out=process.argv[3];if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Loopback required');
const exe=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
const browser=await chromium.launch({executablePath:exe,headless:true,args:['--disable-background-networking']});try{
const context=await browser.newContext({viewport:{width:1366,height:950}});await context.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());const p=await context.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto(origin+'/release1');await p.locator('#token').fill('2'.repeat(64));await p.locator('#signin').click();await p.locator('#workspace').waitFor({state:'visible'});
await p.locator('#navigation').getByRole('button',{name:'Quarantine',exact:true}).click();await p.locator('#content').getByRole('button',{name:'Details',exact:true}).first().click();
await p.locator('#investigation-drawer').getByText('analyst01',{exact:true}).first().waitFor();await p.getByRole('button',{name:'Correct / Revalidate',exact:true}).click();
await p.locator('#correction-account-id').selectOption('20000000-0000-4000-8000-000000000001');await p.locator('#notes').fill('Verify own-upload unknown account correction');await p.screenshot({path:path.join(out,'own-upload-account-correction.png'),fullPage:false});await p.locator('#submit-action').click();
await p.locator('#investigation-drawer').getByText('Verify own-upload unknown account correction',{exact:true}).waitFor();
for(let i=0;i<30&&await p.getByRole('button',{name:'Resulting transaction',exact:true}).count()===0;i++){await p.getByRole('button',{name:'Refresh recovery outcome',exact:true}).click();await p.waitForTimeout(200);}
await p.getByRole('button',{name:'Resulting transaction',exact:true}).waitFor();await p.screenshot({path:path.join(out,'own-upload-revalidated.png'),fullPage:true});await p.getByRole('button',{name:'Resulting transaction',exact:true}).click();await p.waitForFunction(()=>document.querySelector('.recorded-lifecycle')?.textContent.includes('STORED'));
if(errors.length)throw Error(errors.join(';'));fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({status:'PASSED',local_only:true,checks:['own upload detail','assigned-account selection','correction submitted','worker accepted','ledger lifecycle STORED'],page_errors:errors},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
