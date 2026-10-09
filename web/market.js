'use strict';
(()=>{
  const el=id=>document.getElementById(id);
  const node=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n;};
  async function api(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),45000);
    try{const response=await fetch(path,{signal:controller.signal,method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
      if(!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('The server did not return an API response. Please retry later.');
      const data=await response.json();if(!response.ok)throw new Error(data.error||'Request failed. Please retry.');return data;
    }catch(error){if(error.name==='AbortError')throw new Error('The request took too long. It may have completed; check your email or account before submitting again.');throw error;}finally{clearTimeout(timer);}
  }
  function encode(file,maximum){if(!file||file.size===0||file.size>maximum)throw new Error(`Choose a non-empty file no larger than ${maximum===500000?'500 KB':'2 MB'}.`);return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(new Error('The selected file could not be read.'));r.readAsDataURL(file);});}
  async function product(form){const f=form.elements;return {title:f.title.value,description:f.description.value,category:f.category.value,location:f.location.value,unit:f.unit.value,moq:Number(f.moq.value),price:f.price.value,currency:f.currency.value,content_consent:f.content_consent.checked,image:f.photo.files[0]?await encode(f.photo.files[0],500000):''};}
  function task(id,status,action){const form=el(id);if(!form)return;form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button[type="submit"]');if(button.disabled)return;button.disabled=true;el(status).textContent='Working…';try{await action(form);}catch(error){el(status).textContent=error.message;}finally{button.disabled=false;}});}
  if(el('market-register')){
    const form=el('market-register'),wa=form.elements.whatsapp,wc=form.elements.wechat;
    const validate=()=>wa.setCustomValidity(wa.value.trim()||wc.value.trim()?'':'Provide WhatsApp or WeChat. You do not need both.');
    wa.addEventListener('input',validate);wc.addEventListener('input',validate);validate();
  }
  task('market-register','market-register-status',async form=>{
    const f=form.elements,data={};for(const k of ['company','contact','email','country','whatsapp','wechat','license_number'])data[k]=f[k].value;
    data.consent=f.consent.checked;data.license_pdf=await encode(f.document.files[0],2*1024*1024);data.product=await product(form);
    await api('/api/marketplace/register',data);form.reset();form.hidden=true;el('market-register-success').hidden=false;el('market-register-success').focus();
  });
  task('market-access','market-access-status',async form=>{el('market-access-status').textContent=(await api('/api/marketplace/request-access',{email:form.elements.email.value})).message;});
  const categories={industrial:'Industrial components',packaging:'Packaging',consumer:'Consumer products',food:'Food & ingredients'};
  function card(p,owned=false){
    const article=node('article',undefined,'product-card');
    if(p.image_url&&p.visibility!=='withdrawn'&&p.visibility!=='hidden'){const image=node('img');image.src=p.image_url;image.alt=p.title;image.loading='lazy';image.width=800;image.height=600;article.append(image);}else article.append(node('div',p.visibility&&p.visibility!=='published'?'NOT PUBLIC':'PHOTO NOT PROVIDED','product-no-photo'));
    const body=node('div',undefined,'product-card-content');body.append(node('span',`${p.reference} / ${categories[p.category]||'Product'}`,'ref'),node('h3',p.title),node('p',p.description),node('p',`Advertised MOQ: ${p.moq} ${p.unit}`),node('p',p.price?`Advertised: ${p.currency} ${p.price} per ${p.unit==='pieces'?'piece':p.unit==='sets'?'set':p.unit==='kilograms'?'kilogram':p.unit==='litres'?'litre':'metre'}`:'Price: inquire through STRATEVO'),node('p',`Supply location: ${p.location||'Not supplied'}`),node('p','Lead time and certification evidence: not established.'));
    const actions=node('div',undefined,'actions');
    if(owned){body.append(node('p',`Listing status: ${p.visibility}`));if(p.visibility==='published'){const button=node('button','Withdraw product','quiet');button.type='button';button.onclick=async()=>{button.disabled=true;try{await api('/api/marketplace/withdraw',{id:p.id});await account();}catch(error){el('market-account-status').textContent=error.message;button.disabled=false;}};actions.append(button);}}
    else{const link=node('a','Inquire via STRATEVO ↗','secondary');link.href='https://app.minup.io/book/stratevo';link.target='_blank';link.rel='noopener noreferrer';actions.append(link);body.append(node('p','Mention this product reference in your booking. No inquiry has been sent yet.'));}
    body.append(actions);article.append(body);return article;
  }
  let generation=0,nextOffset=0,filters={q:'',category:''};
  async function load(append=false){
    const run=++generation;el('market-more').disabled=true;el('market-status').textContent='Loading products…';
    try{const query=new URLSearchParams({...filters,offset:append?nextOffset:0}),data=await api('/api/marketplace?'+query);if(run!==generation)return;
      if(!append)el('market-products').replaceChildren();data.products.forEach(p=>el('market-products').append(card(p)));nextOffset=data.offset+data.products.length;el('market-more').hidden=!data.has_more;
      el('market-status').textContent=`${data.total} ${data.total===1?'product':'products'} found${data.total===data.scan_limit?' within the latest 2,000 listings':''}.`;
      if(!data.products.length&&!append){const empty=node('section',undefined,'market-empty');empty.append(node('h2','No products to display yet.'),node('p',filters.q||filters.category?'Try different keywords or another category.':'Supplier products appear here after email confirmation. We do not populate the Marketplace with invented listings.'));const link=node('a','List your first product ↗','secondary');link.href='/supplier';empty.append(link);el('market-products').append(empty);}
    }catch(error){if(run===generation){el('market-status').textContent=error.message;el('market-more').hidden=true;if(!append)el('market-products').replaceChildren();}}finally{if(run===generation)el('market-more').disabled=false;}
  }
  if(el('market-filter')){el('market-filter').onsubmit=event=>{event.preventDefault();filters={q:el('market-query').value.trim(),category:el('market-category').value};load();};el('market-more').onclick=()=>load(true);load();}
  async function account(){
    try{const data=await api('/api/marketplace/me');el('market-account').hidden=false;el('market-account-status').textContent='Email-confirmed account. Business and product claims are not independently verified.';el('market-profile').textContent=data.profile.company;el('market-owned').replaceChildren(...data.products.map(p=>card(p,true)));if(!data.products.length)el('market-owned').append(node('p','No products yet. Add one below.'));
    }catch(error){el('market-account').hidden=true;el('market-account-status').replaceChildren(node('span',error.message+' '));const link=node('a','Request a secure email link.');link.href='/supplier#sign-in';el('market-account-status').append(link);}
  }
  if(el('market-account')){account();el('market-logout').onclick=async()=>{try{await api('/api/marketplace/logout',{});location.assign('/supplier#sign-in');}catch(error){el('market-account-status').textContent=error.message;}};}
  task('market-add','market-add-status',async form=>{const data=await api('/api/marketplace/products',await product(form));form.reset();el('market-add-status').textContent=data.message;await account();});
  if(el('load-market-admin'))el('load-market-admin').onclick=async()=>{
    const button=el('load-market-admin');button.disabled=true;el('market-admin-status').textContent='Loading private registry…';
    try{const data=await api('/api/admin/marketplace');el('market-admin-records').replaceChildren();el('market-admin-status').textContent=`${data.accounts.length} accounts shown (latest ${data.limit}). No manager approval required.`;
      for(const account of data.accounts){const section=node('section',undefined,'form-panel');section.append(node('h3',account.profile.company),node('p',account.email_confirmed?'Email confirmed — not business verified':'Email unconfirmed — products not public'));
        const details=node('dl',undefined,'details');for(const [key,value] of Object.entries(account.profile)){details.append(node('dt',key.replaceAll('_',' ')),node('dd',value||'Not supplied'));}section.append(details);
        const document=node('a','Download private license (unscanned PDF)','secondary');document.href='/api/admin/market-license/'+encodeURIComponent(account.id);section.append(document);
        for(const p of account.products){const row=node('div',undefined,'form-panel');row.append(node('h4',p.title),node('p',`${p.reference} · ${account.email_confirmed?p.visibility:'not public: email unconfirmed'}`));if(p.visibility==='published'){const hide=node('button','Remove listing','quiet');hide.type='button';hide.onclick=async()=>{hide.disabled=true;try{await api('/api/admin/hide-product',{id:p.id});row.append(node('p','Listing removed from the public Marketplace.'));}catch(error){el('market-admin-status').textContent=error.message;hide.disabled=false;}};row.append(hide);}section.append(row);}el('market-admin-records').append(section);
      }
    }catch(error){el('market-admin-status').textContent=error.message;}finally{button.disabled=false;}
  };
})();
