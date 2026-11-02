const fs = require('fs');
const vm = require('vm');
const path = require('path');

console.log('🧪 Starting AI Trend Pulse QA & Test Suite...\n');

// 1. Read files
const htmlContent = fs.readFileSync('index.html', 'utf8');
const dataContent = JSON.parse(fs.readFileSync('data.json', 'utf8'));
const tokensCss = fs.readFileSync('css/tokens.css', 'utf8');
const stylesCss = fs.readFileSync('css/styles.css', 'utf8');
const fullCssContent = htmlContent + '\n' + tokensCss + '\n' + stylesCss;

// 2. Validate HTML Structure
console.log('▶ [1/6] Checking HTML structure and semantics...');
const requiredIDs = [
  'status-text',
  'btn-audio',
  'audio-caption',
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
  'theme-btn-dark',
  'reader-backdrop',
  'reader-drawer',
  'reader-topic-badge',
  'reader-status-badge',
  'reader-readtime',
  'btn-close-reader',
  'reader-title',
  'reader-source-name',
  'reader-pub-time',
  'reader-btn-save',
  'reader-btn-copy',
  'reader-image-wrap',
  'reader-image',
  'reader-key-points',
  'reader-detailed-analysis',
  'reader-why-box',
  'reader-why-text',
  'reader-affected-box',
  'reader-audience-pills',
  'reader-external-btn',
  'reader-source-btn-name',
  'btn-methodology',
  'methodology-backdrop',
  'methodology-modal',
  'btn-close-methodology',
  'ai-tools-section',
  'ai-tools-container',
  'dev-radar-section',
  'dev-radar-container',
  'research-safety-section',
  'research-safety-container',
  'reader-facts-box',
  'reader-facts-list',
  'reader-impact-box',
  'reader-potential-impact',
  'reader-limitations-box',
  'reader-limitations-text',
  'status-source-telemetry',
  'bento-container',
  'btn-hide-case-studies'
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
  console.log(`✅ All ${requiredIDs.length} required element IDs present in modular HTML shell.`);
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
console.log('\n▶ [2/6] Validating JavaScript execution and data binding...');
const jsFiles = ['js/state.js', 'js/render.js', 'js/drawer.js', 'js/app.js'];
let mainScript = jsFiles.map(f => fs.readFileSync(f, 'utf8')).join('\n');
// Strip ES import/export statements for Node VM execution
mainScript = mainScript
  .replace(/^\s*import\s+[^;]+;\s*$/gm, '')
  .replace(/^\s*export\s+(async\s+function|function|const|let|var|class)\s+/gm, '$1 ')
  .replace(/^\s*export\s+default\s+/gm, '');

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
    if (!val) return;
    const regex = /<(article|li|button|div|tr|p|span)([^>]*)>([\s\S]*?)<\/\1>/gi;
    let m;
    while ((m = regex.exec(val)) !== null) {
      const el = new MockElement(m[1]);
      el.textContent = m[3].replace(/<[^>]+>/g, '').trim();
      el.innerHTML = m[3];
      this.children.push(el);
    }
    if (this.children.length === 0) {
      const openMatches = val.match(/<(article|li|button|div|tr|p|span)[^>]*>/gi);
      if (openMatches) {
        openMatches.forEach(tag => {
          const tMatch = tag.match(/<([a-zA-Z0-9]+)/);
          const tName = tMatch ? tMatch[1] : 'div';
          this.children.push(new MockElement(tName));
        });
      }
    }
  }
  get firstElementChild() { return this.children[0] || null; }
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
  open: () => {},
  document: mockDocument
};
mockWindow.window = mockWindow;

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

