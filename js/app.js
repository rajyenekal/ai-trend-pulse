/**
 * AI Trend Pulse — Core Application Controller & Orchestration (js/app.js)
 * v2.1 High-Signal Editorial Architecture
 */

import {
  state,
  initState,
  setThemePreference,
  isItemSaved,
  toggleSaveItem,
  updateSavedCountLabel,
  getFilteredStories,
  setUserFilter,
  toggleUserFilter,
  setSectionFilter,
  persistUserFilters,
  parseStoryTimestamp,
} from './state.js';

import {
  renderTop5Bento,
  renderCompactWire,
  renderEditorialCards,
  renderDispatches,
  renderTopicPills,
  renderCuratedSections,
  renderDeveloperTrends,
  renderDailyOverview,
  renderStatusBar,
  getTopicImageUrl,
  getTopicFallbackSVG,
  formatIST,
} from './render.js';

import {
  openReaderView,
  closeReaderView,
  openSavedDrawer,
  closeSavedDrawer,
  openMethodologyModal,
  closeMethodologyModal,
  handleMethodologyBackdropClick,
  openSearchModal,
  closeSearchModal,
  handleSearchBackdropClick,
  clearModalSearch,
  setSearchFilter,
  updateModalSearchResults,
  renderSavedItemsList,
  toggleAudioBriefing,
  copyReaderStory,
  toggleSaveCurrentReaderItem,
} from './drawer.js';

// Canonical categories definition (10 canonical domains)
export const CANONICAL_CATEGORIES = [
  'Frontier Models',
  'AI Research',
  'AI Agents',
  'Open Source AI',
  'AI Infrastructure',
  'AI Business',
  'AI Safety',
  'AI Policy',
  'Developer Tools',
  'Consumer AI',
];

// -------------------------------------------------------------
// 1. DATA RE-RENDERING PIPELINE
// -------------------------------------------------------------
export function reRenderDevelopments() {
  if (!state.data) return;
  const filtered = getFilteredStories(state.data.top_stories || []);

  // When viewing default unfiltered feed ("All Intelligence" and no search query),
  // avoid repeating the top 5 stories already showcased in the Bento Grid directly above
  const isDefaultView = state.activeTopic === 'all' && state.activeSection === 'all' && !state.searchQuery;
  const displayItems = (isDefaultView && filtered.length > 5) ? filtered.slice(5) : filtered;

  if (state.activeView === 'wire') {
    renderCompactWire(displayItems);
  } else {
    renderEditorialCards(displayItems);
  }

  // Update view mode toggle active states
  const gridBtn = document.getElementById('view-grid-btn');
  const listBtn = document.getElementById('view-list-btn');
  if (gridBtn) gridBtn.classList.toggle('active', state.activeView === 'cards');
  if (listBtn) listBtn.classList.toggle('active', state.activeView === 'wire');

  // Update Hide Case Studies button active state
  const prBtn = document.getElementById('btn-hide-case-studies');
  if (prBtn) prBtn.classList.toggle('active', state.hideCaseStudies);
}

export function renderCompleteUI(data) {
  if (!data) return;
  state.data = data;

  // 1. Compute category counts across top_stories
  const counts = {};
  CANONICAL_CATEGORIES.forEach(c => { counts[c] = 0; });
  (data.top_stories || []).forEach(s => {
    const cat = s.category || s.topic;
    if (cat && counts[cat] !== undefined) {
      counts[cat]++;
    }
  });

  // 2. Render sections with individual component fault isolation
  try { renderDailyOverview(data.daily_overview, data); } catch (e) { console.error('DailyOverview error:', e); }
  try { renderTop5Bento(data.top_stories || []); } catch (e) { console.error('Top5Bento error:', e); }
  try { syncFilterControlsUI(); } catch (e) { console.error('FilterUI error:', e); }
  try { reRenderDevelopments(); } catch (e) { console.error('Developments error:', e); }

  // Dispatches wire feed sorted chronologically so fresh breaking dispatches lead
  try {
    const latestDispatches = [...(data.top_stories || [])].sort((a, b) => {
      const tA = parseStoryTimestamp(a);
      const tB = parseStoryTimestamp(b);
      return tB !== tA ? tB - tA : (Number(b.pulse_score || 0) - Number(a.pulse_score || 0));
    });
    renderDispatches(latestDispatches);
  } catch (e) { console.error('Dispatches error:', e); }

  try { renderTopicPills(CANONICAL_CATEGORIES, counts); } catch (e) { console.error('TopicPills error:', e); }
  try { renderCuratedSections(data); } catch (e) { console.error('CuratedSections error:', e); }
  try { renderDeveloperTrends(data); } catch (e) { console.error('DeveloperTrends error:', e); }
  try { renderStatusBar(data); } catch (e) { console.error('StatusBar error:', e); }
  try { updateSavedCountLabel(); } catch (e) { console.error('SavedCount error:', e); }
}

