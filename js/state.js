/**
 * AI Trend Pulse — Reactive State Store & Persistence Layer (js/state.js)
 * v2.1 High-Signal Editorial Architecture
 */

const STORAGE_KEYS = {
  THEME: 'ai_trend_theme_preference',
  BOOKMARKS: 'ai_trend_saved_stories_v2',
  VIEW_MODE: 'ai_trend_view_mode',
  HIDE_CASE_STUDIES: 'ai_trend_hide_case_studies',
};

export const state = {
  data: null,
  activeView: 'cards', // 'cards' (editorial grid) or 'wire' (compact scannable rows)
  hideCaseStudies: false,
  activeTopic: 'All',
  searchQuery: '',
  currentSort: 'latest',
  advancedFilters: {
    tiers: new Set([1, 2, 3, 4]),
    minScore: 0,
    timeHorizonHours: 72,
  },
  savedStories: [],
  themePreference: 'system',
};

// Initialize persistent settings from localStorage safely
export function initState() {
  try {
    state.themePreference = localStorage.getItem(STORAGE_KEYS.THEME) || 'system';
    state.activeView = localStorage.getItem(STORAGE_KEYS.VIEW_MODE) || 'cards';
    state.hideCaseStudies = localStorage.getItem(STORAGE_KEYS.HIDE_CASE_STUDIES) === 'true';
    
    const saved = localStorage.getItem(STORAGE_KEYS.BOOKMARKS);
    if (saved) {
      state.savedStories = JSON.parse(saved);
    }
  } catch (e) {
    console.warn('LocalStorage unavailable or corrupted:', e);
  }
}

// -------------------------------------------------------------
// THEME PREFERENCE MANAGEMENT
// -------------------------------------------------------------
export function setThemePreference(preference) {
  state.themePreference = preference;
  try {
    localStorage.setItem(STORAGE_KEYS.THEME, preference);
  } catch (e) {}

  document.documentElement.setAttribute('data-theme-preference', preference);
  
  const sysDark = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  let activeTheme = 'dark';
  if (preference === 'light') activeTheme = 'light';
  else if (preference === 'dark') activeTheme = 'dark';
  else activeTheme = sysDark ? 'dark' : 'light';
  
  document.documentElement.setAttribute('data-theme', activeTheme);

  // Update theme button aria-checked states
  ['system', 'light', 'dark'].forEach(t => {
    const btn = document.getElementById(`theme-btn-${t}`);
    if (btn) {
      btn.setAttribute('aria-checked', preference === t ? 'true' : 'false');
    }
  });
}

// -------------------------------------------------------------
// BOOKMARKING / SAVED STORIES STORAGE
// -------------------------------------------------------------
export function isItemSaved(title) {
  if (!title) return false;
  const tNorm = title.trim().toLowerCase();
  return state.savedStories.some(s => (s.title || '').trim().toLowerCase() === tNorm);
}

export function toggleSaveItem(title, source, link, company, fullStory = null) {
  if (!title) return false;
  const tNorm = title.trim().toLowerCase();
  const existingIdx = state.savedStories.findIndex(s => (s.title || '').trim().toLowerCase() === tNorm);

  if (existingIdx >= 0) {
    state.savedStories.splice(existingIdx, 1);
  } else {
    state.savedStories.unshift({
      title: title.trim(),
      source: source || 'AI News',
      link: link || '#',
      company: company || 'default',
      saved_at: new Date().toISOString(),
      story: fullStory,
    });
  }

  try {
    localStorage.setItem(STORAGE_KEYS.BOOKMARKS, JSON.stringify(state.savedStories));
  } catch (e) {}

  updateSavedCountLabel();
  return isItemSaved(title);
}

export function updateSavedCountLabel() {
  const lbl = document.getElementById('saved-count-label');
  if (lbl) {
    lbl.textContent = `Saved (${state.savedStories.length})`;
  }
}

// -------------------------------------------------------------
// FILTERING & SORTING LOGIC
// -------------------------------------------------------------
export function getFilteredStories(stories) {
  if (!stories || !Array.isArray(stories)) return [];

  return stories.filter(story => {
    // 1. Hide vendor PR / single-source case studies toggle
    if (state.hideCaseStudies && story.article_type === 'case_study_pr') {
      return false;
    }

    // 2. Topic category filter
    if (state.activeTopic && state.activeTopic !== 'All') {
      const cat = story.category || story.topic || '';
      if (cat.toLowerCase() !== state.activeTopic.toLowerCase()) {
        return false;
      }
    }

    // 3. Search query filter
    if (state.searchQuery && state.searchQuery.trim()) {
      const q = state.searchQuery.trim().toLowerCase();
      const content = `${story.title || ''} ${story.summary || ''} ${story.what_changed || ''} ${story.source || ''} ${story.company || ''}`.toLowerCase();
      if (!content.includes(q)) {
        return false;
      }
    }

    // 4. Trust Tier filter
    const tier = Number(story.trust_tier || 2);
    if (!state.advancedFilters.tiers.has(tier)) {
      return false;
    }

    // 5. Minimum Pulse Score filter
    const score = Number(story.pulse_score || story.overall_score || 0);
    if (score < state.advancedFilters.minScore) {
      return false;
    }

    return true;
  }).sort((a, b) => {
    if (state.currentSort === 'reading-time') {
      const tA = parseInt(a.reading_time || '2', 10);
      const tB = parseInt(b.reading_time || '2', 10);
      return tB - tA;
    }
    if (state.currentSort === 'title') {
      return (a.title || '').localeCompare(b.title || '');
    }
    // Default: pulse score descending
    const sA = Number(a.pulse_score || a.overall_score || 0);
    const sB = Number(b.pulse_score || b.overall_score || 0);
    return sB - sA;
  });
}
