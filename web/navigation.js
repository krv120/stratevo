'use strict';
(()=>{
 const button=document.getElementById('menu-open'),drawer=document.getElementById('navigation-drawer');if(!button||!drawer)return;
 function close(){button.setAttribute('aria-expanded','false');document.body.classList.remove('nav-open');drawer.close();button.focus();}
 button.addEventListener('click',()=>{drawer.showModal();button.setAttribute('aria-expanded','true');document.body.classList.add('nav-open');drawer.querySelector('button').focus();});
 drawer.querySelector('[data-menu-close]').addEventListener('click',close);
 drawer.addEventListener('cancel',event=>{event.preventDefault();close();});
 drawer.addEventListener('click',event=>{if(event.target===drawer){const r=drawer.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close();}if(event.target.closest('a'))close();});
 drawer.addEventListener('close',()=>{button.setAttribute('aria-expanded','false');document.body.classList.remove('nav-open');button.focus();});
})();
