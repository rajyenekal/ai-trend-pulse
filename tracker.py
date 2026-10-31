import json
import os
import re
import time
import feedparser
from google import genai

FEEDS = {
    "TechCrunch AI": (
        "https://techcrunch.com/category/artificial-intelligence/feed/"
    ),
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
}


def collect_news():
  articles = []
  print("Fetching news feeds...")
  for source, url in FEEDS.items():
    try:
      feed = feedparser.parse(url)
      for entry in feed.entries[:3]:
        articles.append({
            "source": source,
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", "")[:250],
            "published": entry.get("published", "Today"),
        })
    except Exception as e:
      print(f"Skipping {source}: {e}")
  return articles


def analyze(articles):
  text = "".join([
      f"- [{a['source']}] {a['title']}: {a['summary']}\n" for a in articles
  ])
  prompt = f"""
You are an expert AI industry analyst. Based on these fresh stories:
{text}

Output ONLY valid JSON with this exact schema:
{{
  "trends": [
    {{"title": "Trend name", "explanation": "2-sentence breakdown", "source": "Source name"}}
  ],
  "takeaway": "1-sentence high-level summary"
}}
"""

  client = genai.Client()

  # Try primary model, then fallback model if server is busy
  models_to_try = ["gemini-3.8-flash", "gemini-2.0-flash"]

  for model_name in models_to_try:
    for attempt in range(1, 3):
      try:
        print(f"Calling {model_name} (Attempt {attempt})...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        raw_text = response.text.strip()
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
          return json.loads(json_match.group(0))
        return json.loads(raw_text)
      except Exception as e:
        print(f"⚠️ {model_name} attempt {attempt} failed: {e}")
        time.sleep(3)

  # Graceful fallback: If Google API is completely unavailable, build report from raw headlines
  print("⚡ Building graceful fallback from top news headlines...")
  fallback_trends = []
  for a in articles[:3]:
    fallback_trends.append({
        "title": a["title"],
        "explanation": (
            a["summary"] or "Recent development tracked across top AI portals."
        ),
        "source": a["source"],
    })

  return {
      "trends": fallback_trends,
      "takeaway": (
          "Autonomous agents, specialized models, and enterprise AI tools"
          " continue rapid development."
      ),
  }


if __name__ == "__main__":
  articles = collect_news()
  analysis = analyze(articles)

  with open("data.json", "w") as f:
    json.dump(analysis, f, indent=2)

  print("✅ data.json written successfully!")
