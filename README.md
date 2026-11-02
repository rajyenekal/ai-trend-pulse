# ⚡ AI Trend Pulse (v2.1 High-Signal Modular Architecture)

> **Autonomous, hourly AI market intelligence with traceable evidence provenance, 4-tier source verification, intent-calibrated pulse scoring, hybrid semantic clustering, and a modular zero-dependency architecture.**

- **Live Deployment**: [https://rajyenekal.github.io/ai-trend-pulse/](https://rajyenekal.github.io/ai-trend-pulse/)
- **Mirror Deployment**: [https://aitrend-pulse.netlify.app](https://aitrend-pulse.netlify.app)
- **Repository**: [https://github.com/rajyenekal/ai-trend-pulse](https://github.com/rajyenekal/ai-trend-pulse)

---

## 🏛️ Editorial Architecture & 4-Tier Source Registry

AI Trend Pulse organizes 25 monitored feeds into four transparent verification tiers codified in [`sources.json`](sources.json), distinguishing primary research releases from independent journalism, builder communities, and preprint analysis:

| Tier | Tier Name | Monitored Sources & Research Desks | Primary Role | Weight |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Primary AI Labs & Frontier Developers** | OpenAI Research & News, Anthropic Official News, Google DeepMind Blog, Google AI Blog, Microsoft AI Blog, Meta AI Research, xAI, Mistral AI | Primary model weights, architecture specs, safety evaluations, and official API releases | `1.00` |
| **Tier 2** | **Independent Technology Journalism** | MIT Technology Review, The Verge AI, TechCrunch AI, Ars Technica, The Decoder | Independent evaluation, investigative reporting, antitrust scrutiny, and societal impact | `0.95` |
| **Tier 3** | **Open Research & Cloud Infrastructure** | Hugging Face Blog, NVIDIA Developer Blog, AWS Machine Learning Blog, Amazon Science, LMSYS Org, Hugging Face Daily Papers | Open weights, inference optimization, enterprise clusters, and hardware benchmarks | `0.90` |
| **Tier 4** | **Community, Academic & Practitioner Analysis** | arXiv (cs.AI, cs.LG, cs.CL), Simon Willison Weblog, Berkeley AI Research (BAIR), Import AI (Jack Clark), Latent Space | Preprints, empirical engineering evaluations, MCP standards, and frontier capability tracking | `0.85` |

### Verification Status Definitions
- **`official_claim`**: Direct announcement from a primary research lab or frontier developer.
- **`source_linked`**: Independently verified report grounded with direct URL provenance to a reputable journalism or engineering outlet.
- **`independently_confirmed`**: Cross-corroborated development confirmed across two or more independent sources via Jaccard clustering.
- **`cached_fallback`**: Live ingestion preserved healthy previous dataset when upstream networks fail, maintaining valid timestamps.
- **`raw_headlines`**: Non-LLM deterministic fallback displaying verified headlines directly from source feeds with zero fabricated content.

---

## 🔬 Grounding in Industry Research

The product and curation mechanics of AI Trend Pulse are aligned with empirical research across AI engineering and information trust:

1. **Stack Overflow 2026 Developer Survey**: Highlights that over 75% of engineers integrate AI tooling into daily workflows, requiring dedicated signals for coding agents, SDK APIs, and open-weights models. AI Trend Pulse delivers this via the **Developer Radar** section.
2. **Pew Research Center (2026 AI Public Awareness Study)**: Reveals growing public demand for transparent provenance and distinct separation between corporate PR and independent evaluation. Addressed via our **4-Tier verification badges** and clear source attribution.
3. **Reuters Institute Digital News Report (2026)**: Notes a migration toward concise, evidence-grounded syntheses over unstructured headline feeds. Addressed via **"Why It Matters"** impact callouts, **Key Takeaways**, and canonical source links.
4. **Epoch AI (Empirical Compute & Frontier Capability Studies)**: Demonstrates the velocity of benchmark and compute transitions. Addressed via our **Algorithmic Pulse Ranking Formula** and **Research, Safety & Policy** coverage.

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
   - Validates 8-type intent taxonomy and multipliers.
   - Verifies case study 0.60x multiplier and 64.0 score cap.
   - Verifies hybrid clustering with anchor entity tokens.
   - Verifies conditional HTTP 304 caching and ETag handling.
   - Verifies URL normalization, parameter removal, and RFC-2822 timestamp parsing.
   - Validates payload structure and atomic write guarantees.
2. **`node test_qa.js` (6 phases)**:
   - Validates HTML semantic tags and all required DOM element IDs.
   - Tests full JavaScript runtime execution in a headless sandbox.
   - Verifies rendering of Dispatches, Topic Pills, Developments Feed, Top 5 Bento Grid, AI Tools, Developer Radar, and Research/Safety sections.
   - Tests theme switching, bookmarking/saving, search filtering, topic filtering, Reader View open/close, and Methodology modal open/close.
   - Tests 3-tier image system, signature vector visuals, and IST timestamp formatting.
   - Verifies 11 mobile-first CSS architecture patterns.
   - Verifies article_type taxonomy, Compact Wire view, and Hide Case Studies toggle.
3. **`node test_viewports.js`**:
   - Performs responsive QA across all 10 device viewports from `320px` to `1440px`.
   - Verifies Top 5 Bento Grid responsive rules across mobile, tablet, and desktop.
   - Asserts standard card height reduction >= 25% (measured 34.5% reduction).
   - Verifies URL normalization and tracking parameter removal.
   - Tests publication timestamp parsing without fabrication.
   - Tests suffix-stemmed Jaccard story clustering across syndications.
   - Verifies scoring function determinism.
   - Validates payload structure and atomic write guarantees.
2. **`node test_qa.js`**:
   - Validates HTML semantic tags and all required DOM element IDs.
   - Tests full JavaScript runtime execution in a headless sandbox.
   - Verifies rendering of Dispatches, Topic Pills, Developments Feed, AI Tools, Developer Radar, and Research/Safety sections.
   - Tests theme switching, bookmarking/saving, search filtering, topic filtering, Reader View open/close, and Methodology modal open/close.
   - Tests 3-tier image system and SVG fallbacks.
   - Verifies 12 mobile-first CSS architecture patterns.
3. **`node test_viewports.js`**:
   - Performs responsive QA across all 10 device viewports from `320px` to `1440px`.

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