// -------------------------------------------------------------
// 2. USER ACTIONS & FILTER HANDLERS
// -------------------------------------------------------------
export function handleSearchInput(query) {
  state.searchQuery = query || '';
  const searchInput = document.getElementById('modal-search-input');
  if (searchInput && searchInput.value !== state.searchQuery) {
    searchInput.value = state.searchQuery;
  }
  updateModalSearchResults();
  reRenderDevelopments();
}

export function selectTopicFilter(topic) {
  state.activeTopic = topic || 'All';
  const pillBar = document.getElementById('topic-pills-bar');
  if (pillBar) {
    pillBar.querySelectorAll('.topic-pill').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-topic') === state.activeTopic);
    });
  }
  reRenderDevelopments();
}

export function handleSectionFilterChange(section, btnEl) {
  setSectionFilter(section);
  const bar = document.getElementById('editorial-filter-bar');
  if (bar) {
    bar.querySelectorAll('.editorial-filter-pill').forEach(btn => {
      const isAct = btn.getAttribute('data-section') === section;
      btn.classList.toggle('active', isAct);
      btn.setAttribute('aria-pressed', isAct ? 'true' : 'false');
    });
  }
  reRenderDevelopments();
}

export function toggleFilter(filterKey) {
  toggleUserFilter(filterKey);
  syncFilterControlsUI();
  reRenderDevelopments();
}

export function syncFilterControlsUI() {
  const csBtn = document.getElementById('btn-hide-case-studies');
  if (csBtn) {
    const active = Boolean(state.hideCaseStudies || state.userFilters?.hideCaseStudies);
    csBtn.classList.toggle('active', active);
    csBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
  }
  const preprintsBtn = document.getElementById('btn-hide-preprints');
  if (preprintsBtn) {
    const active = Boolean(state.userFilters?.hidePreprints);
    preprintsBtn.classList.toggle('active', active);
    preprintsBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
  }
  const minorBtn = document.getElementById('btn-hide-minor');
  if (minorBtn) {
    const active = Boolean(state.userFilters?.hideMinorUpdates);
    minorBtn.classList.toggle('active', active);
    minorBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
  }
  const fundingBtn = document.getElementById('btn-hide-funding');
  if (fundingBtn) {
    const active = Boolean(state.userFilters?.hideFunding);
    fundingBtn.classList.toggle('active', active);
    fundingBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
  }
  const opinionBtn = document.getElementById('btn-hide-opinion');
  if (opinionBtn) {
    const active = Boolean(state.userFilters?.hideOpinion);
    opinionBtn.classList.toggle('active', active);
    opinionBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
  }
  const bar = document.getElementById('editorial-filter-bar');
  if (bar) {
    bar.querySelectorAll('.editorial-filter-pill').forEach(btn => {
      const isAct = btn.getAttribute('data-section') === state.activeSectionFilter;
      btn.classList.toggle('active', isAct);
      btn.setAttribute('aria-pressed', isAct ? 'true' : 'false');
    });
  }
}

export function resetAllFilters() {
  state.activeTopic = 'All';
  state.searchQuery = '';
  state.hideCaseStudies = false;
  state.activeSectionFilter = 'all';
  if (state.userFilters) {
    state.userFilters.hideCaseStudies = false;
    state.userFilters.hidePreprints = false;
    state.userFilters.hideMinorUpdates = false;
    state.userFilters.hideFunding = false;
    state.userFilters.hideOpinion = false;
  }
  persistUserFilters();
  state.advancedFilters.tiers = new Set([1, 2, 3, 4]);
  state.advancedFilters.minScore = 0;

  const searchInput = document.getElementById('modal-search-input');
  if (searchInput) searchInput.value = '';

  const pillBar = document.getElementById('topic-pills-bar');
  if (pillBar) {
    pillBar.querySelectorAll('.topic-pill').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-topic') === 'All');
    });
  }

  syncFilterControlsUI();
  updateModalSearchResults();
  reRenderDevelopments();
}

