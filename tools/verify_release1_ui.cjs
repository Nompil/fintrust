// Automated local browser acceptance test. All navigation/network stays loopback.
const fs=require('node:fs');
const path=require('node:path');
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
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/release1');
  await page.locator('#token').fill('a'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.locator('#workspace').waitFor({state:'visible'});await page.locator('#status').filter({hasText:'Current assigned-account data'}).waitFor();
  await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();
  async function admit(input,expected,screenshot){
   await page.locator('#csv-file').setInputFiles(input);
   await page.getByRole('button',{name:'Upload and process locally',exact:true}).click();
   await page.waitForFunction(text=>document.querySelector('#upload-notice-message').textContent.includes(text),expected);
   await page.getByRole('button',{name:'Upload and process locally',exact:true}).waitFor({state:'visible'});
   await page.waitForFunction(()=>!document.querySelector('#upload-form button').disabled);
   await page.screenshot({path:path.join(output,screenshot),fullPage:true});
  }
  const fixtures=process.env.FINTRUST_DATASET_FIXTURES;
  if(!fixtures)throw Error('Actual derived fixtures required');
  await admit({name:'wrong.csv',mimeType:'text/csv',buffer:Buffer.from('wrong,headers\n1,2')},'Upload rejected:','invalid-file-rejection.png');
  await page.locator('#navigation').getByRole('button',{name:'Overview',exact:true}).click();
  await page.locator('#upload-notice').waitFor({state:'visible'});
  if(!(await page.locator('#upload-notice-message').textContent()).includes('Upload rejected:'))throw Error('Serious notice lost on navigation');
  await page.getByRole('button',{name:'Acknowledge',exact:true}).click();await page.locator('#upload-notice').waitFor({state:'hidden'});
  await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();
  await admit(path.join(fixtures,'fintrust_release1_transactions_A.csv'),'29 accepted, 12 quarantined, 1 duplicates','A-upload-warning.png');
  await admit(path.join(fixtures,'fintrust_release1_transactions_B.csv'),'7 accepted, 4 quarantined, 1 duplicates','B-upload-warning.png');
  if(!(await page.locator('#upload-notice-message').textContent()).includes('29 accepted, 12 quarantined'))throw Error('Unacknowledged A warning was lost after B');
  await admit(path.join(fixtures,'fintrust_release1_transactions_A.csv'),'File already processed','A-whole-file-replay.png');
  const pages=['Overview','Rejected Uploads','Notifications','Transactions','Risk Events','Review Queue','Quarantine','Ingestion Batches','Reports','Accounts','Account History','Audit','Operations','Administration'];
  for(const name of pages){await page.locator('#navigation').getByRole('button',{name,exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));if(await page.locator('#error').isVisible())throw Error(name+': '+await page.locator('#error').textContent());if(['Transactions','Risk Events','Review Queue','Quarantine','Ingestion Batches'].includes(name))await page.screenshot({path:path.join(output,name.toLowerCase().replaceAll(' ','-')+'.png'),fullPage:true});}
  await page.locator('#navigation').getByRole('button',{name:'Overview',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.metrics'));await page.screenshot({path:path.join(output,'overview.png'),fullPage:true});
  const metrics=await page.locator('.metrics').innerText();if(!metrics.includes('36')||!metrics.includes('16')||!metrics.includes('2'))throw Error('Actual A/B counters missing');
  await page.locator('#navigation').getByRole('button',{name:'Rejected Uploads',exact:true}).click();await page.getByRole('cell',{name:'INVALID_CSV_SCHEMA',exact:true}).waitFor();await page.screenshot({path:path.join(output,'rejected-uploads-history.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Ingestion Batches',exact:true}).click();await page.getByRole('button',{name:'Batch detail',exact:true}).first().click();await page.locator('#title').filter({hasText:'Batch Detail'}).waitFor();await page.waitForFunction(()=>!document.querySelector('#status').textContent.startsWith('Loading'));await page.screenshot({path:path.join(output,'batch-reconciliation.png'),fullPage:true});
  await page.getByRole('button',{name:'Duplicates',exact:true}).click();await page.getByRole('cell',{name:'No additional ledger entry created',exact:true}).waitFor();await page.screenshot({path:path.join(output,'duplicate-occurrences.png'),fullPage:true});
  await page.getByRole('button',{name:'Failures',exact:true}).click();await page.getByText('No matching records.',{exact:true}).waitFor();
  await page.locator('#navigation').getByRole('button',{name:'Quarantine',exact:true}).click();await page.getByRole('button',{name:'Details',exact:true}).first().click();await page.getByRole('heading',{name:'Original safe values',exact:true}).waitFor();await page.screenshot({path:path.join(output,'quarantine-detail.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Audit',exact:true}).click();await page.getByRole('cell',{name:'ROW_ACCEPTED',exact:true}).first().waitFor();await page.screenshot({path:path.join(output,'audit-trail.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Notifications',exact:true}).click();await page.getByRole('button',{name:'Open Ingestion Batches'}).first().waitFor();await page.screenshot({path:path.join(output,'notification-center.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.locator('[data-filter="risk_level"]').selectOption('High');await page.getByRole('button',{name:'Apply filters',exact:true}).click();await page.getByRole('button',{name:'Details / audit timeline'}).first().click();await page.getByRole('heading',{name:'Risk assessment',exact:true}).waitFor();await page.screenshot({path:path.join(output,'high-risk-transaction.png'),fullPage:true});
  await page.locator('[data-filter="risk_level"]').selectOption('');
  await page.locator('#navigation').getByRole('button',{name:'Review Queue',exact:true}).click();await page.locator('#content tr').filter({has:page.getByRole('cell',{name:'70',exact:true})}).getByRole('button',{name:'Open action'}).first().click();await page.locator('#notes').fill('Browser acceptance: assigned for investigation');await page.getByRole('button',{name:'Submit',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('#submit-action').disabled && document.querySelector('#action').hidden);
  if(await page.locator('#error').isVisible())throw Error(await page.locator('#error').textContent());
  await page.screenshot({path:path.join(output,'review-workflow.png'),fullPage:true});
  await page.locator('#navigation').getByRole('button',{name:'Transactions',exact:true}).click();await page.getByRole('button',{name:'Details / audit timeline'}).first().click();await page.locator('#title').filter({hasText:'Transaction Detail'}).waitFor();
  await page.screenshot({path:path.join(output,'release1-transaction-detail.png'),fullPage:true});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.locator('#login').waitFor({state:'visible'});
  await page.locator('#token').fill('b'.repeat(64));await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.locator('#workspace').waitFor({state:'visible'});
  if(await page.locator('#navigation').getByRole('button',{name:'Operations',exact:true}).count()||await page.locator('#navigation').getByRole('button',{name:'Administration',exact:true}).count())throw Error('Analyst sees technical/governance navigation');
  await page.locator('#navigation').getByRole('button',{name:'Review Queue',exact:true}).click();await page.locator('#filter-status').fill('OPEN');await page.getByRole('button',{name:'Refresh',exact:true}).click();await page.getByRole('button',{name:'Open action'}).first().click();
  const reviewId=(await page.locator('#action-title').innerText()).match(/Review (\d+)/)[1];await page.locator('#notes').fill('Analyst investigation started');await page.getByRole('button',{name:'Submit',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('#submit-action').disabled&&document.querySelector('#action').hidden);
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
  if(errors.length)throw Error(errors.join('; '));
  fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify({status:'PASSED',source_commit:process.env.FINTRUST_RELEASE_COMMIT,browser:executablePath,pages:['Login',...pages,'Transaction Detail','Batch Detail','Quarantine Detail'],dataset_sequence:'A -> B -> exact A replay',upload_counts:{A:{accepted:29,quarantined:12,duplicates:1},B:{accepted:7,quarantined:4,duplicates:1}},invalid_file_rejected:true,notice_persists_until_acknowledged:true,review_mutation:'OPEN -> UNDER_REVIEW -> CLEARED',quarantine_mutation:'RESUBMITTED (worker revalidation pending)',roles_verified:['Admin','Risk/Compliance Analyst','Read-only/Auditor','Maintainer'],loading_error_empty_verified:true,auditor_mutation_buttons:0,maintainer_compliance_pages:0,maintainer_technical_actions_visible:true,page_errors:errors,aws_access:false},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
