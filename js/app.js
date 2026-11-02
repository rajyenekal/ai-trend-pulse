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
} from './state.js';

import {
  renderTop5Bento,
  renderCompactWire,
  renderEditorialCards,
  renderDispatches,
  renderTopicPills,
  renderCuratedSections,
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
  openSearchModal,
  closeSearchModal,
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
  reRenderDevelopments();
  renderDispatches(data.top_stories || []);
  renderTopicPills(CANONICAL_CATEGORIES, counts);
  renderCuratedSections(data);
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

export function resetAllFilters() {
  state.activeTopic = 'All';
  state.searchQuery = '';
  state.hideCaseStudies = false;
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
  state.hideCaseStudies = !state.hideCaseStudies;
  try {
    localStorage.setItem('ai_trend_hide_case_studies', String(state.hideCaseStudies));
  } catch (e) {}
  reRenderDevelopments();
}

export function handleSortChange(sortValue) {
  state.currentSort = sortValue || 'latest';
  reRenderDevelopments();
}

// -------------------------------------------------------------
// 3. APPLICATION BOOTSTRAPPING & EVENT BINDINGS
// -------------------------------------------------------------
export async function loadData() {
  try {
    const resp = await fetch('data.json');
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
  window.handleSortChange = handleSortChange;
  window.openReaderView = openReaderView;
  window.closeReaderView = closeReaderView;
  window.openMethodologyModal = openMethodologyModal;
  window.closeMethodologyModal = closeMethodologyModal;
  window.openSavedDrawer = openSavedDrawer;
  window.closeSavedDrawer = closeSavedDrawer;
  window.openSearchModal = openSearchModal;
  window.closeSearchModal = closeSearchModal;
  window.toggleAudioBriefing = toggleAudioBriefing;
  window.copyReaderStory = copyReaderStory;
  window.toggleSaveCurrentReaderItem = toggleSaveCurrentReaderItem;
  window.getTopicImageUrl = getTopicImageUrl;
  window.getTopicFallbackSVG = getTopicFallbackSVG;
  window.formatIST = formatIST;

  // Initialize on DOM ready
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      initState();
      setupEventListeners();
      loadData();
    });
  }
}
