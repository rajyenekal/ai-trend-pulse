import json
import os
import re
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
    feed = feedparser.parse(url)
    for entry in feed.entries[:3]:
      articles.append({
          "source": source,
          "title": entry.title,
          "link": entry.link,
          "summary": entry.get("summary", "")[:250],
          "published": entry.get("published", "Today"),
      })
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
  print("Calling Gemini 3.8 Flash...")
  client = genai.Client()
  response = client.models.generate_content(
      model="gemini-3.8-flash",
      contents=prompt,
  )

  # Extract JSON even if wrapped in markdown formatting
  raw_text = response.text.strip()
  json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
  if json_match:
    return json.loads(json_match.group(0))
  return json.loads(raw_text)


if __name__ == "__main__":
  articles = collect_news()
  analysis = analyze(articles)

  output = {"trends": analysis["trends"], "takeaway": analysis["takeaway"]}

  with open("data.json", "w") as f:
    json.dump(output, f, indent=2)

  print("Updated data.json successfully!")
