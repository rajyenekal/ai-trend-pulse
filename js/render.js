/**
 * AI Trend Pulse — Pure Rendering Engine & Vector Visuals (js/render.js)
 * v2.1 High-Signal Editorial Architecture
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
  'AI Models': 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=800&q=80',
  'AI Agents': 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=800&q=80',
  'AI Coding': 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=800&q=80',
  'AI Products': 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80',
  'Research': 'https://images.unsplash.com/photo-1507668077129-56e32842fceb?auto=format&fit=crop&w=800&q=80',
  'Business & Funding': 'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=800&q=80',
  'Open Source': 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=800&q=80',
  'AI Safety': 'https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=800&q=80',
  'Model Releases': 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=800&q=80',
  'Research & Safety': 'https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=800&q=80',
  'AI Business': 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80',
  'AI Tools & Ecosystem': 'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80',
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
    huggingface: { name: 'Hugging Face', subtitle: 'Open-Source Ecosystem & Hub', c1: '#ffd21e', c2: '#d97706', c3: '#451a03' },
    apple: { name: 'Apple Intelligence', subtitle: 'Private On-Device Foundation Models', c1: '#64748b', c2: '#334155', c3: '#0f172a' }
  };

  const cfg = LAB_CONFIGS[lab] || LAB_CONFIGS.openai;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 340" width="100%" height="100%">
    <defs>
      <linearGradient id="g_${lab}" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${cfg.c1}"/>
        <stop offset="60%" stop-color="${cfg.c2}"/>
        <stop offset="100%" stop-color="${cfg.c3}"/>
      </linearGradient>
    </defs>
    <rect width="600" height="340" fill="url(#g_${lab})"/>
    <circle cx="500" cy="90" r="160" fill="rgba(255,255,255,0.06)"/>
    <g fill="#ffffff" opacity="0.95" transform="translate(48, 220)">
      <text font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="28" font-weight="800" fill="#ffffff">${escapeHTML(cfg.name)}</text>
      <text y="28" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="13" font-weight="500" fill="rgba(255,255,255,0.85)">${escapeHTML(cfg.subtitle)}</text>
      <text y="48" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="11" font-weight="600" fill="rgba(255,255,255,0.65)" letter-spacing="1.2" text-transform="uppercase">${escapeHTML(t)}</text>
    </g>
  </svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function getTopicFallbackSVG(topic) {
  const t = topic || 'AI Intelligence';
  const colors = {
    'AI Policy & Regulation': ['#831843', '#be185d', '#9d174d'],
    'AI Security & Safety': ['#9a3412', '#ea580c', '#7c2d12'],
    'AI Infrastructure': ['#0f766e', '#14b8a6', '#115e59'],
    'AI Business & Funding': ['#1e40af', '#3b82f6', '#1d4ed8'],
    'AI Models & Research': ['#4338ca', '#6366f1', '#3730a3'],
    'AI Products & Tools': ['#065f46', '#10b981', '#047857'],
    'AI Applications': ['#0369a1', '#0ea5e9', '#0284c7'],
    'AI News': ['#334155', '#64748b', '#1e293b'],
    'AI Agents': ['#0369a1', '#0ea5e9', '#0284c7'],
    'default': ['#0f172a', '#1e293b', '#0f172a']
  };
  const [c1, c2, c3] = colors[t] || colors.default;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 340" width="100%" height="100%">
    <defs>
      <linearGradient id="g_${encodeURIComponent(t)}" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${c1}"/>
        <stop offset="50%" stop-color="${c2}"/>
        <stop offset="100%" stop-color="${c3}"/>
      </linearGradient>
    </defs>
    <rect width="600" height="340" fill="url(#g_${encodeURIComponent(t)})"/>
    <g fill="#ffffff" opacity="0.9" transform="translate(40, 240)">
      <text font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="20" font-weight="700" text-transform="uppercase" fill="#ffffff">${escapeHTML(t)}</text>
      <text y="25" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="13" fill="rgba(255,255,255,0.75)">AI TREND PULSE • EDITORIAL PROVENANCE</text>
    </g>
  </svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function getTopicImageUrl(topic, imageUrl = null, companyKey = null) {
  if (companyKey && isKnownLab(companyKey)) {
    return getLabSignatureVisual(companyKey, topic);
  }
  if (imageUrl && typeof imageUrl === 'string' && imageUrl.startsWith('http')) {
    return imageUrl;
  }
  if (TOPIC_IMAGES[topic]) {
    return TOPIC_IMAGES[topic];
  }
  return TOPIC_IMAGES.default;
}

// -------------------------------------------------------------
// 3. INDIAN STANDARD TIME (IST) & RELATIVE TIME FORMATTING
// -------------------------------------------------------------
export function formatIST(dateInput) {
  if (!dateInput) return 'IST';
  try {
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) return 'IST';

    // Format directly using Intl.DateTimeFormat with Asia/Kolkata timezone
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      timeZoneName: 'short'
    }).format(d);
  } catch (e) {
    return 'IST';
  }
}

export function formatRelativeTime(dateInput) {
  if (!dateInput) return 'Recent';
  try {
    const d = new Date(dateInput);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diffSec < 60) return 'Just now';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch (e) {
    return 'Recent';
  }
}

// -------------------------------------------------------------
// 4. RENDERING TIER A: TOP 5 EXECUTIVE BENTO GRID
// -------------------------------------------------------------
export function renderTop5Bento(items) {
  const container = document.getElementById('bento-container');
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = '';
    return;
  }

  const top5 = items.slice(0, 5);
  const hero = top5[0];
  const subcards = top5.slice(1, 5);

  let html = `
    <div class="bento-section">
      <div class="bento-header">
        <div class="bento-title-wrap">
          <span class="bento-badge-tag">Top 5 Executive Digest</span>
          <span style="font-size:0.82rem; color:var(--text-muted);">Highest-signal developments across frontier labs</span>
        </div>
      </div>
      <div class="bento-grid">
        <!-- Hero Card -->
        <article class="bento-card bento-hero" data-story-idx="0">
          <div>
            <div class="bento-card-meta">
              <span class="badge-signal">${escapeHTML(hero.signal_badge || '🚀 Frontier Launch')}</span>
              <span class="badge-tier tier-${hero.trust_tier || 1}"><span class="badge-tier-dot"></span>${escapeHTML(hero.tier || 'Official Lab')}</span>
              <span style="font-size:0.76rem; color:var(--text-muted);">${formatRelativeTime(hero.published_at || hero.published)}</span>
            </div>
            <h2 class="bento-headline font-serif">${escapeHTML(hero.title)}</h2>
            <p class="bento-summary">${escapeHTML(hero.what_changed || hero.summary)}</p>
          </div>
          <div class="bento-footer">
            <span class="bento-source-pill">${getCompanyLogoSVG(hero.company)} ${escapeHTML(hero.source)}</span>
            <span style="color:var(--accent-text); font-weight:600;">Deep Read →</span>
          </div>
        </article>
        
        <!-- 4 Subcards -->
        <div style="display:grid; grid-template-columns:1fr; gap:12px;">
  `;

  subcards.forEach((item, idx) => {
    html += `
      <article class="bento-card bento-subcard" data-story-idx="${idx + 1}">
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
// 5. RENDERING TIER B: COMPACT LIVE WIRE TABLE
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
      <div class="wire-row" data-wire-idx="${idx}">
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
// 6. RENDERING DECLUTTERED EDITORIAL CARDS
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
    const relTime = formatRelativeTime(item.published_at || item.published);
    const corrobCount = item.claim_corroboration || item.independent_source_count || 1;
    const corrobLabel = corrobCount >= 2 ? `Covered by ${corrobCount} sources` : 'Single-Source';

    html += `
      <article class="card-standard" data-card-idx="${idx}">
        <div>
          <div class="card-top-bar">
            <span class="badge-signal">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>
            <span class="badge-tier tier-${item.trust_tier || 2}">
              <span class="badge-tier-dot"></span>
              <span class="badge-tier-label">${escapeHTML(item.source)}</span>
            </span>
            <span style="font-size:0.75rem; color:var(--text-muted); margin-left:auto;">${escapeHTML(relTime)}</span>
          </div>

          <h2 class="card-headline font-serif">${escapeHTML(item.title)}</h2>

          <div class="card-editorial-trio">
            <p class="card-what-changed">${escapeHTML(item.what_changed || item.summary)}</p>
            ${item.why_it_matters ? `
              <div class="card-why-callout">
                <strong>Why it matters:</strong> ${escapeHTML(item.why_it_matters)}
              </div>
            ` : ''}
          </div>
        </div>

        <div class="card-bottom-bar">
          <span style="font-size:0.74rem; color:var(--text-muted);">${escapeHTML(corrobLabel)}</span>
          <button class="btn-action-icon" style="min-height:32px; font-size:0.78rem; font-weight:600; color:var(--accent-text);">
            Deep Read →
          </button>
        </div>
      </article>
    `;
  });

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 7. RENDERING MONITORED DISPATCHES FEED
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
    html += `
      <li class="card-standard" data-dispatch-idx="${idx}">
        <div>
          <div class="card-top-bar">
            <span class="badge-signal" style="font-size:0.7rem;">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>
            <span class="badge-tier tier-${item.trust_tier || 2}">
              <span class="badge-tier-dot"></span>
              <span class="badge-tier-label">${escapeHTML(item.source)}</span>
            </span>
            <span style="font-size:0.74rem; color:var(--text-muted); margin-left:auto;">${escapeHTML(relTime)}</span>
          </div>
          <h3 class="card-headline font-serif" style="font-size:1.05rem;">${escapeHTML(item.title)}</h3>
          <p class="card-what-changed" style="font-size:0.84rem;">${escapeHTML(item.what_changed || item.summary)}</p>
        </div>
        <div class="card-bottom-bar" style="padding-top:8px;">
          <span style="font-size:0.74rem; color:var(--text-muted);">${escapeHTML(item.category || item.topic || 'AI News')}</span>
          <button class="btn-action-icon" style="min-height:30px; font-size:0.76rem; color:var(--accent-text); font-weight:600;">
            Read →
          </button>
        </div>
      </li>
    `;
  });

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 8. RENDERING TOPIC PILLS & COUNTS
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
    const cnt = counts[cat] || 0;
    html += `
      <button class="topic-pill ${state.activeTopic === cat ? 'active' : ''}" data-topic="${escapeHTML(cat)}">
        ${escapeHTML(cat)} <span class="pill-count">${cnt}</span>
      </button>
    `;
  });

  container.innerHTML = html;
}

// -------------------------------------------------------------
// 9. RENDERING CURATED DOMAIN SECTIONS
// -------------------------------------------------------------
export function renderCuratedSections(data) {
  const sections = [
    { containerId: 'ai-tools-container', items: data.ai_tools || [] },
    { containerId: 'dev-radar-container', items: data.dev_radar || [] },
    { containerId: 'research-safety-container', items: data.research_safety || [] }
  ];

  sections.forEach(({ containerId, items }) => {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = '<div style="padding:16px; color:var(--text-muted);">No verified developments in this section.</div>';
      return;
    }

    let html = '';
    items.slice(0, 4).forEach((item, idx) => {
      html += `
        <article class="card-standard" data-curated-section="${containerId}" data-curated-idx="${idx}">
          <div>
            <div class="card-top-bar">
              <span class="badge-signal" style="font-size:0.7rem;">${escapeHTML(item.signal_badge || '📰 AI Update')}</span>
              <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHTML(item.source)}</span>
            </div>
            <h3 class="card-headline font-serif" style="font-size:1.02rem;">${escapeHTML(item.title)}</h3>
            <p class="card-what-changed" style="font-size:0.83rem;">${escapeHTML(item.what_changed || item.summary)}</p>
          </div>
          <div class="card-bottom-bar" style="padding-top:8px;">
            <span style="font-size:0.74rem; color:var(--text-muted);">${escapeHTML(item.target_audience || 'For Developers')}</span>
            <button class="btn-action-icon" style="min-height:30px; font-size:0.76rem; color:var(--accent-text); font-weight:600;">
              Read →
            </button>
          </div>
        </article>
      `;
    });

    container.innerHTML = html;
  });
}

// -------------------------------------------------------------
// 10. RENDERING DAILY BRIEFING & STATUS BAR
// -------------------------------------------------------------
export function renderDailyOverview(overview, data) {
  if (!overview) return;

  const briefingText = document.getElementById('overview-briefing-text');
  if (briefingText) {
    briefingText.textContent = overview.briefing_text || '';
  }

  const countVal = document.getElementById('overview-count-val');
  if (countVal) {
    countVal.textContent = String(overview.total_developments_today || (data.top_stories ? data.top_stories.length : 0));
  }

  const lastUpdated = document.getElementById('overview-last-updated');
  if (lastUpdated && overview.last_updated) {
    lastUpdated.textContent = `Updated ${formatIST(overview.last_updated)}`;
  }

  const catchMeUp = document.getElementById('catch-me-up-items');
  if (catchMeUp && overview.top_developments) {
    let html = '';
    overview.top_developments.slice(0, 4).forEach((dev, idx) => {
      html += `
        <div class="catch-me-up-item" data-dev-idx="${idx}">
          <span class="badge-signal" style="font-size:0.7rem; margin-bottom:4px;">${escapeHTML(dev.signal_badge || '🚀 Frontier Launch')}</span>
          <h4 style="font-size:0.92rem; font-weight:600; margin-bottom:4px;">${escapeHTML(dev.title)}</h4>
          <p style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:6px;">${escapeHTML(dev.why_it_matters)}</p>
          <span style="font-size:0.74rem; color:var(--accent-text); font-weight:600;">${escapeHTML(dev.target_audience || '')}</span>
        </div>
      `;
    });
    catchMeUp.innerHTML = html;
  }
}

export function renderStatusBar(data) {
  const statusText = document.getElementById('status-text');
  if (statusText) {
    const istTime = data.last_successful_update ? formatIST(data.last_successful_update) : 'Recently';
    statusText.textContent = `● Live Pipeline Active • Hourly updates (Last: ${istTime})`;
  }

  const telemetry = document.getElementById('status-source-telemetry');
  if (telemetry) {
    const configuredCount = data.source_health_summary?.configured_sources_count || 25;
    telemetry.innerHTML = `
      <span>${configuredCount} monitored research sources</span>
      <span>•</span>
      <span>Strict provenance tracking</span>
    `;
  }
}
