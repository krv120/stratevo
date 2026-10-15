'use strict';
(()=>{
 const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
 const link=(label,url)=>{const el=node('a',label);try{const u=new URL(url);if(!['https:','http:'].includes(u.protocol))return node('span',label);el.href=u.href;el.target='_blank';el.rel='noopener noreferrer';}catch(_){return node('span',label);}return el;};
 function render(output,data){
  output.replaceChildren(node('h3',data.marketplace_label||'Marketplace suppliers — verification not established'));
  const local=data.marketplace_suppliers||[];output.append(node('p',local.length?`${local.length} matching public products.`:'No matching Marketplace products in this search.'));
  local.forEach(p=>{const card=node('article');card.className='form-panel';card.append(node('h4',p.title),node('p',p.description),node('p',p.notice));output.append(card);});
  if(data.catalog_research?.length){output.append(node('h3','Anonymized catalog research — unverified'));for(const item of data.catalog_research)output.append(node('p',item.reference+': '+item.description));}
  output.append(node('h3',data.external_label||'AI-discovered live external leads — unverified'));
  for(const lead of data.external_leads||[]){const card=node('article');card.className='form-panel';card.append(node('h4',lead.company_name),node('p',`${lead.lead_type} · ${lead.country} · ${lead.city_region}`),link('Company website',lead.website_url),node('p','Contact pathway: '+lead.contact_channel),node('p','Reported capabilities: '+lead.specialties_and_capabilities.join(', ')),node('p','Certification claims, not verified: '+(lead.certifications.join(', ')||'Unknown')),node('p','MOQ / lead time: '+lead.estimated_moq_and_lead_time),node('p',`AI fit estimate: ${lead.fit_score??'Unknown'}/100. ${lead.ai_rationale}`),node('p',lead.notice));const sources=node('ul');for(const url of lead.source_urls){const item=node('li');item.append(link('Search source',url));sources.append(item);}card.append(sources);output.append(card);}
  output.append(node('p',data.message||''));if(data.storage?.warning)output.append(node('p',data.storage.warning));
 }
 window.StratevoLeads={render};
 document.querySelectorAll('[data-lead-finder]').forEach(panel=>{
  const form=panel.querySelector('form'),status=panel.querySelector('[data-lead-status]'),output=panel.querySelector('[data-lead-results]');
  form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button');if(button.disabled)return;button.disabled=true;status.textContent='Searching live sources and saving supported leads…';const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),55000);
   try{const data={query:form.elements.query.value.trim(),geography:form.elements.geography.value.trim(),lead_type:form.elements.lead_type.value};const response=await fetch(panel.closest('#admin-workspace')?'/api/admin/leads/find':'/api/leads/find',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:controller.signal});const result=await response.json();if(!response.ok)throw new Error(result.error||'Lead search failed.');render(output,result);status.textContent=result.message||result.status;document.dispatchEvent(new Event('stratevo:manager-refresh'));}
   catch(error){status.textContent=error.name==='AbortError'?'Search timed out; it may still finish on the server. Check the saved leads before retrying.':error.message;}
   finally{clearTimeout(timer);button.disabled=false;}
  });
 });
})();
