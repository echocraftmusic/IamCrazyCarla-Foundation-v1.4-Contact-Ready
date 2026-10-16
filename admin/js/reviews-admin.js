(() => {
'use strict';
const API=window.location.origin; // /api/admin/* routed to the existing Worker on this hostname.
const login=document.querySelector('#login-panel'),dashboard=document.querySelector('#dashboard'),list=document.querySelector('#review-list'),signOut=document.querySelector('#sign-out'),loginStatus=document.querySelector('#login-status');
let reviews=[],filter='pending',checking=false;
const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
async function request(path,method='GET',data){
 const opts={method,credentials:'include',cache:'no-store',headers:{'Accept':'application/json'}};
 if(data!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(data);}
 const result=await fetch(API+path,opts);
 if(!result.ok)throw new Error(result.status===401||result.status===403?'Administrator login required':('API error '+result.status));
 const json=await result.json();return json;
}
async function load(){
 if(checking)return;
 checking=true;
 try{
  const data=await request('/api/admin/reviews');
  if(!Array.isArray(data.reviews))throw new Error('Invalid review response');
  reviews=data.reviews;login.hidden=true;dashboard.hidden=false;signOut.hidden=false;
  for(const s of ['pending','approved','archived'])document.querySelector('#'+s+'-count').textContent=reviews.filter(r=>r.status===s).length;
  render();
 }catch(e){dashboard.hidden=true;login.hidden=false;signOut.hidden=true;loginStatus.textContent='Sign in with Cloudflare, then return to this tab. '+e.message;}finally{checking=false;}
}
function render(){
 const rows=filter==='all'?reviews:reviews.filter(r=>r.status===filter);
 if(!rows.length){list.innerHTML='<div class="empty">No reviews in this group.</div>';return;}
 list.innerHTML=rows.map(r=>`<article class="admin-review" data-id="${esc(r.id)}"><div class="admin-review-head"><div><h3>${esc(r.reviewer_name)}</h3><div class="stars">${'★'.repeat(Math.max(0,Math.min(5,r.rating)))}${'☆'.repeat(Math.max(0,5-r.rating))}</div></div><span class="badge ${esc(r.status)}">${esc(r.status)}</span></div><p class="private-email">Private email: ${esc(r.reviewer_email)} · ${esc(r.category)} · Submitted ${esc(r.created_at)}</p><p class="review-copy">${esc(r.review_text)}</p><div class="actions">${r.status!=='approved'?'<button class="approve" data-action="approve">Approve & publish</button>':'<button class="archive" data-action="archive">Unpublish</button>'}<button class="ghost" data-action="edit">Edit</button>${r.status!=='archived'?'<button class="archive" data-action="archive">Archive</button>':''}<button class="danger" data-action="delete">Delete</button></div></article>`).join('');
}
document.querySelector('#login-form').addEventListener('submit',e=>{e.preventDefault();window.open(API+'/api/admin/reviews','_blank','noopener,noreferrer');loginStatus.textContent='Complete your one-time PIN login in the new tab, then return here. Your dashboard will load automatically.';});
window.addEventListener('focus',()=>{if(!checking)load();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!checking)load();});
document.querySelector('#refresh').addEventListener('click',load);
document.querySelector('#refresh-access').addEventListener('click',load);
signOut.addEventListener('click',()=>{location.href='https://echocraft-aimusic.cloudflareaccess.com/cdn-cgi/access/logout';});
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');filter=b.dataset.filter;render();}));
list.addEventListener('click',async e=>{
 const btn=e.target.closest('button[data-action]');if(!btn)return;
 const id=btn.closest('[data-id]').dataset.id,r=reviews.find(x=>x.id===id),action=btn.dataset.action;
 if(action==='edit'){openEdit(r);return;}
 if(action==='delete'&&!confirm('Permanently delete this review?'))return;
 btn.disabled=true;
 try{if(action==='delete')await request('/api/admin/reviews/'+encodeURIComponent(id),'DELETE');
 else await request('/api/admin/reviews/'+encodeURIComponent(id),'PATCH',{status:action==='approve'?'approved':'archived'});
 await load();}catch(err){alert(err.message);btn.disabled=false;}
});
const dialog=document.querySelector('#edit-dialog'),editForm=document.querySelector('#edit-form');
function openEdit(r){editForm.elements.id.value=r.id;editForm.elements.reviewer_name.value=r.reviewer_name;editForm.elements.category.value=r.category;editForm.elements.rating.value=r.rating;editForm.elements.review_text.value=r.review_text;editForm.elements.featured.checked=!!r.featured;dialog.showModal();}
document.querySelector('#save-edit').addEventListener('click',async e=>{
 e.preventDefault();const v=Object.fromEntries(new FormData(editForm));
 try{await request('/api/admin/reviews/'+encodeURIComponent(v.id),'PATCH',{reviewer_name:v.reviewer_name,category:v.category,rating:Number(v.rating),review_text:v.review_text,featured:Boolean(v.featured)});dialog.close();await load();}
 catch(err){alert(err.message);}
});
load();
})();