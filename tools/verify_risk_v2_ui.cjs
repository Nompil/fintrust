'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);
const origin=process.argv[2],out=process.argv[3],rows=JSON.parse(process.env.FINTRUST_RISK_BROWSER_ROWS);
(async()=>{
 const executablePath=['C:/Program Files/Google/Chrome/Application/chrome.exe',chromium.executablePath()].find(p=>fs.existsSync(p));
 const browser=await chromium.launch({headless:true,executablePath});
 try{
  const p=await browser.newPage({viewport:{width:1366,height:950}}),errors=[];p.on('pageerror',e=>errors.push(e.name));
  await p.route('**/*',route=>new URL(route.request().url()).origin===new URL(origin).origin?route.continue():route.abort());
  await p.goto(origin+'/release1');await p.locator('#token').fill('2'.repeat(64));await p.getByRole('button',{name:'Sign in',exact:true}).click();await p.locator('#workspace').waitFor({state:'visible'});
  async function nav(name){if(!await p.locator('#navigation').getByRole('button',{name,exact:true}).isVisible())await p.getByRole('button',{name:'Toggle navigation',exact:true}).click();await p.locator('#navigation').getByRole('button',{name,exact:true}).click();await p.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));}
  async function filter(ref){await nav('Transactions');await p.locator('[data-filter=tx_id]').fill(ref);await p.getByRole('button',{name:'Apply filters',exact:true}).click();await p.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));}
  await filter(rows['V2-DEMO'].tx);assert.equal((await p.locator('#content .risk-score').innerText()).replace(/\s+/g,''),'65%');
  assert.match(await p.locator('#content .risk-score').getAttribute('title'),/not the probability of fraud/);
  await p.getByRole('button',{name:'Details / audit timeline',exact:true}).click();await p.getByRole('heading',{name:'Why It Was Flagged',exact:true}).waitFor();
  const detail=p.locator('.transaction-detail');assert.equal(await detail.locator('.risk-component[data-rule=AMOUNT_RISK]').count(),1);
  assert.match(await detail.locator('.risk-score').innerText(),/65%\s*— HIGH/);
  assert.match(await detail.innerText(),/fintrust-r2-rules-2026-10-13/);
  const velocity=detail.locator('[data-rule=HIGH_VELOCITY]');assert.match(await velocity.innerText(),/8 accepted transactions within 300 seconds/);assert.match(await velocity.innerText(),/More than 5 transactions within 5 minutes/);assert.match(await velocity.innerText(),/09:55:00/);assert.match(await velocity.innerText(),/10:00:00/);
  assert.match(await detail.locator('[data-rule=AMOUNT_RISK]').innerText(),/150000/);assert.match(await detail.locator('[data-rule=CROSS_BORDER]').innerText(),/US[\s\S]*ZA/);
  await p.screenshot({path:path.join(out,'v2-transaction-components.png'),fullPage:true});
  await nav('Risk Events');await p.getByLabel('Scenario',{exact:true}).selectOption('AMOUNT_RISK');await p.getByRole('button',{name:'Apply investigation filters',exact:true}).click();
  const risk=p.locator('#content .investigable-row').filter({hasText:'RISK-'+String(rows['V2-DEMO'].event).padStart(4,'0')});await risk.getByRole('button',{name:'Investigate',exact:true}).click();
  const drawer=p.locator('#investigation-drawer');for(const name of ['WHAT HAPPENED','WHY IS IT RISKY','ACCOUNT CONTEXT','ALERT AND REVIEW','NEXT STEPS'])await drawer.getByRole('heading',{name,exact:true}).waitFor();
  assert.match(await drawer.locator('.case-score').innerText(),/65%\s*— HIGH/);await drawer.locator('[data-rule=HIGH_VELOCITY]').scrollIntoViewIfNeeded();await p.screenshot({path:path.join(out,'v2-velocity-investigation.png')});await p.keyboard.press('Escape');
  await filter(rows['V2-DUP-B'].tx);await p.getByRole('button',{name:'Details / audit timeline',exact:true}).click();await p.getByRole('heading',{name:'Why It Was Flagged',exact:true}).waitFor();
  const dupe=p.locator('.transaction-detail [data-rule=POSSIBLE_DUPLICATE_CHARGE]');assert.match(await dupe.innerText(),/\+20/);assert.match(await dupe.innerText(),/30/);assert.match(await dupe.innerText(),/account_id, merchant, amount, currency, source_system, tx_type/);assert.equal(await dupe.getByRole('button',{name:/^Related TX-/}).count(),1);
  await filter(rows['V2-ZERO'].tx);assert.equal((await p.locator('#content .risk-score').innerText()).replace(/\s+/g,''),'0%');
  await filter(rows['V2-OLD'].tx);await p.getByRole('button',{name:'Details / audit timeline',exact:true}).click();await p.getByRole('heading',{name:'Why It Was Flagged',exact:true}).waitFor();assert.match(await detail.innerText(),/70%\s*— HIGH/);assert.match(await detail.innerText(),/Historical assessment/);assert.match(await detail.innerText(),/fintrust-r1-rules-2026-10-09/);assert.equal(await detail.locator('[data-rule=AMOUNT_RISK]').count(),1);assert.match(await detail.locator('[data-rule=AMOUNT_RISK]').innerText(),/\+55/);assert.match(await detail.innerText(),/Missing measurements are not reconstructed/);
  await p.screenshot({path:path.join(out,'legacy-v1-preserved.png'),fullPage:true});
  await nav('Transactions');await p.locator('[data-filter=tx_id]').fill('');await p.getByRole('button',{name:'Apply filters',exact:true}).click();await p.locator('.risk-score.unassessed').first().waitFor();assert.equal(await p.locator('.risk-score.unassessed').first().innerText(),'Not assessed');
  await nav('Insights');await p.locator('#insights-days').selectOption('all');await p.getByRole('button',{name:'Apply analytical filters',exact:true}).click();await p.getByRole('heading',{name:'Recorded scoring versions',exact:true}).waitFor();assert.match(await p.locator('#content').innerText(),/fintrust-r1-rules-2026-10-09/);assert.match(await p.locator('#content').innerText(),/fintrust-r2-rules-2026-10-13/);assert.match(await p.locator('#content').innerText(),/Amount risk groups legacy amount bands once per transaction/);
  await p.setViewportSize({width:390,height:844});await filter(rows['V2-DEMO'].tx);assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.getByRole('button',{name:'Details / audit timeline',exact:true}).click();await p.getByRole('heading',{name:'Why It Was Flagged',exact:true}).waitFor();assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.screenshot({path:path.join(out,'v2-components-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify({status:'PASSED',checks:['65% with disclaimer','one amount component','frozen velocity count/threshold/windows/points','cross-border countries','duplicate fields/reference/proximity/points','zero 0%','missing Not assessed','V1 70% preserved and grouped amount 55','mixed scoring versions','Analyst evidence/context/actions','390px containment'],external_network:'blocked',page_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exit(1)});
