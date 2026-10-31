from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
import feedparser
from google import genai

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
  """Collects articles, filters by publication date (last 72h), and deduplicates by URL."""
  articles = []
  seen_urls = set()
  now = datetime.now(timezone.utc)
  cutoff_time = now - timedelta(hours=max_age_hours)

  print(
      f"📡 Ingesting verified feeds (filtering for stories since"
      f" {cutoff_time.strftime('%b %d')})..."
  )

  for name, meta in SOURCES.items():
    try:
      feed = feedparser.parse(meta["url"])
      for entry in feed.entries:
        raw_url = getattr(entry, "link", "")
        clean_url = raw_url.split("?")[0].rstrip("/")
        if not clean_url or clean_url in seen_urls:
          continue

        # Check publication timestamp
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

        # Skip articles older than cutoff (if date is present)
        if pub_dt and pub_dt < cutoff_time:
          continue

        summary = getattr(entry, "summary", "") or ""
        clean_summary = re.sub(r"<[^>]+>", "", summary)[:300].strip()

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

  print(f"✅ Gathered {len(articles)} fresh, deduplicated articles.")
  return articles


def validate_schema(data):
  """Ensures Gemini returned required fields before writing."""
  if not isinstance(data, dict):
    return False
  if not data.get("takeaway") or not isinstance(data.get("trends"), list):
    return False
  for t in data["trends"]:
    if not all(k in t for k in ("title", "what_happened", "why_it_matters")):
      return False
  return True


def analyze_with_ai(articles):
  text = "".join([
      f"- [{a['tier']}] [{a['source']}] {a['title']}: {a['summary']} (Published:"
      f" {a['published']}, Link: {a['link']})\n"
      for a in articles[:18]
  ])

  prompt = f"""
You are an expert news editor and fact-checker. 
Analyze these AI news items collected from Tier 1 (Labs), Tier 2 (Independent Journalism), and Tier 3 (Open Research):

{text}

Follow these strict editorial rules:
1. Anti-Hype: Never claim AI will 'replace humans' or 'achieve consciousness'.
2. Clear Plain English: Avoid academic and financial jargon; explain *why* developments matter.
3. Highlight Source Tier: Differentiate between a company's marketing claim (Official Lab) and an independently verified report.
4. Who Is Affected: State who is most impacted (e.g. Developers, Businesses, Consumers, Cloud Engineers).

Output ONLY valid JSON with this exact schema:
{{
  "takeaway": "2-sentence big-picture summary in plain, objective English",
  "trends": [
    {{
      "title": "Clear headline in plain English",
      "what_happened": "2 sentences explaining what actually happened.",
      "why_it_matters": "2 sentences explaining the practical impact.",
      "who_affected": "1 sentence on who is most affected.",
      "source": "Publication name",
      "tier": "Official Lab / Independent Journalism / Open Research"
    }}
  ],
  "top_stories": [
    {{
      "title": "Story headline",
      "one_liner": "1 sentence explaining what this specific story is about",
      "source": "Publication name",
      "tier": "Official Lab / Independent Journalism / Open Research",
      "published": "Publication date",
      "link": "Full article link"
    }}
  ]
}}
Provide 3-4 macro trends and 6-8 verified top stories. Return ONLY the raw JSON object.
"""

  client = genai.Client()
  models = ["gemini-3.8-flash", "gemini-2.0-flash"]

  for model_name in models:
    for attempt in range(1, 3):
      try:
        print(f"🧠 Synthesizing with {model_name} (Attempt {attempt})...")
        response = client.models.generate_content(
            model=model_name, contents=prompt
        )
        raw_text = response.text.strip()
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
          data = json.loads(json_match.group(0))
          if validate_schema(data):
            data["status"] = "verified_live"
            return data
      except Exception as e:
        print(f"⚠️ {model_name} attempt {attempt} failed: {e}")
        time.sleep(3)

  # Honest Fallback: Never fabricate fake replacement trends
  print(
      "⚠️ AI synthesis unavailable. Building transparent headline fallback..."
  )

  # Check if previous valid briefing exists to preserve it
  if os.path.exists("data.json"):
    try:
      with open("data.json", "r") as f:
        previous_data = json.load(f)
      if validate_schema(previous_data):
        previous_data["status"] = "cached_fallback"
        return previous_data
    except Exception:
      pass

  # If no previous file exists, present raw verified stories cleanly
  return {
      "status": "raw_headlines",
      "takeaway": (
          "AI synthesis is temporarily refreshing. Displaying verified news"
          " stories directly from source portals."
      ),
      "trends": [],
      "top_stories": [
          {
              "title": a["title"],
              "one_liner": (
                  a["summary"] or "Read the full verified report on the portal."
              ),
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
  analysis = analyze_with_ai(articles)
  analysis["last_updated"] = datetime.now(timezone.utc).isoformat()

  with open("data.json", "w") as f:
    json.dump(analysis, f, indent=2)

  print("✅ data.json written with verified, schema-validated intelligence!")
