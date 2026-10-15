'use strict';
(()=>{
 const form=document.getElementById('assessment-form');if(!form)return;
 const $=id=>document.getElementById(id),steps=[...form.querySelectorAll('[data-step]')],progress=[...$('assessment-progress').children];let current=0,started=false;
 const emit=name=>window.StratevoStages?.emit(name);
 function values(){return Object.fromEntries(new FormData(form));}
 function brief(){const v=values();return {product:v.product.trim(),quantity:v.quantity.trim(),destination:v.destination.trim(),budget:v.budget.trim(),timeline:v.timeline.trim(),requirements:v.specs.trim()+'\n\nCustomization: '+v.customization+'\nEvidence requirements: '+(v.evidence.trim()||'Not specified; needs review')};}
 function review(){const v=brief(),finder=document.querySelector('[data-lead-finder] form');if(finder&&!finder.elements.query.value)finder.elements.query.value=(v.product+' '+values().specs).slice(0,600);const dl=$('assessment-review');dl.replaceChildren();for(const [key,value] of Object.entries(v)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value||'Not decided';dl.append(dt,dd);}const missing=['budget','timeline'].filter(k=>!v[k]);if(!values().evidence.trim())missing.push('certification/evidence requirements');$('assessment-gaps').textContent=missing.length?'Still to clarify: '+missing.join(', ')+'. This is a checklist, not a readiness score.':'Your fields are filled. Accuracy, feasibility and supplier evidence still need human review.';}
 function show(){steps.forEach((el,i)=>el.hidden=i!==current);progress.forEach((el,i)=>{if(i===current)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});$('assessment-back').hidden=current===0;$('assessment-next').hidden=current===3;$('assessment-use').hidden=current!==3;$('assessment-status').textContent='Step '+(current+1)+' of 4';$('assessment-heading').focus();if(current===3)review();}
 form.addEventListener('input',()=>{if(!started){started=true;emit('assessment_started');}});
 $('assessment-controls').hidden=false;show();
 function next(){for(const el of steps[current].querySelectorAll('input,textarea,select')){el.setCustomValidity('');const value=el.value.trim();if(el.required&&!value)el.setCustomValidity('Please complete this field, or explicitly say Not decided where allowed.');else if(el.minLength>0&&value.length<el.minLength)el.setCustomValidity('Please enter at least '+el.minLength+' characters.');if(!el.reportValidity())return;}current=Math.min(current+1,3);show();if(current===3)emit('assessment_reviewed');}
 $('assessment-next').onclick=next;$('assessment-back').onclick=()=>{current=Math.max(0,current-1);show();};
 // Enter advances a step without accidentally submitting data or bypassing hidden required fields.
 form.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.tagName==='INPUT'){event.preventDefault();if(current<3)next();}});
 form.addEventListener('submit',event=>event.preventDefault());
 $('assessment-use').onclick=()=>{const fields=brief();const text=Object.entries(fields).map(([k,v])=>k+': '+(v||'Not decided')).join('\n\n');try{sessionStorage.setItem('stratevo-assessment-draft',JSON.stringify({version:1,created_at:Date.now(),fields}));location.assign('/inquiry?from=assessment');}catch{$('assessment-error').textContent='Your browser blocked temporary storage. Your answers are still here: copy the brief below into the inquiry form.';$('assessment-copy').hidden=false;$('assessment-copy').open=true;$('assessment-copy-text').value=text;}};
})();
