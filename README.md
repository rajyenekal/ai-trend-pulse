# ⚡ AI Trend Pulse

> **Autonomous, hourly AI market intelligence with traceable evidence provenance, 3-tier source verification, and a mobile-first editorial reading experience.**

- GitHub Pages: **[https://rajyenekal.github.io/ai-trend-pulse/](https://rajyenekal.github.io/ai-trend-pulse/)**
- Live Mirror: **[https://aitrend-pulse.netlify.app](https://aitrend-pulse.netlify.app)**

---

## 🏛️ Editorial Architecture (3-Tier Verification)

AI Trend Pulse separates company announcements from independent journalism and open ecosystem benchmarks:

| Tier | Sources | Purpose | Status Label |
| :--- | :--- | :--- | :--- |
| **Tier 1: Official Labs** | OpenAI News, Google DeepMind | Primary model launches, API changes, and direct lab announcements. | `🏢 Official Lab Announcement` (`official_claim`) |
| **Tier 2: Independent Journalism** | MIT Technology Review, The Verge AI, TechCrunch AI, Ars Technica | Independent evaluation, hype fact-checking, and societal/business impact. | `🔍 Source-Linked Report` (`source_linked`) |
| **Tier 3: Open Ecosystem** | Hugging Face | Open-weights models, developer benchmarks, and community research. | `🔬 Open Ecosystem` (`source_linked`) |

### Verification Status Definitions
- **`official_claim`**: Official announcement from a primary research laboratory or company.
- **`source_linked`**: Independently reported story verified against a reputable tech journalism publication with direct URL provenance.
- **`independently_confirmed`**: Corroborated across multiple independent reporting outlets.
- **`cached_fallback`**: Live AI synthesis temporarily unavailable; previous verified briefing preserved with its original timestamp.
- **`raw_headlines`**: Fallback mode displaying verified headlines directly from source feeds with zero fabricated trends.

---

## 📱 Mobile-First UI/UX & Editorial System

1. **Mobile-First Responsiveness**:
   - Zero horizontal overflow across all device viewports: `320px`, `360px`, `375px`, `390px`, `414px`, `430px`, `768px`, `1024px`, `1280px`, `1440px`.
   - Fluid typography using CSS `clamp()`.
   - Accessible touch targets (minimum 44px) for all interactive controls.
   - Mobile bottom sheet for Saved Stories and full-sheet search palette with iOS safe-area support (`env(safe-area-inset-bottom)`).

2. **5-Tier Story Card Design System**:
   - **Card Type 1 (Featured Story)**: Full-width lead development with 16:9 thumbnail, headline, summary, Why It Matters callout, and action toolbar.
   - **Card Type 2 (Standard News Card)**: 16:10 thumbnail, topic badge, concise explanation, and quick save/copy actions.
   - **Card Type 3 (Compact News Item)**: High-density item for secondary developments to reduce mobile scroll fatigue.
   - **Card Type 4 (Breaking / Official Lab Release)**: Distinctive accent border, official badge, and direct lab links.
   - **Card Type 5 (Related Story Group)**: Multi-source corroboration with expandable source provenance links.

3. **3-Tier Reliable Image System**:
   - Priority 1: Actual article image extracted from RSS feeds where available.
   - Priority 2: Curated high-resolution editorial imagery mapped by topic category.
   - Priority 3: Instant inline SVG vector artwork with topic-matched gradients and zero layout shift on network error.

4. **Features & Controls**:
   - **Why It Matters**: Concise explanation of the real-world operational and business impact.
   - **The Pulse**: Touch-momentum swipeable horizontal highlights bar on mobile, 4-column grid on desktop.
   - **Trending in AI**: Horizontal topic discovery chips with live story counts.
   - **Saved Stories**: Private browser storage with bookmarking and removal.
   - **Search Experience**: Command palette (`⌘K` or `/`) with live multi-field filtering.
   - **Theme Selector**: System (Auto) / Light / Dark modes persisted with zero flicker.
   - **Audio Briefing**: Web Speech API text-to-speech synthesis ("Listen (2m)").

---

## 🧪 Testing & Quality Assurance

Run the automated QA test suite:

```bash
npm test
```

This verifies:
1. HTML semantics and required element IDs.
2. Full JavaScript execution in a sandbox environment.
3. Bookmarking, search filtering, and theme switching.
4. 3-tier image system and SVG fallbacks.
5. Mobile-first CSS rules and all 10 target viewports.
