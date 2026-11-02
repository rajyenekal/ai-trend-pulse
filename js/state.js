/**
 * AI Trend Pulse — Reactive State Store & Persistence Layer (js/state.js)
 * v2.1 High-Signal Editorial Architecture
 */

const STORAGE_KEYS = {
  THEME: 'ai_trend_theme_preference',
  BOOKMARKS: 'ai_trend_saved_stories_v2',
  VIEW_MODE: 'ai_trend_view_mode',
  HIDE_CASE_STUDIES: 'ai_trend_hide_case_studies',
  USER_FILTERS: 'ai_trend_editorial_user_filters',
  ACTIVE_SECTION: 'ai_trend_active_section_filter',
};

export const state = {
  data: null,
  activeView: 'cards', // 'cards' (editorial grid) or 'wire' (compact scannable rows)
  hideCaseStudies: false,
  activeTopic: 'All',
  activeSectionFilter: 'all', // 'all', 'briefing', 'research', 'developer', 'industry', 'safety'
  userFilters: {
    hideCaseStudies: false,
    hidePreprints: false,
    hideMinorUpdates: false,
    hideFunding: false,
    hideOpinion: false,
  },
  activeDevLanguage: 'All',
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
    state.activeSectionFilter = localStorage.getItem(STORAGE_KEYS.ACTIVE_SECTION) || 'all';

    const savedLegacyHide = localStorage.getItem(STORAGE_KEYS.HIDE_CASE_STUDIES) === 'true';
    const savedUserFilters = localStorage.getItem(STORAGE_KEYS.USER_FILTERS);
    if (savedUserFilters) {
      try {
        const parsed = JSON.parse(savedUserFilters);
        state.userFilters = Object.assign({}, state.userFilters, parsed);
      } catch (e) {}
    } else if (savedLegacyHide) {
      state.userFilters.hideCaseStudies = true;
    }
    state.hideCaseStudies = Boolean(state.userFilters.hideCaseStudies);

    const saved = localStorage.getItem(STORAGE_KEYS.BOOKMARKS);
    if (saved) {
      state.savedStories = JSON.parse(saved);
    }
  } catch (e) {
    console.warn('LocalStorage unavailable or corrupted:', e);
  }
}

export function persistUserFilters() {
  try {
    localStorage.setItem(STORAGE_KEYS.USER_FILTERS, JSON.stringify(state.userFilters));
    localStorage.setItem(STORAGE_KEYS.HIDE_CASE_STUDIES, String(state.userFilters.hideCaseStudies));
    localStorage.setItem(STORAGE_KEYS.ACTIVE_SECTION, state.activeSectionFilter);
  } catch (e) {}
}

export function setUserFilter(key, value) {
  if (key in state.userFilters) {
    state.userFilters[key] = Boolean(value);
    if (key === 'hideCaseStudies') {
      state.hideCaseStudies = state.userFilters.hideCaseStudies;
    }
    persistUserFilters();
  }
}

export function toggleUserFilter(key) {
  if (key in state.userFilters) {
    state.userFilters[key] = !state.userFilters[key];
    if (key === 'hideCaseStudies') {
      state.hideCaseStudies = state.userFilters.hideCaseStudies;
    }
    persistUserFilters();
    return state.userFilters[key];
  }
  return false;
}

export function setSectionFilter(section) {
  state.activeSectionFilter = section || 'all';
  persistUserFilters();
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
    const artType = story.article_type || '';
    const titleLower = (story.title || '').toLowerCase();
    const summaryLower = (story.summary || '').toLowerCase();

    // 1. User Filter Toggles: Case Studies, Preprints, Minor Updates, Funding, Opinion
    if ((state.hideCaseStudies || state.userFilters?.hideCaseStudies) && (artType === 'case_study_pr' || titleLower.includes('case study') || (titleLower.includes('how ') && titleLower.includes(' uses ')))) {
      return false;
    }
    if (state.userFilters?.hidePreprints && (artType === 'research_paper' || story.evidence_status === 'research_preprint' || (story.source && story.source.toLowerCase().includes('arxiv')))) {
      return false;
    }
    if (state.userFilters?.hideMinorUpdates && artType === 'routine_minor_update') {
      return false;
    }
    if (state.userFilters?.hideFunding && (titleLower.includes('raises $') || titleLower.includes('secures $') || titleLower.includes('series a') || titleLower.includes('series b') || titleLower.includes('series c') || titleLower.includes('funding round') || titleLower.includes('valuation'))) {
      return false;
    }
    if (state.userFilters?.hideOpinion && (artType === 'opinion_commentary' || titleLower.startsWith('opinion:') || titleLower.startsWith('analysis:') || story.trust_tier === 4)) {
      return false;
    }

    // 2. Section Filter: Briefing, Research, Developer, Industry, Safety
    if (state.activeSectionFilter && state.activeSectionFilter !== 'all') {
      const cat = story.category || story.topic || '';
      const sec = state.activeSectionFilter.toLowerCase();
      if (sec === 'briefing') {
        const isEligible = story.eligible_for_briefing !== false && (Number(story.pulse_score || story.overall_score || 0) >= 78 || (story.claim_corroboration && story.claim_corroboration > 1));
        if (!isEligible) return false;
      } else if (sec === 'research') {
        const isResearch = artType === 'research_paper' || cat === 'AI Models & Research' || story.trust_tier === 3 || (story.source && story.source.toLowerCase().includes('arxiv'));
        if (!isResearch) return false;
      } else if (sec === 'developer') {
        const isDev = artType === 'sdk_api_update' || cat === 'AI Products & Tools' || ['api', 'sdk', 'code', 'agent', 'github', 'repo', 'framework', 'library', 'model spec'].some(k => titleLower.includes(k));
        if (!isDev) return false;
      } else if (sec === 'industry') {
        const isIndustry = cat === 'AI Enterprise & Industry' || cat === 'AI Applications' || cat === 'AI Infrastructure';
        if (!isIndustry) return false;
      } else if (sec === 'safety') {
        const isSafety = artType === 'security_vulnerability' || artType === 'policy_regulation' || cat === 'AI Security & Safety' || cat === 'AI Policy & Regulation';
        if (!isSafety) return false;
      }
    }

    // 3. Topic category filter
    if (state.activeTopic && state.activeTopic !== 'All') {
      const cat = story.category || story.topic || '';
      if (cat.toLowerCase() !== state.activeTopic.toLowerCase()) {
        return false;
      }
    }

    // 4. Search query filter
    if (state.searchQuery && state.searchQuery.trim()) {
      const q = state.searchQuery.trim().toLowerCase();
      const content = `${story.title || ''} ${story.summary || ''} ${story.what_changed || ''} ${story.why_it_matters || ''} ${story.source || ''} ${story.company || ''}`.toLowerCase();
      if (!content.includes(q)) {
        return false;
      }
    }

    // 5. Trust Tier filter
    const tier = Number(story.trust_tier || 2);
    if (!state.advancedFilters.tiers.has(tier)) {
      return false;
    }

    // 6. Minimum Pulse Score filter
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

