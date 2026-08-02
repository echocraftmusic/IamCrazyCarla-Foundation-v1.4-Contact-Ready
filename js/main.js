const root=document.documentElement;
const savedTheme=localStorage.getItem('carla-theme');
if(savedTheme) root.dataset.theme=savedTheme;
const themeBtn=document.querySelector('.theme-toggle');
function syncTheme(){const light=root.dataset.theme==='light';themeBtn.querySelector('.theme-icon').textContent=light?'☀':'☾';themeBtn.setAttribute('aria-label',light?'Switch to dark mode':'Switch to light mode');}
themeBtn.addEventListener('click',()=>{root.dataset.theme=root.dataset.theme==='light'?'dark':'light';localStorage.setItem('carla-theme',root.dataset.theme);syncTheme();});syncTheme();
const menuBtn=document.querySelector('.menu-toggle'),nav=document.querySelector('#site-nav');menuBtn.addEventListener('click',()=>{const open=nav.classList.toggle('open');menuBtn.setAttribute('aria-expanded',String(open));});nav.addEventListener('click',()=>{nav.classList.remove('open');menuBtn.setAttribute('aria-expanded','false')});
document.querySelector('#year').textContent=new Date().getFullYear();
const io=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('visible')}),{threshold:.12});document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
async function loadGallery(){try{const r=await fetch('data/gallery.json',{cache:'no-store'});const items=await r.json();document.querySelector('#gallery-track').innerHTML=items.filter(x=>x.active!==false).map(x=>`<figure class="gallery-card"><img src="${x.src}" alt="${x.alt||'Crazy Carla portrait'}" loading="lazy"><figcaption>${x.caption||''}</figcaption></figure>`).join('')}catch(e){console.error('Gallery failed',e)}}
async function loadVideos(){try{const r=await fetch('data/youtube-videos.json',{cache:'no-store'});if(!r.ok)throw new Error('No video data');const d=await r.json();const videos=d.videos||[];if(!videos.length)return;const first=videos[0];document.querySelector('#featured-video').innerHTML=`<iframe src="https://www.youtube-nocookie.com/embed/${first.id}" title="${first.title.replaceAll('"','&quot;')}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>`;document.querySelector('#featured-title').textContent=first.title;document.querySelector('#recent-videos').innerHTML=videos.slice(1,4).map(v=>`<a class="video-card" href="${v.url}" target="_blank" rel="noopener"><img src="${v.thumbnail}" alt="" loading="lazy"><div><h4>${v.title}</h4><time>${new Date(v.published).toLocaleDateString()}</time></div></a>`).join('')}catch(e){console.info('Using YouTube placeholder until first scheduled update.')}}
loadGallery();loadVideos();

// Subtle premium interactions: progress, active section, elevated header and desktop portrait depth.
const progressBar=document.querySelector('.scroll-progress span');
const header=document.querySelector('.site-header');
const backToTop=document.querySelector('.back-to-top');
const navLinks=[...document.querySelectorAll('#site-nav a')];
const sections=navLinks.map(link=>document.querySelector(link.getAttribute('href'))).filter(Boolean);
function updateScrollUI(){
  const max=document.documentElement.scrollHeight-window.innerHeight;
  progressBar.style.width=`${max>0?(window.scrollY/max)*100:0}%`;
  header.classList.toggle('is-scrolled',window.scrollY>18);
  backToTop.classList.toggle('visible',window.scrollY>700);
  let current='';
  sections.forEach(section=>{if(window.scrollY>=section.offsetTop-180)current=section.id});
  navLinks.forEach(link=>link.classList.toggle('active',link.getAttribute('href')===`#${current}`));
}
window.addEventListener('scroll',updateScrollUI,{passive:true});
window.addEventListener('resize',updateScrollUI);updateScrollUI();
const heroPhoto=document.querySelector('.hero-photo');
if(heroPhoto&&matchMedia('(min-width:1101px) and (prefers-reduced-motion:no-preference)').matches){
  heroPhoto.addEventListener('pointermove',e=>{const r=heroPhoto.getBoundingClientRect();const x=(e.clientX-r.left)/r.width-.5;const y=(e.clientY-r.top)/r.height-.5;heroPhoto.style.transform=`translate3d(${x*8}px,${y*5}px,0)`});
  heroPhoto.addEventListener('pointerleave',()=>heroPhoto.style.transform='');
}
