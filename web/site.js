'use strict';
const byId = id => document.getElementById(id);
const make = (tag, value, cls) => {const el = document.createElement(tag); if (value !== undefined) el.textContent = value; if(cls) el.className = cls; return el;};
async function request(path, body) {
  const response = await fetch(path, {method:body === undefined ? 'GET':'POST', credentials:'same-origin', headers: {'Content-Type':'application/json'}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const result = await response.json();
  if(!response.ok) {const error = new Error(result.error || 'Request failed. Please try again.'); error.status=response.status; throw error;}
  return result;
}
function formTask(id, output, action) {
  const form = byId(id); if(!form) return;
  form.addEventListener('submit', async event => {event.preventDefault(); const button=form.querySelector('button[type="submit"]'); button.disabled=true; byId(output).textContent='Working…'; try {await action(Object.fromEntries(new FormData(form)), form);} catch(error) {byId(output).textContent=error.message;} finally {button.disabled=false;}});
}
formTask('application-form','application-status',async (data, form) => {
  if(!data.whatsapp.trim() && !data.wechat.trim()) throw new Error('Enter WhatsApp or WeChat. You do not need both.');
  const file=byId('license-file').files[0];
  if(!file || file.size>2*1024*1024) throw new Error('Choose a PDF license no larger than 2 MB.');
  const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('Could not read the document.'));reader.readAsDataURL(file);});
  data.license_pdf=encoded; data.consent=form.elements.consent.checked;
  const result=await request('/api/supplier/apply',data); form.reset(); byId('application-status').textContent=result.message;
});
formTask('access-form','access-status',async data => {byId('access-status').textContent=(await request('/api/supplier/request-access',data)).message;});
let applications=[];
function details(container, pairs) {pairs.forEach(([label,value])=>{const group=make('div');group.append(make('dt',label),make('dd',value || '—'));container.append(group);});}
function renderApplications(){
  const list=byId('applications'), term=byId('filter-search').value.toLowerCase(), status=byId('filter-status').value;
  list.replaceChildren();
  const filtered=applications.filter(row=>(status==='all'||row.status===status) && `${row.company} ${row.email} ${row.category}`.toLowerCase().includes(term));
  if(!filtered.length) list.append(make('p','No applications match this view.','empty-state'));
  filtered.forEach(row=>{
    const card=make('article',undefined,'application-card'), head=make('div',undefined,'application-head');
    head.append(make('h3',row.company),make('span',row.status.replace('_',' '),'badge '+row.status));card.append(head);
    const dl=make('dl',undefined,'details');details(dl,[['Contact',row.contact],['Email',row.email],['Country',row.country],['Category',row.category],['WhatsApp',row.whatsapp],['WeChat',row.wechat],['License number',row.license_number],['Submitted',new Date(row.created_at*1000).toLocaleString()]]);card.append(dl,make('p',row.capabilities,'capabilities'));
    const download=make('a','Download private license PDF ↓','license-link'); download.href='/api/admin/license/'+encodeURIComponent(row.id); download.setAttribute('download','business-license.pdf'); card.append(download);
    if(row.status==='pending'){
      const label=make('label','Decision note (required for rejection)'); label.className='sub'; const note=make('textarea'); note.maxLength=2000;note.rows=2;note.setAttribute('aria-label',`Decision note for ${row.company}`);label.append(note);card.append(label);
      const controls=make('div',undefined,'review-controls');
      ['approved','rejected'].forEach(decision=>{const button=make('button',decision==='approved'?'Approve & queue access email':'Reject application',decision==='rejected'?'reject':'');button.type='button';button.onclick=async()=>{
        if(decision==='rejected'&&!note.value.trim()){byId('admin-status').textContent='Add a rejection reason first.';note.focus();return;}
        if(!window.confirm(`${decision==='approved'?'Approve':'Reject'} ${row.company}? This sends a decision email when the mail queue is processed.`))return;
        controls.querySelectorAll('button').forEach(b=>b.disabled=true);
        try {const result=await request('/api/admin/review',{id:row.id,decision,note:note.value});byId('admin-status').textContent=result.message;await loadApplications();}catch(error){byId('admin-status').textContent=error.message;controls.querySelectorAll('button').forEach(b=>b.disabled=false);}
      };controls.append(button);});card.append(controls);
    }else if(row.status==='pending_email'){card.append(make('p','Email verification is required before a manager can approve or reject this application.','sub'));}
    else if(row.review_note){card.append(make('p','Decision note: '+row.review_note,'capabilities'));}
    if(row.status==='approved'){const profileLink=make('a','Open supplier profile ↗','license-link');profileLink.href='/portal?application='+encodeURIComponent(row.id);card.append(profileLink);}
    list.append(card);
  });
}
async function loadApplications(){
  const result=await request('/api/admin/applications');applications=result.applications;
  byId('admin-login').hidden=true;byId('admin-workspace').hidden=false;
  byId('admin-summary').textContent=`${result.total} total applications · Showing latest ${applications.length} · ${result.queued_emails} unsent emails · ${result.smtp_configured?'SMTP configured — delivery must be checked':'Email delivery NOT configured'}`;
  renderApplications();
  const connection = await request('/api/admin/connections');
  byId('connection-status').textContent=`AI: ${connection.ai_configured?'configured':'missing configuration'} · Online search: ${connection.search_configured?'configured':'disabled or missing key'} · Email: ${connection.email_configured?'configured':'not configured'}. ${connection.notice}`;
}
formTask('admin-login-form','admin-login-status',async(data,form)=>{await request('/api/admin/login',data);form.reset();await loadApplications();});
if(byId('admin-workspace')){
  loadApplications().catch(error=>{if(![401,403].includes(error.status))byId('admin-login-status').textContent=error.message;});
  byId('filter-search').oninput=renderApplications;byId('filter-status').onchange=renderApplications;
  byId('refresh').onclick=()=>loadApplications().catch(error=>byId('admin-status').textContent=error.message);
  byId('admin-logout').onclick=async()=>{try{await request('/api/admin/logout',{});location.reload();}catch(error){byId('admin-status').textContent=error.message;}};
  byId('send-mail').onclick=async()=>{const button=byId('send-mail');button.disabled=true;try{const result=await request('/api/admin/send-mail',{});byId('admin-status').textContent=`${result.sent} sent; ${result.failed} failed. Refresh or check the server configuration if delivery fails.`;await loadApplications();}catch(error){byId('admin-status').textContent=error.message;}finally{button.disabled=false;}};
}
if(byId('consume-link')){
  let token=null;
  function readEmailLink(){
    token=new URLSearchParams(location.hash.slice(1)).get('token');
    history.replaceState(null,'',location.pathname);
    byId('consume-link').disabled=!token; byId('portal-link').hidden=true;
    byId('consume-status').textContent=token?'':'No email token found. Open the complete link from your email or request a new one.';
  }
  readEmailLink(); window.addEventListener('hashchange',readEmailLink);
  byId('consume-link').onclick=async()=>{byId('consume-link').disabled=true;try{const result=await request('/api/supplier/consume',{token});byId('consume-status').textContent=result.message;if(result.status==='approved'){byId('portal-link').hidden=false;location.replace('/portal');}}catch(error){byId('consume-status').textContent=error.message;}};
}
if(byId('portal-content')){
  const profileId=new URLSearchParams(location.search).get('application');
  if(profileId){byId('supplier-logout').hidden=true;byId('portal-status').textContent='Private manager view of an approved supplier.';}
  request(profileId?'/api/admin/supplier-profile/'+encodeURIComponent(profileId):'/api/supplier/me').then(result=>{const row=result.application;byId('portal-content').hidden=false;details(byId('profile'),[['Company',row.company],['Contact',row.contact],['Email',row.email],['Country',row.country],['Category',row.category],['Capabilities',row.capabilities]]);}).catch(error=>{byId('portal-status').textContent=error.message+' Request a secure link from the supplier application page.';});
  byId('supplier-logout').onclick=async()=>{try{await request('/api/supplier/logout',{});location.href='/supplier#sign-in';}catch(error){byId('portal-status').textContent=error.message;}};
}

