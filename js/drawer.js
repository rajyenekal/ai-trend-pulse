/**
 * AI Trend Pulse — Drawers, Modals & Detail Reader (js/drawer.js)
 * v2.1 High-Signal Editorial Architecture
 */

import { state, isItemSaved, toggleSaveItem } from './state.js';
import { escapeHTML, getCompanyLogoSVG, getTopicImageUrl, formatIST } from './render.js';

let currentReaderStory = null;
let isAudioSpeaking = false;
let activeTriggerElement = null;
let activeFocusTrapCleanup = null;

function activateFocusTrap(modalEl, closeFn) {
  if (activeFocusTrapCleanup) {
    activeFocusTrapCleanup();
    activeFocusTrapCleanup = null;
  }
  if (!modalEl) return;

  if (modalEl.setAttribute) modalEl.setAttribute('aria-hidden', 'false');
  if (modalEl.removeAttribute) modalEl.removeAttribute('inert');

  const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  const focusables = Array.from(modalEl.querySelectorAll(focusableSelector)).filter(el => !el.disabled && el.offsetParent !== null);

  if (focusables.length > 0) {
    const firstFocusable = focusables[0];
    const lastFocusable = focusables[focusables.length - 1];
    setTimeout(() => firstFocusable.focus(), 60);

    const keyHandler = (e) => {
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          if (document.activeElement === firstFocusable) {
            e.preventDefault();
            lastFocusable.focus();
          }
        } else {
          if (document.activeElement === lastFocusable) {
            e.preventDefault();
            firstFocusable.focus();
          }
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        if (closeFn) closeFn();
      }
    };

    modalEl.addEventListener('keydown', keyHandler);
    activeFocusTrapCleanup = () => {
      modalEl.removeEventListener('keydown', keyHandler);
    };
  }
}

function deactivateFocusTrap(modalEl) {
  if (activeFocusTrapCleanup) {
    activeFocusTrapCleanup();
    activeFocusTrapCleanup = null;
  }
  if (modalEl) {
    if (modalEl.setAttribute) {
      modalEl.setAttribute('aria-hidden', 'true');
      modalEl.setAttribute('inert', '');
    }
  }
  if (activeTriggerElement && typeof activeTriggerElement.focus === 'function') {
    try {
      activeTriggerElement.focus();
    } catch (e) {}
    activeTriggerElement = null;
  }
}

