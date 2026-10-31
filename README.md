# ⚡ AI Trend Pulse

> **Autonomous, hourly AI market intelligence with traceable evidence provenance and 3-tier source verification.**

Live Dashboard: **[https://aitrend-pulse.netlify.app](https://aitrend-pulse.netlify.app)**

---

## 🏛️ Editorial Architecture (3-Tier Verification)

AI Trend Pulse does not treat all news equally. It separates company PR claims from independent journalism and open ecosystem benchmarks:

| Tier | Sources | Purpose | Status Label |
| :--- | :--- | :--- | :--- |
| **Tier 1: Official Labs** | OpenAI News, Google DeepMind | Primary model launches, API changes, and direct lab announcements. | `🏢 Official Lab Announcement` (`official_claim`) |
| **Tier 2: Independent Journalism** | MIT Technology Review, The Verge AI, TechCrunch AI, Ars Technica | Independent evaluation, hype fact-checking, and societal/business impact. | `🔍 Source-Linked Report` (`source_linked`) |
| **Tier 3: Open Ecosystem** | Hugging Face | Open-weights models, developer benchmarks, and community research. | `🔬 Open Ecosystem` (`source_linked`) |

### Verification Status Definitions
- **`official_claim`**: The statement is an official announcement from a lab or company (e.g. model specs, commercial launch).
- **`source_linked`**: An independently reported story verified against a reputable tech journalism publication with a direct link to the original article.
- **`independently_confirmed`**: Corroborated across multiple independent reporting outlets.
- **`cached_fallback`**: Live AI synthesis was temporarily busy; the previous verified briefing is safely preserved with its original timestamp.
- **`raw_headlines`**: Fallback mode displaying verified headlines directly from source feeds with zero fabricated trends.

---

## ⚙️ How It Works (Hourly Cloud Pipeline)
