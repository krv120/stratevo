'use strict';
(()=>{
 const KEY='stratevo_supplier_public_v1',FIELDS=['id','company','focus','focus_label','specialty','description'];
 function clear(){try{localStorage.removeItem(KEY);}catch(_){}}
 function save(supplier){if(!supplier)return false;const value=Object.fromEntries(FIELDS.map(k=>[k,String(supplier[k]||'')]));try{localStorage.setItem(KEY,JSON.stringify({version:1,expires_at:Date.now()+7*86400000,supplier:value}));return true;}catch(_){return false;}}
 function load(){try{const value=JSON.parse(localStorage.getItem(KEY)||'null');if(!value||value.version!==1||!Number.isFinite(value.expires_at)||value.expires_at<Date.now()||!value.supplier?.id){clear();return null;}return value.supplier;}catch(_){clear();return null;}}
 async function reconcile(){const value=load();if(!value)return;try{const result=await window.StratevoUI.api('/api/suppliers/sync',{id:value.id},10000);if(result.supplier)save(result.supplier);else clear();}catch(_){/* A browser record never grants ownership or becomes a public server listing. */}}
 window.StratevoStorage={save,clear,reconcile};
 reconcile();
})();