// -------------------------------------------------------------
// 1. STORY DETAIL READER VIEW (DRAWER)
// -------------------------------------------------------------
export function openReaderView(story) {
  if (!story) return;
  activeTriggerElement = document.activeElement;
  currentReaderStory = story;

  const drawer = document.getElementById('reader-drawer');
  const backdrop = document.getElementById('reader-backdrop');
  if (!drawer) return;

  // Title
  const titleEl = document.getElementById('reader-title');
  if (titleEl) titleEl.textContent = story.title || 'AI Development';

  // Topic Badge
  const topicBadge = document.getElementById('reader-topic-badge');
  if (topicBadge) {
    topicBadge.textContent = story.category || story.topic || 'AI News';
  }

  // Tier Status Badge
  const statusBadge = document.getElementById('reader-status-badge');
  if (statusBadge) {
    const tier = story.trust_tier || 2;
    statusBadge.className = `badge-tier tier-${tier}`;
    const dot = statusBadge.querySelector('.badge-tier-dot') || document.createElement('span');
    dot.className = 'badge-tier-dot';
    const lbl = statusBadge.querySelector('.badge-tier-label') || document.createElement('span');
    lbl.className = 'badge-tier-label';
    lbl.textContent = story.tier || `Tier ${tier}`;
    if (!statusBadge.children.length) {
      statusBadge.appendChild(dot);
      statusBadge.appendChild(lbl);
    }
  }

  // Reading Time
  const readTime = document.getElementById('reader-readtime');
  if (readTime) readTime.textContent = story.reading_time || '2 min read';

  // Publisher & Pub Date
  const srcName = document.getElementById('reader-source-name');
  if (srcName) srcName.textContent = story.source || 'Primary Source';

  const pubTime = document.getElementById('reader-pub-time');
  if (pubTime) {
    pubTime.textContent = story.published_at ? `Published ${formatIST(story.published_at)}` : (story.published || 'Recently');
  }

  const srcLogo = document.getElementById('reader-source-logo');
  if (srcLogo) srcLogo.innerHTML = getCompanyLogoSVG(story.company);

  // Audio briefing feature detection
  const audioBtn = document.getElementById('btn-audio');
  if (audioBtn) {
    audioBtn.style.display = (typeof window !== 'undefined' && 'speechSynthesis' in window) ? 'inline-flex' : 'none';
  }

  // Visual Image
  const imgEl = document.getElementById('reader-image');
  if (imgEl) {
    imgEl.src = getTopicImageUrl(story.category || story.topic, story.image || story.image_url, story.company);
    imgEl.alt = story.title ? `${story.title} illustration` : 'Story illustration';
  }

  // -----------------------------------------------------------
  // DEDUPLICATION & CROSS-SECTION CONTENT FILTERING ENGINE
  // Eliminates repetitive sentences across Takeaways, Facts, Analysis, and Callouts
  // -----------------------------------------------------------
  const normTitle = (story.title || '').trim().toLowerCase().replace(/[^\w\s]/g, '');

  function normalizeSentence(text) {
    return (text || '').toLowerCase().replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim();
  }

  function areSimilar(a, b) {
    const nA = normalizeSentence(a);
    const nB = normalizeSentence(b);
    if (!nA || !nB) return false;
    if (nA === nB) return true;
    if (nA.includes(nB) && nB.length >= nA.length * 0.7) return true;
    if (nB.includes(nA) && nA.length >= nB.length * 0.7) return true;
    return false;
  }

  // 1. Identify distinct Why It Matters & Potential Impact first so they are reserved for their dedicated cards
  const whyBox = document.getElementById('reader-why-box');
  const whyText = document.getElementById('reader-why-text');
  const rawWhy = (story.why_it_matters || '').trim();
  const distinctWhy = (rawWhy && normalizeSentence(rawWhy) !== normTitle) ? rawWhy : '';

  const impactBox = document.getElementById('reader-impact-box');
  const impactText = document.getElementById('reader-potential-impact');
  const rawImpact = (story.potential_impact || '').trim();
  const distinctImpact = (rawImpact && normalizeSentence(rawImpact) !== normTitle && (!distinctWhy || !areSimilar(rawImpact, distinctWhy))) ? rawImpact : '';

  // 2. Key Takeaways (filtered so they NEVER duplicate Why It Matters, Potential Impact, or Title)
  const kpContainer = document.getElementById('reader-key-points');
  const seenTakeaways = new Set();
  if (normTitle) seenTakeaways.add(normTitle);

  if (kpContainer) {
    kpContainer.innerHTML = '';
    const rawPoints = story.key_points || (story.what_changed ? [story.what_changed] : [story.summary]);
    const uniquePoints = [];

    (Array.isArray(rawPoints) ? rawPoints : [rawPoints]).forEach(pt => {
      const cleanPt = (pt || '').trim();
      if (!cleanPt) return;

      // Filter out if identical to Why It Matters or Potential Impact (they have dedicated cards)
      if (distinctWhy && areSimilar(cleanPt, distinctWhy)) return;
      if (distinctImpact && areSimilar(cleanPt, distinctImpact)) return;

      const normPt = normalizeSentence(cleanPt);
      if (normPt && !seenTakeaways.has(normPt)) {
        seenTakeaways.add(normPt);
        uniquePoints.push(cleanPt);
      }
    });

    if (uniquePoints.length === 0) {
      const fallback = (story.what_changed || story.summary || '').trim();
      if (fallback && (!distinctWhy || !areSimilar(fallback, distinctWhy)) && (!distinctImpact || !areSimilar(fallback, distinctImpact))) {
        uniquePoints.push(fallback);
        seenTakeaways.add(normalizeSentence(fallback));
      } else {
        const cat = story.category || story.topic || 'AI News';
        uniquePoints.push(`Strategic update announced in ${cat}.`);
      }
    }

    uniquePoints.forEach(pt => {
      const li = document.createElement('li');
      li.textContent = pt;
      kpContainer.appendChild(li);
    });
  }

  // 3. Verified Reported Facts (clean, distinct source data points — NEVER repeat takeaway bullets)
  const factsBox = document.getElementById('reader-facts-box');
  const factsList = document.getElementById('reader-facts-list');
  if (factsBox && factsList) {
    factsList.innerHTML = '';
    const rawFacts = Array.isArray(story.reported_facts) ? story.reported_facts : [];
    const uniqueFacts = [];
    const seenFacts = new Set();

    rawFacts.forEach(fact => {
      let cleanFact = (fact || '').trim();
      cleanFact = cleanFact.replace(/^(?:[\w\s.-]+)\s+reported\s+that\s+/i, '');
      if (!cleanFact) return;

      // Must not duplicate title, Why It Matters, Potential Impact, or any Takeaway
      if (distinctWhy && areSimilar(cleanFact, distinctWhy)) return;
      if (distinctImpact && areSimilar(cleanFact, distinctImpact)) return;
      for (const t of seenTakeaways) {
        if (areSimilar(cleanFact, t)) return;
      }

      const normFact = normalizeSentence(cleanFact);
      if (normFact && !seenFacts.has(normFact)) {
        seenFacts.add(normFact);
        uniqueFacts.push(cleanFact);
      }
    });

    if (uniqueFacts.length === 0 && rawFacts.length > 0) {
      const src = story.source || 'official technical documentation';
      uniqueFacts.push(`Primary reporting documented by ${src}.`);
    }

    if (uniqueFacts.length > 0) {
      uniqueFacts.forEach(fact => {
        const li = document.createElement('li');
        li.textContent = fact;
        factsList.appendChild(li);
      });
      factsBox.style.display = 'block';
    } else {
      factsBox.style.display = 'none';
    }
  }

  // 4. In-Depth Story & Context (clean narrative paragraphs without duplicating Potential Impact or Why It Matters)
  const daContainer = document.getElementById('reader-detailed-analysis');
  const contentSection = document.getElementById('reader-content-section') || (typeof document.querySelector === 'function' ? document.querySelector('.reader-content-section') : null);
  if (daContainer) {
    daContainer.innerHTML = '';
    const rawAnalysis = story.detailed_analysis || story.summary || story.what_changed || '';
    const paragraphs = rawAnalysis.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
    const uniqueParagraphs = [];
    const seenParas = new Set();

    paragraphs.forEach(p => {
      if (!p) return;
      // Do NOT repeat Potential Impact or Why It Matters in narrative analysis
      if (distinctImpact && areSimilar(p, distinctImpact)) return;
      if (distinctWhy && areSimilar(p, distinctWhy)) return;

      const normP = normalizeSentence(p);
      if (normP && !seenParas.has(normP)) {
        seenParas.add(normP);
        uniqueParagraphs.push(p);
      }
    });

    // Guarantee at least 1 clean narrative paragraph
    if (uniqueParagraphs.length === 0) {
      const fallback = (story.summary || story.what_changed || story.title || 'Verified AI development dispatch.').trim();
      uniqueParagraphs.push(fallback);
    }

    uniqueParagraphs.forEach(p => {
      const pEl = document.createElement('p');
      pEl.textContent = p;
      daContainer.appendChild(pEl);
    });
    if (contentSection) contentSection.style.display = 'block';
  }

  // 5. Why It Matters Callout
  if (whyBox && whyText) {
    if (distinctWhy) {
      whyText.textContent = distinctWhy;
      whyBox.style.display = 'block';
    } else {
      whyBox.style.display = 'none';
    }
  }

  // 6. Potential Impact Callout
  if (impactBox && impactText) {
    if (distinctImpact) {
      impactText.textContent = distinctImpact;
      impactBox.style.display = 'block';
    } else {
      impactBox.style.display = 'none';
    }
  }

  // Epistemic Bounds & Verification Limitations
  const limBox = document.getElementById('reader-limitations-box');
  const limText = document.getElementById('reader-limitations-text');
  if (limBox && limText) {
    if (story.analysis_limitations) {
      limText.textContent = story.analysis_limitations;
      limBox.style.display = 'block';
    } else {
      limBox.style.display = 'none';
    }
  }

  // Audience & Stakeholders
  const audPills = document.getElementById('reader-audience-pills');
  if (audPills) {
    audPills.innerHTML = '';
    const pills = story.audience_pills || story.affected_stakeholders || (story.target_audience ? [story.target_audience] : ['Developers', 'Enterprises']);
    pills.forEach(pill => {
      const span = document.createElement('span');
      span.className = 'hero-audience-pill';
      span.textContent = pill;
      audPills.appendChild(span);
    });
  }

  // Corroborated Evidence Links (Paired references)
  const corrobBox = document.getElementById('reader-corroboration-box');
  const evList = document.getElementById('reader-evidence-links');
  if (corrobBox && evList) {
    evList.innerHTML = '';
    const evRefs = story.evidence || story.evidence_objects || [];
    if (evRefs.length > 0) {
      evRefs.forEach(ref => {
        const li = document.createElement('li');
        li.className = 'evidence-item';
        li.innerHTML = `
          <a href="${escapeHTML(ref.canonical_url || ref.link)}" target="_blank" rel="noopener noreferrer" class="evidence-link">
            <span class="evidence-source">${escapeHTML(ref.source_name || ref.source || 'Source')}</span>
            <span class="evidence-url">${escapeHTML(ref.canonical_url || ref.link)}</span>
          </a>
        `;
        evList.appendChild(li);
      });
      corrobBox.style.display = 'block';
    } else {
      corrobBox.style.display = 'none';
    }
  }

  // External Action Button
  const extBtn = document.getElementById('reader-external-btn');
  const extName = document.getElementById('reader-source-btn-name');
  if (extBtn) {
    extBtn.onclick = () => window.open(story.link, '_blank', 'noopener,noreferrer');
  }
  if (extName) {
    extName.textContent = story.source || 'Original Source';
  }

  // Update Save button status
  updateReaderSaveButton(story);

  // Open drawer
  drawer.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
  activateFocusTrap(drawer, closeReaderView);
}

