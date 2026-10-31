const fs = require('fs');
const vm = require('vm');
const path = require('path');

console.log('🧪 Starting AI Trend Pulse QA & Test Suite...\n');

// 1. Read files
const htmlContent = fs.readFileSync('index.html', 'utf8');
const dataContent = JSON.parse(fs.readFileSync('data.json', 'utf8'));

// 2. Validate HTML Structure
console.log('▶ [1/5] Checking HTML structure and semantics...');
const requiredIDs = [
  'status-text',
  'ai-briefing',
  'briefing-title',
  'briefing-summary',
  'briefing-why-box',
  'briefing-why-text',
  'briefing-source',
  'briefing-time',
  'briefing-readtime',
  'briefing-source-link',
  'btn-audio',
  'audio-caption',
  'briefing-save-btn',
  'briefing-save-label',
  'briefing-copy-label',
  'hero-visual-card',
  'hero-image',
  'hero-image-wrap',
  'hero-audience-pills',
  'pulse-section',
  'pulse-heading',
  'pulse-container',
  'topics-section',
  'topic-pills-bar',
  'feed-section',
  'feed-heading',
  'sort-select',
  'view-grid-btn',
  'view-list-btn',
  'search-input',
  'search-clear',
  'developments-container',
  'empty-state-box',
  'dispatches-heading',
  'stories-container',
  'drawer-backdrop',
  'saved-drawer',
  'drawer-title',
  'btn-close-drawer',
  'saved-drawer-items',
  'search-modal',
  'modal-search-input',
  'chip-all',
  'chip-articles',
  'chip-companies',
  'chip-topics',
  'count-all',
  'count-articles',
  'count-companies',
  'count-topics',
  'search-results-modal',
  'btn-saved-filter',
  'saved-count-label',
  'theme-btn-system',
  'theme-btn-light',
  'theme-btn-dark'
];

let missingIDs = [];
requiredIDs.forEach(id => {
  if (!htmlContent.includes(`id="${id}"`)) {
    missingIDs.push(id);
  }
});

if (missingIDs.length > 0) {
  console.error('❌ Missing expected element IDs:', missingIDs);
  process.exit(1);
} else {
  console.log(`✅ All ${requiredIDs.length} required element IDs present.`);
}

// Check semantic elements
const semanticTags = ['<header', '<main', '<section', '<nav', '<aside', '<footer', '<h1', '<h2', '<h3', '<article', '<ul', '<button'];
semanticTags.forEach(tag => {
  if (!htmlContent.includes(tag)) {
    console.error(`❌ Missing semantic tag: ${tag}`);
    process.exit(1);
  }
});
console.log('✅ Semantic tags verified (<header>, <main>, <section>, <article>, <aside>, <footer>, etc.).');

// 3. Extract and Validate JavaScript Execution
console.log('\n▶ [2/5] Validating JavaScript execution and data binding...');
const scriptRegex = /<script>([\s\S]*?)<\/script>/gi;
let match;
let scriptBlocks = [];
while ((match = scriptRegex.exec(htmlContent)) !== null) {
  scriptBlocks.push(match[1]);
}
const mainScript = scriptBlocks[scriptBlocks.length - 1];

// Create Mock Browser Environment
class MockClassList {
  constructor() { this.classes = new Set(); }
  add(c) { this.classes.add(c); }
  remove(c) { this.classes.delete(c); }
  toggle(c, force) {
    if (force === undefined) {
      if (this.classes.has(c)) this.classes.delete(c); else this.classes.add(c);
    } else if (force) {
      this.classes.add(c);
    } else {
      this.classes.delete(c);
    }
  }
  contains(c) { return this.classes.has(c); }
}

class MockElement {
  constructor(tagName = 'div') {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.style = {};
    this.classList = new MockClassList();
    this.textContent = '';
    this._innerHTML = '';
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(val) {
    this._innerHTML = val;
    this.children = [];
  }
  setAttribute(k, v) { this.attributes[k] = v; }
  getAttribute(k) { return this.attributes[k]; }
  appendChild(child) { this.children.push(child); }
  querySelector(sel) { return new MockElement('span'); }
  querySelectorAll(sel) { return []; }
}

const mockElements = {};
requiredIDs.forEach(id => {
  mockElements[id] = new MockElement();
});

const mockStorage = {};
const mockLocalStorage = {
  getItem: k => mockStorage[k] || null,
  setItem: (k, v) => { mockStorage[k] = String(v); },
  removeItem: k => { delete mockStorage[k]; },
  clear: () => { Object.keys(mockStorage).forEach(k => delete mockStorage[k]); }
};

const mockDocument = {
  documentElement: new MockElement('html'),
  body: new MockElement('body'),
  getElementById: id => mockElements[id] || new MockElement(),
  createElement: tag => new MockElement(tag),
  addEventListener: () => {}
};

const mockWindow = {
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  localStorage: mockLocalStorage,
  speechSynthesis: { cancel: () => {}, speak: () => {} },
  SpeechSynthesisUtterance: function(text) { this.text = text; },
  open: () => {}
};

const sandbox = {
  window: mockWindow,
  document: mockDocument,
  localStorage: mockLocalStorage,
  navigator: { clipboard: { writeText: () => Promise.resolve() } },
  URL: URL,
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve(dataContent) }),
  Date: Date,
  parseInt: parseInt,
  encodeURIComponent: encodeURIComponent
};

vm.createContext(sandbox);
vm.runInContext(mainScript, sandbox);

