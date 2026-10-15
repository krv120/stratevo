'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  const node=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n;};
  async function api(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),55000);
    try{const response=await fetch(path,{signal:controller.signal,method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
      if(!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('The server did not return an API response. Please retry later.');
      const data=await response.json();if(!response.ok){const error=new Error(data.error||'Request failed. Please retry.');error.field=data.field;throw error;}return data;
    }catch(error){if(error.name==='AbortError')throw new Error('The request took too long. It may have completed; check your email or account before submitting again.');throw error;}finally{clearTimeout(timer);}
  }
  function encode(file,maximum){if(!file||file.size===0||file.size>maximum)throw new Error(`Choose a non-empty file no larger than ${maximum===500000?'500 KB':'2 MB'}.`);return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(new Error('The selected file could not be read.'));r.readAsDataURL(file);});}
  async function product(form){const f=form.elements;return {title:f.title.value,description:f.description.value,category:f.category.value,location:f.location.value,unit:f.unit.value,moq:f.moq.value.trim()||null,price:f.price.value,currency:f.currency.value,content_consent:f.content_consent.checked,image:f.photo.files[0]?await encode(f.photo.files[0],500000):''};}
  function task(id,status,action){const form=el(id);if(!form)return;form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button[type="submit"]');if(button.disabled)return;button.disabled=true;el(status).textContent='Working…';try{await action(form);}catch(error){el(status).textContent=error.message;}finally{button.disabled=false;}});}
  function showFieldError(input,message){
    input.setAttribute('aria-invalid','true');const id=(input.id||input.name)+'-error';let error=document.getElementById(id);if(!error){error=node('p');error.id=id;error.className='field-error';input.after(error);}error.textContent=message;input.setAttribute('aria-describedby',id);input.focus();input.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  }
  document.querySelectorAll('#market-register input,#market-register textarea,#market-register select').forEach(input=>{input.addEventListener('invalid',()=>showFieldError(input,input.validationMessage));input.addEventListener('input',()=>{input.removeAttribute('aria-invalid');const error=document.getElementById((input.id||input.name)+'-error');if(error)error.textContent='';});});
  if(el('enhance-profile'))el('enhance-profile').onclick=async()=>{
    const button=el('enhance-profile');button.disabled=true;el('enhance-status').textContent='Preparing an AI suggestion…';
    try{const result=await api('/api/supplier/enhance',{summary:el('supplier-capabilities').value.trim()});el('enhance-preview').replaceChildren(node('p',result.summary),node('p','Keywords: '+result.keywords.join(', ')),node('p','Suggested evidence checks, NOT certifications: '+result.suggested_checks.join('; ')),node('p',result.buyer_match_preview));el('enhance-status').textContent=result.notice;el('apply-enhancement').hidden=false;el('apply-enhancement').onclick=()=>{el('supplier-capabilities').value=result.summary;el('apply-enhancement').hidden=true;};}
    catch(error){el('enhance-status').textContent=error.message;if(error.field==='summary')showFieldError(el('supplier-capabilities'),error.message);}finally{button.disabled=false;}
  };
  let registrationAttempt=null;
  task('market-register','market-register-status',async form=>{
    const f=form.elements,data={};for(const k of ['company','contact','email','country','city','whatsapp','wechat','license_number','website','phone','capabilities','categories','certifications','materials','regions','lead_time','employees','founded_year'])data[k]=f[k]?.value.normalize('NFKC').trim()||'';if(data.website&&!data.website.includes('://')&&!data.website.startsWith('['))data.website='https://'+data.website;
    data.consent=f.consent.checked;data.license_pdf='';data.product=await product(form);
    // A random bearer idempotency key permits exact retries after response loss, never access by email alone.
    const signature=JSON.stringify(data);
    if(!registrationAttempt||registrationAttempt.signature!==signature)registrationAttempt={signature,key:Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,'0')).join('')};
    data.submission_key=registrationAttempt.key;
    const dialog=el('market-review');el('market-review-product').replaceChildren(node('h3',data.product.title),node('p',data.product.description),node('p',`Category: ${data.product.category}; MOQ: ${data.product.moq??'not supplied'} ${data.product.unit}; price: ${data.product.price||'not supplied'} ${data.product.currency}.`));
    el('market-review-status').textContent='Review the public details. Company and contact fields remain private.';
    dialog.showModal();el('market-register-status').textContent='Review your product before publishing.';
    const publish=el('market-confirm-publish'),cancel=el('market-review-cancel');
    publish.onclick=async()=>{
      if(publish.disabled)return;publish.disabled=true;cancel.disabled=true;publish.textContent='Publishing & notifying admin…';
      const preventClose=e=>e.preventDefault();dialog.addEventListener('cancel',preventClose);
      try{
        const result=await api('/api/marketplace/register',data);
        el('market-review-status').textContent=result.message;
        if(!result.published)return;
        registrationAttempt=null;form.reset();form.hidden=true;dialog.close();
        const success=el('market-register-success');el('market-register-result').textContent=result.message;el('owner-notification-status').textContent='Admin notification: '+(result.email_notification_status||'queued_in_admin_inbox')+'. Sent means transport accepted, not confirmed inbox delivery.';window.StratevoLeads?.render(el('instant-buyer-leads'),result.buyer_leads||{});success.hidden=false;success.focus();
      }catch(error){if(error.field&&form.elements[error.field]){dialog.close();showFieldError(form.elements[error.field],error.message);}el('market-review-status').textContent=error.message+' Your details are retained. Retry Confirm and Publish without changing this review to recover the same submission.';}
      finally{publish.textContent='Confirm and Publish';publish.disabled=false;cancel.disabled=false;dialog.removeEventListener('cancel',preventClose);}
    };
    cancel.onclick=()=>dialog.close();
  });
  task('market-access','market-access-status',async form=>{el('market-access-status').textContent=(await api('/api/marketplace/request-access',{email:form.elements.email.value})).message;});
  const categories={industrial:'Industrial components',packaging:'Packaging',consumer:'Consumer products',food:'Food & ingredients'};
  function card(p,owned=false){
    const article=node('article',undefined,'product-card');
    if(p.image_url&&p.visibility!=='withdrawn'&&p.visibility!=='hidden'){const image=node('img');image.src=p.image_url;image.alt=p.title;image.loading='lazy';image.width=800;image.height=600;article.append(image);}else article.append(node('div',p.visibility&&p.visibility!=='published'?'NOT PUBLIC':'PHOTO NOT PROVIDED','product-no-photo'));
    const body=node('div',undefined,'product-card-content');body.append(node('span',`${p.reference} / ${categories[p.category]||'Product'}`,'ref'),node('h3',p.title),node('p',p.description),node('p',`Advertised MOQ: ${p.moq??'Not supplied'} ${p.moq==null?'':p.unit}`),node('p',p.price?`Advertised: ${p.currency} ${p.price} per ${p.unit==='pieces'?'piece':p.unit==='sets'?'set':p.unit==='kilograms'?'kilogram':p.unit==='litres'?'litre':'metre'}`:'Price: inquire through STRATEVO'),node('p',`Supply location: ${p.location||'Not supplied'}`),node('p','Lead time and certification evidence: not established.'));
    const actions=node('div',undefined,'actions');
    if(owned){body.append(node('p',`Listing status: ${p.visibility}`));if(p.visibility==='published'){const button=node('button','Withdraw product','quiet');button.type='button';button.onclick=async()=>{button.disabled=true;try{await api('/api/marketplace/withdraw',{id:p.id});await account();}catch(error){el('market-account-status').textContent=error.message;button.disabled=false;}};actions.append(button);}}
    else{const link=node('a','Inquire via STRATEVO ↗','secondary');link.href=document.querySelector('[data-booking]')?.href||document.querySelector('a[href^="https://app.minup.io/"]')?.href||'/inquiry';link.target='_blank';link.rel='noopener noreferrer';actions.append(link);body.append(node('p','Mention this product reference in your booking. No inquiry has been sent yet.'));}
    if(!owned){const report=node('details');report.append(node('summary','Report this listing'));const form=node('form'),reason=node('textarea');reason.required=true;reason.minLength=10;reason.maxLength=1000;reason.setAttribute('aria-label','Reason for reporting '+p.reference);const submit=node('button','Send private report','quiet');submit.type='submit';const status=node('p');status.setAttribute('role','status');form.append(reason,submit,status);form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{status.textContent=(await api('/api/marketplace/report',{id:p.id,reason:reason.value})).message;reason.value='';}catch(error){status.textContent=error.message;}finally{submit.disabled=false;}};report.append(form);body.append(report);}
    body.append(actions);article.append(body);return article;
  }
  let generation=0,nextOffset=0,filters={q:(new URLSearchParams(location.search).get('q')||'').slice(0,100),category:''};
  async function load(append=false){
    const run=++generation;el('market-more').disabled=true;el('market-status').textContent='Loading products…';
    try{const query=new URLSearchParams({...filters,offset:append?nextOffset:0}),data=await api('/api/marketplace?'+query);if(run!==generation)return;
      if(!append)el('market-products').replaceChildren();data.products.forEach(p=>el('market-products').append(card(p)));nextOffset=data.offset+data.products.length;el('market-more').hidden=!data.has_more;
      el('market-status').textContent=`${data.total} ${data.total===1?'product':'products'} found.`;
      if(!data.products.length&&!append){const empty=node('section',undefined,'market-empty');empty.append(node('h2','No products to display yet.'),node('p',filters.q||filters.category?'Try different keywords or another category.':'Supplier products appear here after Confirm and Publish. We do not populate the Marketplace with invented listings.'));const link=node('a','List your first product ↗','secondary');link.href='/supplier';empty.append(link);el('market-products').append(empty);}
    }catch(error){if(run===generation){el('market-status').textContent=error.message;el('market-more').hidden=true;if(!append)el('market-products').replaceChildren();}}finally{if(run===generation)el('market-more').disabled=false;}
  }
  if(el('market-filter')){el('market-query').value=filters.q;el('market-filter').onsubmit=event=>{event.preventDefault();filters={q:el('market-query').value.trim(),category:el('market-category').value};load();};el('market-more').onclick=()=>load(true);load();}
  async function account(){
    try{const data=await api('/api/marketplace/me');el('market-account').hidden=false;el('market-account-status').textContent=(data.email_confirmed?'Email confirmed. ':'Email not yet confirmed. This browser has a management session; email access requires a configured delivery service. ')+ 'Business and product claims are not independently verified. '+(data.storage?.warning||'');el('market-profile').textContent=data.profile.company;if(el('market-profile-fields')&&!el('market-profile-edit').dataset.loaded){for(const key of ['company','contact','country','city','phone','website','capabilities','categories','certifications','materials','regions','lead_time','employees','founded_year']){const label=node('label',key.replaceAll('_',' '),'field'),input=node(key==='capabilities'?'textarea':'input');input.name=key;input.maxLength=key==='capabilities'?3000:1000;input.value=Array.isArray(data.profile[key])?data.profile[key].join(', '):data.profile[key]||'';label.append(input);el('market-profile-fields').append(label);}el('market-profile-edit').dataset.loaded='true';}el('market-owned').replaceChildren(...data.products.map(p=>card(p,true)));if(!data.products.length)el('market-owned').append(node('p','No products yet. Add one below.'));
    }catch(error){el('market-account').hidden=true;el('market-account-status').replaceChildren(node('span',error.message+' '));const link=node('a','Request a secure email link.');link.href='/supplier#sign-in';el('market-account-status').append(link);}
  }
  if(el('market-account')){account();el('market-logout').onclick=async()=>{try{await api('/api/marketplace/logout',{});location.assign('/supplier#sign-in');}catch(error){el('market-account-status').textContent=error.message;}};}
  task('market-profile-edit','market-profile-status',async form=>{const profile=Object.fromEntries(new FormData(form));const result=await api('/api/marketplace/profile',{profile});el('market-profile-status').textContent=result.message;el('market-profile-fields').replaceChildren();delete form.dataset.loaded;await account();});
  task('market-add','market-add-status',async form=>{const data=await api('/api/marketplace/products',await product(form));form.reset();el('market-add-status').textContent=data.message;await account();});
  let adminOffset=0;
  if(el('load-market-admin'))el('load-market-admin').onclick=async()=>{
    const button=el('load-market-admin');button.disabled=true;el('market-admin-status').textContent='Loading private registry…';
    try{const data=await api('/api/admin/marketplace?offset='+adminOffset);if(!adminOffset)el('market-admin-records').replaceChildren();el('market-admin-status').textContent=`${data.accounts.length} accounts shown (latest ${data.limit}). No manager approval required.`;adminOffset=data.has_more?data.offset+25:0;button.textContent=data.has_more?'Load more supplier accounts':'Refresh supplier registry';
      for(const account of data.accounts){const section=node('section',undefined,'form-panel');section.append(node('h3',account.profile.company),node('p',account.email_confirmed?'Email confirmed — not business verified':account.publication_enabled?'Published — email unconfirmed':'Email unconfirmed — legacy products not public'));
        const reason=node('textarea');reason.setAttribute('aria-label','Suspension or restoration reason for '+account.profile.company);reason.maxLength=500;const suspend=node('button',account.suspended?'Restore account access':'Suspend account and hide listings','quiet');suspend.type='button';suspend.onclick=async()=>{suspend.disabled=true;try{el('market-admin-status').textContent=(await api('/api/admin/suspend',{id:account.id,suspended:!account.suspended,reason:reason.value})).message;}catch(error){el('market-admin-status').textContent=error.message;suspend.disabled=false;}};section.append(reason,suspend);
        const details=node('dl',undefined,'details');for(const [key,value] of Object.entries(account.profile)){details.append(node('dt',key.replaceAll('_',' ')),node('dd',value||'Not supplied'));}section.append(details);
        const document=node('a','Download private license (unscanned PDF)','secondary');document.href='/api/admin/market-license/'+encodeURIComponent(account.id);if(account.has_license)section.append(document);
        section.append(node('p','Submitted: '+new Date(account.created_at*1000).toLocaleString()));
        const review=node('select');review.setAttribute('aria-label','Review status for '+account.profile.company);for(const state of ['new','contacted','reviewed','declined']){const option=node('option',state);option.value=state;review.append(option);}review.value=account.review_status;
        const save=node('button','Save review status','quiet');save.type='button';save.onclick=async()=>{save.disabled=true;try{el('market-admin-status').textContent=(await api('/api/admin/supplier-status',{id:account.id,status:review.value})).message;}catch(error){el('market-admin-status').textContent=error.message;}finally{save.disabled=false;}};section.append(review,save);
        for(const p of account.products){const row=node('div',undefined,'form-panel');row.append(node('h4',p.title),node('p',`${p.reference} · ${account.publication_enabled?p.visibility:'not public: legacy email confirmation pending'}`));if(p.visibility==='published'){const hide=node('button','Remove listing','quiet');hide.type='button';hide.onclick=async()=>{hide.disabled=true;try{await api('/api/admin/hide-product',{id:p.id});row.append(node('p','Listing removed from the public Marketplace.'));}catch(error){el('market-admin-status').textContent=error.message;hide.disabled=false;}};row.append(hide);}section.append(row);}el('market-admin-records').append(section);
      }
    }catch(error){el('market-admin-status').textContent=error.message;}finally{button.disabled=false;}
  };
})();
