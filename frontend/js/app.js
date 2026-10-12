'use strict';
const $ = id => document.getElementById(id);
let offset = 0;
let cursors = [null];
let nextCursor = null;
function resetPages() { offset = 0; cursors = [null]; nextCursor = null; }
const limit = 10;
const money = n => {
  const [whole, fraction = ''] = String(n).split('.');
  return `${new Intl.NumberFormat('en-ZA').format(BigInt(whole))}.${fraction.padEnd(2, '0')}`;
};
function element(tag, text, className) { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; }
async function api(path, options) {
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('FinTrust could not connect. Check that the local server is running, then refresh.'); }
  let body;
  try { body = await response.json(); }
  catch { throw new Error('FinTrust received an unexpected response. Please try again.'); }
  if (!response.ok) {
    const message = response.status >= 500 ? 'The service is temporarily unavailable. Please try again.' : body.error || 'This request could not be completed.';
    throw new Error(`${response.status}: ${message}`);
  }
  return body;
}
function showError(error) { $('error').textContent = error.message; $('error').hidden = false; }
function chart(days) {
  const svg = $('trend'); svg.replaceChildren(); $('chart-data').replaceChildren();
  if (!days.length) { $('trend-caption').textContent = 'No transactions yet. Add a file to see activity here.'; return; }
  const max = Math.max(...days.map(d => d.transactions));
  const width = 630 / days.length;
  const shape = (tag, attrs, text) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    svg.append(node); return node;
  };
  [0, 0.5, 1].forEach(fraction => {
    const y = 175 - fraction * 145;
    shape('line', {x1: 40, y1: y, x2: 680, y2: y, stroke: '#e3e8e3', 'stroke-dasharray': '3 5'});
    shape('text', {x: 29, y: y + 4, 'text-anchor': 'end'}, Math.round(max * fraction));
  });
  days.forEach((d, i) => {
    const height = d.transactions / max * 145;
    const bar = shape('rect', {x: 45 + i * width, y: 175 - height, width: Math.max(1, width * 0.65), height, rx: 3});
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${d.day}: ${d.transactions} transactions`; bar.append(title);
    const row = document.createElement('tr'); row.append(element('td', d.day), element('td', d.transactions)); $('chart-data').append(row);
  });
  shape('text', {x: 40, y: 202}, days[0].day);
  shape('text', {x: 680, y: 202, 'text-anchor': 'end'}, days.at(-1).day);
  $('trend-caption').textContent = `${days.length} days with activity. Busiest day: ${max} transactions. Days without transactions are not shown.`;
}
let ledgerRequest = 0;
async function ledger() {
  const requestId = ++ledgerRequest;
  if (!$('account').value) {
    $('ledger').replaceChildren();
    const row = document.createElement('tr'); const cell = element('td', 'No accounts are available yet.'); cell.colSpan = 6; row.append(cell); $('ledger').append(row);
    $('previous').disabled = true; $('next').disabled = true; $('page-label').textContent = '';
    $('account-reference').textContent = ''; $('insight').textContent = 'No example score available.'; return;
  }
  $('account-reference').textContent = `Account reference: ${$('account').value}`;
  if ($('from').value && $('to').value && $('from').value > $('to').value) throw new Error('Choose an end date on or after the start date.');
  const params = new URLSearchParams({account_id: $('account').value, limit});
  if (cursors[offset / limit]) params.set('cursor', cursors[offset / limit]);
  if ($('from').value) params.set('from', `${$('from').value}T00:00:00Z`);
  if ($('to').value) params.set('to', `${$('to').value}T23:59:59.999999Z`);
  const result = await api(`/v1/transactions?${params}`); if (requestId !== ledgerRequest) return; $('ledger').replaceChildren();
  result.data.forEach(row => {
    const tr = document.createElement('tr');
    const when = new Date(row.tx_date).toLocaleString('en-GB', {timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'});
    const type = {debit: 'Payment out', credit: 'Payment in', transfer: 'Transfer'}[row.tx_type] || row.tx_type;
    [when, row.merchant || 'Not provided', type, money(row.amount), row.currency, row.cross_border ? 'International' : 'South Africa'].forEach((value, index) => {
      const cell = element('td', value); if (index === 3) cell.className = 'amount-cell';
      if (index === 2) cell.replaceChildren(element('span', value, 'type-label'));
      tr.append(cell);
    }); $('ledger').append(tr);
  });
  if (!result.data.length) { const td = element('td', 'No transactions match this account and date range. Try different dates.'); td.colSpan = 6; const tr = document.createElement('tr'); tr.append(td); $('ledger').append(tr); }
  $('page-label').textContent = result.data.length ? `Showing ${offset + 1}-${offset + result.data.length}` : 'No matching transactions';
  nextCursor = result.meta.next_cursor;
  $('previous').disabled = offset === 0; $('next').disabled = !nextCursor;
  try { const insight = await api(`/v1/insights?account_id=${encodeURIComponent($('account').value)}`); if (requestId !== ledgerRequest) return; $('insight').textContent = `Example score: ${insight.data.risk_score} out of 100, dated ${insight.data.score_date}. This is saved demonstration data.`; }
  catch (error) { if (requestId !== ledgerRequest) return; $('insight').textContent = error.message.startsWith('404:') ? 'No example score is available for this account today.' : 'The example score could not be loaded. Try refreshing the page.'; }
}
async function refresh() {
  $('error').hidden = true; $('refresh').disabled = true;
  try {
    const [health, overview, accounts] = await Promise.all([api('/v1/health'), api('/v1/overview'), api('/v1/accounts')]);
    $('health').textContent = health.db === 'ok' ? 'Connected' : 'Connection unavailable';
    const data = overview.data; $('total').textContent = data.counts.transactions.toLocaleString(); $('accounts-count').textContent = data.counts.active_accounts; $('cross-border').textContent = data.counts.cross_border;
    $('currency-totals').replaceChildren(); data.totals_by_currency.forEach(item => { const row = element('div', '', 'currency-line'); const label = element('div', item.currency); label.append(element('small', `${item.transactions} transactions`)); row.append(label, element('strong', money(item.gross_amount))); $('currency-totals').append(row); }); chart(data.daily_transactions);
    const selected = $('account').value; $('account').replaceChildren(); accounts.data.forEach((a, index) => { const type = a.account_type.replaceAll('_', ' '); const option = element('option', `Account ${index + 1} - ${type.charAt(0).toUpperCase() + type.slice(1)} (${a.account_id.slice(-4)})`); option.value = a.account_id; $('account').append(option); });
    if (accounts.data.some(a => a.account_id === selected)) $('account').value = selected;
    resetPages(); await ledger(); $('updated').textContent = `Refreshed ${new Date().toLocaleTimeString()}`;
  } catch (error) { $('health').textContent = 'Connection needs attention'; showError(error); } finally { $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', refresh);
$('account').addEventListener('change', () => { resetPages(); ledger().catch(showError); });
$('filter-form').addEventListener('submit', event => { event.preventDefault(); $('error').hidden = true; resetPages(); ledger().catch(showError); });
$('clear-filters').addEventListener('click', () => { $('from').value = ''; $('to').value = ''; $('error').hidden = true; resetPages(); ledger().catch(showError); });
document.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => { document.querySelectorAll('nav a').forEach(item => item.classList.remove('active')); link.classList.add('active'); }));
async function changePage(target) {
  const previousOffset = offset;
  offset = target;
  $('previous').disabled = true; $('next').disabled = true;
  try { await ledger(); }
  catch (error) {
    offset = previousOffset;
    $('previous').disabled = offset === 0; $('next').disabled = !nextCursor;
    showError(error);
  }
}
$('previous').addEventListener('click', () => changePage(Math.max(0, offset - limit)));
$('next').addEventListener('click', () => { if (!nextCursor) return; cursors[offset / limit + 1] = nextCursor; changePage(offset + limit); });
$('upload-form').addEventListener('submit', async event => {
  event.preventDefault(); const files = [...$('files').files];
  if (files.length > 5) { showError(new Error('Select at most five files per batch.')); return; }
  $('error').hidden = true; $('upload-button').disabled = true; $('upload-button').textContent = 'Checking your files...'; $('upload-results').replaceChildren();
  for (const file of files) {
    const row = element('div', '', 'upload-result'); row.append(element('h3', file.name), element('p', 'Checking transactions...')); $('upload-results').append(row);
    try { if (file.size > 1048576) throw new Error('This file is too large. Choose a file smaller than 1,048,576 bytes.'); const form = new FormData(); form.append('file', file); const {data} = await api('/v1/upload', {method: 'POST', body: form}); row.lastChild.textContent = `${data.rows_received} rows checked: ${data.rows_valid} passed, ${data.rows_quarantined} need attention.`; row.append(element('p', 'Rows that need attention are kept separately for review. Entries already added from this unchanged file are not added again.'));
      if (data.quarantine.length) { const details = document.createElement('details'); details.append(element('summary', `What needs fixing (${data.quarantine.length} shown)`)); data.quarantine.forEach(item => details.append(element('p', `Row ${item.source_row ?? 'database'}: ${item.error}`))); row.append(details); }
    } catch (error) { row.lastChild.textContent = error.message; }
  }
  $('upload-button').disabled = false; $('upload-button').textContent = 'Check and add transactions'; await refresh();
});
refresh();
