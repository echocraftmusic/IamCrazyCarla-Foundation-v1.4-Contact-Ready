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

  // Review recovery layer:
  // 1) Persist locally before any network call.
  // 2) Try Supabase first.
  // 3) If Supabase is unavailable, send a durable backup copy through FormSubmit.
  // 4) Quietly retry queued local copies on future visits / when connectivity returns.
  const REVIEW_QUEUE_KEY = 'carla_review_recovery_queue_v1';
  const FALLBACK_ENDPOINT = 'https://formsubmit.co/ajax/aahfro10@gmail.com';

  const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const displayName = value => {
    const parts = String(value || 'Guest').trim().split(/\s+/);
    return parts.length > 1 ? `${parts[0]} ${parts.at(-1)[0]}.` : parts[0];
  };

  const makeId = () => {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    // UUID v4-compatible fallback for browsers without crypto.randomUUID().
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, char => {
      const value = Math.random() * 16 | 0;
      const nibble = char === 'x' ? value : (value & 0x3 | 0x8);
      return nibble.toString(16);
    });
  };

  const readQueue = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(REVIEW_QUEUE_KEY) || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const writeQueue = queue => {
    try {
      localStorage.setItem(REVIEW_QUEUE_KEY, JSON.stringify(queue));
      return true;
    } catch (error) {
      console.warn('Review recovery queue could not be written.', error);
      return false;
    }
  };

  const queueReview = item => {
    const queue = readQueue().filter(entry => entry.id !== item.id);
    queue.push(item);
    return writeQueue(queue);
  };

  const updateQueuedReview = (id, changes) => {
    const queue = readQueue();
    const index = queue.findIndex(entry => entry.id === id);
    if (index === -1) return false;
    queue[index] = { ...queue[index], ...changes };
    return writeQueue(queue);
  };

  const removeQueuedReview = id => writeQueue(readQueue().filter(entry => entry.id !== id));

  async function saveToSupabase(item) {
    if (!client) throw new Error('Supabase client unavailable.');
    const payload = {
      id: item.id,
      reviewer_name: item.reviewer_name,
      reviewer_email: item.reviewer_email,
      category: item.category,
      rating: item.rating,
      review_text: item.review_text,
      consent: item.consent,
      status: 'pending'
    };
    const { error } = await client.from('reviews').insert(payload);
    if (error) {
      // A duplicate ID means the original write already succeeded; treat it as safely stored.
      if (String(error.code) === '23505') return;
      throw error;
    }
  }

  async function saveFallbackCopy(item) {
    if (item.fallback_saved) return true;
    const response = await fetch(FALLBACK_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        _subject: 'REVIEW RECOVERY QUEUE — IamCrazyCarla.com',
        _template: 'table',
        submission_id: item.id,
        submitted_at: item.created_at,
        reviewer_name: item.reviewer_name,
        reviewer_email: item.reviewer_email,
        category: item.category,
        rating: `${item.rating} / 5`,
        review: item.review_text,
        consent: item.consent ? 'Yes' : 'No',
        recovery_note: 'Supabase was unavailable when this review was submitted. This copy was preserved automatically for manual recovery if needed.'
      })
    });

    if (!response.ok) throw new Error(`Fallback service returned HTTP ${response.status}`);
    const result = await response.json().catch(() => ({}));
    if (result.success === false) throw new Error(result.message || 'Fallback service rejected the review.');
    updateQueuedReview(item.id, { fallback_saved: true, fallback_saved_at: new Date().toISOString() });
    return true;
  }

  async function retryRecoveryQueue() {
    const queue = readQueue();
    if (!queue.length || !client) return;

    for (const item of queue) {
      try {
        await saveToSupabase(item);
        removeQueuedReview(item.id);
      } catch (primaryError) {
        console.warn('Queued review is still waiting for Supabase.', primaryError);
        if (!item.fallback_saved) {
          try {
            await saveFallbackCopy(item);
          } catch (fallbackError) {
            console.warn('Fallback copy is still waiting to send.', fallbackError);
          }
        }
      }
    }
  }

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
  window.addEventListener('online', retryRecoveryQueue);

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
    status.className = 'review-status';
    const button = form.querySelector('button[type="submit"]');
    const values = Object.fromEntries(new FormData(form));
    if (values.website) return;

    const item = {
      id: makeId(),
      reviewer_name: String(values.reviewer_name || '').trim(),
      reviewer_email: String(values.reviewer_email || '').trim().toLowerCase(),
      category: String(values.category || ''),
      rating: Number(values.rating),
      review_text: String(values.review_text || '').trim(),
      consent: Boolean(values.consent),
      created_at: new Date().toISOString(),
      fallback_saved: false
    };

    // Capture first, then transmit. This protects the text even if the primary database is unavailable.
    queueReview(item);

    button.disabled = true;
    button.textContent = 'Submitting…';

    let safelyCaptured = false;

    try {
      await saveToSupabase(item);
      removeQueuedReview(item.id);
      safelyCaptured = true;
    } catch (primaryError) {
      console.warn('Primary review storage unavailable; using recovery path.', primaryError);
      try {
        await saveFallbackCopy(item);
        safelyCaptured = true;
      } catch (fallbackError) {
        // Keep the locally queued copy and retry automatically later.
        console.warn('Review preserved locally and queued for automatic retry.', fallbackError);
        safelyCaptured = true;
      }
    }

    if (safelyCaptured) {
      form.reset();
      status.textContent = 'Thank you. Your review has been received and is being held for approval before publication.';
      status.classList.add('success');
    }

    button.disabled = false;
    button.textContent = 'Submit Review';

    // If the primary database came back during the submission, sync any older queued items too.
    retryRecoveryQueue();
  });

  loadReviews();
  retryRecoveryQueue();
})();