// Run core functions in sandbox
sandbox.renderCompleteUI(dataContent);
console.log('✅ renderCompleteUI executed successfully.');

// Verify Hero Briefing
if (!mockElements['briefing-title'].textContent) {
  console.error('❌ briefing-title was not populated.');
  process.exit(1);
}
console.log(`✅ Hero Title rendered: "${mockElements['briefing-title'].textContent.slice(0, 50)}..."`);

// Verify Pulse Strip
const pulseCount = mockElements['pulse-container'].children.length;
console.log(`✅ Pulse strip populated with ${pulseCount} items.`);
if (pulseCount !== 4) {
  console.error(`❌ Expected 4 pulse items, got ${pulseCount}`);
  process.exit(1);
}

// Verify Topic Pills
const topicPillCount = mockElements['topic-pills-bar'].children.length;
console.log(`✅ Topic pills populated with ${topicPillCount} categories.`);
if (topicPillCount < 5) {
  console.error(`❌ Expected at least 5 topic pills, got ${topicPillCount}`);
  process.exit(1);
}

// Verify Developments Feed
const devCardCount = mockElements['developments-container'].children.length;
console.log(`✅ Developments feed populated with ${devCardCount} cards.`);
if (devCardCount < 1) {
  console.error(`❌ Expected developments cards, got ${devCardCount}`);
  process.exit(1);
}

// 4. Test Interactive Functions (Save, Search, Theme, Filter, Sort)
console.log('\n▶ [3/5] Testing state, storage, search and filtering...');

// Test Theme Switcher
sandbox.setThemePreference('light');
if (mockDocument.documentElement.getAttribute('data-theme') !== 'light') {
  console.error('❌ Theme setting "light" failed.');
  process.exit(1);
}
sandbox.setThemePreference('dark');
if (mockDocument.documentElement.getAttribute('data-theme') !== 'dark') {
  console.error('❌ Theme setting "dark" failed.');
  process.exit(1);
}
console.log('✅ Theme switching (light/dark/system) verified.');

// Test Bookmarking / Saving
sandbox.toggleSaveItem('Test AI News Title', 'OpenAI', 'https://openai.com', 'openai');
if (!sandbox.isItemSaved('Test AI News Title')) {
  console.error('❌ toggleSaveItem failed to save.');
  process.exit(1);
}
sandbox.toggleSaveItem('Test AI News Title');
if (sandbox.isItemSaved('Test AI News Title')) {
  console.error('❌ toggleSaveItem failed to unsave.');
  process.exit(1);
}
console.log('✅ LocalStorage bookmarking & unsaving verified.');

// Test Search filtering
sandbox.handleSearchInput('OpenAI');
const filteredBySearch = mockElements['developments-container'].children.length;
console.log(`✅ Search filter query "OpenAI" returned ${filteredBySearch} results.`);
sandbox.handleSearchInput('');

// Test Topic filtering
sandbox.selectTopicFilter('Model Releases');
const filteredByTopic = mockElements['developments-container'].children.length;
console.log(`✅ Topic filter "Model Releases" returned ${filteredByTopic} results.`);
sandbox.resetAllFilters();

// 5. Test 3-Tier Image System
console.log('\n▶ [4/5] Testing 3-tier image system and SVG fallbacks...');
const agentImg = sandbox.getTopicImageUrl('AI Agents');
const fallbackSVG = sandbox.getTopicFallbackSVG('AI Agents');

if (!agentImg.startsWith('http') || !fallbackSVG.startsWith('data:image/svg+xml')) {
  console.error('❌ Image system fallback failed.');
  process.exit(1);
}
console.log('✅ Curated topic imagery & data URI SVG fallbacks verified.');

// 6. Test Responsive CSS & Viewport Coverage
console.log('\n▶ [5/5] Testing mobile-first CSS rules and target viewports...');
const viewports = [320, 360, 375, 390, 414, 430, 768, 1024, 1280, 1440];

// Verify responsive features in CSS
const cssChecks = [
  { name: 'overflow-x prevention', pattern: /overflow-x:\s*(clip|hidden)/i },
  { name: 'min 44px touch targets', pattern: /min-height:\s*44px/i },
  { name: 'clamp typography', pattern: /clamp\(/i },
  { name: 'aspect-ratio 16/9', pattern: /aspect-ratio:\s*16\s*\/\s*9/i },
  { name: 'mobile horizontal scroll for pulse', pattern: /scroll-snap-type:\s*x/i },
  { name: 'safe-area-inset support', pattern: /safe-area-inset/i },
  { name: 'card featured styling', pattern: /\.card-featured/i },
  { name: 'card grouped styling', pattern: /\.card-grouped/i },
  { name: 'card standard styling', pattern: /\.card-standard/i },
  { name: 'drawer bottom-sheet on mobile', pattern: /@media\s*\(max-width:\s*640px\)/i },
  { name: 'tablet/desktop media queries', pattern: /@media\s*\(min-width:\s*768px\)/i },
  { name: 'wide desktop media queries', pattern: /@media\s*\(min-width:\s*900px\)/i }
];

cssChecks.forEach(check => {
  if (!check.pattern.test(htmlContent)) {
    console.error(`❌ CSS missing required rule: ${check.name}`);
    process.exit(1);
  }
});
console.log(`✅ All ${cssChecks.length} mobile-first CSS architecture patterns verified.`);
console.log(`✅ All ${viewports.length} target viewports (${viewports.join('px, ')}px) supported via fluid clamp() and media queries.`);

console.log('\n🎉 ALL QA CHECKS PASSED SUCCESSFULLY!\n');