export function setLayoutView(viewMode) {
  state.activeView = viewMode === 'list' || viewMode === 'wire' ? 'wire' : 'cards';
  try {
    localStorage.setItem('ai_trend_view_mode', state.activeView);
  } catch (e) {}
  reRenderDevelopments();
}

export function toggleHideCaseStudies() {
  toggleUserFilter('hideCaseStudies');
  syncFilterControlsUI();
  reRenderDevelopments();
}

export function handleSortChange(sortValue) {
  state.currentSort = sortValue || 'latest';
  reRenderDevelopments();
}

// -------------------------------------------------------------
// 2B. STORY ACTION HANDLERS & IN-APP READER DISPATCHES
// -------------------------------------------------------------
export function openReaderForBento(idx, e) {
  if (e) e.preventDefault();
  const item = state.data?.top_stories?.[idx];
  if (item) openReaderView(item);
}

export function openReaderForTrend(idx, e) {
  if (e) e.preventDefault();
  const filtered = getFilteredStories(state.data?.top_stories || []);
  const isDefaultView = state.activeTopic === 'all' && state.activeSection === 'all' && !state.searchQuery;
  const displayItems = (isDefaultView && filtered.length > 5) ? filtered.slice(5) : filtered;
  const item = displayItems[idx] || filtered[idx] || state.data?.top_stories?.[idx] || state.data?.trends?.[idx];
  if (item) openReaderView(item);
}

export function openReaderForDispatch(idx, e) {
  if (e) e.preventDefault();
  const item = state.data?.top_stories?.[idx] || state.data?.trends?.[idx];
  if (item) openReaderView(item);
}

export function openReaderForCurated(sectionType, idx, e) {
  if (e) e.preventDefault();
  const list = state.data?.[sectionType] || [];
  if (list[idx]) openReaderView(list[idx]);
}

export function openReaderForDailyItem(idx, e) {
  if (e) e.preventDefault();
  const overview = state.data?.daily_overview;
  const topDevs = (overview && overview.top_developments) ? overview.top_developments : [];
  const dev = topDevs[idx];
  if (!dev) return;

  const allStories = [...(state.data?.top_stories || []), ...(state.data?.trends || [])];
  const matched = allStories.find(s => s.title === dev.title || s.link === dev.link);
  if (matched) {
    openReaderView(matched);
  } else {
    openReaderView({
      title: dev.title,
      source: dev.source || 'Verified Source',
      link: dev.link || '#',
      category: 'AI Models & Research',
      what_changed: dev.one_line_explanation || dev.what_changed || dev.summary,
      summary: dev.one_line_explanation || dev.summary,
      why_it_matters: dev.why_it_matters,
      published: 'Today'
    });
  }
}

export function handleSaveTrend(idx, btn) {
  const filtered = getFilteredStories(state.data?.top_stories || []);
  const isDefaultView = state.activeTopic === 'all' && state.activeSection === 'all' && !state.searchQuery;
  const displayItems = (isDefaultView && filtered.length > 5) ? filtered.slice(5) : filtered;
  const item = displayItems[idx] || filtered[idx] || state.data?.top_stories?.[idx];
  if (!item) return;
  const url = (item.evidence_urls && item.evidence_urls[0]) || item.link || '#';
  const isSaved = toggleSaveItem(item.title, item.source, url, item.company, item);
  if (btn) btn.classList.toggle('saved', isSaved);
}

export function handleSaveDispatch(idx, btn) {
  const item = state.data?.top_stories?.[idx];
  if (!item) return;
  const url = item.link || '#';
  const isSaved = toggleSaveItem(item.title, item.source, url, item.company, item);
  if (btn) btn.classList.toggle('saved', isSaved);
}

export function handleSaveCurated(sectionType, idx, btn) {
  const list = state.data?.[sectionType] || [];
  const item = list[idx];
  if (!item) return;
  const url = item.link || '#';
  const isSaved = toggleSaveItem(item.title, item.source, url, item.company, item);
  if (btn) btn.classList.toggle('saved', isSaved);
}

