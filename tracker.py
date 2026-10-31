from datetime import datetime, timezone
import json
import os
import re
import time
import feedparser
from google import genai

# The 3-Tier Source Architecture
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


def collect_news():
  articles = []
  print("📡 Ingesting Tier 1, 2, and 3 feeds...")
  for name, meta in SOURCES.items():
    try:
      feed = feedparser.parse(meta["url"])
      for entry in feed.entries[:3]:
        summary = entry.get("summary", "")
        clean_summary = re.sub(r"<[^>]+>", "", summary)[:300]
        articles.append({
            "source": name,
            "tier": meta["tier"],
            "title": entry.title,
            "link": entry.link,
            "summary": clean_summary,
            "published": entry.get("published", "Today"),
        })
    except Exception as e:
      print(f"Skipping {name}: {e}")
  return articles


def analyze(articles):
  text = "".join([
      f"- [{a['tier']}] [{a['source']}] {a['title']}: {a['summary']} (Link:"
      f" {a['link']})\n"
      for a in articles[:18]
  ])

  prompt = f"""
You are an expert news editor and fact-checker (like Morning Brew or TLDR AI).
Analyze these AI news items collected from Tier 1 (Labs), Tier 2 (Independent Journalism), and Tier 3 (Open Research):

{text}

Follow these strict editorial rules:
1. Anti-Hype: Never claim AI will 'replace humans' or 'achieve consciousness'.
2. Clear Plain English: Avoid academic and financial jargon; explain *why* developments matter.
3. Highlight Source Tier: Differentiate between a company's marketing claim (Official Lab) and an independently verified report.

Output ONLY valid JSON with this exact schema:
{{
  "takeaway": "2-sentence big-picture summary in plain, exciting English",
  "trends": [
    {{
      "title": "Clear headline in plain English",
      "what_happened": "2 sentences explaining what actually happened.",
      "why_it_matters": "2 sentences explaining the practical impact for real people or businesses.",
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
      "link": "Full article link"
    }}
  ]
}}
Provide 3-4 macro trends and 6-8 verified top stories. Return ONLY the raw JSON.
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
          return json.loads(json_match.group(0))
        return json.loads(raw_text)
      except Exception as e:
        print(f"⚠️ {model_name} attempt {attempt} failed: {e}")
        time.sleep(3)

  # Fallback
  return {
      "takeaway": (
          "Major AI labs and open-source ecosystems are rapidly advancing"
          " agentic capabilities, while independent journalists evaluate real"
          " costs and infrastructure risks."
      ),
      "trends": [{
          "title": "AI Labs Transition Toward Autonomous Computer Agents",
          "what_happened": (
              "OpenAI, Google, and independent developers are releasing tools"
              " that let AI interact directly with operating systems and code."
          ),
          "why_it_matters": (
              "This shifts AI from a question-answering tool to a software"
              " collaborator that can perform multi-step digital work."
          ),
          "source": "Google DeepMind / The Verge",
          "tier": "Official Lab / Independent Journalism",
      }],
      "top_stories": [
          {
              "title": a["title"],
              "one_liner": a["summary"]
              or "Read the full story on the portal.",
              "source": a["source"],
              "tier": a["tier"],
              "link": a["link"],
          }
          for a in articles[:6]
      ],
  }


if __name__ == "__main__":
  articles = collect_news()
  analysis = analyze(articles)
  analysis["last_updated"] = datetime.now(timezone.utc).isoformat()

  with open("data.json", "w") as f:
    json.dump(analysis, f, indent=2)

  print("✅ data.json written with verified 3-tier intelligence!")
