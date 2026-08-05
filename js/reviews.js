(() => {
  const track = document.querySelector('#reviews-track');
  const form = document.querySelector('#review-form');
  const status = document.querySelector('#review-status');
  const prevButton = document.querySelector('#reviews-prev');
  const nextButton = document.querySelector('#reviews-next');
  if (!track || !form) return;

  const config = window.CARLA_SUPABASE || {};
  const configured = config.url && config.anonKey && !config.url.startsWith('YOUR_');
  const client = configured && window.supabase ? window.supabase.createClient(config.url, config.anonKey) : null;

  const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const displayName = value => {
    const parts = String(value || 'Guest').trim().split(/\s+/);
    return parts.length > 1 ? `${parts[0]} ${parts.at(-1)[0]}.` : parts[0];
  };
  const updateNavigation = () => {
    if (!prevButton || !nextButton) return;
    const maxScroll = Math.max(0, track.scrollWidth - track.clientWidth - 4);
    prevButton.disabled = track.scrollLeft <= 4;
    nextButton.disabled = track.scrollLeft >= maxScroll;
  };

  const render = reviews => {
    track.classList.remove('review-count-1','review-count-2','review-count-many');
    track.classList.add(reviews.length === 1 ? 'review-count-1' : reviews.length === 2 ? 'review-count-2' : 'review-count-many');
    if (!reviews.length) {
      track.innerHTML = '<div class="reviews-empty">Carla’s approved reviews will appear here soon.</div>';
      updateNavigation();
      return;
    }
    track.innerHTML = reviews.map(review => `
      <article class="review-card${review.featured ? ' featured' : ''}">
        <div class="review-stars" aria-label="${review.rating} out of 5 stars">${'★'.repeat(review.rating)}${'☆'.repeat(5-review.rating)}</div>
        <blockquote>“${escapeHTML(review.review_text)}”</blockquote>
        <div class="review-meta"><strong>${escapeHTML(displayName(review.reviewer_name))}</strong><span class="review-category">${escapeHTML(review.category || 'Review')}</span></div>
      </article>`).join('');
    requestAnimationFrame(updateNavigation);
  };

  const scrollReviews = direction => {
    const card = track.querySelector('.review-card');
    const distance = card ? card.getBoundingClientRect().width + 16 : track.clientWidth * .86;
    track.scrollBy({ left: direction * distance, behavior: 'smooth' });
  };
  prevButton?.addEventListener('click', () => scrollReviews(-1));
  nextButton?.addEventListener('click', () => scrollReviews(1));
  track.addEventListener('scroll', updateNavigation, { passive: true });
  window.addEventListener('resize', updateNavigation);

  async function loadReviews() {
    if (!client) {
      render([
        {reviewer_name:'Sample Reviewer',rating:5,category:'Audience or Viewer',review_text:'This is a preview card. Approved reviews submitted through Carla’s review system will appear here automatically.',featured:true}
      ]);
      return;
    }
    const { data, error } = await client.from('reviews').select('id,reviewer_name,rating,category,review_text,featured,approved_at').eq('status','approved').order('featured',{ascending:false}).order('approved_at',{ascending:false}).limit(12);
    if (error) { console.error(error); render([]); return; }
    render(data || []);
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    status.className='review-status';
    const button=form.querySelector('button[type="submit"]');
    const values=Object.fromEntries(new FormData(form));
    if (values.website) return;
    if (!client) {
      status.textContent='The review form design is ready, but Supabase still needs to be connected before submissions can be accepted.';
      status.classList.add('error');
      return;
    }
    button.disabled=true; button.textContent='Submitting…';
    const payload={
      reviewer_name:String(values.reviewer_name).trim(),
      reviewer_email:String(values.reviewer_email).trim().toLowerCase(),
      category:String(values.category),
      rating:Number(values.rating),
      review_text:String(values.review_text).trim(),
      consent:Boolean(values.consent),
      status:'pending'
    };
    const { error }=await client.from('reviews').insert(payload);
    if (error) {
      console.error(error); status.textContent='Your review could not be submitted. Please try again shortly.'; status.classList.add('error');
    } else {
      form.reset(); status.textContent='Thank you. Your review was submitted privately and will appear only if Carla approves it.'; status.classList.add('success');
    }
    button.disabled=false; button.textContent='Submit Review';
  });
  loadReviews();
})();
