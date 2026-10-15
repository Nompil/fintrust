'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.FINTRUST_PLAYWRIGHT_MODULE);

(async () => {
  const origin = process.argv[2], out = process.argv[3];
  assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
  const input = JSON.parse(fs.readFileSync(path.join(out, 'inputs.json'), 'utf8'));
  const executablePath = [chromium.executablePath(), 'C:/Program Files/Google/Chrome/Application/chrome.exe']
    .find(candidate => fs.existsSync(candidate));
  const browser = await chromium.launch({headless: true, executablePath, args: ['--disable-background-networking']});
  const errors = [], writes = [], checks = [];
  try {
    const context = await browser.newContext({viewport: {width: 1366, height: 950}});
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const p = await context.newPage();
    p.on('pageerror', error => errors.push(error.message));
    p.on('request', request => {if (request.method() === 'POST') writes.push(new URL(request.url()).pathname);});
    async function ready() {
      await p.waitForFunction(() => !document.querySelector('#status').textContent.startsWith('Loading'));
      await assert.equal(await p.locator('#error').isVisible(), false, await p.locator('#error').textContent());
    }
    async function login(key = '2') {
      await p.goto(origin + '/release1');
      await p.locator('#token').fill(key.repeat(64));
      await p.locator('#signin').click();
      await p.locator('#workspace').waitFor({state: 'visible'});
      await ready();
    }
    async function nav(name) {
      const button = p.locator('#navigation').getByRole('button', {name, exact: true});
      if (!await button.isVisible()) await p.getByRole('button', {name: 'Toggle navigation', exact: true}).click();
      await button.click();
      await ready();
    }
    async function api(route, key = '2') {
      const response = await context.request.get(origin + route, {headers: {Authorization: 'Bearer ' + key.repeat(64)}});
      assert.equal(response.status(), 200, route);
      return response.json();
    }
    async function screen(name, fullPage = true) {
      await p.screenshot({path: path.join(out, name + '.png'), fullPage});
      if (['sla-workload', 'filtered-quarantined-rows', 'journey-medium-decision',
           'journey-high-decision', 'insights-evidence-scope'].includes(name)) {
        await p.setViewportSize({width: 390, height: 950});
        assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
          'Workspace overflow at mobile width: ' + name);
        await p.screenshot({path: path.join(out, name + '-390.png'), fullPage});
        await p.setViewportSize({width: 1366, height: 950});
      }
    }
    async function transaction(source) {
      await nav('Transactions');
      await p.locator('[data-filter=source_id]').fill(source);
      await p.getByRole('button', {name: 'Apply filters', exact: true}).click();
      await ready();
      const evidence = (await api('/v1/workflows/transactions?source_id=' + encodeURIComponent(source))).data;
      assert.equal(evidence.length, 1, 'Expected one API ledger transaction for ' + source);
      const alias = await p.evaluate(id => FinTrustDisplay.reference('tx_id', id), evidence[0].tx_id);
      const rows = p.locator('#content tr').filter({hasText: alias});
      assert.equal(await rows.count(), 1, 'Expected one ledger transaction for ' + source);
      return rows;
    }
    async function investigate(source) {
      const rows = await transaction(source);
      await rows.getByRole('button', {name: 'Investigate', exact: true}).click();
      await p.locator('#investigation-drawer').getByRole('heading', {name: 'NEXT STEPS', exact: true}).waitFor();
      return p.locator('#investigation-drawer');
    }
    async function decide(source, decision, note) {
      const transactionEvidence = (await api('/v1/workflows/transactions?source_id=' + encodeURIComponent(source))).data[0];
      const reviewEvidence = (await api('/v1/risk-events/' + transactionEvidence.risk_event_id)).data;
      assert.equal(reviewEvidence.review_status, 'OPEN');
      assert.equal(reviewEvidence.reviewer_subject, null);
      assert.equal(reviewEvidence.sla_seconds, source === 'JOURNEY-MEDIUM' ? 86400 : 14400);
      assert.equal(reviewEvidence.alert.delivery_state, source === 'JOURNEY-MEDIUM' ? 'NOT_REQUIRED' : 'PENDING');
      const drawer = await investigate(source);
      await drawer.getByRole('button', {name: 'Claim Review', exact: true}).click();
      await drawer.locator('textarea').waitFor({state: 'visible'});
      await drawer.locator('textarea').fill('Investigation note: merchant and source evidence checked');
      const noteResponse = p.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/notes') && r.status() === 200);
      await drawer.getByRole('button', {name: 'Save investigation', exact: true}).click();
      await noteResponse;
      await drawer.getByText('Investigation note: merchant and source evidence checked', {exact: true}).waitFor();
      await p.getByLabel('Investigation action', {exact: true}).selectOption(decision);
      await drawer.locator('textarea').fill(note);
      const outcome = p.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/transition') && r.status() === 200);
      await drawer.getByRole('button', {name: 'Save investigation', exact: true}).click();
      await outcome;
      await drawer.getByText(decision.replaceAll('_', ' '), {exact: true}).first().waitFor();
      await screen(source.toLowerCase() + '-decision');
      await p.keyboard.press('Escape');
    }

    await login();
    await p.locator('.my-day-strip').getByText('Overdue', {exact: true}).waitFor();
    const overview = await api('/v1/release1/overview');
    assert.equal(overview.data.reviews_over_sla, 1);
    await screen('sla-workload');
    checks.push('G: controlled SLA clock marks a HIGH review overdue without a decision or timestamp rewrite');

    await nav('Upload Transactions');
    await p.locator('#csv-file').setInputFiles({name: input.filename, mimeType: 'text/csv', buffer: Buffer.from(input.csv)});
    const submitted = p.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/v1/upload') && r.status() === 200);
    await p.locator('#process-file').click();
    const receipt = (await (await submitted).json()).data;
    await p.locator('#upload-notice').waitFor({state: 'visible'});
    assert.deepEqual(['rows_received', 'accepted', 'quarantined', 'duplicate', 'failed_technical', 'pending']
      .map(key => receipt.reconciliation[key]), [6, 3, 2, 1, 0, 0]);
    assert.match(await p.locator('#upload-notice').innerText(), /Processing completed.*attention required/i);
    assert.match(await p.locator('#upload-notice').innerText(), /one or more rows require attention/i);
    const counters = await api('/v1/batches/' + receipt.batch_id);
    const transactionsBefore = await api('/v1/workflows/transactions?limit=100');
    const reviewsBefore = await api('/v1/workflows/reviews?limit=100');
    const auditBefore = await api('/v1/audit-events?limit=100', '4');
    const postCount = writes.length;
    await p.locator('#acknowledge-upload').getByText('Mark as read', {exact: true}).waitFor();
    assert.match(await p.locator('#acknowledge-upload').getAttribute('title'), /does not approve transactions or change processing results/);
    await p.locator('#acknowledge-upload').click();
    assert.equal(await p.locator('#upload-notice').isVisible(), false);
    assert.equal(writes.length, postCount, 'Mark as read must not issue a backend mutation');
    assert.deepEqual(await api('/v1/batches/' + receipt.batch_id), counters);
    assert.deepEqual(await api('/v1/workflows/transactions?limit=100'), transactionsBefore);
    assert.deepEqual(await api('/v1/workflows/reviews?limit=100'), reviewsBefore);
    assert.deepEqual(await api('/v1/audit-events?limit=100', '4'), auditBefore);
    checks.push('Mark as read changes only session notification state, with unchanged processing, ledger and reviews');

    await nav('Processing History');
    const runAlias = await p.evaluate(id => FinTrustDisplay.reference('batch_id', id), receipt.batch_id);
    await p.locator('#content tr').filter({hasText: runAlias}).getByRole('button', {name: 'View processing details', exact: true}).click();
    await p.locator('#title').getByText('Processing Details', {exact: true}).waitFor();
    await p.getByRole('heading', {name: 'Row Outcomes', exact: true}).waitFor();
    for (const tab of ['All', 'Accepted', 'Quarantined', 'Duplicate', 'Failed', 'Pending']) {
      await p.locator('.tabs').getByRole('button', {name: tab, exact: true}).waitFor();
    }
    assert.match(await p.locator('#content').innerText(), /Received\s*=\s*Accepted\s*\+\s*Quarantined\s*\+\s*Duplicate\s*\+\s*Failed\s*\+\s*Pending/);
    for (const width of [1366, 390]) {
      await p.setViewportSize({width, height: 950});
      const filenameCell = p.locator('.processing-summary dd').filter({hasText: input.filename});
      await filenameCell.waitFor();
      const box = await filenameCell.boundingBox();
      assert.ok(box.width >= 180, 'Filename column collapsed into vertical characters at ' + width);
      assert.ok(box.height < 160, 'Filename wrapped into excessive lines at ' + width);
      const reason = p.locator('.processing-details > .table-scroll td:nth-child(3)').filter({hasText: 'INVALID_AMOUNT'}).first();
      const reasonBox = await reason.boundingBox();
      assert.ok(reasonBox.width >= 120, 'Validation reason column collapsed at ' + width);
      assert.ok(reasonBox.height < 100, 'Validation issue wrapped into vertical characters at ' + width);
      assert.equal(await reason.innerText(), 'INVALID_AMOUNT');
      assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      await screen('processing-details-' + width);
    }
    await p.setViewportSize({width: 1366, height: 950});
    await p.getByRole('button', {name: 'Review quarantined rows', exact: true}).click();
    await p.locator('#title').getByText('Quarantined Rows', {exact: true}).waitFor();
    const runContext = p.locator('#quarantined-run-context');
    assert.match(await runContext.innerText(), new RegExp(input.filename.replaceAll('.', '\\.')));
    assert.match(await runContext.innerText(), new RegExp(runAlias));
    assert.equal(await p.locator('#content .investigable-row').count(), 2);
    await screen('filtered-quarantined-rows');
    await p.getByRole('button', {name: 'Show all quarantined rows', exact: true}).click();
    await ready();
    assert.equal(await p.locator('#content .investigable-row').count(), 3);
    assert.equal(await p.locator('#quarantined-run-context').count(), 0);
    checks.push('Upload lineage: run-filtered quarantine, clear filter, correct source count, long filename and all outcome tabs');

    const cases = (await api('/v1/workflows/quarantine?batch_id=' + receipt.batch_id)).data;
    const corrected = cases.find(item => item.source_row === 5), rejected = cases.find(item => item.source_row === 6);
    assert.ok(corrected && rejected);
    async function quarantineCase(item) {
      await nav('Quarantined Rows');
      const alias = await p.evaluate(id => FinTrustDisplay.reference('quarantine_id', id), item.quarantine_id);
      await p.locator('#content tr').filter({hasText: alias}).getByRole('button', {name: 'View issue', exact: true}).click();
      await p.locator('#investigation-drawer').getByText('Original safe values', {exact: true}).waitFor();
      return p.locator('#investigation-drawer');
    }
    let drawer = await quarantineCase(corrected);
    assert.match(await drawer.innerText(), /INVALID_AMOUNT/);
    await drawer.getByRole('button', {name: 'Correct and resubmit', exact: true}).click();
    await p.locator('#correction-amount').fill('25.00');
    await p.locator('#notes').fill('Correct amount after checking immutable original source');
    await screen('quarantine-correction');
    await p.locator('#submit-action').click();
    await drawer.getByText('Correct amount after checking immutable original source', {exact: true}).waitFor();
    for (let attempt = 0; attempt < 40 && !await drawer.getByRole('button', {name: 'Resulting transaction', exact: true}).count(); attempt++) {
      await drawer.getByRole('button', {name: 'Refresh recovery outcome', exact: true}).click();
      await p.waitForTimeout(100);
    }
    await drawer.getByRole('button', {name: 'Resulting transaction', exact: true}).waitFor();
    await screen('quarantine-corrected-result');
    await p.keyboard.press('Escape');
    drawer = await quarantineCase(rejected);
    await drawer.getByRole('button', {name: 'Reject row', exact: true}).click();
    await p.locator('#notes').fill('Unrecoverable source evidence; reject without ledger entry');
    await p.locator('#submit-action').click();
    await drawer.getByText('Rejected — no ledger entry. Original evidence retained.', {exact: true}).waitFor();
    await screen('quarantine-rejected-evidence');
    await p.keyboard.press('Escape');
    checks.push('D/E: permitted correction revalidates to ledger; rejection retains source and notes without ledger entry');

    const low = await transaction('JOURNEY-LOW');
    assert.match(await low.innerText(), /0\s*%/);
    assert.match(await low.innerText(), /No review required/);
    await low.getByRole('button', {name: 'View details', exact: true}).click();
    await p.getByRole('heading', {name: 'Transaction lifecycle', exact: true}).waitFor();
    await p.locator('.recorded-lifecycle .case-journey li').last().waitFor();
    const lowEvidence=(await api('/v1/workflows/transactions?source_id=JOURNEY-LOW')).data[0];const lowJourney=(await api('/v1/transactions/'+lowEvidence.tx_id+'/lifecycle')).data.source_journey;assert.equal(await p.locator('.recorded-lifecycle .case-journey li').count(),lowJourney.stages.length);
    assert.match(await p.locator('.recorded-lifecycle').innerText(), /Assessed[\s\S]*Stored/);
    assert.equal((await p.locator('.recorded-lifecycle').innerText()).includes('Loading recorded events'), false);
    assert.match(await p.locator('.transaction-detail').innerText(), /Not required/);
    assert.equal(await p.getByRole('button', {name: 'Claim Review', exact: true}).count(), 0);
    await screen('low-lifecycle');
    checks.push('A: LOW is stored, scored 0%, requires no review or alert, and remains reportable');
    await decide('JOURNEY-MEDIUM', 'CLEARED', 'Valid activity supported by merchant and source evidence');
    checks.push('B: MEDIUM claim, 24h policy, attributed note, clear and immutable history');
    await decide('JOURNEY-HIGH', 'CONFIRMED_RISK', 'Suspicious activity supported by recorded risk evidence');
    checks.push('C: HIGH claim, independent pending alert, 4h policy, attributed note and confirm risk');

    await nav('Transactions');
    await p.locator('[data-filter=source_id]').fill('');
    await p.locator('[data-filter=tx_id]').fill(input.historical_tx);
    await p.getByRole('button', {name: 'Apply filters', exact: true}).click();
    await ready();
    assert.match(await p.locator('#content').innerText(), /Historical — not scored/);
    assert.match(await p.locator('#content').innerText(), /Historical — no review record/);
    await p.getByRole('button', {name: 'View details', exact: true}).click();
    assert.match(await p.locator('.transaction-detail').innerText(), /Historical — not scored/);
    assert.equal(await p.locator('.transaction-detail .risk-score:not(.unassessed)').count(), 0);
    await screen('historical-no-fabricated-score');
    checks.push('F: known seed provenance labels historical without inventing assessment or review');

    await nav('Review Queue');
    for (const label of ['My Work', 'Unassigned', 'All visible']) await p.locator('.case-view-tabs').getByRole('button', {name: label, exact: true}).waitFor();
    await p.getByRole('button', {name: 'Overdue', exact: true}).click();
    await ready();
    assert.match(await p.locator('#content').innerText(), /Overdue/);
    await screen('review-queue-overdue');
    await nav('Insights');
    await p.locator('#insights-days').selectOption('all');
    await p.getByRole('button', {name: 'Apply analytical filters', exact: true}).click();
    await ready();
    for (const heading of ['WHAT HAPPENED?', 'WHERE IS THE RISK?', 'WHAT NEEDS ATTENTION?', 'WHAT WAS THE OUTCOME?'])
      await p.getByRole('heading', {name: heading, exact: true}).waitFor();
    assert.match(await p.locator('#content').innerText(), /SAST/);
    const aggregate = await api('/v1/release1/insights?days=all');
    assert.equal(aggregate.data.metrics.reviews_over_sla, 1);
    assert.equal(aggregate.data.metrics.high_risk_rate, 40);
    await p.locator('[data-insights-filter=risk_level]').selectOption('High');
    await p.locator('[data-insights-filter=country]').selectOption('US');
    await p.locator('#insights-days').selectOption('custom');
    await p.locator('[data-insights-filter=from]').fill('2026-10-09');
    await p.locator('[data-insights-filter=to]').fill('2026-10-10');
    await p.getByRole('button', {name: 'Apply analytical filters', exact: true}).click();
    await ready();
    await screen('insights-evidence-scope');
    const trend = p.locator('.insight-chart').filter({has: p.getByRole('heading',
      {name: 'HIGH-risk trend · SAST', exact: true})});
    const evidenceRequest = p.waitForResponse(r => new URL(r.url()).pathname === '/v1/workflows/transactions');
    await trend.getByRole('button', {name: 'Investigate these transactions', exact: true}).click();
    const evidenceUrl = new URL((await evidenceRequest).url());
    assert.equal(evidenceUrl.searchParams.get('risk_level'), 'High', 'Trend must not send a date as risk_level');
    assert.equal(evidenceUrl.searchParams.get('country'), 'US');
    assert.equal(evidenceUrl.searchParams.get('to_exclusive'), '1');
    assert.equal(evidenceUrl.searchParams.get('from'), '2026-10-08T22:00:00.000Z');
    assert.equal(evidenceUrl.searchParams.get('to'), '2026-10-09T22:00:00.000Z');
    await ready();
    assert.equal(await p.locator('#title').innerText(), 'Transactions');
    assert.match(await p.locator('#evidence-scope').innerText(), /High/);
    assert.match(await p.locator('#evidence-scope').innerText(), /US/);
    assert.equal(await p.locator('#content .investigable-row').count(), 1);
    await nav('Reports');
    assert.match(await p.locator('#content').innerText(), /ZAR/);
    await p.getByRole('button', {name: 'Download CSV · current page', exact: true}).waitFor();
    checks.push('Scoped Insights denominator excludes seed history, SAST labels and matching investigation drill down; report includes ledger');

    const mutations = [
      ['/v1/reviews/' + input.sla_event + '/assignment', {request_id: crypto.randomUUID(), expected_version: 1, assignee: 'auditor01', notes: 'Denied role mutation'}],
      ['/v1/reviews/' + input.sla_event + '/transition', {request_id: crypto.randomUUID(), expected_version: 1, status: 'CLEARED', resolution_code: 'VALID_ACTIVITY', notes: 'Denied role decision'}],
      ['/v1/quarantine/' + rejected.quarantine_id + '/corrections', {request_id: crypto.randomUUID(), action: 'REJECT', notes: 'Denied role correction'}],
    ];
    for (const key of ['4', '5']) for (const [route, data] of mutations) {
      const denied = await context.request.post(origin + route, {headers: {Authorization: 'Bearer ' + key.repeat(64)}, data});
      assert.equal(denied.status(), 403, 'Auditor/Maintainer financial mutation denial');
    }
    const adminDenied = await context.request.post(origin + mutations[1][0], {headers: {Authorization: 'Bearer ' + '1'.repeat(64)}, data: mutations[1][1]});
    assert.equal(adminDenied.status(), 403);
    await login('4');
    await nav('Quarantined Rows');
    assert.equal(await p.getByRole('button', {name: 'Reject row', exact: true}).count(), 0);
    await p.setViewportSize({width: 390, height: 844});
    assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await screen('auditor-read-only-mobile');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(out, 'browser-result.json'), JSON.stringify({status: 'PASSED', scenarios: [...'ABCDEFG'], checks,
      batch_id: receipt.batch_id, corrected_case: corrected.quarantine_id, rejected_case: rejected.quarantine_id,
      sla_clock: input.sla_clock, external_network: 'blocked', aws_transport: 'mocked', page_errors: errors}, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error.stack); process.exit(1);});
