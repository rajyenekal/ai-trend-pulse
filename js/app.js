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

// Canonical categories definition
export const CANONICAL_CATEGORIES = [
  'AI Policy & Regulation',
  'AI Security & Safety',
  'AI Infrastructure',
  'AI Business & Funding',
  'AI Models & Research',
  'AI Products & Tools',
  'AI Applications',
  'AI News',
];

// -------------------------------------------------------------
// 1. DATA RE-RENDERING PIPELINE
// -------------------------------------------------------------
export function reRenderDevelopments() {
  if (!state.data) return;
  const filtered = getFilteredStories(state.data.top_stories || []);

  if (state.activeView === 'wire') {
    renderCompactWire(filtered);
  } else {
    renderEditorialCards(filtered);
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

  // 2. Render sections
  renderDailyOverview(data.daily_overview, data);
  renderTop5Bento(data.top_stories || []);
  syncFilterControlsUI();
  reRenderDevelopments();

  // Dispatches wire feed sorted chronologically so fresh breaking dispatches lead
  const latestDispatches = [...(data.top_stories || [])].sort((a, b) => {
    const tA = parseStoryTimestamp(a);
    const tB = parseStoryTimestamp(b);
    return tB !== tA ? tB - tA : (Number(b.pulse_score || 0) - Number(a.pulse_score || 0));
  });
  renderDispatches(latestDispatches);
  renderTopicPills(CANONICAL_CATEGORIES, counts);
  renderCuratedSections(data);
  renderDeveloperTrends(data);
  renderStatusBar(data);
  updateSavedCountLabel();
}

// -------------------------------------------------------------
// 2. USER ACTIONS & FILTER HANDLERS
// -------------------------------------------------------------
export function handleSearchInput(query) {
  state.searchQuery = query || '';
  const searchInput = document.getElementById('search-input');
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
      btn.setAttribute('aria-selected', isAct ? 'true' : 'false');
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
    csBtn.classList.toggle('active', Boolean(state.hideCaseStudies || state.userFilters?.hideCaseStudies));
  }
  const preprintsBtn = document.getElementById('btn-hide-preprints');
  if (preprintsBtn) {
    preprintsBtn.classList.toggle('active', Boolean(state.userFilters?.hidePreprints));
  }
  const minorBtn = document.getElementById('btn-hide-minor');
  if (minorBtn) {
    minorBtn.classList.toggle('active', Boolean(state.userFilters?.hideMinorUpdates));
  }
  const fundingBtn = document.getElementById('btn-hide-funding');
  if (fundingBtn) {
    fundingBtn.classList.toggle('active', Boolean(state.userFilters?.hideFunding));
  }
  const opinionBtn = document.getElementById('btn-hide-opinion');
  if (opinionBtn) {
    opinionBtn.classList.toggle('active', Boolean(state.userFilters?.hideOpinion));
  }
  const bar = document.getElementById('editorial-filter-bar');
  if (bar) {
    bar.querySelectorAll('.editorial-filter-pill').forEach(btn => {
      const isAct = btn.getAttribute('data-section') === state.activeSectionFilter;
      btn.classList.toggle('active', isAct);
      btn.setAttribute('aria-selected', isAct ? 'true' : 'false');
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
  
  const searchInput = document.getElementById('search-input');
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
export function openReaderForTrend(idx, e) {
  if (e) e.preventDefault();
  const filtered = getFilteredStories(state.data?.top_stories || []);
  const item = filtered[idx] || state.data?.top_stories?.[idx] || state.data?.trends?.[idx];
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
  const item = filtered[idx] || state.data?.top_stories?.[idx];
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
  const item = filtered[idx] || state.data?.top_stories?.[idx];
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
export async function loadData() {
  try {
    const cacheBuster = `t=${Date.now()}`;
    const resp = await fetch(`data.json?${cacheBuster}`, { cache: 'no-cache' });
    if (!resp.ok) {
      throw new Error(`HTTP error ${resp.status}`);
    }
    const data = await resp.json();
    renderCompleteUI(data);
  } catch (e) {
    console.error('Failed to load data.json:', e);
    const statusText = document.getElementById('status-text');
    if (statusText) {
      statusText.textContent = '⚠️ Could not load latest intelligence payload.';
    }
  }
}

export function setupEventListeners() {
  // Desktop search trigger keyboard accessibility (Enter/Space on div[role="button"])
  const searchBarTrigger = document.querySelector('.search-bar-trigger');
  if (searchBarTrigger) {
    searchBarTrigger.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openSearchModal();
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

  // Card clicks delegation (Open Reader Drawer)
  document.addEventListener('click', e => {
    // Bento card click
    const bentoCard = e.target.closest('.bento-card');
    if (bentoCard && state.data && state.data.top_stories) {
      const idx = parseInt(bentoCard.getAttribute('data-story-idx'), 10);
      if (!isNaN(idx) && state.data.top_stories[idx]) {
        openReaderView(state.data.top_stories[idx]);
        return;
      }
    }

    // Developments card click
    const devCard = e.target.closest('.card-standard');
    if (devCard) {
      const idx = parseInt(devCard.getAttribute('data-card-idx'), 10);
      const filtered = getFilteredStories(state.data?.top_stories || []);
      if (!isNaN(idx) && filtered[idx]) {
        openReaderView(filtered[idx]);
        return;
      }
    }

    // Wire row click
    const wireRow = e.target.closest('.wire-row');
    if (wireRow) {
      const idx = parseInt(wireRow.getAttribute('data-wire-idx'), 10);
      const filtered = getFilteredStories(state.data?.top_stories || []);
      if (!isNaN(idx) && filtered[idx]) {
        openReaderView(filtered[idx]);
        return;
      }
    }

    // Curated card click
    const curatedCard = e.target.closest('[data-curated-section]');
    if (curatedCard && state.data) {
      const section = curatedCard.getAttribute('data-curated-section');
      const idx = parseInt(curatedCard.getAttribute('data-curated-idx'), 10);
      let items = [];
      if (section === 'ai-tools-container') items = state.data.ai_tools;
      else if (section === 'dev-radar-container') items = state.data.dev_radar;
      else if (section === 'research-safety-container') items = state.data.research_safety;
      if (items && items[idx]) {
        openReaderView(items[idx]);
        return;
      }
    }
  });

  // Saved drawer item removal delegation
  const savedContainer = document.getElementById('saved-drawer-items');
  if (savedContainer) {
    savedContainer.addEventListener('click', e => {
      const btn = e.target.closest('.btn-remove-saved');
      if (btn) {
        const idx = parseInt(btn.getAttribute('data-saved-idx'), 10);
        if (!isNaN(idx) && state.savedStories[idx]) {
          toggleSaveItem(state.savedStories[idx].title);
          renderSavedItemsList();
        }
      }
    });
  }

  // Global Keyboard Shortcuts
  window.addEventListener('keydown', e => {
    // 'Escape' closes any open modal or drawer
    if (e.key === 'Escape') {
      closeReaderView();
      closeSavedDrawer();
      closeMethodologyModal();
      closeSearchModal();
    }
    // '⌘K' or '/' opens search modal
    if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && document.activeElement?.tagName !== 'INPUT')) {
      e.preventDefault();
      openSearchModal();
    }
  });
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
  window.openReaderForTrend = openReaderForTrend;
  window.openReaderForDispatch = openReaderForDispatch;
  window.openReaderForCurated = openReaderForCurated;
  window.openReaderForDailyItem = openReaderForDailyItem;
  window.handleSaveTrend = handleSaveTrend;
  window.handleSaveDispatch = handleSaveDispatch;
  window.handleSaveCurated = handleSaveCurated;
  window.handleCopyTrend = handleCopyTrend;

  // Initialize on DOM ready
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      initState();
      setupEventListeners();
      loadData();
    });
  }
}