if(byId('load-research')) byId('load-research').onclick=async()=>{
  const button=byId('load-research');button.disabled=true;
  try{
    const result=await request('/api/admin/research');
    byId('research-status').textContent=`${result.total} imported research rows. Import completeness is not established; only stored records are counted. ${result.notice}`;
    byId('research-records').replaceChildren();
    result.records.forEach(row=>{
      const card=make('article',undefined,'result');
      card.append(make('span',row.source_row_id,'ref'),make('h3',row.description_summary),make('p','Supplier as listed: '+(row.supplier_as_listed_private||'Not identified')),make('p','Advertised: '+(row.advertised_price?.display||'Unknown')+' · Currency '+(row.advertised_price?.currency_code||'unconfirmed')),make('small','Unverified research; not approved platform membership'));
      byId('research-records').append(card);
    });
  }catch(error){byId('research-status').textContent=error.message;}finally{button.disabled=false;}
};

for (const [id, service] of [['check-ai','ai'],['check-search','search']]) {
  if (!byId(id)) continue;
  byId(id).onclick = async () => {
    if(!window.confirm('Run a live provider test? Provider charges may apply.')) return;
    byId('check-ai').disabled=byId('check-search').disabled=true;
    byId('connection-test-status').textContent='Testing the configured service…';
    try {const result=await request('/api/admin/check-connection',{service});byId('connection-test-status').textContent=(result.ok?'Success: ':'Not connected: ')+result.message;}
    catch(error){byId('connection-test-status').textContent=error.message;}
    finally{byId('check-ai').disabled=byId('check-search').disabled=false;}
  };
}
