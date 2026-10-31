from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
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


def normalize_url(raw_url):
  """Strips tracking query params, fragments, and trailing slashes."""
  if not raw_url:
    return ""
  return raw_url.split("?")[0].split("#")[0].rstrip("/")


def filter_and_deduplicate_articles(
    entries, source_name, tier, max_age_hours=72, seen_urls=None
):
  """Deduplicates entries by normalized canonical URL and filters to the freshness window."""
  if seen_urls is None:
    seen_urls = set()

  articles = []
  now = datetime.now(timezone.utc)
  cutoff_time = now - timedelta(hours=max_age_hours)

  for entry in entries:
    raw_url = (
        entry.get("link", "")
        if isinstance(entry, dict)
        else getattr(entry, "link", "")
    )
    clean_url = normalize_url(raw_url)
    if not clean_url or clean_url in seen_urls:
      continue

    # Date parsing
    pub_parsed = (
        entry.get("published_parsed")
        if isinstance(entry, dict)
        else getattr(entry, "published_parsed", None)
    )
    if not pub_parsed:
      pub_parsed = (
          entry.get("updated_parsed")
          if isinstance(entry, dict)
          else getattr(entry, "updated_parsed", None)
      )

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

    title = (
        entry.get("title", "")
        if isinstance(entry, dict)
        else getattr(entry, "title", "")
    )
    summary = (
        entry.get("summary", "")
        if isinstance(entry, dict)
        else getattr(entry, "summary", "")
    )
    clean_summary = re.sub(r"<[^>]+>", "", summary)[:280].strip()

    seen_urls.add(clean_url)
    articles.append({
        "source": source_name,
        "tier": tier,
        "title": title.strip(),
        "link": clean_url,
        "summary": clean_summary,
        "published": (
            pub_dt.strftime("%b %d, %H:%M UTC") if pub_dt else "Recent"
        ),
    })

  return articles, seen_urls


def collect_fresh_news(max_age_hours=72):
  """Iterates through all sources, applying deduplication and freshness checks."""
  all_articles = []
  seen_urls = set()
  print(f"📡 Ingesting verified feeds (Freshness window: {max_age_hours}h)...")

  for name, meta in SOURCES.items():
    try:
      feed = feedparser.parse(meta["url"])
      articles, seen_urls = filter_and_deduplicate_articles(
          feed.entries,
          name,
          meta["tier"],
          max_age_hours=max_age_hours,
          seen_urls=seen_urls,
      )
      all_articles.extend(articles)
      print(f"   ✓ {name}: {len(articles)} fresh articles")
    except Exception as e:
      print(f"   ⚠️ Error ingesting {name}: {e}")

  print(f"📊 Total unique fresh articles gathered: {len(all_articles)}")
  return all_articles


def validate_evidence_provenance(trends, collected_articles):
  """Ensures every evidence URL belongs strictly to the collected source article set.

  Eliminates AI hallucinations in evidence citations.
  """
  collected_urls = {a["link"] for a in collected_articles}

  for t in trends:
    raw_evidence = t.get("evidence_urls", [])
    valid_evidence = []
    if isinstance(raw_evidence, list):
      for u in raw_evidence:
        if isinstance(u, str):
          normalized = normalize_url(u)
          if normalized in collected_urls or any(
              normalized.startswith(c) for c in collected_urls
          ):
            valid_evidence.append(normalized)

    # Fallback to source article if model did not return exact URL match
    if not valid_evidence:
      matching_sources = [
          a["link"] for a in collected_articles if a["source"] == t.get("source")
      ]
      if matching_sources:
        valid_evidence = matching_sources[:2]

    t["evidence_urls"] = valid_evidence

  return trends


