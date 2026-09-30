'use strict';
const $ = id => document.getElementById(id);
let offset = 0;
const limit = 10;
const money = n => {
  const [whole, fraction = ''] = String(n).split('.');
  return `${new Intl.NumberFormat('en-ZA').format(BigInt(whole))}.${fraction.padEnd(2, '0')}`;
};
function element(tag, text, className) { const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node; }
async function api(path, options) { const response = await fetch(path, options); const body = await response.json(); if (!response.ok) throw new Error(`${response.status}: ${body.error || 'Request failed'}`); return body; }
function showError(error) { $('error').textContent = error.message; $('error').hidden = false; }
function chart(days) {
  const svg = $('trend'); svg.replaceChildren();
  if (!days.length) { $('trend-caption').textContent = 'No ledger activity yet.'; return; }
  const max = Math.max(...days.map(d => d.transactions)); const width = 670 / days.length;
  days.forEach((d, i) => { const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); const height = d.transactions / max * 150; rect.setAttribute('x', 15 + i * width); rect.setAttribute('y', 164 - height); rect.setAttribute('width', Math.max(1, width - 2)); rect.setAttribute('height', height); rect.setAttribute('rx', '2'); const title = document.createElementNS('http://www.w3.org/2000/svg', 'title'); title.textContent = `${d.day}: ${d.transactions} transactions`; rect.append(title); svg.append(rect); });
  $('trend-caption').textContent = `${days[0].day} to ${days.at(-1).day} · ${days.length} active dates · peak ${max} records/day. Missing dates have no plotted bar.`;
}
async function ledger() {
  if (!$('account').value) return;
  const params = new URLSearchParams({account_id: $('account').value, limit, offset});
  if ($('from').value) params.set('from', `${$('from').value}T00:00:00Z`);
  if ($('to').value) params.set('to', `${$('to').value}T23:59:59.999999Z`);
  const result = await api(`/v1/transactions?${params}`); $('ledger').replaceChildren();
  result.data.forEach(row => { const tr = document.createElement('tr'); [row.tx_date?.replace('T', ' ').replace('+00:00', ''), row.merchant || '—', row.tx_type, money(row.amount), row.currency, row.cross_border ? 'Yes' : 'No'].forEach(value => tr.append(element('td', value))); $('ledger').append(tr); });
  if (!result.data.length) { const td = element('td', 'No records for this account and date range.'); td.colSpan = 6; const tr = document.createElement('tr'); tr.append(td); $('ledger').append(tr); }
  $('page-label').textContent = `${result.data.length} records · offset ${offset}`; $('previous').disabled = offset === 0; $('next').disabled = result.data.length < limit;
  try { const insight = await api(`/v1/insights?account_id=${encodeURIComponent($('account').value)}`); $('insight').textContent = `Daily fixture score: ${insight.data.risk_score} / 100 · ${insight.data.score_date}. Automated scoring is not connected.`; }
  catch (error) { $('insight').textContent = error.message.startsWith('404:') ? 'No score exists for this account today.' : `Insight unavailable: ${error.message}`; }
}
async function refresh() {
  $('error').hidden = true; $('refresh').disabled = true;
  try {
    const [health, overview, accounts] = await Promise.all([api('/v1/health'), api('/v1/overview'), api('/v1/accounts')]);
    $('health').textContent = health.db === 'ok' ? '● PostgreSQL connected' : 'Database unavailable';
    const data = overview.data; $('total').textContent = data.counts.transactions.toLocaleString(); $('accounts-count').textContent = data.counts.active_accounts; $('cross-border').textContent = data.counts.cross_border;
    $('currency-totals').replaceChildren(); data.totals_by_currency.forEach(item => { const row = element('div', '', 'currency-line'); const label = element('div', item.currency); label.append(element('small', `${item.transactions} records`)); row.append(label, element('strong', money(item.gross_amount))); $('currency-totals').append(row); }); chart(data.daily_transactions);
    const selected = $('account').value; $('account').replaceChildren(); accounts.data.forEach(a => { const option = element('option', `${a.account_type} · ${a.account_id}`); option.value = a.account_id; $('account').append(option); });
    if (accounts.data.some(a => a.account_id === selected)) $('account').value = selected;
    await ledger(); $('updated').textContent = `Refreshed ${new Date().toLocaleTimeString()}`;
  } catch (error) { $('health').textContent = 'Connection needs attention'; showError(error); } finally { $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', refresh);
$('account').addEventListener('change', () => { offset = 0; ledger().catch(showError); });
$('apply').addEventListener('click', () => { offset = 0; ledger().catch(showError); });
$('previous').addEventListener('click', () => { offset = Math.max(0, offset - limit); ledger().catch(showError); });
$('next').addEventListener('click', () => { offset += limit; ledger().catch(showError); });
$('upload-form').addEventListener('submit', async event => {
  event.preventDefault(); const files = [...$('files').files];
  if (files.length > 5) { showError(new Error('Select at most five files per batch.')); return; }
  $('upload-button').disabled = true; $('upload-results').replaceChildren();
  for (const file of files) {
    const row = element('div', '', 'upload-result'); row.append(element('h3', file.name), element('p', 'Processing...')); $('upload-results').append(row);
    try { if (file.size > 1048576) throw new Error('File exceeds 1 MiB.'); const form = new FormData(); form.append('file', file); const {data} = await api('/v1/upload', {method: 'POST', body: form}); row.lastChild.textContent = `${data.rows_received} received · ${data.rows_valid} accepted · ${data.rows_quarantined} quarantined (${data.quarantine_rate_percent}%).`; row.append(element('p', data.note));
      if (data.quarantine.length) { const details = document.createElement('details'); details.append(element('summary', `Rejected-row reasons (first ${data.quarantine.length})`)); data.quarantine.forEach(item => details.append(element('p', `Row ${item.source_row ?? 'database'}: ${item.error}`))); row.append(details); }
    } catch (error) { row.lastChild.textContent = error.message; }
  }
  $('upload-button').disabled = false; await refresh();
});
refresh();
