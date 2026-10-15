'use strict';
// Non-blocking storage disclosure. Never disable a form because diagnostics fail.
(async()=>{
 const indicators=document.querySelectorAll('[data-storage-status]');if(!indicators.length)return;
 try{const response=await fetch('/api/health',{credentials:'same-origin'});const data=await response.json();
  if(data.storage?.warning)for(const el of indicators){el.textContent=data.storage.warning;el.hidden=false;}
 }catch(_){/* The form's own result remains authoritative. */}
})();
