(() => {
  const track = document.querySelector('#reviews-track');
  const form = document.querySelector('#review-form');
  const status = document.querySelector('#review-status');
  const prevButton = document.querySelector('#reviews-prev');
  const nextButton = document.querySelector('#reviews-next');
  if (!track || !form) return;

  const API = 'https://reviews-api.iamcrazycarla.com/api/reviews';
  // Review recovery layer:
  // 1) Persist locally before any network call.
  // 2) Try the Cloudflare D1 API first.
  // 3) If D1 is unavailable, send a backup notification through FormSubmit.
  // 4) Quietly retry queued local copies on future visits / when connectivity returns.
  const REVIEW_QUEUE_KEY = 'carla_review_recovery_queue_v1';
  const FALLBACK_ENDPOINT = 'https://formsubmit.co/ajax/troy.saha@gmail.com';

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

  async function saveToCloudflare(item) {
    const response = await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
    if(!response.ok)throw new Error('Review API returned '+response.status);
    const data=await response.json();
    if(!data.success)throw new Error('Review was not accepted');
  }

  // Best-effort notification only AFTER D1 confirms the new review was saved.
  // Email failure must never roll back a review or prompt a second submission.
  async function notifyNewReview(item) {
    const response = await fetch(FALLBACK_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({
        _subject: 'New review awaiting approval — IamCrazyCarla.com',
        _template: 'table',
        _url: 'https://iamcrazycarla.com/#reviews',
        _captcha: 'false',
        reviewer_name: item.reviewer_name,
        category: item.category,
        rating: item.rating + ' / 5',
        review: item.review_text,
        submitted_at: item.created_at,
        review_manager: 'https://iamcrazycarla.com/admin/reviews.html',
        message: 'Saved successfully in Cloudflare D1. Review is pending approval.'
      })
    });
    if (!response.ok) throw new Error('FormSubmit notification HTTP ' + response.status);
    const result = await response.json().catch(() => ({}));
    if (result.success === false || result.success === 'false') {
      throw new Error(result.message || 'FormSubmit did not accept the notification');
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
        recovery_note: 'The D1 API was unavailable when this review was submitted. This copy was preserved automatically for manual recovery if needed.'
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
    if (!queue.length) return;

    for (const item of queue) {
      try {
        await saveToCloudflare(item);
        removeQueuedReview(item.id);
      } catch (primaryError) {
        console.warn('Queued review is still waiting for Cloudflare D1.', primaryError);
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
    try {
      const response=await fetch(API,{cache:'no-store'});
      if(!response.ok)throw new Error('Review API unavailable');
      const data=await response.json();
      render(Array.isArray(data.reviews)?data.reviews:[]);
    } catch(error) {
      console.error('Could not load approved reviews',error);
      track.innerHTML='<div class="reviews-empty">Reviews are temporarily unavailable. Please check back soon.</div>';
    }
  }

  const consentCheckbox = form.querySelector('input[name="consent"]');
  const submitButton = form.querySelector('button[type="submit"]');
  let submitting = false;
  function syncSubmitPermission() {
    submitButton.disabled = submitting || !consentCheckbox.checked;
  }
  consentCheckbox.addEventListener('change', syncSubmitPermission);
  syncSubmitPermission();

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

    submitting = true;
    syncSubmitPermission();
    button.textContent = 'Submitting…';

    let safelyCaptured = false;

    try {
      await saveToCloudflare(item);
      removeQueuedReview(item.id);
      safelyCaptured = true;
      // A failed email notification never changes the confirmed D1 save.
      try {
        await notifyNewReview(item);
      } catch (emailError) {
        console.warn('Review saved in D1, but email notification was not confirmed.', emailError);
      }
    } catch (primaryError) {
      console.warn('Primary review storage unavailable; using recovery path.', primaryError);
      try {
        await saveFallbackCopy(item);
        safelyCaptured = false; // Email backup does not confirm D1 review submission.
      } catch (fallbackError) {
        // Local queue does not guarantee server receipt: do not report successful submission.
        console.warn('Review remains locally queued. No server confirmed receipt.', fallbackError);
        safelyCaptured = false;
      }
    }

    if (safelyCaptured) {
      form.reset();
      status.textContent = 'Thank you. Your review has been received and is being held for approval before publication.';
      status.classList.add('success');
    } else {
      status.textContent = 'Submission could not be confirmed. Please try again later; this browser retained a local recovery copy.';
    }

    submitting = false;
    syncSubmitPermission();
    button.textContent = 'Submit Review';

    // If the primary database came back during the submission, sync any older queued items too.
    retryRecoveryQueue();
  });

  loadReviews();
  retryRecoveryQueue();
})();
