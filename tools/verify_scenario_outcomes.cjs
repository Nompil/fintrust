const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);
(async()=>{const origin=process.argv[2],out=process.argv[3];if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Loopback only');
const exe=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
const browser=await chromium.launch({executablePath:exe,headless:true,args:['--disable-background-networking']});try{
const context=await browser.newContext({viewport:{width:1500,height:1000}});await context.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());
const p=await context.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.goto(origin+'/release1');await p.locator('#token').fill('2'.repeat(64));await p.locator('#signin').click();await p.locator('#workspace').waitFor({state:'visible'});
for(const test of JSON.parse(fs.readFileSync(path.join(out,'inputs.json'),'utf8'))){
await p.locator('#navigation').getByRole('button',{name:'Risk Events',exact:true}).click();await p.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
const ref=await p.evaluate(id=>FinTrustDisplay.reference('risk_event_id',id),test.event_id);
await p.locator('#content tr').filter({hasText:ref}).getByRole('button',{name:'Investigate',exact:true}).click();
let drawer=p.locator('#investigation-drawer');await drawer.getByRole('button',{name:'Claim Review',exact:true}).click();await drawer.locator('textarea').waitFor();
await drawer.locator('textarea').fill('Controlled scenario: merchant and source evidence checked');await drawer.locator('form select').selectOption(test.status);
const done=p.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/transition')&&r.status()===200);
await drawer.getByRole('button',{name:'Save investigation',exact:true}).click();await done;
await p.waitForFunction(expected=>document.querySelector('#investigation-drawer')?.textContent.includes(expected),test.status);
await p.screenshot({path:path.join(out,test.status.toLowerCase()+'.png'),fullPage:true});await p.keyboard.press('Escape');
}
if(errors.length)throw Error(errors.join(';'));fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify({status:'PASSED',checks:['claim then clear','claim then confirm risk','claim then escalate','decision visible in investigation drawer'],external_network:'blocked',aws_access:false},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exit(1)});
