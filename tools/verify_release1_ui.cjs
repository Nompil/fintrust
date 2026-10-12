// Automated local browser acceptance test. All navigation/network stays loopback.
const fs=require('node:fs');
const path=require('node:path');
const display=require('../frontend/release1-display.js');
const {chromium}=require(process.env.FINTRUST_PLAYWRIGHT_MODULE);
(async()=>{
 const url=process.argv[2];const output=process.argv[3];
 if(!/^http:\/\/127\.0\.0\.1:\d+$/.test(url))throw Error('Dedicated loopback server required');
 const candidates=[chromium.executablePath(),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','/usr/bin/google-chrome','/usr/bin/chromium'];
 const executablePath=candidates.find(p=>fs.existsSync(p));if(!executablePath)throw Error('No installed headless browser; no tooling installation attempted');
 const browser=await chromium.launch({executablePath,headless:true,args:['--disable-background-networking','--no-first-run']});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route('**/*',route=>{const target=new URL(route.request().url());return target.origin===url?route.continue():route.abort();});
  const page=await context.newPage();let reportResponse,insightsResponse,overviewResponse;page.on('response',r=>{const p=new URL(r.url()).pathname;if(r.status()===200&&p==='/v1/release1/overview')overviewResponse=r.json().catch(()=>null);if(r.status()===200&&p==='/v1/reports')reportResponse=r.json().catch(()=>null);if(r.status()===200&&p==='/v1/release1/insights')insightsResponse=r.json().catch(()=>null);});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/');
  if(await page.getByText('earlier learning interface',{exact:false}).count())throw Error('Legacy entry point exposed');
  await page.locator('#token').fill('b'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.locator('#workspace').waitFor({state:'visible'});await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
  if(await page.locator('#title').innerText()!=='Overview')throw Error('Analyst did not land on overview');
  if(await page.locator('#account option').count()<2)throw Error('Assigned accounts did not load');
  const analystOrder=['Overview','Transactions','Risk Events','Review Queue','Quarantine','Insights','Reports','Upload Transactions','Ingestion Batches','Rejected Uploads','Notifications'];
  if(JSON.stringify((await page.locator('#navigation button').allTextContents()).slice(0,11))!==JSON.stringify(analystOrder))throw Error('Analyst navigation priority incorrect');
  const headings=await page.locator('#business-overview h3').allTextContents();
  if(headings.indexOf('Recent ingestion activity')<=headings.indexOf('Requires review'))throw Error('Ingestion must follow transaction and review activity');
  const overview=(await overviewResponse).data;const tiles=await page.locator('.business-metrics strong').allTextContents();
  const expectedMetrics=[overview.counts.transactions,...['Low','Medium','High'].map(level=>overview.risk_distribution.filter(r=>String(r.risk_level).toLowerCase()===level.toLowerCase()).reduce((n,r)=>n+Number(r.count),0)),overview.open_reviews,overview.quarantined_rows].map(String);
  if(JSON.stringify(tiles)!==JSON.stringify(expectedMetrics))throw Error('Business metrics differ from authorized backend results');
  await page.screenshot({path:path.join(output,'analyst-transactions-risk-overview.png'),fullPage:true});

  await page.locator('#navigation').getByRole('button',{name:'Upload Transactions',exact:true}).click();
  if(!(await page.locator('#csv-contract').innerText()).includes('source_system'))throw Error('Current CSV contract missing');
  async function admit(input,expected,screenshot){
   await page.locator('#csv-file').setInputFiles(input);
   await page.getByRole('button',{name:'Validate and process file',exact:true}).click();
   await page.waitForFunction(text=>document.querySelector('#upload-notice-message').textContent.includes(text),expected);
   await page.getByRole('button',{name:'Validate and process file',exact:true}).waitFor({state:'visible'});
   await page.waitForFunction(()=>!document.querySelector('#upload-form button').disabled);
   await page.screenshot({path:path.join(output,screenshot),fullPage:true});
  }
  const fixtures=process.env.FINTRUST_DATASET_FIXTURES;
  if(!fixtures)throw Error('Actual derived fixtures required');
  await admit({name:'wrong.csv',mimeType:'text/csv',buffer:Buffer.from('wrong,headers\n1,2')},'File rejected.','invalid-file-rejection.png');
  await page.locator('#navigation').getByRole('button',{name:'Overview',exact:true}).click();
  await page.locator('#upload-notice').waitFor({state:'visible'});
  if(!(await page.locator('#upload-notice-message').textContent()).includes('File rejected.'))throw Error('Serious notice lost on navigation');
  await page.getByRole('button',{name:'Acknowledge',exact:true}).click();await page.locator('#upload-notice').waitFor({state:'hidden'});
  await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();
  await admit(path.join(fixtures,'fintrust_release1_transactions_A.csv'),'29 accepted, 12 quarantined, 1 duplicates','A-upload-warning.png');

  const outcomes=['View accepted transactions','Review quarantined rows','View risk events','View batch details'];
  if(JSON.stringify(await page.locator('#upload-notice-message button').allTextContents())!==JSON.stringify(outcomes))throw Error('Upload outcome action order incorrect');
  if(!await page.locator('#upload-notice').getByRole('button',{name:'View batch details',exact:true}).evaluate(n=>n.classList.contains('secondary-action')))throw Error('Batch action must be secondary');
  for(const [label,target] of [['View accepted transactions','Transactions'],['Review quarantined rows','Quarantine'],['View risk events','Risk Events']]){await page.locator('#upload-notice').getByRole('button',{name:label,exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.locator('#title').innerText()!==target||await page.locator('#error').isVisible())throw Error('Upload business outcome navigation failed: '+target);}
await page.locator('#upload-notice').getByRole('button',{name:'View batch details',exact:true}).first().click();await page.locator('#batch-receipt').waitFor();if(!(await page.locator('#batch-receipt').innerText()).includes('Submission receipt'))throw Error('Mixed batch receipt unavailable');
  await page.locator('#batch-receipt').getByRole('button',{name:'View accepted transactions',exact:true}).click();await page.getByRole('button',{name:'Details / audit timeline'}).first().waitFor();
  await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();
  await admit(path.join(fixtures,'fintrust_release1_transactions_B.csv'),'7 accepted, 4 quarantined, 1 duplicates','B-upload-warning.png');
  if(!(await page.locator('#upload-notice-message').textContent()).includes('29 accepted, 12 quarantined'))throw Error('Unacknowledged A warning was lost after B');
  await admit(path.join(fixtures,'fintrust_release1_transactions_A.csv'),'File already processed','A-whole-file-replay.png');
  if(!await page.locator('#upload-panel').evaluate(n=>n.compareDocumentPosition(document.querySelector('#content'))&Node.DOCUMENT_POSITION_FOLLOWING))throw Error('Upload must precede history');
  if(/request [a-f0-9-]{36}/i.test(await page.locator('#upload-notice-message').innerText()))throw Error('Request ID exposed');
  await page.locator('#navigation').getByRole('button',{name:'Notifications',exact:true}).click();await page.getByRole('button',{name:'Open Ingestion Batches'}).first().waitFor();await page.screenshot({path:path.join(output,'notification-center.png'),fullPage:true});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.locator('#token').fill('a'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#workspace').waitFor({state:'visible'});
  const pages=['Overview','Rejected Uploads','Notifications','Transactions','Risk Events','Review Queue','Quarantine','Ingestion Batches','Reports','Insights','Accounts','Account History','Audit','Operations','Administration'];
  for(const name of pages){await page.locator('#navigation').getByRole('button',{name,exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.locator('#error').isVisible())throw Error(name+': '+await page.locator('#error').textContent());if(['Overview','Transactions','Risk Events','Review Queue','Quarantine','Ingestion Batches','Insights','Administration'].includes(name))await page.screenshot({path:path.join(output,name.toLowerCase().replaceAll(' ','-')+'.png'),fullPage:true});}
  await page.locator('#navigation').getByRole('button',{name:'Insights',exact:true}).click();await page.locator('.insight-chart').first().waitFor();
  if(await page.locator('.insight-chart').count()!==8)throw Error('Missing backend chart panels');
  if(!(await page.locator('#content').innerText()).includes('scored accepted'))throw Error('Unscored caveat missing');
  await page.locator('#insights-days').selectOption('all');await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
  const insightData=(await insightsResponse).data;const chartKeys=['activity','risk','rules','quality','reviews','accounts','cross_border','batch_outcomes'];
  for(let i=0;i<chartKeys.length;i++){const actual=await page.locator('.insight-chart').nth(i).locator('table tr').evaluateAll(rows=>rows.filter(r=>r.querySelector('td')).map(r=>Array.from(r.querySelectorAll('td')).map(c=>c.textContent)));const expected=insightData[chartKeys[i]].map(r=>[display.uuid(r.label)?display.reference("account_id",r.label):String(r.label),String(r.count)]);if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error('Chart table disagrees with backend: '+chartKeys[i]);}
  await page.screenshot({path:path.join(output,'insights-all-dates.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Reports',exact:true}).click();await page.getByRole('button',{name:'Download CSV · current page'}).waitFor();
  const downloadPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download CSV · current page'}).click();const download=await downloadPromise;await download.saveAs(path.join(output,'report-current-page.csv'));
  if(!fs.readFileSync(path.join(output,'report-current-page.csv'),'utf8').startsWith('account_id,currency,transactions,net_movement,gross_amount'))throw Error('Report export contract failed');
  const jsonPromise=page.waitForEvent('download');await page.getByRole('button',{name:'Download JSON · current page'}).click();const jsonDownload=await jsonPromise;await jsonDownload.saveAs(path.join(output,'report-current-page.json'));
  const exported=JSON.parse(fs.readFileSync(path.join(output,'report-current-page.json'),'utf8'));if(!exported.rows.length||exported.scope!=='Current authorized report page')throw Error('JSON report export invalid');
  const reportRows=(await reportResponse).data;if(JSON.stringify(exported.rows)!==JSON.stringify(reportRows))throw Error('JSON export disagrees with backend report');
  const csvText=fs.readFileSync(path.join(output,'report-current-page.csv'),'utf8');const lines=csvText.split(/\r?\n/);if(lines.length!==reportRows.length+1)throw Error('CSV row count disagrees with backend');
  for(let i=0;i<reportRows.length;i++){const cells=Array.from(lines[i+1].matchAll(/"((?:[^"]|"")*)"(?:,|$)/g),m=>m[1].replaceAll('""','"'));const expected=['account_id','currency','transactions','net_movement','gross_amount'].map(k=>String(reportRows[i][k]));if(JSON.stringify(cells)!==JSON.stringify(expected))throw Error('CSV values disagree with backend report');}

  await page.locator('#navigation').getByRole('button',{name:'Accounts',exact:true}).click();await page.getByRole('button',{name:'View history'}).first().click();await page.locator('#title').filter({hasText:'Account History'}).waitFor();if(!await page.locator('#account').inputValue())throw Error('Account history not scoped');
  await page.locator('#account').selectOption('');
  await page.locator('#navigation').getByRole('button',{name:'Administration',exact:true}).click();await page.getByRole('button',{name:'Add local user record'}).click();
  await page.locator('[name="username"]').fill('analyst02');await page.locator('[name="display_name"]').fill('Analyst Two');await page.locator('[name="role"]').selectOption('Risk/Compliance Analyst');await page.locator('[name="notes"]').fill('Synthetic presentation governance');await page.getByRole('button',{name:'Save local user',exact:true}).click();await page.getByRole('cell',{name:'analyst02',exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'administration-user-created.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Overview',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.metrics'));await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
  const metrics=await page.locator('.ingestion-metrics').innerText();const businessMetrics=await page.locator('.business-metrics').innerText();if(!businessMetrics.includes('Quarantined rows')||!businessMetrics.includes('16'))throw Error('Quarantine business total missing');if(!metrics.includes('36')||!metrics.includes('2'))throw Error('Actual A/B counters missing');
  await page.locator('#navigation').getByRole('button',{name:'Rejected Uploads',exact:true}).click();await page.getByRole('cell',{name:'INVALID_CSV_SCHEMA',exact:true}).waitFor();await page.screenshot({path:path.join(output,'rejected-uploads-history.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();await page.getByRole('button',{name:'Batch detail',exact:true}).first().click();await page.locator('#title').filter({hasText:'Batch Detail'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));await page.screenshot({path:path.join(output,'batch-reconciliation.png'),fullPage:true});
  await page.getByRole('button',{name:'Duplicates',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));await page.getByRole('cell',{name:'No additional ledger entry created',exact:true}).waitFor();await page.screenshot({path:path.join(output,'duplicate-occurrences.png'),fullPage:true});
  await page.getByRole('button',{name:'Failures',exact:true}).click();await page.getByText('No rows in this batch outcome.',{exact:true}).waitFor();
  await page.locator('#navigation').getByRole('button',{name:'Quarantine',exact:true}).click();await page.getByRole('button',{name:'Details',exact:true}).first().click();await page.getByRole('heading',{name:'Original safe values',exact:true}).waitFor();await page.screenshot({path:path.join(output,'quarantine-detail.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Audit',exact:true}).click();await page.getByRole('cell',{name:'ROW_ACCEPTED',exact:true}).first().waitFor();await page.screenshot({path:path.join(output,'audit-trail.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.locator('[data-filter="risk_level"]').selectOption('High');await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.getByRole('button',{name:'Details / audit timeline'}).first().click();await page.getByRole('heading',{name:'Risk assessment',exact:true}).waitFor();await page.screenshot({path:path.join(output,'high-risk-transaction.png'),fullPage:true});
  for(const [label,target] of [['View related risk event','Risk Events'],['View related review','Review Queue']]){await page.getByRole('button',{name:label,exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.locator('#title').innerText()!==target||await page.locator('#error').isVisible()||!(await page.locator('#status').innerText()).startsWith('Related to'))throw Error('Related transaction investigation failed: '+target);await page.getByRole('button',{name:'Back to transaction',exact:true}).click();}
  await page.getByRole('button',{name:'View source batch',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.locator('#error').isVisible()||await page.locator('#title').innerText()!=='Batch Detail')throw Error('Transaction source batch link failed');

  await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.locator('[data-filter="risk_level"]').selectOption('');
  await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.locator('[data-filter="source_id"]').fill('TX-DOUBLE-002');await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.getByRole('button',{name:'Details / audit timeline'}).first().click();await page.getByRole('heading',{name:'Possible duplicate charge · distinct accepted ledger entries',exact:true}).waitFor();await page.getByRole('cell',{name:'TX-DOUBLE-001',exact:true}).waitFor();await page.screenshot({path:path.join(output,'possible-duplicate-charge.png'),fullPage:true});await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.locator('[data-filter="source_id"]').fill('');
  await page.locator('#navigation').getByRole('button',{name:'Review Queue',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.getByRole('button',{name:'Open action'}).count())throw Error('Admin can make compliance decisions');await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();if(await page.locator('#upload-panel').isVisible())throw Error('Admin upload exposed');await page.locator('#navigation').getByRole('button',{name:'Operations',exact:true}).click();if(await page.locator('#operations-actions').isVisible())throw Error('Admin recovery exposed');
  await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.getByRole('button',{name:'Details / audit timeline'}).first().click();await page.locator('#title').filter({hasText:'Transaction Detail'}).waitFor();
  await page.screenshot({path:path.join(output,'release1-transaction-detail.png'),fullPage:true});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.locator('#login').waitFor({state:'visible'});
  await page.locator('#token').fill('b'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#workspace').waitFor({state:'visible'});
  if(await page.locator('#navigation').getByRole('button',{name:'Operations',exact:true}).count()||await page.locator('#navigation').getByRole('button',{name:'Administration',exact:true}).count())throw Error('Analyst sees technical/governance navigation');
  await page.locator('#navigation').getByRole('button',{name:'Review Queue',exact:true}).click();await page.locator('#filter-status').fill('OPEN');await page.getByRole('button',{name:'Refresh',exact:true}).click();const reviewId=await page.getByRole('button',{name:'Open action'}).first().locator('xpath=ancestor::tr').locator('td').filter({hasText:/^RISK-\d+$/}).innerText();if(!/^RISK-\d+$/.test(reviewId))throw Error('Review reference is not readable');await page.getByRole('button',{name:'Open action'}).first().click();
  if(await page.locator('#action-title').innerText()!==`Review ${reviewId}`)throw Error('Review heading does not match selected record');await page.locator('#notes').fill('Analyst investigation started');await page.getByRole('button',{name:'Submit',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#submit-action').disabled&&document.querySelector('#action').hidden);
  await page.locator('#filter-status').fill('UNDER_REVIEW');await page.getByRole('button',{name:'Refresh',exact:true}).click();await page.locator('#content tr').filter({has:page.getByRole('cell',{name:reviewId,exact:true})}).getByRole('button',{name:'Open action'}).click();await page.locator('#action-kind').selectOption('CLEARED');await page.locator('#resolution').selectOption('VALID_ACTIVITY');await page.locator('#notes').fill('Verified synthetic activity against source evidence');await page.getByRole('button',{name:'Submit',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#submit-action').disabled&&document.querySelector('#action').hidden);if(await page.locator('#error').isVisible())throw Error(await page.locator('#error').innerText());
  await page.locator('#filter-status').fill('CLEARED');await page.getByRole('button',{name:'Refresh',exact:true}).click();await page.getByRole('cell',{name:reviewId,exact:true}).waitFor();await page.screenshot({path:path.join(output,'analyst-review-cleared.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Quarantine',exact:true}).click();await page.locator('#content tr').filter({has:page.getByRole('cell',{name:'ZERO_AMOUNT',exact:true})}).getByRole('button',{name:'Open action'}).first().click();await page.waitForFunction(()=>document.querySelector('#candidate').value.trim().startsWith('{')&&!document.querySelector('#action').hidden);const corrected=JSON.parse(await page.locator('#candidate').inputValue());corrected.amount='15.00';await page.locator('#candidate').fill(JSON.stringify(corrected));await page.locator('#notes').fill('Corrected source amount; worker must revalidate and deduplicate');await page.getByRole('button',{name:'Submit',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#submit-action').disabled&&document.querySelector('#action').hidden);if(await page.locator('#error').isVisible())throw Error(await page.locator('#error').innerText());await page.getByRole('cell',{name:'RESUBMITTED',exact:true}).waitFor();await page.screenshot({path:path.join(output,'analyst-quarantine-resubmitted.png'),fullPage:true});
  await page.route('**/v1/workflows/transactions?**',async route=>{await new Promise(resolve=>setTimeout(resolve,500));await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'service temporarily unavailable'})});});await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.locator('#status').filter({hasText:'Loading'}).waitFor();await page.locator('#error').waitFor({state:'visible'});if((await page.locator('#content').innerText()).trim())throw Error('Stale data remains on API error');await page.screenshot({path:path.join(output,'api-unavailable.png'),fullPage:true});await page.unroute('**/v1/workflows/transactions?**');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.locator('#token').fill('c'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#workspace').waitFor({state:'visible'});
  await page.locator('#navigation').getByRole('button',{name:'Review Queue',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
  if(await page.getByRole('button',{name:'Open action'}).count())throw Error('Auditor sees mutation buttons');
  await page.screenshot({path:path.join(output,'release1-auditor-review-queue.png'),fullPage:true});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.locator('#token').fill('d'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#workspace').waitFor({state:'visible'});
  await page.locator('#title').filter({hasText:'Operations'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
  if(await page.locator('#navigation').getByRole('button',{name:'Review Queue',exact:true}).count())throw Error('Maintainer sees compliance page');
  await page.locator('#operations-actions').waitFor({state:'visible'});
  if(await page.locator('#paging').isVisible())throw Error('Operations incorrectly shows row pagination');
  const operationsText=await page.locator('#content').innerText();
  if(operationsText.includes('NaN')||operationsText.includes('UNDECLARED')||!/[a-f0-9]{40}/.test(operationsText))throw Error('Operations source/pagination evidence is invalid');

  await page.screenshot({path:path.join(output,'release1-maintainer-operations.png'),fullPage:true});
  const denied=await page.evaluate(async()=>{const r=await fetch('/v1/reviews/1/transition',{method:'POST',headers:{Authorization:'Bearer '+'d'.repeat(64),'Content-Type':'application/json'},body:'{}'});return r.status;});if(denied!==403)throw Error('Maintainer mutation was not denied by backend');
  // Hold an old Admin detail response until a different role is signed in.
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.locator('#token').fill('a'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.waitForFunction(()=>!!document.querySelector('.metrics'));
  let releaseOld,observedOld,finishedOld;const hold=new Promise(resolve=>releaseOld=resolve);const observed=new Promise(resolve=>observedOld=resolve);const finished=new Promise(resolve=>finishedOld=resolve);
  await page.route('**/v1/transactions/*',async route=>{const response=await route.fetch();observedOld();await hold;await route.fulfill({response});finishedOld();});
  await page.locator('#content').getByRole('button',{name:'Details',exact:true}).first().click();await observed;
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.locator('#token').fill('d'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#title').filter({hasText:'Operations'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));releaseOld();await finished;await page.waitForTimeout(250);
  if((await page.locator('#title').innerText())!=='Operations'||await page.getByRole('heading',{name:'Immutable transaction facts',exact:true}).count())throw Error('Old-role response leaked after sign-out');await page.unroute('**/v1/transactions/*');
  // Final Analyst/Auditor presentation checks retain actual backend token switching.
  for(const [user,key] of [['analyst01','b'],['auditor01','c']]){
    await page.getByRole('button',{name:'Sign out',exact:true}).click();
    await page.locator('#token').fill(key.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.locator('#workspace').waitFor({state:'visible'});await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
    if(!(await page.locator('#identity').innerText()).startsWith(user))throw Error('Actual identity not switched');
    const opts=await page.locator('#account option').evaluateAll(xs=>xs.map(x=>({label:x.textContent,value:x.value})));
    if(!opts.slice(1).every(x=>x.label.startsWith('ACC-')&&display.uuid(x.value)))throw Error('Account labels/UUID transport changed');
    await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
    const refs=await page.locator('#content td[data-internal-id]').evaluateAll(xs=>xs.map(x=>({label:x.textContent,id:x.dataset.internalId})));
    if(!refs.length||refs.some(x=>x.label===x.id)||!refs.some(x=>x.label.startsWith('TX-')))throw Error('Primary table is UUID-heavy');
    for(let pageNumber=0;pageNumber<8&&!(await page.locator('#content').innerText()).includes('Not assessed');pageNumber++){
      if(!await page.locator('#next').isVisible()||await page.locator('#next').isDisabled())break;
      await page.locator('#next').click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
    }
    if(!(await page.locator('#content').innerText()).includes('Not assessed'))throw Error('Historical risk was not clearly labelled');
    await page.screenshot({path:path.join(output,user+'-historical-transactions.png'),fullPage:true});
    await page.locator('#navigation').getByRole('button',{name:'Insights',exact:true}).click();await page.locator('.insight-chart').first().waitFor();
    await page.locator('#insights-days').selectOption('all');await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
    const data=(await insightsResponse).data;
    for(let i=0;i<chartKeys.length;i++){
      const actual=await page.locator('.insight-chart').nth(i).locator('table tr').evaluateAll(rs=>rs.filter(x=>x.querySelector('td')).map(x=>Array.from(x.querySelectorAll('td')).map(c=>c.textContent)));
      const expected=data[chartKeys[i]].map(x=>[display.uuid(x.label)?display.reference('account_id',x.label):String(x.label),String(x.count)]);
      if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error(user+' chart mismatch '+chartKeys[i]);
    }
    await page.screenshot({path:path.join(output,user+'-insights-verified.png'),fullPage:true});
    await page.locator('#navigation').getByRole('button',{name:'Reports',exact:true}).click();await page.getByRole('button',{name:'Download CSV · current page'}).waitFor();
    if(user==='auditor01'){
      for(const target of ['Review Queue','Quarantine','Ingestion Batches']){await page.locator('#navigation').getByRole('button',{name:target,exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.getByRole('button',{name:/Open action|Correct \/ reject|Validate and process file/}).count())throw Error('Auditor mutation control visible');}
      const status=await page.evaluate(async()=>{const r=await fetch('/v1/upload',{method:'POST',headers:{Authorization:'Bearer '+'c'.repeat(64)}});return r.status;});if(status!==403)throw Error('Auditor backend upload not denied');
    }
    await page.route('**/v1/release1/insights?**',route=>route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({error:'Not Found',detail:'unsafe provider detail'})}));
    await page.locator('#navigation').getByRole('button',{name:'Insights',exact:true}).click();await page.locator('#error').waitFor({state:'visible'});
    if(!(await page.locator('#error').innerText()).includes('Refresh and try again'))throw Error('Insight error lacks recovery');
    await page.locator('#navigation').getByRole('button',{name:'Notifications',exact:true}).click();
    const notices=await page.locator('#content').innerText();if(/Not Found|unsafe provider|\bERROR\b/.test(notices)||!notices.includes('Insight unavailable'))throw Error('Technical notification leaked');
    await page.unroute('**/v1/release1/insights?**');
    await page.locator('#navigation').getByRole('button',{name:'Insights',exact:true}).click();await page.locator('.insight-chart').first().waitFor();
    await page.route('**/v1/release1/overview',route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"backend failed"}'}));
    await page.locator('#navigation').getByRole('button',{name:'Overview',exact:true}).click();await page.locator('#error').waitFor({state:'visible'});
    if((await page.locator('.metrics strong').allTextContents()).some(x=>x!=='Unavailable'))throw Error('Metric failure silently became zero');
    await page.unroute('**/v1/release1/overview');await page.getByRole('button',{name:'Refresh',exact:true}).last().click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));
    if(await page.locator('#error').isVisible())throw Error('Metric refresh did not recover');
    await page.screenshot({path:path.join(output,user+'-overview.png'),fullPage:true});
  }
  await page.route('**/v1/release1/overview',route=>route.fulfill({status:401,contentType:'application/json',body:'{"error":"authentication required"}'}));
  await page.locator('#navigation').getByRole('button',{name:'Overview',exact:true}).click();await page.getByRole('heading',{name:'Session expired',exact:true}).waitFor();
  if(!(await page.locator('#session-message').innerText()).includes('Sign in again'))throw Error('Session recovery missing');
  if((await page.locator('body').innerText()).includes('401'))throw Error('Raw HTTP error leaked');
  await page.unroute('**/v1/release1/overview');await page.locator('#token').fill('b'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#workspace').waitFor({state:'visible'});
  await page.locator('#navigation').getByRole('button',{name:'Upload Transactions',exact:true}).click();
  await page.route('**/v1/upload',route=>route.fulfill({status:401,contentType:'application/json',body:'{"error":"authentication required"}'}));
  await page.locator('#csv-file').setInputFiles(path.join(fixtures,'fintrust_release1_transactions_A.csv'));await page.getByRole('button',{name:'Validate and process file',exact:true}).click();
  await page.getByRole('heading',{name:'Session expired',exact:true}).waitFor();await page.screenshot({path:path.join(output,'session-expired.png'),fullPage:true});
  await page.unroute('**/v1/upload');
  if(errors.length)throw Error(errors.join('; '));
  fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify({status:'PASSED',analyst_navigation_priority_verified:true,business_metric_values_verified:true,upload_outcome_navigation_verified:true,batch_details_secondary_verified:true,related_risk_review_and_source_batch_verified:true,root_workspace_verified:true,analyst_upload_receipt_link_verified:true,session_expiry_on_read_and_upload_verified:true,source_commit:process.env.FINTRUST_RELEASE_COMMIT,browser:executablePath,pages:['Login',...pages,'Transaction Detail','Batch Detail','Quarantine Detail'],dataset_sequence:'A -> B -> exact A replay',charts_verified:8,analyst_and_auditor_chart_values_verified:true,display_uuid_transport_verified:true,metric_error_vs_zero_verified:true,friendly_insight_failure_recovery_verified:true,role_switch_method:"Sign out and backend-authenticated token sign in",user_creation_audited:true,report_csv_verified:true,report_json_verified:true,account_history_navigation_verified:true,admin_compliance_actions:0,upload_counts:{A:{accepted:29,quarantined:12,duplicates:1},B:{accepted:7,quarantined:4,duplicates:1}},invalid_file_rejected:true,notice_persists_until_acknowledged:true,review_mutation:'OPEN -> UNDER_REVIEW -> CLEARED',quarantine_mutation:'RESUBMITTED (worker revalidation pending)',roles_verified:['Admin','Risk/Compliance Analyst','Read-only/Auditor','Maintainer'],loading_error_empty_verified:true,old_role_response_discarded:true,auditor_mutation_buttons:0,maintainer_compliance_pages:0,maintainer_technical_actions_visible:true,page_errors:errors,aws_access:false},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