export function handleCopyTrend(idx, btn) {
  const filtered = getFilteredStories(state.data?.top_stories || []);
  const isDefaultView = state.activeTopic === 'all' && state.activeSection === 'all' && !state.searchQuery;
  const displayItems = (isDefaultView && filtered.length > 5) ? filtered.slice(5) : filtered;
  const item = displayItems[idx] || filtered[idx] || state.data?.top_stories?.[idx];
  if (!item) return;
  const text = `${item.title}\n\n${item.what_changed || item.summary || ''}\n\nWhy it matters: ${item.why_it_matters || ''}\nSource: ${item.source}`;
  if (navigator?.clipboard?.writeText) {
    navigator.clipboard.writeText(text);
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = '✓';
      setTimeout(() => { btn.innerHTML = orig; }, 1500);
    }
  }
}

// -------------------------------------------------------------
// 3. APPLICATION BOOTSTRAPPING & EVENT BINDINGS
// -------------------------------------------------------------
export function renderPipelineErrorUI(errorMsg) {
  const statusText = document.getElementById('status-text');
  if (statusText) {
    statusText.innerHTML = '<span style="color:#ef4444; font-weight:700;">● Ingestion Error</span>: Feed sync unreachable';
  }
  const developmentsContainer = document.getElementById('developments-container');
  if (developmentsContainer) {
    developmentsContainer.innerHTML = `
      <div class="pipeline-error-box" role="alert">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" class="error-icon"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
        <h3 class="pipeline-error-title">Unable to Load AI Intelligence Feed</h3>
        <p class="pipeline-error-desc">We encountered an issue fetching the latest intelligence dataset (${escapeHTML(errorMsg || 'Network error')}). The pipeline preserves verified snapshots rather than publishing corrupted state.</p>
        <button class="btn-retry-load" onclick="window.loadData && window.loadData()">Retry Ingestion Sync</button>
      </div>
    `;
  }
  // Clear lingering skeleton loaders so user is not stuck on placeholders
  const bento = document.getElementById('bento-container');
  if (bento && bento.querySelector('.skeleton-card')) bento.innerHTML = '';
  const glance = document.getElementById('catch-me-up-items');
  if (glance && glance.querySelector('.skeleton-card')) glance.innerHTML = '<p style="color:var(--text-muted); font-size:0.85rem; padding:12px;">Data snapshot unavailable.</p>';
  ['developer-trends-container', 'ai-tools-container', 'dev-radar-container', 'research-safety-container', 'stories-container'].forEach(id => {
    const el = document.getElementById(id);
    if (el && el.querySelector('.skeleton-card')) el.innerHTML = '<p style="color:var(--text-muted); font-size:0.85rem; padding:12px;">Intelligence feed temporarily unavailable.</p>';
  });
}

export function initPlatformKbdShortcut() {
  const isMac = typeof navigator !== 'undefined' && (/Mac|iPod|iPhone|iPad/.test(navigator.platform) || /Macintosh|Mac OS X/.test(navigator.userAgent));
  const kbdEls = document.querySelectorAll('.search-kbd');
  kbdEls.forEach(el => {
    el.textContent = isMac ? '⌘K' : 'Ctrl+K';
  });
}

export function initScrollSpy() {
  if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') return;

  const sectionIds = [
    'daily-overview-section',
    'feed-section',
    'developer-trends-section',
    'ai-tools-section',
    'research-safety-section',
    'dispatches-section'
  ];

  const sections = sectionIds.map(id => document.getElementById(id)).filter(Boolean);
  if (sections.length === 0) return;

  const desktopLinks = document.querySelectorAll('.header-nav .nav-link');
  const mobilePills = document.querySelectorAll('.mobile-section-nav .mobile-nav-pill');

  function updateActiveNav(activeId) {
    desktopLinks.forEach(link => {
      const href = link.getAttribute('href');
      link.classList.toggle('active', href === `#${activeId}`);
    });
    mobilePills.forEach(pill => {
      const href = pill.getAttribute('href');
      pill.classList.toggle('active', href === `#${activeId}`);
    });
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        updateActiveNav(entry.target.id);
      }
    });
  }, {
    root: null,
    rootMargin: '-15% 0px -65% 0px',
    threshold: 0
  });

  sections.forEach(s => observer.observe(s));
}

