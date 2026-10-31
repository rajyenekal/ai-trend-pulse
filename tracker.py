from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
import time
try:
  import feedparser
except ImportError:
  feedparser = None

try:
  from google import genai
  from google.genai import types
except ImportError:
  genai = None
  types = None

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
  clean = raw_url.split("?")[0].split("#")[0].rstrip("/")
  return clean


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

    # Extract article image if present in media tags or enclosure
    img_url = ""
    media_content = (
        entry.get("media_content", [])
        if isinstance(entry, dict)
        else getattr(entry, "media_content", [])
    )
    if isinstance(media_content, list) and media_content and isinstance(media_content[0], dict) and media_content[0].get("url"):
      img_url = media_content[0]["url"]
    if not img_url:
      media_thumb = (
          entry.get("media_thumbnail", [])
          if isinstance(entry, dict)
          else getattr(entry, "media_thumbnail", [])
      )
      if isinstance(media_thumb, list) and media_thumb and isinstance(media_thumb[0], dict) and media_thumb[0].get("url"):
        img_url = media_thumb[0]["url"]
    if not img_url:
      enclosures = (
          entry.get("enclosures", [])
          if isinstance(entry, dict)
          else getattr(entry, "enclosures", [])
      )
      if isinstance(enclosures, list) and enclosures and isinstance(enclosures[0], dict) and enclosures[0].get("href"):
        img_url = enclosures[0]["href"]
    if not img_url:
      m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', summary)
      if m:
        img_url = m.group(1)

    seen_urls.add(clean_url)
    articles.append({
        "source": source_name,
        "tier": tier,
        "title": title.strip(),
        "link": clean_url,
        "summary": clean_summary,
        "image": img_url,
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

  # Required root keys
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

    # Normalize tier and status
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

    # Ensure evidence_urls is a list
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
            data["trends"] = validate_evidence_provenance(data["trends"], articles)
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

  # If no prior file exists, display raw verified headlines directly
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


def classify_topic(title, summary=""):
  """Classifies an AI news story into one of the supported editorial categories."""
  content = f"{title} {summary}".lower()
  if any(k in content for k in ["agent", "autonomous", "runtime", "supervision", "tool use", "breakout", "workflow"]):
    return "AI Agents"
  if any(k in content for k in ["model", "gemini", "gpt", "claude", "llama", "multimodal", "frontier model", "carbon", "o1", "o3", "release", "benchmark"]):
    return "Model Releases"
  if any(k in content for k in ["safety", "alignment", "misalignment", "safeguard", "risk", "disarmament", "evaluations", "framework", "governance"]):
    return "Research & Safety"
  if any(k in content for k in ["enterprise", "business", "commercial", "partner", "adoption", "apple", "china", "finance", "legal", "servicenow", "credit saison"]):
    return "AI Business"
  if any(k in content for k in ["code", "coding", "developer", "programming", "copilot", "software", "ide"]):
    return "AI Coding"
  return "AI Tools & Ecosystem"


def detect_company(text, source=""):
  """Identifies the primary AI organization or research laboratory."""
  t = f"{text} {source}".lower()
  if "openai" in t:
    return "openai"
  if "deepmind" in t or "google" in t:
    return "google"
  if "anthropic" in t or "claude" in t:
    return "anthropic"
  if "apple" in t:
    return "apple"
  if "meta" in t or "llama" in t:
    return "meta"
  if "microsoft" in t:
    return "microsoft"
  if "hugging face" in t or "huggingface" in t:
    return "huggingface"
  if "mit" in t:
    return "mit"
  if "verge" in t:
    return "verge"
  if "techcrunch" in t:
    return "techcrunch"
  return "default"


def estimate_reading_time(text):
  """Calculates estimated reading time in minutes."""
  words = len((text or "").split())
  minutes = max(1, round(words / 160))
  return f"{minutes} min read"


def extract_audience_pills(who_affected_str):
  """Extracts clean, scannable audience badge tags."""
  if not who_affected_str:
    return ["Enterprises", "Developers", "AI Teams"]
  cleaned = who_affected_str.replace(" and ", ", ").replace(" & ", ", ")
  parts = [p.strip().title() for p in cleaned.split(",") if p.strip() and len(p.strip()) < 35]
  return parts[:4] if parts else ["Enterprises", "Developers"]


def enrich_payload(payload, articles=None):
  """Enriches trends and stories with topic, company, reading time, audience tags, and images."""
  url_to_image = {}
  if articles:
    for a in articles:
      if a.get("link") and a.get("image"):
        url_to_image[a["link"]] = a["image"]

  for t in payload.get("trends", []):
    if "topic" not in t:
      t["topic"] = classify_topic(t.get("title", ""), t.get("what_happened", ""))
    if "company" not in t:
      t["company"] = detect_company(t.get("title", ""), t.get("source", ""))
    if "reading_time" not in t:
      full_text = f"{t.get('what_happened', '')} {t.get('why_it_matters', '')}"
      t["reading_time"] = estimate_reading_time(full_text)
    if "audience_pills" not in t:
      t["audience_pills"] = extract_audience_pills(t.get("who_affected", ""))
    if "image" not in t or not t.get("image"):
      # Check if any evidence url has an article image
      for u in t.get("evidence_urls", []):
        if u in url_to_image:
          t["image"] = url_to_image[u]
          break

  for s in payload.get("top_stories", []):
    if "topic" not in s:
      s["topic"] = classify_topic(s.get("title", ""), s.get("one_liner", ""))
    if "company" not in s:
      s["company"] = detect_company(s.get("title", ""), s.get("source", ""))
    if "reading_time" not in s:
      s["reading_time"] = estimate_reading_time(s.get("one_liner", ""))
    if ("image" not in s or not s.get("image")) and s.get("link") in url_to_image:
      s["image"] = url_to_image[s["link"]]

  # Generate curated 4 items for The Pulse strip
  pulse_items = []
  for t in payload.get("trends", []):
    pulse_items.append({
        "title": t.get("title"),
        "topic": t.get("topic", "AI Intelligence"),
        "company": t.get("company", "default"),
        "published": "Recent",
        "link": t.get("evidence_urls", ["#"])[0] if t.get("evidence_urls") else "#",
        "image": t.get("image", "")
    })
  for s in payload.get("top_stories", []):
    if len(pulse_items) >= 4:
      break
    pulse_items.append({
        "title": s.get("title"),
        "topic": s.get("topic", "AI Developments"),
        "company": s.get("company", "default"),
        "published": s.get("published", "Recent"),
        "link": s.get("link", "#"),
        "image": s.get("image", "")
    })
  payload["pulse_items"] = pulse_items[:4]
  return payload


def run_pipeline(dry_run=False, max_age_hours=72):
  """Full execution pipeline."""
  articles = collect_fresh_news(max_age_hours=max_age_hours)
  now_iso = datetime.now(timezone.utc).isoformat()

  payload = analyze_with_gemini(articles)
  payload["last_attempt_at"] = now_iso

  # Timestamp bug fix:
  # NEVER overwrite generated_at if we are reusing cached data!
  if payload.get("data_status") != "cached_fallback" or not payload.get(
      "generated_at"
  ):
    payload["generated_at"] = now_iso

  # Enrich with topics, companies, reading times, images, and Pulse strip
  payload = enrich_payload(payload, articles=articles)

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
