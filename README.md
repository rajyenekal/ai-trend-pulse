# ⚡ AI Trend Pulse (v2.2 High-Signal Editorial & AI Reader Architecture)

> **Autonomous AI market intelligence with traceable evidence provenance, 10 active frontier sources, full structured article extraction, 10-section AI article enhancement, strict cross-section non-duplication, and an in-app reading experience.**

- **Live Deployment**: [https://rajyenekal.github.io/ai-trend-pulse/](https://rajyenekal.github.io/ai-trend-pulse/)
- **Repository**: [https://github.com/rajyenekal/ai-trend-pulse](https://github.com/rajyenekal/ai-trend-pulse)

---

## 🏛️ Source Strategy & Verification Hierarchy

AI Trend Pulse organizes 25 configured sources in [`sources.json`](sources.json) with exactly **10 active frontier sources** enabled and **15 noisy/routine feeds archived in reserve** to maximize the signal-to-noise ratio:

### Active Monitored Sources (10 Enabled)

| Source ID | Publisher Name | Classification | Primary Editorial Role | Trust Tier |
| :--- | :--- | :--- | :--- | :--- |
| `openai_news` | OpenAI News | Tier 1: Primary Lab | Models, ChatGPT, APIs, reasoning research, safety | Tier 1 |
| `anthropic_news` | Anthropic News | Tier 1: Primary Lab | Claude, agents, frontier research, constitutional safety | Tier 1 |
| `deepmind_blog` | Google DeepMind | Tier 1: Primary Lab | Gemini, scientific AI, robotics, multimodal breakthroughs | Tier 1 |
| `nvidia_blog` | NVIDIA Newsroom | Tier 1: Primary Lab | Accelerated silicon, Blackwell GPUs, generative AI infra | Tier 1 |
| `aws_ml_blog` | AWS Machine Learning | Tier 1: Primary Lab | Bedrock, SageMaker, cloud AI, enterprise model hosting | Tier 1 |
| `mit_tech_review` | MIT Technology Review | Tier 2: Tech Press | Independent research evaluation, policy, critical analysis | Tier 2 |
| `techcrunch_ai` | TechCrunch AI | Tier 2: Tech Press | AI startup ecosystems, venture funding, acquisitions | Tier 2 |
| `the_verge_ai` | The Verge AI | Tier 2: Tech Press | Consumer AI applications, product launches, antitrust | Tier 2 |
| `the_decoder` | The Decoder | Tier 2: Tech Press | AI industry, foundation models, agents, technical audits | Tier 2 |
| `huggingface_blog` | Hugging Face | Tier 3: Open Ecosystem | Open weights, developer tooling, community models | Tier 3 |

### Archived Feeds (15 Preserved in Reserve)
`anthropic_hn_discovery`, `google_ai_blog`, `microsoft_ai_news`, `amazon_science`, `github_blog_ai`, `mistral_news`, `ars_technica`, `arxiv_cs_ai`, `arxiv_cs_lg`, `bair_blog`, `simon_willison`, `import_ai`, `lmsys_org`, `latent_space`, `hf_daily_papers`.

---

## 🔍 NVIDIA Generative AI Newsroom Feed

The general NVIDIA blog feed has been replaced by the dedicated **Generative AI newsroom category feed**:
- **Feed URL**: `https://nvidianews.nvidia.com/cats/generative_al.xml`
- **Canonical Listing**: `https://nvidianews.nvidia.com/cats/generative_al`
- **Noise Filtering**: Automatically rejects consumer PC gaming drivers, GeForce game updates, and non-AI graphics releases while prioritizing data center GPU architecture and foundation model partnerships.

---

## 🧠 Full Article Content Extraction & AI Enhancement Engine

When an article is ingested:
1. **Structured Content Extraction (`pipeline/extractor.py`)**:
   - Parses the complete article body from original publisher pages using Trafilatura and JSON-LD / OpenGraph schema metadata.
   - Extracts headline, subtitle, author, publication date, featured image, section hierarchy, clean paragraphs, word count, reading time, and a SHA-256 `content_hash`.
   - Thread-safe caching in `.article_cache.json` eliminates repeated downloads.
   - Respects publisher access restrictions, copyright, and rate limits. Paywalls and authentication gates are never bypassed.

2. **10-Section AI Article Enhancement (`pipeline/enricher.py`)**:
   - **`ai_overview`**: Concise 2-3 sentence overview of the development.
   - **`ai_what_happened`**: Objective announcement breakdown.
   - **`ai_key_details`**: Technical specifics, benchmark metrics, and data points.
   - **`ai_why_it_matters`**: Real-world significance and architectural implications.
   - **`ai_technical_breakdown`**: Underlying technology explained without corporate PR jargon.
   - **`ai_industry_impact`**: Strategic implications for developers, businesses, and researchers.
   - **`ai_whats_new`**: Specific novel contributions compared to prior art.
   - **`ai_key_takeaways`**: Distinct bulleted takeaways.
   - **`ai_limitations`**: Verification bounds, epistemic limitations, and caveats.
   - **`original_source_url`**: Direct clean link to original reporting.

3. **Strict Cross-Section Non-Duplication**:
   - Both the backend enricher and the frontend reader drawer enforce sentence-level deduplication via normalized comparison.
   - Sentences rendered in Overview or Takeaways are never repeated in What Happened, Facts, Technical Breakdown, or Why It Matters.

---

## 🏷️ Canonical Taxonomy (10 Categories) & 3 Impact Levels

Every story is deterministically categorized into one of 10 canonical domains:
1. **Frontier Models**
2. **AI Research**
3. **AI Agents**
4. **Open Source AI**
5. **AI Infrastructure**
6. **AI Business**
7. **AI Safety**
8. **AI Policy**
9. **Developer Tools**
10. **Consumer AI**

Each development is classified into one of 3 impact levels:
- **`Breakthrough`** (Pulse Score $\ge 84$): Major paradigm shifts, landmark foundation models, or historic benchmark leaps.
- **`Major`** (Pulse Score $\ge 74$): Significant product releases, official lab announcements, or major infrastructure updates.
- **`Notable`** (Pulse Score $< 74$): Developer tooling updates, domain workflows, or ecosystem updates.

---

## ⚡ Algorithmic Pulse Scoring Formula

Every ingested dispatch is evaluated through a deterministic scoring function that balances historical significance, developer utility, freshness, and verified multi-publisher corroboration:

$$\text{Pulse Score} = 0.30 \times \text{Importance} + 0.20 \times \text{Audience Relevance} + 0.20 \times \text{Freshness} + 0.15 \times \text{Coverage Corroboration} + 0.15 \times \text{Source Quality}$$

### Component Breakdown
- **Importance ($0.30$)**: Measures architectural significance, benchmark capability jumps, reasoning leaps, safety framework updates, and API releases. Safety, security, alignment, and policy stories receive a guaranteed minimum protected score of 75.
- **Audience Relevance ($0.20$)**: Assesses practical utility for developers, ML engineers, security researchers, and enterprise architects.
- **Freshness ($0.20$)**: Time-decay function anchored to verified publication timestamps; stories with missing dates receive a neutral baseline (50) without artificial freshness boosting.
- **Coverage & Corroboration ($0.15$)**: Grounded strictly in distinct corporate publisher groups. Multiple stories or feeds from the same parent organization (e.g. Google DeepMind + Google AI) count as one publisher group; community discovery channels do not count as independent press.
- **Source Quality & Authority ($0.15$)**: Verification weight determined by the tier classification of the primary publishing entity (Tier 1 = 100, Tier 2 = 85, Tier 3 = 80, Tier 4 = 65).

---

## 📱 In-App Reader View & Per-Article Static Delivery

- **Per-Article Static Delivery**: Individual enriched article documents are generated at `articles/{clean_id}.json`, keeping the homepage bundle (`data.json`) ultra-fast while providing complete, structured article dossiers on click.
- **Client-Side In-Memory Cache**: `drawer.js` maintains an in-memory `articleCache` map for sub-millisecond reader reopening and graceful offline fallback.
- **Sliding Drawer & Mobile Sheet**: Responsive sliding drawer on desktop (720px width), full-screen reading mode on mobile (`<= 640px`).
- **AI Provenance & Extraction Badges**: Real-time provenance pills (`AI-Enhanced Analysis` vs. `Editorial Synthesis`) and extraction status indicators (`Full Article Extracted (N words)`).
- **Strict Cross-Section Deduplication**: Absolute uniqueness engine prevents any sentence from repeating across AI Overview, Key Takeaways, Verified Facts, What Happened, Technical Breakdown, Detailed Analysis, Why It Matters, or Potential Impact. Empty or undisclosed sections hide cleanly without filler.
- **Instant 0ms Initial State Hydration**: Pre-bundled `data.js` executes synchronously before application initialization, guaranteeing zero-skeleton initial paint.

---

## 🔒 Security, Telemetry & Pipeline Auditing (v2.2 Production Audit)

1. **SSRF Protection (`is_safe_public_url`)**:
   - Resolves target hostnames and blocks RFC 1918 private IPv4 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
   - Blocks loopback interfaces (`127.0.0.0/8`, `::1`), link-local metadata endpoints (`169.254.169.254` for AWS/GCP/Azure instance metadata), and multicast ranges.
2. **Extraction Candidate Prioritization**:
   - Selects candidate articles for full-body extraction according to editorial priority: `(pulse_score, -trust_tier, is_official)` taking the top 25 highest-signal stories.
3. **Genuine AI Enhancement & Factual Grounding**:
   - Optional Gemini Flash LLM integration (`gemini-2.5-flash`, `gemini-2.0-flash`) with low temperature (0.2), strict grounding on extracted article body, and JSON schema enforcement.
   - Transparent fallback to deterministic `Editorial Synthesis` when API quotas are exceeded or unconfigured, with explicit `is_llm_generated: false` provenance.
4. **Extraction & Ingestion Telemetry**:
   - Tracks operational metrics: `extraction_attempts`, `successful_full_body_extractions`, `cached_content`, `rss_only_fallbacks`, `blocked_pages`, `missing_content`, `average_extracted_word_count`, `ai_enhancement_success`, and `ai_fallback_usage`.
5. **Zero Boilerplate Guarantee**:
   - Eradication of canned template strings across all pipeline generation stages. Missing technical metrics are explicitly noted as undisclosed rather than hallucinated.

---

## 🧩 Key Product Features & Information Architecture (v2.1)

1. **Tier A: Top 5 Executive Bento Grid**:
   - Visual hierarchy highlighting the 5 highest-signal developments of the hour.
   - Lead Hero card with full editorial summary, publisher vector logo, and deep-read preview.
   - 4 supporting bento subcards for rapid 60-second scanning across multiple viewports.

2. **Tier B: Compact Live Wire Table**:
   - Fast, dense tabular wire view (`setLayoutView('wire')`) for market analysts and power users.
   - Displays publication timestamp, intent signal badge, headline, and multi-publisher corroboration pills.

3. **Decluttered Editorial Cards**:
   - Standard cards redesigned with a >30% height reduction by removing noisy numerical score badges.
   - Concise 1-line "What Changed" and "Why It Matters" callouts.
   - Full 5-metric score breakdown bar tucked cleanly into the reader drawer.

4. **Curated Domain Sections**:
   - **AI Tools You Can Use**: Practical tools, consumer applications, and developer productivity workflows.
   - **Developer Radar**: Coding agents, APIs, open-source weights, MCP protocols, and infrastructure.
   - **Research, Safety & Policy**: Frontier lab alignment, arXiv preprints, governance standards, and policy updates.
   - **Developments Feed**: Multi-tier editorial feed with topic filtering, search query matching, and layout toggles.
   - **Dispatches Feed**: Chronological list of verified stories with full metadata.

5. **Article Intent Classifier & Score Calibration**:
   - 8-type canonical intent taxonomy: `frontier_launch` (1.12x), `open_source_release` (1.12x), `research_paper` (1.05x), `sdk_api_update` (1.05x), `security_vulnerability` (1.05x), `policy_regulation` (1.00x), `opinion_commentary` (0.80x), `case_study_pr` (0.60x).
   - Single-source customer case studies capped at `<= 64.0` to eliminate vendor promotional bias.
   - "Hide Case Studies" quick toggle in UI to filter out promotional content on demand.

6. **In-App Reader View & Story Deep Dive**:
   - Slide-over drawer on desktop, bottom sheet on mobile.
   - Displays topic badge, tier status badge, estimated read time, key takeaways, detailed operational analysis, Why It Matters callout, affected audience tags, and direct canonical source button.

7. **Editorial & Scoring Methodology Modal**:
   - Accessible via `#btn-methodology` or header navigation.
   - Transparent disclosure of the 4-tier source registry, scoring formula, and anti-hallucination policies.
   - Accessible via keyboard shortcuts (`Escape` to close).

8. **Provenance, Claim Verification & Anti-Hallucination Safeguards**:
   - **Paired Evidence References**: Every citation is an atomic object (`article_id`, `canonical_url`, `publisher_group_id`, `supporting_excerpt`, and `text_verified`). Unpaired lists, prefix matching, and mismatched article ID / URL pairs are strictly rejected.
   - **Hybrid Semantic Clustering**: Anchor entity token matching for frontier models (Claude 3.7, GPT-4o, Llama 3.3, DeepSeek-R1, Gemini 2.0, etc.) combined with suffix-stemmed Jaccard similarity.
   - **Decoupled Claim Corroboration vs Trend Diversity**: Decouples independent press corroboration (multiple publisher groups reporting the exact same fact) from theme signal diversity (multiple distinct developments forming a broad industry pattern).
   - **Deterministic Article IDs**: Every article receives a unique, content-grounded identifier (`art_{source_id}_{hash12}`). AI briefings must cite exact matching article IDs.
   - **Exact Normalized URL Matching**: Prefix matching is eliminated. Exact URL equality is required, and hallucinated or unverified citations are rejected rather than substituted with unrelated stories.
   - **Independent Publisher Group Counting**: Distinguishes between feed IDs and corporate publisher groups. Multiple outlets owned by Alphabet/Google, Microsoft, Amazon, or Yahoo/TechCrunch each count as a single publishing entity. Hacker News and social discovery feeds do not add to independent press counts.
   - **Strict Temporal Truth**: Missing or ambiguous publication dates are explicitly displayed as "Date unavailable" and never assigned the current time.
   - **Parameter-Clean URLs**: Strips tracking parameters (`utm_*`, `ref`, `fbclid`, etc.) to guarantee clean provenance and user privacy.
   - **Source Health Monitoring & Zero Silent Failures**: Continuous telemetry tracks all 25 monitored feeds across 5 deterministic operating cases (Normal, Valid Zero, Degraded, Total Upstream Failure Halt, All Content Filtered). If upstream networks fail completely, the pipeline halts with a non-zero exit code to alert CI while preserving verified datasets intact.

---

## 📱 Mobile-First UI/UX Engineering

- **Zero-Bundler Native ES Modules**: Clean separation across `js/state.js`, `js/render.js`, `js/drawer.js`, and `js/app.js` with zero build or bundler dependencies.
- **Design Tokens**: Standardized CSS custom properties in `css/tokens.css` for light, dark, and system themes.
- **Modular Stylesheets**: Component styles encapsulated in `css/styles.css`.
- **Viewport Support**: Zero horizontal overflow across all 10 target viewports: `320px`, `360px`, `375px`, `390px`, `414px`, `430px`, `768px`, `1024px`, `1280px`, `1440px`.
- **Fluid Typography**: Dynamic scaling via CSS `clamp()` without sudden layout shifts.
- **Touch Targets**: Minimum 44px for all buttons and interactive controls.
- **Safe Area Insets**: Support for iOS notch and home indicator (`env(safe-area-inset-bottom)`).
- **Theme Persistence**: Light, Dark, and System (Auto) modes persisted via `localStorage` with zero flicker.
- **Audio Briefing**: In-browser speech synthesis for audio playback of top stories.

---

## 🧪 Testing & Verification

Run the complete test suite:

```bash
npm test
```

This automatically runs:
1. **`python3 test_backend.py` (37 tests)**:
   - Validates `sources.json` schema and 4-tier coverage (25 sources).
   - Validates 9-type intent taxonomy and multipliers.
   - Verifies case study 0.55x multiplier and 62.0 score cap.
   - Verifies hybrid clustering with anchor entity tokens.
   - Verifies conditional HTTP 304 caching and ETag handling.
   - Verifies URL normalization, parameter removal, and RFC-2822 timestamp parsing.
   - Validates payload structure and atomic write guarantees.
2. **`python3 -m unittest discover -s tests -p 'test_*.py'` (39 tests)**:
   - Verifies deterministic editorial curation, explainable score reason codes, and diversity quotas (`test_editorial_curation.py`).
   - Tests clean Trafilatura article extraction with timeouts and fallback (`test_extraction.py`).
   - Tests GitHub Developer Trends collection, star velocity, and snapshot persistence (`test_github_collector.py`).
   - Tests source expansion and feed health telemetry (`test_source_expansion.py`).
3. **`node test_qa.js` (6 phases)**:
   - Validates HTML semantic tags and all required DOM element IDs.
   - Tests full JavaScript runtime execution in a headless sandbox.
   - Verifies rendering of Dispatches, Topic Pills, Developments Feed, Top 5 Bento Grid, AI Tools, Developer Radar, and Research/Safety sections.
   - Tests theme switching, bookmarking/saving, search filtering, topic filtering, Reader View open/close, and Methodology modal open/close.
   - Tests 3-tier image system, signature vector visuals, and IST timestamp formatting.
   - Verifies 11 mobile-first CSS architecture patterns.
   - Verifies article_type taxonomy, Compact Wire view, and Hide Case Studies toggle.
4. **`node test_viewports.js`**:
   - Performs responsive QA across all 10 device viewports from `320px` to `1440px`.
   - Verifies Top 5 Bento Grid responsive rules across mobile, tablet, and desktop.
   - Asserts standard card height reduction >= 25% (measured 34.5% reduction).
   - Confirms zero horizontal overflow across narrow mobile to 4K displays.

---

## 🛠️ Local Development & Execution

### Prerequisites
- Python 3.9+
- Node.js 18+

### Setup
```bash
git clone https://github.com/rajyenekal/ai-trend-pulse.git
cd ai-trend-pulse
```

### Ingestion & Data Refresh
```bash
python3 tracker.py
```

### Run Tests
```bash
npm test
```

### Preview Frontend
```bash
# Serve locally using any static file server
python3 -m http.server 8080
```
Open `http://localhost:8080` in your browser.

---

## 📄 License
MIT License. Free and open-source for personal and educational use.