export async function loadData() {
  // 1. Instantaneous 0ms hydration from pre-bundled or cached state
  if (typeof window !== 'undefined' && window.__INITIAL_DATA__) {
    try {
      renderCompleteUI(window.__INITIAL_DATA__);
    } catch (hydrateErr) {
      console.error('Initial state hydration failed:', hydrateErr);
    }
  }

  // 2. Network synchronization for live background delta updates
  try {
    const cacheBuster = `t=${Date.now()}`;
    const resp = await fetch(`data.json?${cacheBuster}`, { cache: 'no-cache' });
    if (!resp.ok) {
      throw new Error(`HTTP error ${resp.status}`);
    }
    const data = await resp.json();
    if (typeof window !== 'undefined') {
      window.__INITIAL_DATA__ = data;
    }
    renderCompleteUI(data);
  } catch (e) {
    console.warn('Network sync for data.json failed; maintaining active intelligence state:', e);
    // Only surface error UI if absolutely no data has hydrated
    if (!state.data && (typeof window === 'undefined' || !window.__INITIAL_DATA__)) {
      renderPipelineErrorUI(e.message);
    }
  }
}

export function setupEventListeners() {
  // Desktop search trigger click & keyboard accessibility
  const searchBarTrigger = document.querySelector('.search-bar-trigger');
  if (searchBarTrigger) {
    searchBarTrigger.addEventListener('click', openSearchModal);
    searchBarTrigger.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openSearchModal();
      }
    });
  }

  // Mobile search button
  const searchMobileBtn = document.querySelector('.search-mobile-btn');
  if (searchMobileBtn) {
    searchMobileBtn.addEventListener('click', openSearchModal);
  }

  // Methodology Modal triggers
  const btnMethodology = document.getElementById('btn-methodology');
  if (btnMethodology) {
    btnMethodology.addEventListener('click', openMethodologyModal);
  }
  const btnCloseMethodology = document.getElementById('btn-close-methodology');
  if (btnCloseMethodology) {
    btnCloseMethodology.addEventListener('click', closeMethodologyModal);
  }

  // Saved Stories Drawer triggers
  const btnSavedFilter = document.getElementById('btn-saved-filter');
  if (btnSavedFilter) {
    btnSavedFilter.addEventListener('click', openSavedDrawer);
  }
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener('click', closeSavedDrawer);
  }

  // Reader View Close trigger
  const btnCloseReader = document.getElementById('btn-close-reader');
  if (btnCloseReader) {
    btnCloseReader.addEventListener('click', closeReaderView);
  }

  // Audio briefing trigger
  const btnAudio = document.getElementById('btn-audio');
  if (btnAudio) {
    btnAudio.addEventListener('click', toggleAudioBriefing);
  }

  // Reader Save & Copy triggers
  const readerBtnSave = document.getElementById('reader-btn-save');
  if (readerBtnSave) {
    readerBtnSave.addEventListener('click', toggleSaveCurrentReaderItem);
  }
  const readerBtnCopy = document.getElementById('reader-btn-copy');
  if (readerBtnCopy) {
    readerBtnCopy.addEventListener('click', copyReaderStory);
  }

  // Sort select handler
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', e => handleSortChange(e.target.value));
  }

  // View toggle buttons
  const viewGridBtn = document.getElementById('view-grid-btn');
  if (viewGridBtn) {
    viewGridBtn.addEventListener('click', () => setLayoutView('grid'));
  }
  const viewListBtn = document.getElementById('view-list-btn');
  if (viewListBtn) {
    viewListBtn.addEventListener('click', () => setLayoutView('list'));
  }

  // 3-Way Theme switcher
  const themeBtnSystem = document.getElementById('theme-btn-system');
  if (themeBtnSystem) {
    themeBtnSystem.addEventListener('click', () => setThemePreference('system'));
  }
  const themeBtnLight = document.getElementById('theme-btn-light');
  if (themeBtnLight) {
    themeBtnLight.addEventListener('click', () => setThemePreference('light'));
  }
  const themeBtnDark = document.getElementById('theme-btn-dark');
  if (themeBtnDark) {
    themeBtnDark.addEventListener('click', () => setThemePreference('dark'));
  }

  // Noise Reduction Toggles
  const btnHideCaseStudies = document.getElementById('btn-hide-case-studies');
  if (btnHideCaseStudies) {
    btnHideCaseStudies.addEventListener('click', toggleHideCaseStudies);
  }
  const btnHidePreprints = document.getElementById('btn-hide-preprints');
  if (btnHidePreprints) {
    btnHidePreprints.addEventListener('click', () => toggleFilter('hidePreprints'));
  }
  const btnHideMinor = document.getElementById('btn-hide-minor');
  if (btnHideMinor) {
    btnHideMinor.addEventListener('click', () => toggleFilter('hideMinorUpdates'));
  }
  const btnHideFunding = document.getElementById('btn-hide-funding');
  if (btnHideFunding) {
    btnHideFunding.addEventListener('click', () => toggleFilter('hideFunding'));
  }
  const btnHideOpinion = document.getElementById('btn-hide-opinion');
  if (btnHideOpinion) {
    btnHideOpinion.addEventListener('click', () => toggleFilter('hideOpinion'));
  }

  // Editorial section filters delegation
  const editorialFilterBar = document.getElementById('editorial-filter-bar');
  if (editorialFilterBar) {
    editorialFilterBar.addEventListener('click', e => {
      const pill = e.target.closest('.editorial-filter-pill');
      if (pill) {
        handleSectionFilterChange(pill.getAttribute('data-section'), pill);
      }
    });
  }

  // Topic Pill delegation
  const topicPillsBar = document.getElementById('topic-pills-bar');
  if (topicPillsBar) {
    topicPillsBar.addEventListener('click', e => {
      const btn = e.target.closest('.topic-pill');
      if (btn) {
        selectTopicFilter(btn.getAttribute('data-topic'));
      }
    });
  }
}

