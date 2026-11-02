/**
 * AI Trend Pulse — Pure Rendering Engine & Vector Visuals (js/render.js)
 * v2.1 High-Signal Editorial Architecture with Premium Visual Layouts
 */

import { state, isItemSaved, toggleSaveItem } from './state.js';

export function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// -------------------------------------------------------------
// 1. EMBEDDED RETINA VECTOR SVGS FOR AI LABS
// -------------------------------------------------------------
export const LOGO_SVGS = {
  openai: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.6669zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/></svg>`,
  google: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm3.88 11.5h-3.88v-3h6.63a6.8 6.8 0 0 1 .12 1.34 6.74 6.74 0 0 1-6.75 6.66A6.66 6.66 0 1 1 18.66 12h-2.78z"/></svg>`,
  anthropic: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.42 20.35l-5.42-14.7-5.42 14.7h2.7l1.08-3.05h3.28l1.08 3.05h2.7zm-6.02-5.42l1.64-4.63 1.64 4.63h-3.28z"/></svg>`,
  nvidia: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8.94 6.58c-.14.07-.27.14-.39.22-1.81 1.21-2.63 3.65-1.8 6.07.75 2.19 2.5 3.73 4.8 4.25v-2.02c-1.39-.37-2.45-1.39-2.92-2.77-.52-1.54 0-3.13 1.15-4.04.59-.47 1.18-.71 1.77-.71v-1c-.87 0-1.78.29-2.61.99zm-4.32 1.94c-.21.19-.4.39-.58.6-2.54 2.94-2.2 7.37.76 9.9 2.76 2.35 6.8 2.3 9.49.03v-1.63c-1.92 1.34-4.5 1.4-6.49-.07-2.12-1.56-2.6-4.51-1.07-6.64.71-.99 1.76-1.66 2.92-1.94v-1.1c-1.76.2-3.48.9-5.03 2.15zM22.02 12c0-4.42-3.58-8-8-8H14v2.01h.02c3.31 0 6 2.69 6 6s-2.69 6-6 6H14v2.01h.02c4.42 0 8-3.59 8-8.02z"/></svg>`,
  apple: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.42c.62-.75 1.04-1.8 0.92-2.85-.9.04-1.98.6-2.62 1.35-.57.65-1.06 1.7-0.93 2.71 1 .08 2.02-.46 2.63-1.21z"/></svg>`,
  meta: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 4.33c-3.12 0-5.83 2.1-7.05 5.09-1.37 3.39-.77 7.37 1.58 9.93.99 1.08 2.37 1.65 3.79 1.65 1.71 0 3.31-.83 4.32-2.19.46.62 1.05 1.13 1.73 1.49 1.09.58 2.35.79 3.57.57 2.15-.38 4.01-1.87 4.96-3.96 1.14-2.5.86-5.46-.72-7.69C22.65 6.81 17.61 4.33 12 4.33zm-4.78 12.2c-1.63 0-2.92-1.38-2.92-3.14 0-1.87 1.42-3.26 3.12-3.26 1.61 0 2.87 1.35 2.87 3.16 0 1.83-1.38 3.24-3.07 3.24zm9.49 0c-1.69 0-3.07-1.41-3.07-3.24 0-1.81 1.26-3.16 2.87-3.16 1.7 0 3.12 1.39 3.12 3.26 0 1.76-1.29 3.14-2.92 3.14z"/></svg>`,
  microsoft: `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="1" y="1" width="10" height="10"/><rect x="13" y="1" width="10" height="10"/><rect x="1" y="13" width="10" height="10"/><rect x="13" y="13" width="10" height="10"/></svg>`,
  xai: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.24 2.25h3.31l-7.23 8.26 8.5 11.24H16.17l-5.21-6.82-4.66 6.82H2.99l7.73-8.84L2.25 2.25h8.08l4.71 6.23zm-1.16 17.52h1.83L7.08 4.13H5.12z"/></svg>`,
  mistral: `<svg viewBox="0 0 24 24" fill="currentColor"><g fill="currentColor"><rect x="3" y="3" width="4" height="4"/><rect x="17" y="3" width="4" height="4"/><rect x="10" y="7" width="4" height="4"/><rect x="3" y="11" width="4" height="4"/><rect x="10" y="11" width="4" height="4"/><rect x="17" y="11" width="4" height="4"/><rect x="3" y="17" width="18" height="4"/></g></svg>`,
  huggingface: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12c0 2.25.75 4.33 2.01 6-.1.6-.33 1.83-1.01 3 0 0 1.95-.12 3.52-.98A9.96 9.96 0 0 0 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2zm-3.5 8c.83 0 1.5.9 1.5 2s-.67 2-1.5 2S7 13.1 7 12s.67-2 1.5-2zm7 0c.83 0 1.5.9 1.5 2s-.67 2-1.5 2-1.5-.9-1.5-2 .67-2 1.5-2zm-3.5 7.5c-2.33 0-4.31-1.46-5.11-3.5h10.22c-.8 2.04-2.78 3.5-5.11 3.5z"/></svg>`,
  default: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>`
};

export function getCompanyLogoSVG(companyKey) {
  const key = (companyKey || 'default').toLowerCase();
  return LOGO_SVGS[key] || LOGO_SVGS.default;
}

// -------------------------------------------------------------
// 2. 3-TIER EDITORIAL IMAGE SYSTEM & LAB VISUALS
// -------------------------------------------------------------
export const TOPIC_IMAGES = {
  'AI Policy & Regulation': 'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=800&q=80',
  'AI Security & Safety': 'https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=800&q=80',
  'AI Infrastructure': 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=800&q=80',
  'AI Business & Funding': 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=800&q=80',
  'AI Models & Research': 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=800&q=80',
  'AI Products & Tools': 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80',
  'AI Applications': 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=800&q=80',
  'AI News': 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80',
  'default': 'https://images.unsplash.com/photo-1677442136019-21780efad99a?auto=format&fit=crop&w=800&q=80'
};

export function getLabKey(companyKey) {
  if (!companyKey) return null;
  const c = String(companyKey).toLowerCase();
  if (c.includes('openai')) return 'openai';
  if (c.includes('anthropic') || c.includes('claude')) return 'anthropic';
  if (c.includes('deepmind') || c.includes('google')) return 'google';
  if (c.includes('nvidia')) return 'nvidia';
  if (c.includes('meta') || c.includes('llama')) return 'meta';
  if (c.includes('microsoft')) return 'microsoft';
  if (c.includes('xai') || c.includes('grok')) return 'xai';
  if (c.includes('mistral')) return 'mistral';
  if (c.includes('hugging')) return 'huggingface';
  if (c.includes('apple')) return 'apple';
  return null;
}

export function isKnownLab(companyKey) {
  return Boolean(getLabKey(companyKey));
}

export function getLabSignatureVisual(companyKey, topic) {
  const lab = getLabKey(companyKey) || 'openai';
  const t = topic || 'AI Intelligence';

  const LAB_CONFIGS = {
    openai: { name: 'OpenAI', subtitle: 'Frontier Research & Reasoning', c1: '#10a37f', c2: '#0e7054', c3: '#042f2e' },
    anthropic: { name: 'Claude', subtitle: 'Constitutional Safety & Alignment', c1: '#d97706', c2: '#92400e', c3: '#451a03' },
    google: { name: 'Google DeepMind', subtitle: 'Multimodal Frontier Intelligence', c1: '#2563eb', c2: '#1d4ed8', c3: '#172554' },
    nvidia: { name: 'NVIDIA', subtitle: 'Accelerated Architecture & Silicon', c1: '#76b900', c2: '#4d7c00', c3: '#142000' },
    meta: { name: 'Meta AI', subtitle: 'Open Weights & Foundation Research', c1: '#0081fb', c2: '#0058b3', c3: '#001a40' },
    microsoft: { name: 'Microsoft AI', subtitle: 'Enterprise Copilots & Infrastructure', c1: '#00a4ef', c2: '#0078d4', c3: '#002050' },
    mistral: { name: 'Mistral AI', subtitle: 'Open Models & Efficient Inference', c1: '#f97316', c2: '#c2410c', c3: '#431407' },
    xai: { name: 'xAI', subtitle: 'Maximum Truth-Seeking Grok Models', c1: '#e11d48', c2: '#9f1239', c3: '#4c0519' },
    huggingface: { name: 'Hugging Face', subtitle: 'Open-Source Ecosystem & Hub', c1: '#ffd21e', c2: '#d97706', c3: '#451a03' }
  };

  const cfg = LAB_CONFIGS[lab] || LAB_CONFIGS.openai;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
    <defs>
      <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${cfg.c1}"/>
        <stop offset="60%" stop-color="${cfg.c2}"/>
        <stop offset="100%" stop-color="${cfg.c3}"/>
      </linearGradient>
    </defs>
    <rect width="1200" height="630" fill="url(#bg)"/>
    <text x="80" y="320" font-family="system-ui, -apple-system, sans-serif" font-size="72" font-weight="800" fill="#ffffff">${cfg.name}</text>
    <text x="80" y="390" font-family="system-ui, -apple-system, sans-serif" font-size="32" font-weight="500" fill="#ffffff" opacity="0.9">${cfg.subtitle}</text>
    <text x="80" y="450" font-family="system-ui, -apple-system, sans-serif" font-size="24" font-weight="600" fill="#ffffff" opacity="0.75">DISPATCH • ${t.toUpperCase()}</text>
  </svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export function getTopicFallbackSVG(topic) {
  const t = topic || 'AI News';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
    <rect width="1200" height="630" fill="#0f172a"/>
    <text x="80" y="340" font-family="system-ui, -apple-system, sans-serif" font-size="64" font-weight="800" fill="#38bdf8">${t}</text>
    <text x="80" y="410" font-family="system-ui, -apple-system, sans-serif" font-size="28" font-weight="500" fill="#94a3b8">AI Trend Pulse • Verified Intelligence</text>
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export function getTopicImageUrl(topic, rawImage, companyKey) {
  if (companyKey && isKnownLab(companyKey)) {
    return getLabSignatureVisual(companyKey, topic);
  }
  if (rawImage && String(rawImage).startsWith('http')) {
    return rawImage;
  }
  return TOPIC_IMAGES[topic] || TOPIC_IMAGES.default || getTopicFallbackSVG(topic);
}

// -------------------------------------------------------------
// 3. BADGES & SOURCE METADATA HELPERS
// -------------------------------------------------------------
export function getTierMeta(source, tier) {
  const s = (source || '').toLowerCase();
  const t = (tier || '').toLowerCase();

  // Tier 1: Primary Lab Announcements & Official Research
  if (
    s.includes('openai') ||
    s.includes('deepmind') ||
    s.includes('anthropic') ||
    s.includes('mistral') ||
    s.includes('meta ai') ||
    t.includes('official') ||
    t.includes('tier 1')
  ) {
    return {
      tierNum: 1,
      tierClass: 'tier-1',
      badgeLabel: 'Tier 1 • Official Lab',
      badgeShort: 'Tier 1: Official Lab',
      icon: '🏢',
      sourceName: source || 'Official Lab'
    };
  }

  // Tier 3: Open Ecosystem & Research Repositories
  if (
    s.includes('arxiv') ||
    s.includes('bair') ||
    s.includes('berkeley') ||
    t.includes('open research') ||
    t.includes('tier 3')
  ) {
    return {
      tierNum: 3,
      tierClass: 'tier-3',
      badgeLabel: 'Tier 3 • Open Research',
      badgeShort: 'Tier 3: Research',
      icon: '📄',
      sourceName: source || 'Research Preprint'
    };
  }

  // Tier 4: Practitioner & Community Discovery
  if (
    s.includes('hacker news') ||
    s.includes('hn') ||
    s.includes('simon willison') ||
    s.includes('import ai') ||
    t.includes('community') ||
    t.includes('practitioner') ||
    t.includes('tier 4')
  ) {
    return {
      tierNum: 4,
      tierClass: 'tier-4',
      badgeLabel: 'Tier 4 • Community Signal',
      badgeShort: 'Tier 4: Community',
      icon: '💬',
      sourceName: source || 'Community Discovery'
    };
  }

  // Tier 2: Default to Independent Tech Journalism
  return {
    tierNum: 2,
    tierClass: 'tier-2',
    badgeLabel: 'Tier 2 • Independent Press',
    badgeShort: 'Tier 2: Tech Press',
    icon: '📰',
    sourceName: source || 'Independent Tech Press'
  };
}

export function getTierBadgeHTML(source, tier) {
  const meta = getTierMeta(source, tier);
  return `<span class="badge-tier ${meta.tierClass}" title="${escapeHTML(meta.badgeLabel)}">
    <span class="badge-tier-dot"></span>
    <span class="badge-tier-label">${escapeHTML(meta.badgeShort)}</span>
  </span>`;
}

export function getEvidenceBadgeHTML(item) {
  if (!item) return '';
  const status = item.evidence_status;
  const trendType = item.trend_type || (status === 'emerging_theme' ? 'emerging_theme' : 'single_development');
  const signalDiversity = item.trend_signal_diversity || (item.evidence_urls ? item.evidence_urls.length : 1);
  const claimCorrob = item.claim_corroboration || item.independent_source_count || (item.evidence_urls ? item.evidence_urls.length : (item.covered_by_sources_count || 1));
  const isOfficial = item.is_official || item.tier === 'Official Lab' || status === 'official_announcement' || item.status === 'official_claim';

  if (trendType === 'emerging_theme' || status === 'emerging_theme') {
    return `<span class="badge-evidence badge-evidence-theme" title="Emerging multi-development theme synthesizing ${signalDiversity} distinct industry signals">🌐 Emerging Theme (${signalDiversity} Signals)</span>`;
  }

  if (isOfficial) {
    if (claimCorrob >= 2) {
      return `<span class="badge-evidence badge-evidence-corroborated" title="Official lab release confirmed across ${claimCorrob} independent publisher groups">🏛️ Official + ${claimCorrob - 1} Sources</span>`;
    }
    return `<span class="badge-evidence badge-evidence-official" title="Direct announcement from official lab or developer">🏛️ Official Source</span>`;
  }
  if (status === 'research_preprint' || item.topic === 'Research' || item.source_type === 'research' || (item.source && item.source.toLowerCase().includes('arxiv'))) {
    return `<span class="badge-evidence badge-evidence-research" title="Research paper preprint / academic evaluation">📄 Research Preprint</span>`;
  }
  if (status === 'practitioner_report' || item.trust_tier === 4) {
    return `<span class="badge-evidence badge-evidence-practitioner" title="Practitioner observation or community discovery signal">🔬 Practitioner Report</span>`;
  }
  if (claimCorrob >= 2) {
    return `<span class="badge-evidence badge-evidence-corroborated" title="Reported and corroborated across ${claimCorrob} independent publisher groups">✓ ${claimCorrob} Independent Sources</span>`;
  }
  return `<span class="badge-evidence badge-evidence-single" title="Reported by a single tech news outlet">📰 Single Source</span>`;
}

// -------------------------------------------------------------
// 4. DATE AND TIME FORMATTING HELPERS (IST Support)
// -------------------------------------------------------------
export function formatIST(dateInput) {
  if (!dateInput) return '';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  return d.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata'
  }) + ' IST';
}

export function formatISTDateTime(dateInput) {
  if (!dateInput) return '';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  return d.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'Asia/Kolkata'
  }) + ' IST';
}

export function formatRelativeTime(dateInput) {
  if (!dateInput) return 'Recently';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);
  const now = new Date();
  const diffHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60);

  if (diffHours < 1) {
    const mins = Math.max(1, Math.round(diffHours * 60));
    return `${mins}m ago`;
  }
  if (diffHours < 24) {
    return `${Math.round(diffHours)}h ago`;
  }
  const days = Math.round(diffHours / 24);
  return `${days}d ago`;
}

// -------------------------------------------------------------
// 5. RENDERING TIER A: TOP 5 EXECUTIVE BENTO GRID
// -------------------------------------------------------------
export function renderTop5Bento(stories) {
  const container = document.getElementById('bento-container');
  if (!container) return;

  const top5 = (stories || []).slice(0, 5);
  if (top5.length === 0) {
    container.innerHTML = '';
    return;
  }

  const hero = top5[0];
  const subcards = top5.slice(1, 5);

  let html = `
    <div class="bento-section">
      <div class="bento-header">
        <div class="bento-title-wrap">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          <span style="font-weight:700; font-size:1.05rem; color:var(--text-primary);">Top 5 Executive Pulse</span>
          <span class="bento-badge-tag">High Signal</span>
        </div>
        <span style="font-size:0.75rem; color:var(--text-muted);">Updated Hourly</span>
      </div>

      <div class="bento-grid">
        <!-- Lead Hero Bento Card -->
        <article class="bento-card bento-hero" onclick="openReaderForTrend(0, event)">
          <div>
            <div class="bento-card-meta">
              <span class="badge-signal">${escapeHTML(hero.signal_badge || '🚀 Frontier Launch')}</span>
              <span class="badge-tier tier-${hero.trust_tier || 1}">${escapeHTML(hero.source)}</span>
              <span style="font-size:0.75rem; color:var(--text-muted); margin-left:auto;">${formatRelativeTime(hero.published_at || hero.published)}</span>
            </div>
            <h2 class="bento-headline font-serif" style="font-size: clamp(1.2rem, 2vw, 1.45rem); margin: 10px 0 8px 0;">${escapeHTML(hero.title)}</h2>
            <p class="bento-summary" style="font-size:0.9rem; line-height:1.5;">${escapeHTML(hero.what_changed || hero.summary || '')}</p>
          </div>
          <div class="bento-footer">
            <span class="bento-source-pill">${getCompanyLogoSVG(hero.company)} ${escapeHTML(hero.source)}</span>
            <span style="color:var(--accent-text); font-weight:600;">Deep Read →</span>
          </div>
        </article>
        
        <!-- 4 Subcards Grid -->
        <div style="display:grid; grid-template-columns:1fr; gap:12px;">
  `;

  subcards.forEach((item, idx) => {
    html += `
      <article class="bento-card bento-subcard" onclick="openReaderForTrend(${idx + 1}, event)">
        <div>
          <div class="bento-card-meta">
            <span class="badge-signal">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>
            <span style="font-size:0.74rem; color:var(--text-muted);">${formatRelativeTime(item.published_at || item.published)}</span>
          </div>
          <h3 class="bento-headline font-serif" style="font-size:0.95rem;">${escapeHTML(item.title)}</h3>
        </div>
        <div class="bento-footer" style="padding-top:6px;">
          <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHTML(item.source)}</span>
          <span style="color:var(--accent-text); font-size:0.75rem; font-weight:600;">Details →</span>
        </div>
      </article>
    `;
  });

  html += `
        </div>
      </div>
    </div>
  `;

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 6. RENDERING TIER B: COMPACT LIVE WIRE TABLE
// -------------------------------------------------------------
export function renderCompactWire(items) {
  const container = document.getElementById('developments-container');
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '';
    const emptyBox = document.getElementById('empty-state-box');
    if (emptyBox) emptyBox.style.display = 'block';
    return;
  }

  const emptyBox = document.getElementById('empty-state-box');
  if (emptyBox) emptyBox.style.display = 'none';

  let html = `<div class="wire-container"><div class="wire-table">`;

  items.forEach((item, idx) => {
    const relTime = formatRelativeTime(item.published_at || item.published);
    const corrobCount = item.claim_corroboration || item.independent_source_count || 1;
    const corrobPill = corrobCount >= 2 
      ? `<span class="badge-tier tier-2" style="font-size:0.72rem; padding:2px 6px;">+${corrobCount - 1} independent sources</span>`
      : '';

    html += `
      <div class="wire-row" data-wire-idx="${idx}" onclick="openReaderForTrend(${idx}, event)">
        <div class="wire-col-time">${escapeHTML(relTime)}</div>
        <div class="wire-col-badge">
          <span class="badge-signal" style="font-size:0.7rem;">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>
        </div>
        <div class="wire-col-headline">
          <span class="wire-title-text">${escapeHTML(item.title)}</span>
          <span class="wire-source-tag">${escapeHTML(item.source)}</span>
        </div>
        <div class="wire-col-corrob">
          ${corrobPill}
          <button class="btn-action-icon" style="min-height:30px; padding:2px 8px; font-size:0.76rem;" title="View Details">
            Expand
          </button>
        </div>
      </div>
    `;
  });

  html += `</div></div>`;
  container.innerHTML = html;
}

// -------------------------------------------------------------
// 7. RENDERING RICH EDITORIAL DEVELOPMENTS CARDS
// -------------------------------------------------------------
export function renderEditorialCards(items) {
  const container = document.getElementById('developments-container');
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '';
    const emptyBox = document.getElementById('empty-state-box');
    if (emptyBox) emptyBox.style.display = 'block';
    return;
  }

  const emptyBox = document.getElementById('empty-state-box');
  if (emptyBox) emptyBox.style.display = 'none';

  let html = '';
  items.forEach((item, idx) => {
    const topic = item.category || item.topic || 'AI News';
    const company = item.company || 'default';
    const readTime = item.reading_time || '2 min read';
    const primaryUrl = (item.evidence_urls && item.evidence_urls[0]) || item.link || '#';
    const isSaved = isItemSaved(item.title);
    const imgUrl = getTopicImageUrl(topic, item.image || item.image_url, company);

    const tierBadgeHTML = getTierBadgeHTML(item.source, item.tier || item.trust_tier);
    const evidenceBadgeHTML = getEvidenceBadgeHTML(item);
    const scoreVal = item.pulse_score ? Math.round(item.pulse_score) : (item.overall_score ? Math.round(item.overall_score) : null);
    const scorePillHTML = scoreVal ? `<span class="score-pill" title="Algorithmic Pulse Score (0-100)">⚡ ${scoreVal}</span>` : '';
    const signalBadgeHTML = `<span class="badge-signal">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>`;
    const corroborationCount = item.claim_corroboration || item.independent_source_count || (item.evidence_urls ? item.evidence_urls.length : 1);
    const hasMultipleSources = corroborationCount > 1 && item.evidence_urls && item.evidence_urls.length > 1;
    const isOfficial = item.is_official || item.trust_tier === 1;

    const headline = item.title || '';
    const summary = item.what_changed || item.what_happened || item.summary || '';
    const whyItMatters = item.why_it_matters || '';

    // Takeaways
    const keyPoints = (item.key_points && item.key_points.length) ? item.key_points.slice(0, 3) : [];
    const takeawaysHTML = keyPoints.length ? `
      <div class="card-takeaways">
        <div class="takeaways-header">
          <svg class="takeaways-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
          <span>Key Takeaways</span>
        </div>
        <ul class="takeaways-list">
          ${keyPoints.map(kp => `<li>${escapeHTML(kp)}</li>`).join('')}
        </ul>
      </div>
    ` : '';

    // Why it matters callout
    const whyItMattersHTML = whyItMatters ? `
      <div class="card-why-callout">
        <div class="card-why-callout-title">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
          <span>Why It Matters</span>
        </div>
        <div class="card-why-callout-body">${escapeHTML(whyItMatters)}</div>
      </div>
    ` : '';

    // Affected Audience Callout
    const audienceTarget = item.target_audience || (item.audience_impact ? item.audience_impact.target : 'For developers & builders');
    const audienceImpact = item.audience_impact_statement || (item.audience_impact ? item.audience_impact.impact : 'Affects engineering decisions and practical workflows.');
    const audienceCalloutHTML = `
      <div class="card-audience-callout">
        <div class="audience-target-tag">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <span>${escapeHTML(audienceTarget)}</span>
        </div>
        <div class="audience-impact-desc">${escapeHTML(audienceImpact)}</div>
      </div>
    `;

    const publishedStr = item.published_at ? formatRelativeTime(item.published_at) : (item.published || 'Recently');

    if (idx === 0) {
      // CARD TYPE 1: FEATURED STORY CARD (Lead Hero Layout)
      html += `
        <article class="card-base card-featured" data-card-idx="${idx}">
          <div class="card-featured-inner">
            <div class="card-featured-media">
              <img src="${escapeHTML(imgUrl)}" alt="${escapeHTML(headline)}" loading="lazy" />
              <div class="hero-image-badge">
                <span>${escapeHTML(topic)}</span>
              </div>
            </div>
            <div class="card-featured-body">
              <div>
                <div class="card-kicker-row">
                  <div class="card-kicker-left">
                    ${signalBadgeHTML}
                    ${tierBadgeHTML}
                    <span class="badge-card-topic">${escapeHTML(topic)}</span>
                    ${scorePillHTML}
                    ${evidenceBadgeHTML}
                  </div>
                  <span style="font-size:0.76rem; color:var(--text-muted); font-weight:500;">⏱ ${escapeHTML(readTime)}</span>
                </div>
                <h3 class="card-headline font-serif" style="margin-top:8px;">
                  <a href="${escapeHTML(primaryUrl)}" onclick="openReaderForTrend(${idx}, event)">${escapeHTML(headline)}</a>
                </h3>
                <p class="card-summary" style="margin-top:8px;">${escapeHTML(summary)}</p>
                ${takeawaysHTML}
                ${whyItMattersHTML}
                ${audienceCalloutHTML}
              </div>

              <div class="card-footer">
                <div class="card-source-meta">
                  <span style="font-weight:700; color:var(--text-primary);">${escapeHTML(item.source)}</span>
                  <span>•</span>
                  <span>${escapeHTML(publishedStr)}</span>
                </div>
                <div class="card-actions">
                  <button class="btn-read-deep-dive" onclick="openReaderForTrend(${idx}, event)" aria-label="Deep dive into story">
                    <span>Read Deep Dive</span>
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  </button>
                  <button class="btn-action-icon ${isSaved ? 'saved' : ''}" onclick="handleSaveTrend(${idx}, this)" aria-label="Save story" title="Save Story">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
                  </button>
                  <button class="btn-action-icon" onclick="handleCopyTrend(${idx}, this)" aria-label="Copy summary" title="Copy Summary">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  </button>
                  <a href="${escapeHTML(primaryUrl)}" target="_blank" rel="noopener noreferrer" class="btn-action-icon" aria-label="Open original source directly" title="Original Article">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </article>
      `;
    } else if (hasMultipleSources) {
      // CARD TYPE 5: RELATED STORY GROUP (Multi-source corroborated)
      const linksHTML = item.evidence_urls.map((u, i) => {
        let domain = '';
        try { domain = new URL(u).hostname.replace('www.', ''); } catch (e) { domain = u; }
        return `<li>${i + 1}. <a class="evidence-link" href="${escapeHTML(u)}" target="_blank" rel="noopener noreferrer">${escapeHTML(domain)} ↗</a></li>`;
      }).join('');

      html += `
        <article class="card-base card-grouped" data-card-idx="${idx}">
          <div class="card-kicker-row">
            <div class="card-kicker-left">
              ${signalBadgeHTML}
              ${tierBadgeHTML}
              <span class="badge-card-topic">${escapeHTML(topic)}</span>
              ${scorePillHTML}
            </div>
            <span class="badge-status-pill official">Corroborated by ${corroborationCount} sources</span>
          </div>
          <h3 class="card-headline font-serif" style="margin-top:8px;">
            <a href="${escapeHTML(primaryUrl)}" onclick="openReaderForTrend(${idx}, event)">${escapeHTML(headline)}</a>
          </h3>
          <p class="card-summary" style="margin-top:6px;">${escapeHTML(summary)}</p>
          ${takeawaysHTML}
          ${whyItMattersHTML}
          ${audienceCalloutHTML}

          <details class="evidence-block">
            <summary class="evidence-summary">Verified Supporting Sources (${item.evidence_urls.length}) ↗</summary>
            <ul class="evidence-list">${linksHTML}</ul>
          </details>

          <div class="card-footer">
            <div class="card-source-meta">
              <span style="font-weight:700; color:var(--text-primary);">${escapeHTML(item.source)}</span>
              <span>•</span>
              <span>⏱ ${escapeHTML(readTime)}</span>
            </div>
            <div class="card-actions">
              <button class="btn-read-deep-dive" onclick="openReaderForTrend(${idx}, event)" aria-label="Deep dive into story">
                <span>Read Deep Dive</span>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button class="btn-action-icon ${isSaved ? 'saved' : ''}" onclick="handleSaveTrend(${idx}, this)" aria-label="Save story" title="Save Story">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
              </button>
              <button class="btn-action-icon" onclick="handleCopyTrend(${idx}, this)" aria-label="Copy summary" title="Copy Summary">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              </button>
              <a href="${escapeHTML(primaryUrl)}" target="_blank" rel="noopener noreferrer" class="btn-action-icon" aria-label="Open original source directly" title="Original Article">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
              </a>
            </div>
          </div>
        </article>
      `;
    } else {
      // CARD TYPE 2: STANDARD NEWS CARD
      html += `
        <article class="card-base card-standard ${isOfficial ? 'card-breaking' : ''}" data-card-idx="${idx}">
          <div class="card-standard-media">
            <img src="${escapeHTML(imgUrl)}" alt="${escapeHTML(headline)}" loading="lazy" />
            <div class="hero-image-badge" style="top:8px; left:8px;">
              <span>${escapeHTML(topic)}</span>
            </div>
          </div>
          <div class="card-standard-body">
            <div>
              <div class="card-kicker-row">
                <div class="card-kicker-left">
                  ${signalBadgeHTML}
                  ${tierBadgeHTML}
                  <span class="badge-card-topic">${escapeHTML(topic)}</span>
                  ${scorePillHTML}
                  ${evidenceBadgeHTML}
                </div>
                <span style="font-size:0.76rem; color:var(--text-muted); font-weight:500;">⏱ ${escapeHTML(readTime)}</span>
              </div>
              <h3 class="card-headline font-serif" style="margin-top:8px;">
                <a href="${escapeHTML(primaryUrl)}" onclick="openReaderForTrend(${idx}, event)">${escapeHTML(headline)}</a>
              </h3>
              <p class="card-summary" style="margin-top:6px;">${escapeHTML(summary)}</p>
              ${takeawaysHTML}
              ${whyItMattersHTML}
              ${audienceCalloutHTML}
            </div>

            <div class="card-footer">
              <div class="card-source-meta">
                <span style="font-weight:700; color:var(--text-primary);">${escapeHTML(item.source)}</span>
                <span>•</span>
                <span>${escapeHTML(publishedStr)}</span>
              </div>
              <div class="card-actions">
                <button class="btn-read-deep-dive" onclick="openReaderForTrend(${idx}, event)" aria-label="Deep dive into story">
                  <span>Read Deep Dive</span>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </button>
                <button class="btn-action-icon ${isSaved ? 'saved' : ''}" onclick="handleSaveTrend(${idx}, this)" aria-label="Save story" title="Save Story">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
                </button>
                <button class="btn-action-icon" onclick="handleCopyTrend(${idx}, this)" aria-label="Copy summary" title="Copy Summary">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                </button>
                <a href="${escapeHTML(primaryUrl)}" target="_blank" rel="noopener noreferrer" class="btn-action-icon" aria-label="Open original source directly" title="Original Article">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                </a>
              </div>
            </div>
          </div>
        </article>
      `;
    }
  });

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 8. RENDERING MONITORED DISPATCHES FEED
// -------------------------------------------------------------
export function renderDispatches(items) {
  const container = document.getElementById('stories-container');
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '<li style="padding:16px; color:var(--text-muted);">No monitored dispatches collected.</li>';
    return;
  }

  let html = '';
  items.slice(0, 45).forEach((item, idx) => {
    const relTime = formatRelativeTime(item.published_at || item.published);
    const topic = item.category || item.topic || 'AI News';
    const isSaved = isItemSaved(item.title);
    const primaryUrl = item.link || '#';
    const tierBadgeHTML = getTierBadgeHTML(item.source, item.tier || item.trust_tier);

    html += `
      <li class="story-item" data-dispatch-idx="${idx}">
        <div class="story-item-main">
          <div class="story-item-header">
            <span class="badge-signal" style="font-size:0.7rem;">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>
            ${tierBadgeHTML}
            <span class="badge-card-topic" style="font-size:0.7rem;">${escapeHTML(topic)}</span>
            <span style="font-size:0.74rem; color:var(--text-muted); margin-left:auto;">${escapeHTML(relTime)}</span>
          </div>
          <h4 class="story-title font-serif">
            <a href="${escapeHTML(primaryUrl)}" onclick="openReaderForDispatch(${idx}, event)">${escapeHTML(item.title)}</a>
          </h4>
          <p class="story-summary">${escapeHTML(item.what_changed || item.summary || '')}</p>
          <div class="story-footer">
            <span class="story-source">${escapeHTML(item.source)}</span>
            <div class="story-actions">
              <button class="btn-read-deep-dive" style="padding:4px 10px; font-size:0.75rem;" onclick="openReaderForDispatch(${idx}, event)">
                <span>Read</span>
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              </button>
              <button class="btn-action-icon ${isSaved ? 'saved' : ''}" style="width:28px; height:28px;" onclick="handleSaveDispatch(${idx}, this)" aria-label="Save story" title="Save">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
              </button>
              <a href="${escapeHTML(primaryUrl)}" target="_blank" rel="noopener noreferrer" class="btn-action-icon" style="width:28px; height:28px;" title="Original Article">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
              </a>
            </div>
          </div>
        </div>
      </li>
    `;
  });

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 9. RENDERING TOPIC PILLS & COUNTS
// -------------------------------------------------------------
export function renderTopicPills(categories, counts) {
  const container = document.getElementById('topic-pills-bar');
  if (!container) return;

  const allCount = Object.values(counts).reduce((acc, c) => acc + c, 0);
  let html = `
    <button class="topic-pill ${state.activeTopic === 'All' ? 'active' : ''}" data-topic="All">
      All <span class="pill-count">${allCount}</span>
    </button>
  `;

  categories.forEach(cat => {
    const c = counts[cat] || 0;
    html += `
      <button class="topic-pill ${state.activeTopic === cat ? 'active' : ''}" data-topic="${escapeHTML(cat)}">
        ${escapeHTML(cat)} <span class="pill-count">${c}</span>
      </button>
    `;
  });

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 10. RENDERING CURATED SECTIONS (AI Tools, Dev Radar, Safety)
// -------------------------------------------------------------
export function renderCuratedCard(item, idx, sectionType) {
  const company = item.company || 'default';
  const topic = item.category || item.topic || 'AI Intelligence';
  const logoSVG = getCompanyLogoSVG(company);
  const primaryUrl = item.link || '#';
  const isSaved = isItemSaved(item.title);

  return `
    <article class="curated-card" data-curated-section="${sectionType}" data-curated-idx="${idx}">
      <div class="curated-card-top">
        <span class="curated-logo" aria-hidden="true">${logoSVG}</span>
        <span class="curated-topic-badge">${escapeHTML(topic)}</span>
      </div>
      <h3 class="curated-title font-serif">
        <a href="${escapeHTML(primaryUrl)}" onclick="openReaderForCurated('${sectionType}', ${idx}, event)">${escapeHTML(item.title)}</a>
      </h3>
      <p class="curated-summary">${escapeHTML(item.what_happened || item.one_liner || item.summary || '')}</p>
      <div class="curated-footer">
        <span class="curated-source">${escapeHTML(item.source)}</span>
        <div class="curated-actions">
          <button class="btn-read-deep-dive" style="padding:4px 10px; font-size:0.75rem;" onclick="openReaderForCurated('${sectionType}', ${idx}, event)">
            <span>Read</span>
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
          </button>
          <button class="btn-action-icon ${isSaved ? 'saved' : ''}" style="width:28px; height:28px;" onclick="handleSaveCurated('${sectionType}', ${idx}, this)" aria-label="Save" title="Save">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
          </button>
        </div>
      </div>
    </article>
  `;
}

export function renderCuratedSections(data) {
  const toolsEl = document.getElementById('ai-tools-container');
  if (toolsEl && data.ai_tools) {
    toolsEl.innerHTML = data.ai_tools.slice(0, 4).map((it, idx) => renderCuratedCard(it, idx, 'ai_tools')).join('');
  }

  const radarEl = document.getElementById('dev-radar-container');
  if (radarEl && data.dev_radar) {
    radarEl.innerHTML = data.dev_radar.slice(0, 4).map((it, idx) => renderCuratedCard(it, idx, 'dev_radar')).join('');
  }

  const safetyEl = document.getElementById('research-safety-container');
  if (safetyEl && data.research_safety) {
    safetyEl.innerHTML = data.research_safety.slice(0, 4).map((it, idx) => renderCuratedCard(it, idx, 'research_safety')).join('');
  }
}

// -------------------------------------------------------------
// 11. RENDERING DAILY INTELLIGENCE OVERVIEW
// -------------------------------------------------------------
export function renderDailyOverview(overview, data) {
  const briefingEl = document.getElementById('overview-briefing-text');
  const countEl = document.getElementById('overview-count-val');
  const lastUpdatedEl = document.getElementById('overview-last-updated');
  const catchMeUpContainer = document.getElementById('catch-me-up-items');

  const ov = overview || {};
  const totalCount = ov.total_developments_today || (data?.top_stories?.length || 0);

  if (countEl) countEl.textContent = totalCount;
  if (briefingEl) {
    briefingEl.textContent = ov.briefing_text || data?.takeaway || 'Frontier AI developments continue accelerating across practical coding assistants, model architectures, and evaluation standards.';
  }

  const updateTime = data?.last_successful_update || data?.generated_at;
  if (lastUpdatedEl && updateTime) {
    lastUpdatedEl.textContent = `Updated ${formatIST(updateTime)}`;
  }

  if (catchMeUpContainer) {
    const topDevs = ov.top_developments || (data?.top_stories || []).slice(0, 3);
    catchMeUpContainer.innerHTML = topDevs.map((dev, idx) => `
      <div class="catch-me-up-item" onclick="openReaderForDailyItem(${idx}, event)">
        <div class="catch-item-header">
          <span class="catch-item-index font-mono">0${idx + 1}</span>
          <span class="catch-item-source font-mono">${escapeHTML(dev.source || 'Verified Source')}</span>
        </div>
        <h4 class="catch-item-title font-serif">
          <a href="${escapeHTML(dev.link || '#')}" onclick="openReaderForDailyItem(${idx}, event)">${escapeHTML(dev.title || '')}</a>
        </h4>
        <p class="catch-item-expl">${escapeHTML(dev.one_line_explanation || dev.what_changed || dev.summary || '')}</p>
      </div>
    `).join('');
  }
}

// -------------------------------------------------------------
// 12. RENDERING STATUS BAR & TELEMETRY
// -------------------------------------------------------------
export function renderStatusBar(data) {
  const statusEl = document.getElementById('status-text');
  if (!statusEl) return;

  const genTime = data?.last_successful_update || data?.generated_at;
  if (!genTime) {
    statusEl.innerHTML = '● Live Pipeline Active • Hourly updates';
    return;
  }

  const istStr = formatIST(genTime);
  const now = new Date();
  const d = new Date(genTime);
  const ageHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60);

  let statusCategory = 'Fresh';
  let statusDesc = '';

  if (ageHours < 1.5) {
    statusCategory = 'Fresh';
    const minsLeft = Math.max(1, Math.round((1.0 - (ageHours % 1)) * 60));
    statusDesc = `Updated ${istStr} • Next sync in ~${minsLeft}m`;
  } else if (ageHours < 3.0) {
    statusCategory = 'Delayed';
    statusDesc = `Updated ${istStr} (${Math.round(ageHours)}h ago) • Sync delayed; retrying soon`;
  } else {
    statusCategory = 'Stale';
    statusDesc = `Updated ${istStr} (${Math.round(ageHours)}h ago) • Scheduled run pending`;
  }

  statusEl.innerHTML = `<strong>● ${statusCategory}</strong>: ${escapeHTML(statusDesc)}`;

  const telemetryEl = document.getElementById('status-source-telemetry');
  if (telemetryEl) {
    telemetryEl.innerHTML = `
      <span>25 monitored research sources</span>
      <span>•</span>
      <span>Strict provenance tracking</span>
    `;
  }
}
