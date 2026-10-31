from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
import feedparser
from google import genai
from google.genai import types

# 3-Tier Source Architecture
SOURCES = {
    # Tier 1: Primary Lab Announcements
    "OpenAI News": {
        "url": "https://openai.com/news/rss.xml",
        "tier": "Official Lab",
    },
    "Google DeepMind": {
        "url": "https://deepmind.google/blog/rss.xml",
        "tier": "Official Lab",
    },
    # Tier 2: Independent Journalism & Fact-Checking
    "MIT Tech Review": {
        "url": (
            "https://www.technologyreview.com/topic/artificial-intelligence/feed/"
        ),
        "tier": "Independent Journalism",
    },
    "The Verge AI": {
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "tier": "Independent Journalism",
    },
    "TechCrunch AI": {
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "tier": "Independent Journalism",
    },
    "Ars Technica": {
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "tier": "Independent Journalism",
    },
    # Tier 3: Open Ecosystem & Research
    "Hugging Face": {
        "url": "https://huggingface.co/blog/feed.xml",
        "tier": "Open Research",
    },
}


def collect_fresh_news(max_age_hours=72):
  """Collects articles, filters to last 72 hours, and deduplicates canonical URLs."""
  articles = []
  seen_urls = set()
  now = datetime.now(timezone.utc)
  cutoff_time = now - timedelta(hours=max_age_hours)

  for name, meta in SOURCES.items():
    try:
      feed = feedparser.parse(meta["url"])
      for entry in feed.entries:
        raw_url = getattr(entry, "link", "")
        clean_url = raw_url.split("?")[0].rstrip("/")
        if not clean_url or clean_url in seen_urls:
          continue

        pub_parsed = getattr(
            entry, "published_parsed", None
        ) or getattr(entry, "updated_parsed", None)
        pub_dt = None
        if pub_parsed:
          try:
            pub_dt = datetime.fromtimestamp(
                time.mktime(pub_parsed), tz=timezone.utc
            )
          except Exception:
            pass

        if pub_dt and pub_dt < cutoff_time:
          continue

        summary = getattr(entry, "summary", "") or ""
        clean_summary = re.sub(r"<[^>]+>", "", summary)[:280].strip()

        seen_urls.add(clean_url)
        articles.append({
            "source": name,
            "tier": meta["tier"],
            "title": entry.title.strip(),
            "link": clean_url,
            "summary": clean_summary,
            "published": (
                pub_dt.strftime("%b %d, %H:%M UTC") if pub_dt else "Recent"
            ),
        })
    except Exception as e:
      print(f"⚠️ Error reading {name}: {e}")

  return articles


def clean_and_validate_payload(data):
  """Validates schema and sanitizes URLs to ensure stability."""
  if not isinstance(data, dict):
    return False
  if not data.get("takeaway") or not isinstance(data.get("trends"), list):
    return False
  if len(data["trends"]) == 0:
    return False

  for t in data["trends"]:
    if not all(k in t for k in ("title", "what_happened", "why_it_matters")):
      return False

    # Sanitize evidence URLs (keep only valid http/https)
    raw_evidence = t.get("evidence_urls", [])
    if isinstance(raw_evidence, list):
      t["evidence_urls"] = [
          u
          for u in raw_evidence
          if isinstance(u, str)
          and (u.startswith("http://") or u.startswith("https://"))
      ]
    else:
      t["evidence_urls"] = []

  for s in data.get("top_stories", []):
    if not all(k in s for k in ("title", "one_liner", "source")):
      return False
    link = s.get("link", "")
    if not (link.startswith("http://") or link.startswith("https://")):
      s["link"] = "#"

  return True


def analyze_with_gemini(articles):
  articles_text = ""
  for idx, a in enumerate(articles[:16], 1):
    articles_text += (
        f"{idx}. [{a['tier']}] [{a['source']}] {a['title']}\n   Summary:"
        f" {a['summary']}\n   URL: {a['link']}\n\n"
    )

  prompt = f"""
You are an expert news analyst and fact-checker. 
Synthesize these fresh AI news stories into an executive briefing:

{articles_text}

Editorial Rules:
1. Anti-Hype: Never claim AI 'replaces humans' or 'achieves consciousness'.
2. Evidence Provenance: In every trend, you MUST include the exact source URL(s) from the input above in 'evidence_urls'.
3. Transparency: If a trend is based on an official company announcement, label status as 'official_claim'. If verified by journalists, label as 'source_linked'.

Return JSON with this schema:
{{
  "takeaway": "2-sentence big-picture summary in plain English",
  "trends": [
    {{
      "title": "Clear headline in plain English",
      "what_happened": "2 sentences explaining what happened.",
      "why_it_matters": "2 sentences explaining practical impact.",
      "who_affected": "Who is impacted (e.g. Developers, Businesses, Consumers)",
      "source": "Primary source name",
      "status": "official_claim / source_linked",
      "evidence_urls": ["Exact source URLs from the input"]
    }}
  ],
  "top_stories": [
    {{
      "title": "Headline",
      "one_liner": "1 sentence summary",
      "source": "Publication name",
      "tier": "Official Lab / Independent Journalism / Open Research",
      "published": "Publication time",
      "link": "Exact article URL"
    }}
  ]
}}
"""

  client = genai.Client()
  models = ["gemini-3.8-flash", "gemini-2.0-flash"]

  for model in models:
    for attempt in range(1, 3):
      try:
        print(f"🧠 Synthesizing with {model} (Attempt {attempt})...")
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        data = json.loads(response.text.strip())
        if clean_and_validate_payload(data):
          data["schema_version"] = 1
          data["data_status"] = "fresh"
          return data
      except Exception as e:
        print(f"⚠️ {model} attempt {attempt} failed: {e}")
        time.sleep(3)

  # Honest Fallback: Never invent fake replacement trends
  if os.path.exists("data.json"):
    try:
      with open("data.json", "r") as f:
        prev = json.load(f)
      if clean_and_validate_payload(prev):
        prev["data_status"] = "cached_fallback"
        return prev
    except Exception:
      pass

  return {
      "schema_version": 1,
      "data_status": "raw_headlines",
      "takeaway": (
          "Live AI synthesis is refreshing. Displaying verified news stories"
          " directly from primary sources."
      ),
      "trends": [],
      "top_stories": [
          {
              "title": a["title"],
              "one_liner": a["summary"],
              "source": a["source"],
              "tier": a["tier"],
              "published": a["published"],
              "link": a["link"],
          }
          for a in articles[:8]
      ],
  }


if __name__ == "__main__":
  articles = collect_fresh_news(max_age_hours=72)
  print(f"📡 Collected {len(articles)} fresh, deduplicated articles.")

  payload = analyze_with_gemini(articles)
  payload["generated_at"] = datetime.now(timezone.utc).isoformat()

  with open("data.json", "w") as f:
    json.dump(payload, f, indent=2)

  print(
      f"✅ data.json published successfully (Status: {payload['data_status']})!"
  )