// -------------------------------------------------------------
// 4. BROWSER GLOBAL EXPORTS (For test_qa.js & inline handlers)
// -------------------------------------------------------------
if (typeof window !== 'undefined') {
  window.renderCompleteUI = renderCompleteUI;
  window.setThemePreference = setThemePreference;
  window.toggleSaveItem = toggleSaveItem;
  window.isItemSaved = isItemSaved;
  window.handleSearchInput = handleSearchInput;
  window.selectTopicFilter = selectTopicFilter;
  window.resetAllFilters = resetAllFilters;
  window.setLayoutView = setLayoutView;
  window.toggleHideCaseStudies = toggleHideCaseStudies;
  window.toggleFilter = toggleFilter;
  window.handleSectionFilterChange = handleSectionFilterChange;
  window.syncFilterControlsUI = syncFilterControlsUI;
  window.handleSortChange = handleSortChange;
  window.openReaderView = openReaderView;
  window.closeReaderView = closeReaderView;
  window.openMethodologyModal = openMethodologyModal;
  window.closeMethodologyModal = closeMethodologyModal;
  window.handleMethodologyBackdropClick = handleMethodologyBackdropClick;
  window.openSavedDrawer = openSavedDrawer;
  window.closeSavedDrawer = closeSavedDrawer;
  window.openSearchModal = openSearchModal;
  window.closeSearchModal = closeSearchModal;
  window.handleSearchBackdropClick = handleSearchBackdropClick;
  window.clearModalSearch = clearModalSearch;
  window.setSearchFilter = setSearchFilter;
  window.updateModalSearchResults = updateModalSearchResults;
  window.toggleAudioBriefing = toggleAudioBriefing;
  window.copyReaderStory = copyReaderStory;
  window.toggleSaveCurrentReaderItem = toggleSaveCurrentReaderItem;
  window.getTopicImageUrl = getTopicImageUrl;
  window.getTopicFallbackSVG = getTopicFallbackSVG;
  window.formatIST = formatIST;

  // Story action handlers & reader dispatches
  window.openReaderForBento = openReaderForBento;
  window.openReaderForTrend = openReaderForTrend;
  window.openReaderForDispatch = openReaderForDispatch;
  window.openReaderForCurated = openReaderForCurated;
  window.openReaderForDailyItem = openReaderForDailyItem;
  window.handleSaveTrend = handleSaveTrend;
  window.handleSaveDispatch = handleSaveDispatch;
  window.handleSaveCurated = handleSaveCurated;
  window.handleCopyTrend = handleCopyTrend;
  window.loadData = loadData;

  // Initialize on DOM ready or immediately if document is already interactive
  if (typeof document !== 'undefined' && typeof document.querySelector === 'function') {
    const initApp = () => {
      initState();
      setupEventListeners();
      loadData();
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initApp);
    } else {
      initApp();
    }
  }
}

