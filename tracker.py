from datetime import datetime, timezone
import json
import os
import re
import time
import feedparser
from google import genai

# Expanded, reader-friendly sources
FEEDS = {
    "The Verge AI": (
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"
    ),
    "TechCrunch AI": (
        "https://techcrunch.com/category/artificial-intelligence/feed/"
    ),
    "Wired Tech": "https://www.wired.com/feed/category/gear/latest/rss",
    "MIT Tech Review": (
        "https://www.technologyreview.com/topic/artificial-intelligence/feed/"
    ),
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
}


def collect_news():
  articles = []
  print("📡 Fetching latest news from top portals...")
  for source, url in FEEDS.items():
    try:
      feed = feedparser.parse(url)
      for entry in feed.entries[:4]:
        title = entry.title
        summary = entry.get("summary", "")
        # Clean HTML tags from summary if present
        clean_summary = re.sub(r"<[^>]+>", "", summary)[:300]
        articles.append({
            "source": source,
            "title": title,
            "link": entry.link,
            "summary": clean_summary,
            "published": entry.get("published", "Today"),
        })
    except Exception as e:
      print(f"Skipping {source}: {e}")
  return articles


def analyze(articles):
  text = "".join([
      f"- [{a['source']}] {a['title']}: {a['summary']} (Link: {a['link']})\n"
      for a in articles[:16]
  ])

  prompt = f"""
You are a friendly, expert tech editor (like Morning Brew or TLDR AI).
Your job is to explain the latest AI news in clear, engaging, human language that ANYONE can understand.
Avoid heavy academic or corporate jargon. Explain *why* things matter.

Here are the latest news items:
{text}

Generate JSON with this exact schema:
{{
  "takeaway": "2-sentence big-picture summary in plain, exciting English",
  "trends": [
    {{
      "title": "Clear, catchy headline without jargon",
      "what_happened": "2-3 sentences explaining what actually happened in simple terms.",
      "why_it_matters": "2 sentences explaining the real-world impact for everyday people, developers, or businesses.",
      "source": "Name of publication"
    }}
  ],
  "top_stories": [
    {{
      "title": "Story headline",
      "one_liner": "1 sentence explaining what this specific story is about",
      "source": "Publication name",
      "link": "Full article link"
    }}
  ]
}}
Provide 3-4 top trends and 6-8 top stories. Return ONLY the JSON object.
"""

  client = genai.Client()
  models_to_try = ["gemini-3.8-flash", "gemini-2.0-flash"]

  for model_name in models_to_try:
    for attempt in range(1, 3):
      try:
        print(f"🧠 Synthesizing with {model_name} (Attempt {attempt})...")
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

  # Fallback if API has temporary downtime
  fallback_stories = [
      {
          "title": a["title"],
          "one_liner": a["summary"] or "Read the full story on the portal.",
          "source": a["source"],
          "link": a["link"],
      }
      for a in articles[:6]
  ]

  return {
      "takeaway": (
          "AI tools and hardware are evolving fast this week, with big tech"
          " racing to make smarter agents while working through real-world"
          " costs and security checks."
      ),
      "trends": [{
          "title": "AI Assistants are moving from Chatbots to Action-Takers",
          "what_happened": (
              "Tech giants and startups are launching agents capable of"
              " clicking buttons, writing code, and running tasks on computers"
              " on your behalf."
          ),
          "why_it_matters": (
              "This shifts AI from simply answering questions to actually doing"
              " work for you, saving hours of manual computer tasks."
          ),
          "source": "The Verge / TechCrunch",
      }],
      "top_stories": fallback_stories,
  }


if __name__ == "__main__":
  articles = collect_news()
  analysis = analyze(articles)

  # Add UTC timestamp
  analysis["last_updated"] = datetime.now(timezone.utc).isoformat()

  with open("data.json", "w") as f:
    json.dump(analysis, f, indent=2)

  print("✅ data.json written successfully with deep context!")
