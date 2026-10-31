# ⚡ AI Trend Pulse

> **Autonomous, hourly AI market intelligence with evidence provenance and 3-tier credibility verification.**

Live Dashboard: **[https://aitrend-pulse.netlify.app](https://aitrend-pulse.netlify.app)**

---

## 🏛️ Editorial Architecture (3-Tier Verification)

AI Trend Pulse does not treat all news equally. It separates company PR claims from independent journalism:

| Tier | Sources | Purpose |
| :--- | :--- | :--- |
| **Tier 1: Official Labs** | OpenAI News, Google DeepMind | Primary model launches, API changes, and direct lab announcements. |
| **Tier 2: Independent Journalism** | MIT Technology Review, The Verge AI, TechCrunch AI, Ars Technica | Independent evaluation, hype fact-checking, and societal/business impact. |
| **Tier 3: Open Ecosystem** | Hugging Face | Open-weights models, developer benchmarks, and community research. |

---

## ⚙️ How It Works (Hourly Cloud Pipeline)

1. **Ingest & Deduplicate:** Every hour, GitHub Actions fetches the 7 verified RSS feeds, discards stories older than 72 hours, and deduplicates by canonical URL.
2. **AI Synthesis (Grounded):** Google Gemini 3.8 Flash extracts the top macro trends using native structured JSON (`response_mime_type="application/json"`).
3. **Evidence Provenance:** Every trend attaches explicit `evidence_urls` linking back to the original articles that prove the claim.
4. **Zero-Fabrication Fallback:** If the AI API experiences temporary downtime, the pipeline preserves the previous verified briefing or displays raw verified headlines.
5. **Auto-Deploy:** Netlify Edge CDN automatically rebuilds and serves the static dashboard in under 5 seconds.

---

## 📜 Data Contract (`data.json`)

```json
{
  "schema_version": 1,
  "generated_at": "2026-10-31T07:30:00Z",
  "data_status": "fresh | cached_fallback | raw_headlines",
  "takeaway": "Executive 2-sentence summary in plain English.",
  "trends": [
    {
      "title": "Clear headline",
      "what_happened": "2 sentences explaining the event.",
      "why_it_matters": "2 sentences explaining the practical impact.",
      "who_affected": "Impacted group (e.g. Developers, Businesses)",
      "source": "Primary publication name",
      "status": "official_claim | source_linked",
      "evidence_urls": ["https://..."]
    }
  ],
  "top_stories": [
    {
      "title": "Headline",
      "one_liner": "1-sentence summary",
      "source": "Publisher",
      "tier": "Official Lab / Independent Journalism / Open Research",
      "published": "Oct 31, 12:45 UTC",
      "link": "https://..."
    }
  ]
}
```

---

## 🚀 Local Setup

```bash
git clone https://github.com/rajyenekal/ai-trend-pulse.git
cd ai-trend-pulse

pip install feedparser google-genai
export GEMINI_API_KEY="your-api-key"

python tracker.py
```

Open `index.html` in your browser to view the local briefing.

---

## 🔒 Security & Privacy
- **Zero HTML Injection:** All client rendering uses safe DOM APIs (`textContent`, `createElement`).
- **Auditability:** Every story links directly to the original publisher with `rel="noopener noreferrer"`.
- **Zero Server Costs:** 100% serverless, static, and hosted on Netlify Edge CDN.
