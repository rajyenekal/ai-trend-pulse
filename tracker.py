import json
import os
import re
import time
import feedparser
from google import genai
from google.genai import types

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
      print(f"Skipping {source} due to error: {e}")
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

  client = genai.Client(http_options={"timeout": 60000})

  # Retry up to 3 times in case of transient network drop
  for attempt in range(1, 4):
    try:
      print(f"Calling Gemini 3.8 Flash (Attempt {attempt}/3)...")
      response = client.models.generate_content(
          model="gemini-3.8-flash",
          contents=prompt,
      )

      raw_text = response.text.strip()
      json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
      if json_match:
        return json.loads(json_match.group(0))
      return json.loads(raw_text)

    except Exception as e:
      print(f"⚠️ Attempt {attempt} failed: {e}")
      if attempt < 3:
        print("Retrying in 5 seconds...")
        time.sleep(5)
      else:
        print(
            "All 3 attempts failed. Preserving existing data without crashing."
        )
        return None


if __name__ == "__main__":
  articles = collect_news()
  analysis = analyze(articles)

  if analysis and "trends" in analysis:
    output = {"trends": analysis["trends"], "takeaway": analysis["takeaway"]}
    with open("data.json", "w") as f:
      json.dump(output, f, indent=2)
    print("✅ Successfully updated data.json!")
  else:
    print("ℹ️ Keeping existing data.json intact.")