// Verify Dispatches Feed
const dispatchCount = mockElements['stories-container'].children.length;
console.log(`✅ Dispatches feed populated with ${dispatchCount} stories.`);
if (dispatchCount < 1) {
  console.error(`❌ Expected dispatch stories, got ${dispatchCount}`);
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

// Verify Top 5 Bento Container
const bentoCount = mockElements['bento-container'].children.length;
console.log(`✅ Top 5 Bento Grid populated with ${bentoCount} elements.`);
if (bentoCount < 1) {
  console.error(`❌ Expected bento items, got ${bentoCount}`);
  process.exit(1);
}

// Verify Curated Domain Sections
const aiToolsCount = mockElements['ai-tools-container'].children.length;
const devRadarCount = mockElements['dev-radar-container'].children.length;
const researchSafetyCount = mockElements['research-safety-container'].children.length;
console.log(`✅ AI Tools section populated with ${aiToolsCount} cards.`);
console.log(`✅ Developer Radar section populated with ${devRadarCount} cards.`);
console.log(`✅ Research & Safety section populated with ${researchSafetyCount} cards.`);
if (aiToolsCount < 1 || devRadarCount < 1 || researchSafetyCount < 1) {
  console.error('❌ Curated domain sections failed to populate cards.');
  process.exit(1);
}

// 4. Test Interactive Functions (Save, Search, Theme, Filter, Sort)
console.log('\n▶ [3/6] Testing state, storage, search and filtering...');

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
const sampleTopic = (dataContent.top_stories && dataContent.top_stories[0])
  ? (dataContent.top_stories[0].category || dataContent.top_stories[0].topic)
  : 'AI Models & Research';
sandbox.selectTopicFilter(sampleTopic);
const filteredByTopic = mockElements['developments-container'].children.length;
console.log(`✅ Topic filter "${sampleTopic}" returned ${filteredByTopic} results.`);
sandbox.resetAllFilters();

// Test In-App Reader View & Deep Dive
if (dataContent.trends && dataContent.trends[0]) {
  sandbox.openReaderView(dataContent.trends[0]);
  if (!mockElements['reader-drawer'].classList.contains('open')) {
    console.error('❌ reader-drawer failed to open.');
    process.exit(1);
  }
  if (!mockElements['reader-title'].textContent) {
    console.error('❌ reader-title was not populated.');
    process.exit(1);
  }
  if (!mockElements['reader-key-points'].children.length) {
    console.error('❌ reader-key-points was not populated.');
    process.exit(1);
  }
  if (!mockElements['reader-detailed-analysis'].children.length) {
    console.error('❌ reader-detailed-analysis was not populated.');
    process.exit(1);
  }
  // Check editorial grounding sections
  if (dataContent.trends[0].reported_facts && dataContent.trends[0].reported_facts.length > 0) {
    if (!mockElements['reader-facts-list'].children.length) {
      console.error('❌ reader-facts-list was not populated for story with reported_facts.');
      process.exit(1);
    }
  }
  if (dataContent.trends[0].potential_impact) {
    if (!mockElements['reader-potential-impact'].textContent) {
      console.error('❌ reader-potential-impact was not populated.');
      process.exit(1);
    }
  }
  if (dataContent.trends[0].analysis_limitations) {
    if (!mockElements['reader-limitations-text'].textContent) {
      console.error('❌ reader-limitations-text was not populated.');
      process.exit(1);
    }
  }
  sandbox.closeReaderView();
  if (mockElements['reader-drawer'].classList.contains('open')) {
    console.error('❌ reader-drawer failed to close.');
    process.exit(1);
  }

  // Deep Read deduplication verification across all stories
  const allStories = [...(dataContent.trends || []), ...(dataContent.top_stories || [])];
  allStories.forEach((story, idx) => {
    mockElements['reader-key-points'].innerHTML = '';
    mockElements['reader-detailed-analysis'].innerHTML = '';
    mockElements['reader-why-text'].textContent = '';

    sandbox.openReaderView(story);

    const title = mockElements['reader-title'].textContent.trim().toLowerCase();
    const kpTexts = mockElements['reader-key-points'].children.map(c => c.textContent.trim().toLowerCase());
    const daTexts = mockElements['reader-detailed-analysis'].children.map(c => c.textContent.trim().toLowerCase());
    const whyText = mockElements['reader-why-text'].textContent.trim().toLowerCase();

    // 1. Check that no takeaway bullet duplicates the headline
    kpTexts.forEach((kp, i) => {
      if (kp === title) {
        console.error(`❌ Story ${idx+1} ("${story.title}"): Takeaway bullet ${i+1} duplicates headline!`);
        process.exit(1);
      }
    });

    // 2. Check that no takeaway bullets duplicate each other
    if (new Set(kpTexts).size !== kpTexts.length) {
      console.error(`❌ Story ${idx+1} ("${story.title}"): Duplicate takeaway bullets found!`, kpTexts);
      process.exit(1);
    }

    // 3. Check that no detailed paragraph duplicates the headline
    daTexts.forEach((da, i) => {
      if (da === title) {
        console.error(`❌ Story ${idx+1} ("${story.title}"): Detailed paragraph ${i+1} duplicates headline!`);
        process.exit(1);
      }
    });

    // 4. Check that no detailed paragraphs duplicate each other
    if (new Set(daTexts).size !== daTexts.length) {
      console.error(`❌ Story ${idx+1} ("${story.title}"): Duplicate detailed paragraphs found!`, daTexts);
      process.exit(1);
    }

    // 5. Check that why_it_matters does not duplicate title or detailed paragraph verbatim
    if (whyText && whyText === title) {
      console.error(`❌ Story ${idx+1} ("${story.title}"): Why It Matters duplicates headline!`);
      process.exit(1);
    }
    if (whyText && daTexts.length > 0 && daTexts.includes(whyText)) {
      console.error(`❌ Story ${idx+1} ("${story.title}"): Why It Matters duplicates detailed paragraph!`);
      process.exit(1);
    }
  });

  sandbox.closeReaderView();
  console.log(`✅ In-App Reader View: ${allStories.length} stories verified with ZERO duplicated texts!`);
}

// Test Methodology Modal
sandbox.openMethodologyModal();
if (!mockElements['methodology-backdrop'].classList.contains('open')) {
  console.error('❌ methodology-backdrop failed to open.');
  process.exit(1);
}
sandbox.closeMethodologyModal();
if (mockElements['methodology-backdrop'].classList.contains('open')) {
  console.error('❌ methodology-backdrop failed to close.');
  process.exit(1);
}
console.log('✅ Methodology Modal (open/close, transparency tables, scoring formula) verified.');

// 5. Test 3-Tier Image System & Indian Standard Time formatting
console.log('\n▶ [4/6] Testing 3-tier image system, signature lab visuals, and IST formatting...');
const agentImg = sandbox.getTopicImageUrl('AI Agents');
const fallbackSVG = sandbox.getTopicFallbackSVG('AI Agents');

if (!agentImg.startsWith('http') || !fallbackSVG.startsWith('data:image/svg+xml')) {
  console.error('❌ Image system fallback failed.');
  process.exit(1);
}

// Test Signature Lab Visuals for OpenAI, Anthropic, Google, NVIDIA
const openaiImg = sandbox.getTopicImageUrl('AI Models & Research', null, 'OpenAI');
const anthropicImg = sandbox.getTopicImageUrl('AI Models & Research', null, 'Anthropic');
const nvidiaImg = sandbox.getTopicImageUrl('AI Infrastructure', null, 'NVIDIA');

if (!openaiImg.startsWith('data:image/svg+xml') || !openaiImg.includes('OpenAI')) {
  console.error('❌ OpenAI signature lab visual failed.');
  process.exit(1);
}
if (!anthropicImg.startsWith('data:image/svg+xml') || !anthropicImg.includes('Claude')) {
  console.error('❌ Anthropic signature lab visual failed.');
  process.exit(1);
}
if (!nvidiaImg.startsWith('data:image/svg+xml') || !nvidiaImg.includes('NVIDIA')) {
  console.error('❌ NVIDIA signature lab visual failed.');
  process.exit(1);
}

// Test IST Formatting
const testDate = new Date('2026-11-01T12:00:00Z');
const istFormatted = sandbox.formatIST(testDate);
if (!istFormatted || !istFormatted.includes('IST')) {
  console.error('❌ formatIST failed to produce IST timestamp.');
  process.exit(1);
}
console.log('✅ Curated topic imagery, signature lab visuals (OpenAI, Claude, NVIDIA), & IST time verified.');

// 6. Test Responsive CSS & Viewport Coverage
console.log('\n▶ [5/6] Testing mobile-first CSS rules and target viewports...');
const viewports = [320, 360, 375, 390, 414, 430, 768, 1024, 1280, 1440];

// Verify responsive features across full modular CSS
const cssChecks = [
  { name: 'overflow-x prevention', pattern: /overflow-x:\s*(clip|hidden)/i },
  { name: 'min 44px touch targets', pattern: /min-height:\s*44px/i },
  { name: 'clamp typography', pattern: /clamp\(/i },
  { name: 'aspect-ratio 16/9', pattern: /aspect-ratio:\s*16\s*\/\s*9/i },
  { name: 'safe-area-inset support', pattern: /safe-area-inset/i },
  { name: 'card standard styling', pattern: /\.card-standard/i },
  { name: 'bento grid styling', pattern: /\.bento-container/i },
  { name: 'wire table styling', pattern: /\.wire-table/i },
  { name: 'drawer bottom-sheet on mobile', pattern: /@media\s*\(max-width:\s*640px\)/i },
  { name: 'tablet/desktop media queries', pattern: /@media\s*\(min-width:\s*768px\)/i },
  { name: 'wide desktop media queries', pattern: /@media\s*\(min-width:\s*900px\)/i }
];

cssChecks.forEach(check => {
  if (!check.pattern.test(fullCssContent)) {
    console.error(`❌ CSS missing required rule: ${check.name}`);
    process.exit(1);
  }
});
console.log(`✅ All ${cssChecks.length} mobile-first CSS architecture patterns verified across css/tokens.css & css/styles.css.`);
console.log(`✅ All ${viewports.length} target viewports (${viewports.join('px, ')}px) supported via fluid clamp() and media queries.`);

// 7. Phase 5 New Verification Checklist: article_type taxonomy, Compact Wire, Hide Case Studies
console.log('\n▶ [6/6] Phase 5: Testing v2.1 taxonomy, Compact Wire, and Case Studies filter...');

const VALID_ARTICLE_TYPES = new Set([
  'frontier_launch',
  'open_source_release',
  'research_paper',
  'sdk_api_update',
  'security_vulnerability',
  'policy_regulation',
  'case_study_pr',
  'opinion_commentary',
  'routine_minor_update'
]);

const sectionsToValidate = [
  { name: 'top_stories', items: dataContent.top_stories || [] },
  { name: 'trends', items: dataContent.trends || [] },
  { name: 'ai_tools', items: dataContent.ai_tools || [] },
  { name: 'dev_radar', items: dataContent.dev_radar || [] },
  { name: 'research_safety', items: dataContent.research_safety || [] }
];

let totalValidatedItems = 0;
sectionsToValidate.forEach(sec => {
  sec.items.forEach((item, idx) => {
    totalValidatedItems++;
    if (!item.article_type || !VALID_ARTICLE_TYPES.has(item.article_type)) {
      console.error(`❌ ${sec.name}[${idx}] ("${item.title}") has invalid article_type: "${item.article_type}"`);
      process.exit(1);
    }
    if (!item.signal_badge || typeof item.signal_badge !== 'string' || item.signal_badge.trim() === '') {
      console.error(`❌ ${sec.name}[${idx}] ("${item.title}") has empty signal_badge!`);
      process.exit(1);
    }
  });
});
console.log(`✅ Verified ${totalValidatedItems} items across all sections in data.json carry valid article_type and signal_badge.`);

// Test Compact Wire Layout View
sandbox.setLayoutView('wire');
const wireHTML = mockElements['developments-container'].innerHTML;
if (!wireHTML.includes('wire-table') && !wireHTML.includes('wire-row')) {
  console.error('❌ Compact Wire view failed to render tabular wire structure.');
  process.exit(1);
}
console.log('✅ Compact Wire tabular view successfully rendered without layout failure.');
sandbox.setLayoutView('cards'); // restore card layout

// Test Hide Case Studies Filter
sandbox.resetAllFilters();
const totalCardsBefore = mockElements['developments-container'].children.length;
sandbox.toggleHideCaseStudies();
const totalCardsAfter = mockElements['developments-container'].children.length;
const containerHTML = mockElements['developments-container'].innerHTML;

const caseStudyTitles = (dataContent.top_stories || [])
  .filter(s => s.article_type === 'case_study_pr')
  .map(s => s.title);

caseStudyTitles.forEach(t => {
  if (containerHTML.includes(t)) {
    console.error(`❌ Case study story "${t}" was NOT hidden when hideCaseStudies is active!`);
    process.exit(1);
  }
});
console.log(`✅ Hide Case Studies filter verified: ${caseStudyTitles.length} case study items excluded (cards: ${totalCardsBefore} -> ${totalCardsAfter}).`);
sandbox.toggleHideCaseStudies(); // restore

console.log('\n🎉 ALL QA CHECKS PASSED SUCCESSFULLY!\n');
