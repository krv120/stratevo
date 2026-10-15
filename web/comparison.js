'use strict';
(()=>{
 const root=document.getElementById('comparison-demo');if(!root)return;
 const buttons=[...root.querySelectorAll('[data-view]')],rows=[...root.querySelectorAll('tbody tr')];
 for(const button of buttons)button.addEventListener('click',()=>{const view=button.dataset.view;for(const b of buttons)b.setAttribute('aria-pressed',String(b===button));let gaps=0;for(const row of rows){row.hidden=view!=='all'&&row.dataset.group!==view;if(!row.hidden&&row.dataset.followup==='true')gaps++;}document.getElementById('comparison-status').textContent=gaps+' comparison checks in this view need follow-up. This counts rows with missing information; it is not a supplier score or recommendation.';});
})();
