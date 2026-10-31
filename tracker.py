import json
import os
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
You are an expert AI analyst. Based on these fresh stories:
{text}

Output JSON with this exact schema:
{{
  "trends": [
    {{"title": "Trend name", "explanation": "2-sentence breakdown", "source": "Source name"}}
  ],
  "takeaway": "1-sentence high-level summary"
}}
Return ONLY raw JSON, without markdown formatting or backticks.
"""
  client = genai.Client()
  response = client.models.generate_content(
      model="gemini-2.5-flash", contents=prompt
  )
  clean_json = response.text.strip().replace("```json", "").replace("```", "")
  return json.loads(clean_json)


if __name__ == "__main__":
  articles = collect_news()
  analysis = analyze(articles)

  output = {"trends": analysis["trends"], "takeaway": analysis["takeaway"]}

  with open("data.json", "w") as f:
    json.dump(output, f, indent=2)

  print("Updated data.json successfully!")