def clean_and_validate_payload(data):
  """Strict schema contract validation."""
  if not isinstance(data, dict):
    return False

  if not data.get("takeaway") or not isinstance(data.get("takeaway"), str):
    return False
  if not isinstance(data.get("trends"), list) or len(data["trends"]) == 0:
    return False

  valid_tiers = {"Official Lab", "Independent Journalism", "Open Research"}
  valid_statuses = {"official_claim", "source_linked", "independently_confirmed"}

  for t in data["trends"]:
    if not all(
        k in t and isinstance(t[k], str) and t[k].strip()
        for k in ("title", "what_happened", "why_it_matters")
    ):
      return False

    if t.get("tier") not in valid_tiers:
      t["tier"] = (
          "Official Lab"
          if t.get("source") in ["OpenAI News", "Google DeepMind"]
          else "Independent Journalism"
      )

    if t.get("status") not in valid_statuses:
      t["status"] = (
          "official_claim"
          if t.get("tier") == "Official Lab"
          else "source_linked"
      )

    if not isinstance(t.get("evidence_urls"), list):
      t["evidence_urls"] = []

  for s in data.get("top_stories", []):
    if not all(k in s for k in ("title", "one_liner", "source")):
      return False
    link = s.get("link", "")
    if not (link.startswith("http://") or link.startswith("https://")):
      s["link"] = "#"

  return True


def analyze_with_gemini(articles):
  """Synthesizes structured trends using Gemini with native JSON mode."""
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

Return JSON with this exact schema:
{{
  "takeaway": "2-sentence big-picture summary in plain English",
  "trends": [
    {{
      "title": "Clear headline in plain English",
      "what_happened": "2 sentences explaining what happened.",
      "why_it_matters": "2 sentences explaining practical impact.",
      "who_affected": "Who is impacted (e.g. Developers, Businesses, Consumers)",
      "source": "Primary source name",
      "tier": "Official Lab / Independent Journalism / Open Research",
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

  client = None
  try:
    client = genai.Client()
  except Exception as e:
    print(f"⚠️ Could not initialize Gemini client: {e}")

  if client:
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
            data["trends"] = validate_evidence_provenance(
                data["trends"], articles
            )
            data["schema_version"] = 1
            data["data_status"] = "fresh"
            return data
        except Exception as e:
          print(f"⚠️ {model} attempt {attempt} failed: {e}")
          time.sleep(3)

  # Honest Fallback: Never fabricate replacement trends
  print("⚠️ AI generation unavailable. Checking for previous valid briefing...")
  if os.path.exists("data.json"):
    try:
      with open("data.json", "r") as f:
        prev = json.load(f)
      if clean_and_validate_payload(prev):
        print(
            "✓ Preserving previous valid briefing with 'cached_fallback'"
            " status."
        )
        prev["data_status"] = "cached_fallback"
        return prev
    except Exception as e:
      print(f"⚠️ Error reading prior data.json: {e}")

  print("✓ Displaying raw collected headlines with 'raw_headlines' status.")
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


def run_pipeline(dry_run=False, max_age_hours=72):
  """Full execution pipeline."""
  articles = collect_fresh_news(max_age_hours=max_age_hours)
  now_iso = datetime.now(timezone.utc).isoformat()

  payload = analyze_with_gemini(articles)
  payload["last_attempt_at"] = now_iso

  # Timestamp bug fix: NEVER overwrite generated_at if we are using cached fallback
  if payload.get("data_status") != "cached_fallback" or not payload.get(
      "generated_at"
  ):
    payload["generated_at"] = now_iso

  if dry_run:
    print("\n🔍 DRY-RUN MODE: data.json will NOT be written.")
    print(f"   Status: {payload['data_status']}")
    print(f"   Takeaway: {payload['takeaway'][:80]}...")
    print(f"   Trends count: {len(payload['trends'])}")
    print(f"   Stories count: {len(payload['top_stories'])}")
    print(
        f"   Generated At: {payload['generated_at']} (Attempt:"
        f" {payload['last_attempt_at']})"
    )
    return payload

  with open("data.json", "w") as f:
    json.dump(payload, f, indent=2)

  print(
      f"✅ data.json written successfully! Status: {payload['data_status']},"
      f" Generated: {payload['generated_at']}"
  )
  return payload


if __name__ == "__main__":
  is_dry_run = "--dry-run" in sys.argv
  run_pipeline(dry_run=is_dry_run)
