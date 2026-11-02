/**
 * AI Trend Pulse — Drawers, Modals & Detail Reader (js/drawer.js)
 * v2.1 High-Signal Editorial Architecture
 */

import { state, isItemSaved, toggleSaveItem } from './state.js';
import { escapeHTML, getCompanyLogoSVG, getTopicImageUrl, formatIST } from './render.js';

let currentReaderStory = null;
let isAudioSpeaking = false;

// -------------------------------------------------------------
// 1. STORY DETAIL READER VIEW (DRAWER)
// -------------------------------------------------------------
export function openReaderView(story) {
  if (!story) return;
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

  // Visual Image
  const imgEl = document.getElementById('reader-image');
  if (imgEl) {
    imgEl.src = getTopicImageUrl(story.category || story.topic, story.image || story.image_url, story.company);
    imgEl.alt = story.title || 'Story visual';
  }

  // Key Takeaways (deduplicated against headline)
  const kpContainer = document.getElementById('reader-key-points');
  if (kpContainer) {
    kpContainer.innerHTML = '';
    const points = story.key_points || (story.what_changed ? [story.what_changed] : [story.summary]);
    const normTitle = (story.title || '').trim().toLowerCase();
    
    points.forEach(pt => {
      const cleanPt = (pt || '').trim();
      if (cleanPt && cleanPt.toLowerCase() !== normTitle) {
        const li = document.createElement('li');
        li.textContent = cleanPt;
        kpContainer.appendChild(li);
      }
    });

    if (!kpContainer.children.length && story.summary) {
      const li = document.createElement('li');
      li.textContent = story.summary;
      kpContainer.appendChild(li);
    }
  }

  // Verified Reported Facts
  const factsBox = document.getElementById('reader-facts-box');
  const factsList = document.getElementById('reader-facts-list');
  if (factsBox && factsList) {
    factsList.innerHTML = '';
    if (story.reported_facts && Array.isArray(story.reported_facts) && story.reported_facts.length > 0) {
      story.reported_facts.forEach(fact => {
        const li = document.createElement('li');
        li.textContent = fact;
        factsList.appendChild(li);
      });
      factsBox.style.display = 'block';
    } else {
      factsBox.style.display = 'none';
    }
  }

  // Detailed Analysis (deduplicated against headline and each other)
  const daContainer = document.getElementById('reader-detailed-analysis');
  if (daContainer) {
    daContainer.innerHTML = '';
    const normTitle = (story.title || '').trim().toLowerCase();
    const rawAnalysis = story.detailed_analysis || story.summary || story.what_changed || '';
    const paragraphs = rawAnalysis.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
    const seen = new Set();

    paragraphs.forEach(p => {
      const pNorm = p.toLowerCase();
      if (pNorm !== normTitle && !seen.has(pNorm)) {
        seen.add(pNorm);
        const pEl = document.createElement('p');
        pEl.textContent = p;
        daContainer.appendChild(pEl);
      }
    });

    if (!daContainer.children.length) {
      const pEl = document.createElement('p');
      pEl.textContent = story.what_changed || story.summary || 'Verified AI development dispatch.';
      daContainer.appendChild(pEl);
    }
  }

  // Why It Matters Callout
  const whyBox = document.getElementById('reader-why-box');
  const whyText = document.getElementById('reader-why-text');
  if (whyBox && whyText) {
    if (story.why_it_matters) {
      whyText.textContent = story.why_it_matters;
      whyBox.style.display = 'block';
    } else {
      whyBox.style.display = 'none';
    }
  }

  // Potential Impact
  const impactBox = document.getElementById('reader-impact-box');
  const impactText = document.getElementById('reader-potential-impact');
  if (impactBox && impactText) {
    if (story.potential_impact) {
      impactText.textContent = story.potential_impact;
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
}

export function closeReaderView() {
  const drawer = document.getElementById('reader-drawer');
  const backdrop = document.getElementById('reader-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
  currentReaderStory = null;

  if (isAudioSpeaking && typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    isAudioSpeaking = false;
    const caption = document.getElementById('audio-caption');
    if (caption) caption.textContent = 'Listen';
  }
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
  const drawer = document.getElementById('saved-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  renderSavedItemsList();
  if (drawer) drawer.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
}

export function closeSavedDrawer() {
  const drawer = document.getElementById('saved-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  if (drawer) drawer.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
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
  if (e) e.preventDefault();
  const modal = document.getElementById('methodology-modal');
  const backdrop = document.getElementById('methodology-backdrop');
  if (modal) modal.classList.add('open');
  if (backdrop) backdrop.classList.add('open');
  document.body.style.overflow = 'hidden';
}

export function closeMethodologyModal() {
  const modal = document.getElementById('methodology-modal');
  const backdrop = document.getElementById('methodology-backdrop');
  if (modal) modal.classList.remove('open');
  if (backdrop) backdrop.classList.remove('open');
  document.body.style.overflow = '';
}

// -------------------------------------------------------------
// 4. SEARCH MODAL
// -------------------------------------------------------------
export function openSearchModal() {
  const modal = document.getElementById('search-modal');
  if (modal) {
    modal.classList.add('open');
    const input = document.getElementById('modal-search-input');
    if (input) {
      setTimeout(() => input.focus(), 50);
    }
  }
}

export function closeSearchModal() {
  const modal = document.getElementById('search-modal');
  if (modal) modal.classList.remove('open');
}

