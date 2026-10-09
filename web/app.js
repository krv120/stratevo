'use strict';
const $ = id => document.getElementById(id);
let access = '', history = [], busy = false;
async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(()=>controller.abort(),60000);
  try {
    const response = await fetch(path, {signal:controller.signal, method: body ? 'POST' : 'GET', credentials:'same-origin', headers: {'Content-Type': 'application/json', Authorization: `Bearer ${access}`}, ...(body ? {body: JSON.stringify(body)} : {})});
    if(!(response.headers.get('content-type')||'').includes('application/json')) throw new Error('The server did not return an API response. Check this deployment’s routing or try again.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    return data;
  } catch(error) {
    if(error.name==='AbortError') throw new Error('The service took too long to respond. Your question is saved in the input; please try again.');
    throw error;
  } finally {clearTimeout(timer);}
}

function text(tag, value, cls) {const el = document.createElement(tag); el.textContent = value; if (cls) el.className = cls; return el;}
function message(role, value) { $('messages').querySelector('.empty')?.remove(); const el = text('div', value, `message ${role}`); el.prepend(text('span', role === 'user' ? 'YOU' : 'STRATEVO', 'speaker')); $('messages').append(el); el.scrollIntoView({block: 'nearest', behavior: 'smooth'}); }
function cards(rows) {
  $('results').replaceChildren();
  if (!rows.length) $('results').append(text('p', 'No matching research found. Try fewer English keywords. This does not mean no suppliers exist.', 'empty'));
  rows.forEach(row => { const card = document.createElement('article'); card.className = 'result'; card.append(text('span', row.reference, 'ref'), text('h3', row.description)); const p = row.advertised_price, m = row.advertised_moq; card.append(text('p', `Advertised: ${p?.display || 'unknown'} · ${p?.currency_code || 'currency unconfirmed'}`), text('p', `MOQ: ${m?.quantity ?? 'unknown'} ${m?.unit || ''} · Variant unconfirmed`), text('small', 'Unverified listing • not a quotation')); if (row.moq_match) { card.append(text('p', `Category: ${row.matrix?.category || 'Unclassified'} / ${row.reference}`), text('p', `Location: ${row.matrix?.location || 'Unknown'} · MOQ Match: ${row.moq_match}`), text('p', `Lead time: ${row.matrix?.lead_time_days ?? 'Unknown'} · Verified certifications: ${row.matrix?.certifications_verified?.join(', ') || 'None established'} · Target price: ${row.matrix?.target_price ?? 'Not specified'}`), text('p', `Why they fit: ${row.why_fit}`)); } $('results').append(card); });
}
$('connect').onclick = async () => {access = $('token').value.trim(); $('token').value = ''; try {const status = await api('/api/agent/status'); $('status').textContent = `${status.research_rows} research rows · ${status.provider_configured ? 'Provider configured (connection not yet tested)' : 'Catalog only — general AI is not connected'}`;} catch (e) {access = ''; $('status').textContent = e.message;} };
$('search').onsubmit = async e => {e.preventDefault(); const button = e.target.querySelector('button'); button.disabled = true; try {cards((await api('/api/catalog/search', {query: $('query').value})).results);} catch (err) {$('results').replaceChildren(text('p', err.message, 'error'));} finally {button.disabled = false;}};
$('chat').onsubmit = async e => {e.preventDefault(); if (busy) return; const value = $('question').value.trim(); if (!value) return; busy = true; $('chat-progress').textContent='Waiting for the AI service…'; $('messages').setAttribute('aria-busy','true'); $('send').disabled = $('clear').disabled = true; message('user', value); $('question').value = ''; const context = history.slice(-16); while(context.length && (context.reduce((n,m)=>n+m.content.length,0)+value.length>48000)) context.splice(0,2); const pending = [...context, {role:'user', content:value}]; try {const result = await api('/api/chat', {messages:pending}); message('assistant', result.message); if (result.mode === 'model') history = [...pending, {role:'assistant', content:result.message}]; if (result.qualification || result.references.length) cards(result.references);} catch (err) {message('assistant', err.message); $('question').value = value;} finally {busy = false; $('chat-progress').textContent=''; $('messages').setAttribute('aria-busy','false'); $('send').disabled = $('clear').disabled = false; $('question').focus();}};
$('clear').onclick = () => {history = []; $('results').replaceChildren(text('p','Previous research results cleared.','empty')); $('match-status').textContent=''; $('messages').replaceChildren(text('p', 'New conversation. Previous messages have been cleared from this page.', 'empty'));};

// Manager sessions can also unlock research; no second token is needed.
api('/api/agent/status').then(status => { $('status').textContent = `${status.research_rows} research rows · ${status.provider_configured ? 'Provider configured (connection not yet tested)' : 'Catalog only — general AI is not connected'}`; }).catch(() => {});

$('match-form').onsubmit = async e => {
  e.preventDefault(); const button = e.target.querySelector('button'); button.disabled = true;
  const certifications = $('match-certs').value.trim();
  const requirement = {product: $('match-product').value.trim(), volume: Number($('match-volume').value), unit: $('match-unit').value.trim(), location: $('match-location').value.trim(), certifications: certifications.toLowerCase() === 'none' ? [] : certifications.split(',').map(s => s.trim())};
  if ($('match-lead').value) requirement.lead_time_days = Number($('match-lead').value);
  if ($('match-price').value) { requirement.target_price = Number($('match-price').value); requirement.currency = $('match-currency').value.trim().toUpperCase(); }
  try {
    const result = await api($('research-mode').value === 'online' ? '/api/catalog/discover' : '/api/catalog/match', requirement);
    $('match-status').textContent = result.message + (result.evidence_gaps?.length ? ' Evidence gaps: ' + result.evidence_gaps.join('; ') : '');
    cards(result.matches);
    if (!result.matches.length) $('results').replaceChildren(text('p', result.message, 'empty'));
  } catch (error) { $('match-status').textContent = error.message; $('results').replaceChildren(); }
  finally {button.disabled = false;}
};

for(const button of document.querySelectorAll('[data-prompt]')) button.onclick=()=>{$('question').value=button.dataset.prompt;$('question').focus();};
function openBrief(){if(location.hash==='#match-form'){$('match-form').closest('details').open=true;$('match-product').focus();}}
openBrief();window.addEventListener('hashchange',openBrief);

$('question').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!busy)$('chat').requestSubmit();}});