export function closeReaderView() {
  const drawer = document.getElementById('reader-drawer');
  const backdrop = document.getElementById('reader-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';

  const imgEl = document.getElementById('reader-image');
  if (imgEl) {
    imgEl.removeAttribute('src');
    imgEl.alt = '';
  }

  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    isAudioSpeaking = false;
    const caption = document.getElementById('audio-caption');
    if (caption) caption.textContent = 'Listen';
  }

  deactivateFocusTrap(drawer);
  currentReaderStory = null;
}

export function updateReaderSaveButton(story) {
  const btn = document.getElementById('reader-btn-save');
  const lbl = document.getElementById('reader-save-label');
  if (!btn || !story) return;

  const saved = isItemSaved(story.title);
  if (lbl) lbl.textContent = saved ? 'Saved' : 'Save';
  btn.style.color = saved ? 'var(--accent)' : 'inherit';
}

export function toggleSaveCurrentReaderItem() {
  if (!currentReaderStory) return;
  toggleSaveItem(
    currentReaderStory.title,
    currentReaderStory.source,
    currentReaderStory.link,
    currentReaderStory.company,
    currentReaderStory
  );
  updateReaderSaveButton(currentReaderStory);
}

export function copyReaderStory() {
  if (!currentReaderStory) return;
  const text = `${currentReaderStory.title}\n\n${currentReaderStory.what_changed || currentReaderStory.summary}\n\nWhy it matters: ${currentReaderStory.why_it_matters || ''}\n\nSource: ${currentReaderStory.link}`;
  
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      const lbl = document.getElementById('reader-copy-label');
      if (lbl) {
        lbl.textContent = 'Copied!';
        setTimeout(() => { lbl.textContent = 'Copy'; }, 2000);
      }
    });
  }
}

