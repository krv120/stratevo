'use strict';
(()=>{
  const embedded=new URLSearchParams(location.search).get('embed')==='1' && window.self!==window.top;
  if(embedded){document.body.classList.add('embedded');document.addEventListener('click',event=>{const a=event.target.closest('a[href]');if(a&&a.origin===location.origin&&a.pathname!==location.pathname)a.target='_top';});return;}
  if(!window.HTMLDialogElement || !HTMLDialogElement.prototype.showModal)return;
  const dialogs=new Map();
  document.addEventListener('click',event=>{
    const a=event.target.closest('a[href]');
    if(!a||event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||a.target==='_blank')return;
    const url=new URL(a.href);
    if(url.origin!==location.origin||!['/ai','/supplier'].includes(url.pathname))return;
    event.preventDefault();
    const key=url.pathname;
    let entry=dialogs.get(key);
    if(!entry){
      const dialog=document.createElement('dialog');dialog.className=key==='/ai'?'site-dialog ai-dialog':'site-dialog supplier-dialog';dialog.setAttribute('aria-label',key==='/ai'?'STRATEVO AI conversation':'Supplier registration and products');
      const bar=document.createElement('div');bar.className='dialog-bar';
      const title=document.createElement('strong');title.textContent=key==='/ai'?'STRATEVO AI':'SUPPLIER / SELF-SERVICE';
      const close=document.createElement('button');close.type='button';close.autofocus=true;close.className='quiet';close.textContent='Close ×';close.setAttribute('aria-label','Close '+(key==='/ai'?'AI conversation':'supplier form'));
      const full=document.createElement('a');full.href=key;full.textContent='Open as page ↗';full.dataset.noDialog='true';
      full.addEventListener('click',e=>e.stopPropagation());
      bar.append(title,full,close);
      const frame=document.createElement('iframe');frame.title=key==='/ai'?'STRATEVO AI chat':'Supplier details and product form';frame.src=key+'?embed=1'+url.hash;
      dialog.append(bar,frame);document.body.append(dialog);
      entry={dialog,frame,opener:a};dialogs.set(key,entry);
      close.onclick=()=>dialog.close();
      dialog.addEventListener('close',()=>{document.body.classList.remove('dialog-open');entry.opener.focus();});
      // Escape inside a same-origin iframe does not automatically reach the parent dialog.
      frame.addEventListener('load',()=>{try{frame.contentDocument.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();dialog.close();}});}catch{}});
    }else if(url.hash){try{entry.frame.contentWindow.location.hash=url.hash;}catch{}}
    entry.opener=a;entry.dialog.showModal();document.body.classList.add('dialog-open');
  });
})();
