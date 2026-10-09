'use strict';
// Decorative only: no simulated AI work, no analytics, no third-party requests.
const menuButton = document.querySelector('.menu-toggle');
const navigation = document.getElementById('main-nav');
if (menuButton && navigation) {
  const close = () => { navigation.classList.remove('open'); menuButton.setAttribute('aria-expanded','false'); };
  menuButton.addEventListener('click', () => { const open = navigation.classList.toggle('open'); menuButton.setAttribute('aria-expanded',String(open)); });
  navigation.querySelectorAll('a').forEach(link => link.addEventListener('click',close));
  document.addEventListener('keydown',event => {if(event.key==='Escape'){close(); if(navigation.contains(document.activeElement))menuButton.focus();}});
}
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
const canvas = document.getElementById('constellation');
if(canvas && !reduced.matches) {
  const ctx = canvas.getContext('2d');
  if(ctx) {
    let width=0,height=0,points=[],frame=0,last=0;
    const mouse={x:-1000,y:-1000};
    function resize(){width=innerWidth;height=innerHeight;const ratio=Math.min(devicePixelRatio||1,1.5);canvas.width=width*ratio;canvas.height=height*ratio;ctx.setTransform(ratio,0,0,ratio,0,0);points=Array.from({length:width<700?22:48},()=>({x:Math.random()*width,y:Math.random()*height,vx:(Math.random()-.5)*.1,vy:(Math.random()-.5)*.1,blue:Math.random()>.7}));}
    function draw(time){frame=requestAnimationFrame(draw);if(document.hidden || time-last<33)return;last=time;ctx.clearRect(0,0,width,height);for(let i=0;i<points.length;i++){const p=points[i];p.x=(p.x+p.vx+width)%width;p.y=(p.y+p.vy+height)%height;ctx.fillStyle=p.blue?'rgba(105,145,245,.55)':'rgba(220,231,251,.38)';ctx.beginPath();ctx.arc(p.x,p.y,p.blue?1.5:1,0,Math.PI*2);ctx.fill();for(let j=i+1;j<points.length;j++){const q=points[j],d=Math.hypot(p.x-q.x,p.y-q.y);if(d<155){ctx.strokeStyle=`rgba(117,151,228,${.12*(1-d/155)})`;ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke();}}if(Math.hypot(mouse.x-p.x,mouse.y-p.y)<180){ctx.strokeStyle='rgba(132,169,255,.12)';ctx.beginPath();ctx.moveTo(mouse.x,mouse.y);ctx.lineTo(p.x,p.y);ctx.stroke();}}}
    resize();frame=requestAnimationFrame(draw);window.addEventListener('resize',resize,{passive:true});window.addEventListener('pointermove',e=>{mouse.x=e.clientX;mouse.y=e.clientY;},{passive:true});document.addEventListener('pointerleave',()=>{mouse.x=-1000;mouse.y=-1000;});reduced.addEventListener('change',e=>{if(e.matches){cancelAnimationFrame(frame);ctx.clearRect(0,0,width,height);}});
  }
}
const brief=document.getElementById('brief-statement');
if(brief && !reduced.matches){
  const words=brief.textContent.trim().split(/\s+/);brief.replaceChildren();
  words.forEach((word,i)=>{const span=document.createElement('span');span.className='word';span.textContent=word;brief.append(span);if(i<words.length-1)brief.append(document.createTextNode(' '));});
  const section=brief.closest('section');section.classList.add('brief-motion');let queued=false;
  function paint(){const rect=brief.getBoundingClientRect();const progress=Math.max(0,Math.min(1,(innerHeight*.86-rect.top)/(innerHeight*.65)));brief.querySelectorAll('.word').forEach((word,i)=>word.classList.toggle('is-lit',i<Math.max(4,Math.ceil(words.length*progress))));queued=false;}
  addEventListener('scroll',()=>{if(!queued){queued=true;requestAnimationFrame(paint);}},{passive:true});addEventListener('resize',paint,{passive:true});paint();
}
