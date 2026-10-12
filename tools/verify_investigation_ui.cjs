const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);
(async()=>{const origin=process.argv[2],out=process.argv[3];if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin))throw Error('Loopback only');
const exe=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
const browser=await chromium.launch({executablePath:exe,headless:true,args:['--disable-background-networking']});try{
const context=await browser.newContext({viewport:{width:1600,height:1000}});await context.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());
const p=await context.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));
async function login(key){await p.goto(origin+'/release1');await p.locator('#token').fill(key.repeat(64));await p.locator('#signin').click();await p.locator('#workspace').waitFor({state:'visible'});await p.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));}
async function nav(name){await p.locator('#navigation').getByRole('button',{name,exact:true}).click();await p.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));}
async function investigate(){await p.getByLabel('Scenario',{exact:true}).selectOption('HIGH_AMOUNT');await p.getByRole('button',{name:'Apply investigation filters',exact:true}).click();await p.getByRole('button',{name:'Investigate',exact:true}).first().click();await p.locator('#investigation-drawer').getByRole('heading',{name:'NEXT STEPS',exact:true}).waitFor();}
await login('2');await nav('Risk Events');await p.getByLabel('Scenario',{exact:true}).selectOption('HIGH_AMOUNT');await p.getByRole('button',{name:'Apply investigation filters',exact:true}).click();await p.getByRole('button',{name:'Investigate',exact:true}).first().waitFor();await investigate();
for(const name of ['WHAT HAPPENED','WHEN','WHERE','WHY IS IT RISKY','ACCOUNT CONTEXT','ALERT AND REVIEW','AUDIT TIMELINE'])await p.locator('#investigation-drawer').getByRole('heading',{name,exact:true}).waitFor();
if(await p.locator('#content').getByRole('button',{name:'Investigate',exact:true}).count()!==1)throw Error('Queue lost behind drawer');
await p.screenshot({path:path.join(out,'risk-investigation.png'),fullPage:true});await p.locator('#investigation-drawer').getByRole('button',{name:'Claim review',exact:true}).click();await p.locator('#investigation-drawer textarea').waitFor();
await p.locator('#investigation-drawer textarea').fill('Compared merchant and source evidence');await p.getByRole('button',{name:'Save investigation',exact:true}).click();await p.locator('#investigation-drawer').getByText('Compared merchant and source evidence',{exact:true}).waitFor();
await p.locator('#investigation-drawer').getByRole('heading',{name:'NEXT STEPS',exact:true}).scrollIntoViewIfNeeded();await p.screenshot({path:path.join(out,'owned-investigation-history.png'),fullPage:true});
await p.keyboard.press('Escape');if(await p.locator('#investigation-drawer').count())throw Error('Escape did not close detail');
await nav('Quarantine');await p.getByRole('button',{name:'Details',exact:true}).first().click();await p.locator('#investigation-drawer').getByText('Original safe values',{exact:true}).waitFor();await p.screenshot({path:path.join(out,'quarantine-split-detail.png'),fullPage:true});
await login('3');await nav('Risk Events');await investigate();if(await p.locator('#investigation-drawer textarea').count())throw Error('Wrong Analyst can decide');
await login('4');await nav('Risk Events');await investigate();if(await p.getByRole('button',{name:'Save investigation',exact:true}).count())throw Error('Auditor can decide');
await p.setViewportSize({width:390,height:844});await p.screenshot({path:path.join(out,'auditor-investigation-mobile.png'),fullPage:false});
await p.setViewportSize({width:1600,height:1000});await login('1');await nav('Administration');await p.getByLabel('Filter users').fill('analyst02');await p.getByText('Analyst02',{exact:true}).waitFor();await p.screenshot({path:path.join(out,'users-filtered-table.png'),fullPage:true});
if(errors.length)throw Error(errors.join(';'));fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify({status:'PASSED',checks:['scoped scenario filter','queue retained','North Star evidence drawer','claim','append notes','immutable history','Escape close','quarantine split detail','wrong Analyst read-only','Auditor read-only','mobile','user filter'],external_network:'blocked'},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exit(1)});