export function toggleAudioBriefing() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;

  const caption = document.getElementById('audio-caption');
  if (isAudioSpeaking) {
    window.speechSynthesis.cancel();
    isAudioSpeaking = false;
    if (caption) caption.textContent = 'Listen';
    return;
  }

  if (!currentReaderStory) return;
  const script = `${currentReaderStory.title}. ${currentReaderStory.what_changed || currentReaderStory.summary}. Why it matters: ${currentReaderStory.why_it_matters || ''}`;
  
  const utterance = new window.SpeechSynthesisUtterance(script);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  utterance.onend = () => {
    isAudioSpeaking = false;
    if (caption) caption.textContent = 'Listen';
  };
  utterance.onerror = () => {
    isAudioSpeaking = false;
    if (caption) caption.textContent = 'Listen';
  };

  window.speechSynthesis.speak(utterance);
  isAudioSpeaking = true;
  if (caption) caption.textContent = 'Pause';
}

// -------------------------------------------------------------
// 2. SAVED BOOKMARKS DRAWER
// -------------------------------------------------------------
export function openSavedDrawer() {
  activeTriggerElement = document.activeElement;
  const drawer = document.getElementById('saved-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  renderSavedItemsList();
  if (drawer) drawer.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
  activateFocusTrap(drawer, closeSavedDrawer);
}

export function closeSavedDrawer() {
  const drawer = document.getElementById('saved-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
  deactivateFocusTrap(drawer);
}

export function renderSavedItemsList() {
  const container = document.getElementById('saved-drawer-items');
  if (!container) return;

  if (state.savedStories.length === 0) {
    container.innerHTML = `
      <div style="padding:24px; text-align:center; color:var(--text-muted);">
        <p>No saved stories yet.</p>
        <p style="font-size:0.82rem; margin-top:6px;">Bookmark important dispatches while reading to review them here.</p>
      </div>
    `;
    return;
  }

  let html = '';
  state.savedStories.forEach((item, idx) => {
    html += `
      <div class="saved-item-row" style="padding:12px 16px; border-bottom:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center; gap:12px;">
        <div style="min-width:0;">
          <h4 style="font-size:0.9rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHTML(item.title)}</h4>
          <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHTML(item.source)}</span>
        </div>
        <div style="display:flex; gap:6px;">
          <a href="${escapeHTML(item.link)}" target="_blank" rel="noopener noreferrer" class="btn-action-icon" style="min-height:30px; padding:2px 8px; font-size:0.75rem;">Visit</a>
          <button class="btn-action-icon btn-remove-saved" data-saved-idx="${idx}" style="min-height:30px; padding:2px 8px; font-size:0.75rem; color:#ef4444;">Remove</button>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

// -------------------------------------------------------------
// 3. METHODOLOGY MODAL
// -------------------------------------------------------------
export function openMethodologyModal(e) {
  if (e && e.preventDefault) e.preventDefault();
  activeTriggerElement = document.activeElement;
  const modal = document.getElementById('methodology-modal');
  const backdrop = document.getElementById('methodology-backdrop');
  if (modal) modal.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
  activateFocusTrap(modal, closeMethodologyModal);
}

export function closeMethodologyModal() {
  const modal = document.getElementById('methodology-modal');
  const backdrop = document.getElementById('methodology-backdrop');
  if (modal) modal.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
  deactivateFocusTrap(modal);
}

export function handleMethodologyBackdropClick(e) {
  if (e && e.target && (e.target.id === 'methodology-backdrop' || e.target.classList.contains('methodology-modal-backdrop'))) {
    closeMethodologyModal();
  }
}

// -------------------------------------------------------------
// 4. SEARCH MODAL
// -------------------------------------------------------------
let searchModalScope = 'all';

export function openSearchModal() {
  activeTriggerElement = document.activeElement;
  const modal = document.getElementById('search-modal');
  const box = modal?.querySelector('.search-modal-box');
  if (modal) {
    modal.classList.add('open');
    updateModalSearchResults();
    activateFocusTrap(box, closeSearchModal);
    const input = document.getElementById('modal-search-input');
    if (input) {
      setTimeout(() => input.focus(), 60);
    }
  }
}

export function closeSearchModal() {
  const modal = document.getElementById('search-modal');
  const box = modal?.querySelector('.search-modal-box');
  if (modal) modal.classList.remove('open');
  deactivateFocusTrap(box);
}

export function handleSearchBackdropClick(e) {
  if (e && e.target && (e.target.id === 'search-modal' || e.target.classList.contains('search-modal-backdrop'))) {
    closeSearchModal();
  }
}

export function clearModalSearch() {
  const input = document.getElementById('modal-search-input');
  if (input) input.value = '';
  if (typeof window !== 'undefined' && window.handleSearchInput) {
    window.handleSearchInput('');
  }
}

export function setSearchFilter(scope) {
  searchModalScope = scope || 'all';
  ['all', 'articles', 'companies', 'topics'].forEach(s => {
    const btn = document.getElementById(`chip-${s}`);
    if (btn) btn.classList.toggle('active', s === searchModalScope);
  });
  updateModalSearchResults();
}

export function updateModalSearchResults() {
  const container = document.getElementById('search-results-modal');
  if (!container || !state.data) return;
  container.innerHTML = '';

  const q = (state.searchQuery || '').toLowerCase().trim();
  const allArticles = [...(state.data.trends || []), ...(state.data.top_stories || [])];

  let filtered = allArticles;
  if (q) {
    filtered = allArticles.filter(a => {
      const t = (a.title || '').toLowerCase();
      const s = (a.source || '').toLowerCase();
      const w = (a.what_happened || a.what_changed || a.summary || '').toLowerCase();
      const top = (a.topic || a.category || '').toLowerCase();
      return t.includes(q) || s.includes(q) || w.includes(q) || top.includes(q);
    });
  }

  // Scope filtering
  if (searchModalScope === 'companies') {
    filtered = filtered.filter(a => {
      const comp = (a.company || '').toLowerCase();
      return !q || comp.includes(q);
    });
  } else if (searchModalScope === 'topics') {
    filtered = filtered.filter(a => {
      const top = (a.topic || a.category || '').toLowerCase();
      return !q || top.includes(q);
    });
  } else if (searchModalScope === 'articles') {
    if (q) {
      filtered = filtered.filter(a => {
        const t = (a.title || '').toLowerCase();
        const w = (a.what_happened || a.what_changed || a.summary || '').toLowerCase();
        return t.includes(q) || w.includes(q);
      });
    }
  }

  // Update counters
  const countAll = document.getElementById('count-all');
  const countArticles = document.getElementById('count-articles');
  const countCompanies = document.getElementById('count-companies');
  const countTopics = document.getElementById('count-topics');

  if (countAll) countAll.textContent = filtered.length;
  if (countArticles) countArticles.textContent = filtered.length;
  if (countCompanies) countCompanies.textContent = new Set(filtered.map(f => f.company)).size;
  if (countTopics) countTopics.textContent = new Set(filtered.map(f => f.category || f.topic)).size;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
        No matching developments found for "${escapeHTML(q)}"
      </div>
    `;
    return;
  }

  filtered.slice(0, 8).forEach(item => {
    const div = document.createElement('div');
    div.className = 'saved-item-card';
    div.style.cursor = 'pointer';
    div.onclick = () => {
      closeSearchModal();
      openReaderView(item);
    };

    const comp = item.company || 'default';

    div.innerHTML = `
      <div class="saved-item-logo" aria-hidden="true">
        ${getCompanyLogoSVG(comp)}
      </div>
      <div class="saved-item-details">
        <h4 class="saved-item-title">${escapeHTML(item.title)}</h4>
        <span class="saved-item-meta">${escapeHTML(item.source || 'Lab Report')} • ${escapeHTML(item.published || 'Recently')}</span>
      </div>
    `;
    container.appendChild(div);
  });
}

