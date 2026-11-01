"""
AI Trend Pulse — Autonomous Backend Tracker & Intelligence Pipeline
Ingests from centralized source registry (sources.json), validates feeds,
extracts rich article text, performs story clustering & multi-source deduplication,
computes deterministic scores using configurable weights, and produces evidence-grounded intelligence.
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

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

# -------------------------------------------------------------
# 1. CONFIGURATION & SCORING WEIGHTS
# -------------------------------------------------------------
SCORING_WEIGHTS = {
    "importance": 0.30,
    "audience_relevance": 0.25,
    "freshness": 0.20,
    "coverage_corroboration": 0.15,
    "source_confidence": 0.10,
}

CONFIDENCE_TIER_SCORES = {
    1: 100,  # Tier 1: Primary Official Lab / Regulator
    2: 85,   # Tier 2: Reputable Tech Journalism
    3: 80,   # Tier 3: Open Ecosystem & Research Repositories
    4: 65,   # Tier 4: Community & Discovery Signals
}

TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "ref", "fbclid", "gclid", "mc_cid", "mc_eid", "source"
}

SOURCES_REGISTRY_FILE = "sources.json"


# -------------------------------------------------------------
# 2. SOURCE REGISTRY & SCHEMA VALIDATION
# -------------------------------------------------------------
FALLBACK_SOURCE_REGISTRY = [
    {
        "source_id": "openai_news",
        "name": "OpenAI News",
        "canonical_listing_url": "https://openai.com/news",
        "feed_url": "https://openai.com/news/rss.xml",
        "source_type": "official",
        "topic_tags": ["models", "apis", "company"],
        "trust_tier": 1,
        "confidence_score": 100,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "anthropic_news",
        "name": "Anthropic Official News",
        "canonical_listing_url": "https://www.anthropic.com/news",
        "feed_url": "https://www.anthropic.com/news",
        "source_type": "official",
        "topic_tags": ["models", "research", "safety", "agents"],
        "trust_tier": 1,
        "confidence_score": 100,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "html_page_adapter",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "anthropic_hn_discovery",
        "name": "Anthropic Community Discovery (HNRSS)",
        "canonical_listing_url": "https://news.ycombinator.com",
        "feed_url": "https://hnrss.org/newest?q=anthropic.com",
        "source_type": "unofficial_discovery",
        "topic_tags": ["community", "discovery", "mentions"],
        "trust_tier": 4,
        "confidence_score": 60,
        "is_official": False,
        "feed_is_official": False,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "deepmind_blog",
        "name": "Google DeepMind",
        "canonical_listing_url": "https://deepmind.google/blog/",
        "feed_url": "https://deepmind.google/blog/rss.xml",
        "source_type": "official",
        "topic_tags": ["research", "models", "science"],
        "trust_tier": 1,
        "confidence_score": 100,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "google_ai_blog",
        "name": "Google AI Blog",
        "canonical_listing_url": "https://blog.google/technology/ai/",
        "feed_url": "https://blog.google/technology/ai/rss/",
        "source_type": "official",
        "topic_tags": ["tools", "models", "products"],
        "trust_tier": 1,
        "confidence_score": 95,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "microsoft_ai_news",
        "name": "Microsoft AI News",
        "canonical_listing_url": "https://news.microsoft.com/source/topics/ai/",
        "feed_url": "https://news.microsoft.com/source/topics/ai/feed/",
        "source_type": "official",
        "topic_tags": ["enterprise", "copilot", "infrastructure"],
        "trust_tier": 1,
        "confidence_score": 95,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "nvidia_blog",
        "name": "NVIDIA Blog",
        "canonical_listing_url": "https://blogs.nvidia.com/blog/category/ai/",
        "feed_url": "https://blogs.nvidia.com/feed/",
        "source_type": "official",
        "topic_tags": ["infrastructure", "hardware", "models"],
        "trust_tier": 1,
        "confidence_score": 95,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "aws_ml_blog",
        "name": "AWS Machine Learning",
        "canonical_listing_url": "https://aws.amazon.com/blogs/machine-learning/",
        "feed_url": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "source_type": "official",
        "topic_tags": ["infrastructure", "cloud", "developers"],
        "trust_tier": 1,
        "confidence_score": 90,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "amazon_science",
        "name": "Amazon Science",
        "canonical_listing_url": "https://www.amazon.science/",
        "feed_url": "https://www.amazon.science/index.rss",
        "source_type": "official",
        "topic_tags": ["research", "models", "robotics"],
        "trust_tier": 1,
        "confidence_score": 90,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "huggingface_blog",
        "name": "Hugging Face Blog",
        "canonical_listing_url": "https://huggingface.co/blog",
        "feed_url": "https://huggingface.co/blog/feed.xml",
        "source_type": "research",
        "topic_tags": ["open-source", "models", "tools", "developers"],
        "trust_tier": 3,
        "confidence_score": 90,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "github_blog_ai",
        "name": "GitHub Blog AI",
        "canonical_listing_url": "https://github.blog/category/ai-and-ml/",
        "feed_url": "https://github.blog/category/ai-and-ml/feed/",
        "source_type": "official",
        "topic_tags": ["coding", "developers", "tools"],
        "trust_tier": 1,
        "confidence_score": 90,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "mistral_news",
        "name": "Mistral AI News",
        "canonical_listing_url": "https://mistral.ai/news/",
        "feed_url": "https://mistral.ai/news/rss",
        "source_type": "official",
        "topic_tags": ["models", "open-source", "apis"],
        "trust_tier": 1,
        "confidence_score": 95,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "mit_tech_review",
        "name": "MIT Technology Review",
        "canonical_listing_url": "https://www.technologyreview.com/topic/artificial-intelligence/",
        "feed_url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
        "source_type": "publication",
        "topic_tags": ["policy", "research", "safety", "society"],
        "trust_tier": 2,
        "confidence_score": 85,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "the_verge_ai",
        "name": "The Verge AI",
        "canonical_listing_url": "https://www.theverge.com/ai-artificial-intelligence",
        "feed_url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "source_type": "publication",
        "topic_tags": ["products", "industry", "policy", "tools"],
        "trust_tier": 2,
        "confidence_score": 85,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "techcrunch_ai",
        "name": "TechCrunch AI",
        "canonical_listing_url": "https://techcrunch.com/category/artificial-intelligence/",
        "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "source_type": "publication",
        "topic_tags": ["startups", "business", "funding", "tools"],
        "trust_tier": 2,
        "confidence_score": 85,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "ars_technica",
        "name": "Ars Technica",
        "canonical_listing_url": "https://arstechnica.com/ai/",
        "feed_url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "source_type": "publication",
        "topic_tags": ["security", "policy", "infrastructure", "hardware"],
        "trust_tier": 2,
        "confidence_score": 85,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "the_decoder",
        "name": "The Decoder",
        "canonical_listing_url": "https://the-decoder.com/",
        "feed_url": "https://the-decoder.com/feed/",
        "source_type": "publication",
        "topic_tags": ["models", "research", "industry"],
        "trust_tier": 2,
        "confidence_score": 80,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "arxiv_cs_ai",
        "name": "arXiv cs.AI",
        "canonical_listing_url": "https://arxiv.org/list/cs.AI/recent",
        "feed_url": "https://rss.arxiv.org/rss/cs.AI",
        "source_type": "research",
        "topic_tags": ["research", "preprints", "theory"],
        "trust_tier": 3,
        "confidence_score": 80,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 120,
    },
    {
        "source_id": "arxiv_cs_lg",
        "name": "arXiv cs.LG",
        "canonical_listing_url": "https://arxiv.org/list/cs.LG/recent",
        "feed_url": "https://rss.arxiv.org/rss/cs.LG",
        "source_type": "research",
        "topic_tags": ["research", "machine-learning", "preprints"],
        "trust_tier": 3,
        "confidence_score": 80,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 120,
    },
    {
        "source_id": "bair_blog",
        "name": "BAIR Blog",
        "canonical_listing_url": "https://bair.berkeley.edu/blog/",
        "feed_url": "https://bair.berkeley.edu/blog/feed.xml",
        "source_type": "research",
        "topic_tags": ["research", "robotics", "agents"],
        "trust_tier": 3,
        "confidence_score": 85,
        "is_official": True,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 120,
    },
    {
        "source_id": "simon_willison",
        "name": "Simon Willison Weblog",
        "canonical_listing_url": "https://simonwillison.net/",
        "feed_url": "https://simonwillison.net/atom/everything/",
        "source_type": "community",
        "topic_tags": ["tools", "prompt-injection", "developers", "coding"],
        "trust_tier": 4,
        "confidence_score": 75,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "atom",
        "enabled": True,
        "poll_interval_minutes": 60,
    },
    {
        "source_id": "import_ai",
        "name": "Import AI",
        "canonical_listing_url": "https://importai.substack.com/",
        "feed_url": "https://importai.substack.com/feed",
        "source_type": "community",
        "topic_tags": ["policy", "safety", "research"],
        "trust_tier": 4,
        "confidence_score": 75,
        "is_official": False,
        "feed_is_official": True,
        "fetch_method": "rss",
        "enabled": True,
        "poll_interval_minutes": 120,
    },
]


def validate_source_record(source):
  """Strict schema validation for source registry records."""
  if not isinstance(source, dict):
    return False, "Source record must be a dict"

  required_fields = ["source_id", "name", "canonical_listing_url", "source_type", "trust_tier", "confidence_score"]
  for f in required_fields:
    if f not in source or source[f] is None:
      return False, f"Missing required field: {f}"

  if not isinstance(source["source_id"], str) or not source["source_id"].strip():
    return False, "source_id must be non-empty string"

  if not isinstance(source["name"], str) or not source["name"].strip():
    return False, "name must be non-empty string"

  if source["trust_tier"] not in (1, 2, 3, 4):
    return False, f"trust_tier must be 1, 2, 3, or 4; got {source['trust_tier']}"

  if not (0 <= source["confidence_score"] <= 100):
    return False, f"confidence_score must be between 0 and 100; got {source['confidence_score']}"

  valid_types = {"official", "publication", "research", "community", "unofficial_discovery"}
  if source["source_type"] not in valid_types:
    return False, f"source_type must be one of {valid_types}; got {source['source_type']}"

  canon_url = source.get("canonical_listing_url", "")
  if not (canon_url.startswith("http://") or canon_url.startswith("https://")):
    return False, f"canonical_listing_url must start with http:// or https://: {canon_url}"

  feed_url = source.get("feed_url", "")
  if feed_url and not (feed_url.startswith("http://") or feed_url.startswith("https://")):
    return False, f"feed_url must start with http:// or https://: {feed_url}"

  # Unofficial discovery vs Official consistency
  if source["source_type"] == "unofficial_discovery":
    if source.get("is_official") is True:
      return False, "unofficial_discovery source cannot be marked is_official=True"
    if source.get("feed_is_official") is True:
      return False, "unofficial_discovery source cannot be marked feed_is_official=True"

  # Official Anthropic verification
  if source["source_id"] == "anthropic_news":
    if source.get("fetch_method") != "html_page_adapter":
      return False, "anthropic_news must use html_page_adapter fetch_method"
    if not source.get("is_official"):
      return False, "anthropic_news must be is_official=True"

  return True, "Valid"


def load_source_registry(filepath=SOURCES_REGISTRY_FILE):
  """Loads and validates the centralized source registry, falling back to verified sources if missing."""
  candidates = []
  if os.path.exists(filepath):
    try:
      with open(filepath, "r", encoding="utf-8") as f:
        registry = json.load(f)
      if isinstance(registry, list) and len(registry) > 0:
        candidates = registry
    except Exception as e:
      print(f"⚠️ Error reading {filepath}: {e}")

  if not candidates:
    candidates = FALLBACK_SOURCE_REGISTRY

  valid_sources = []
  for s in candidates:
    is_valid, reason = validate_source_record(s)
    if is_valid:
      if s.get("enabled", True):
        valid_sources.append(s)
    else:
      print(f"⚠️ Skipping invalid source record {s.get('source_id')}: {reason}")

  return valid_sources


# -------------------------------------------------------------
# 3. URL SANITIZATION & CANONICALIZATION
# -------------------------------------------------------------
def normalize_url(raw_url):
  """Strips tracking query params, fragments, and trailing slashes while keeping functional parameters."""
  if not raw_url or not isinstance(raw_url, str):
    return ""
  raw_url = raw_url.strip()
  if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
    return ""

  try:
    parsed = urllib.parse.urlparse(raw_url)
    # Parse query parameters selectively
    q_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    clean_pairs = [(k, v) for k, v in q_pairs if k.lower() not in TRACKING_QUERY_PARAMS]
    clean_query = urllib.parse.urlencode(clean_pairs)

    clean_path = parsed.path.rstrip("/")
    if not clean_path and not parsed.netloc:
      return ""

    reconstructed = urllib.parse.urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        clean_path,
        parsed.params,
        clean_query,
        "",  # Strip fragment
    ))
    return reconstructed
  except Exception:
    return raw_url.split("?")[0].split("#")[0].rstrip("/")


# -------------------------------------------------------------
# 4. ROBUST TIMESTAMP PARSING (NO FAKE DATES)
# -------------------------------------------------------------
def parse_published_datetime(date_str, struct_time=None):
  """Parses publication date to a timezone-aware UTC datetime.
  Returns None if missing or unparseable. Never fabricates 'now'.
  """
  if struct_time:
    try:
      return datetime.fromtimestamp(time.mktime(struct_time), tz=timezone.utc)
    except Exception:
      pass

  if not date_str or not isinstance(date_str, str):
    return None

  date_str = date_str.strip()
  if not date_str:
    return None

  # Try RFC-2822 / RFC-822 email format (common in RSS)
  try:
    dt = parsedate_to_datetime(date_str)
    if dt:
      if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
      return dt.astimezone(timezone.utc)
  except Exception:
    pass

  # Try ISO-8601 and common date string formats
  iso_formats = [
      "%Y-%m-%dT%H:%M:%S%z",
      "%Y-%m-%dT%H:%M:%SZ",
      "%Y-%m-%d %H:%M:%S%z",
      "%Y-%m-%d %H:%M:%S",
      "%Y-%m-%d",
      "%b %d, %Y",
      "%B %d, %Y",
      "%b %d %Y",
      "%B %d %Y",
      "%d %b %Y",
      "%d %B %Y",
      "%Y/%m/%d",
      "%m/%d/%Y",
  ]
  cleaned_str = date_str.replace("Z", "+0000")
  for fmt in iso_formats:
    try:
      dt = datetime.strptime(cleaned_str, fmt)
      if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
      return dt.astimezone(timezone.utc)
    except Exception:
      continue

  return None


# -------------------------------------------------------------
# 5. DUAL FEED PARSER (FEEDPARSER + STD LIB XML FALLBACK)
# -------------------------------------------------------------
def parse_feed_with_fallback(feed_url, timeout=6.0):
  """Parses RSS/Atom feeds using feedparser if present, or xml.etree.ElementTree as fallback."""
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
      ),
      "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
  }

  raw_bytes = b""
  try:
    req = urllib.request.Request(feed_url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
      raw_bytes = resp.read()
      if resp.headers.get("Content-Encoding") == "gzip" or raw_bytes.startswith(b"\x1f\x8b"):
        try:
          raw_bytes = gzip.decompress(raw_bytes)
        except Exception:
          pass
  except Exception as e:
    # If feedparser is available, give it a direct shot in case it handles redirects differently
    if feedparser:
      try:
        parsed = feedparser.parse(feed_url)
        if parsed and getattr(parsed, "entries", None):
          return parsed.entries
      except Exception:
        pass
    raise e

  if feedparser:
    parsed = feedparser.parse(raw_bytes)
    if parsed and getattr(parsed, "entries", None):
      return parsed.entries

  # Built-in Standard Library XML ElementTree Parser Fallback
  entries = []
  try:
    root = ET.fromstring(raw_bytes)
    # Check for RSS 2.0 (<rss><channel><item>)
    channel = root.find("channel")
    if channel is not None:
      for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = item.findtext("pubDate") or item.findtext("date") or ""
        entries.append({
            "title": title,
            "link": link,
            "summary": desc,
            "published": pub_date,
        })
      return entries

    # Check for Atom (<feed><entry>)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    atom_entries = root.findall("atom:entry", ns) or root.findall("entry")
    for entry in atom_entries:
      title_el = entry.find("atom:title", ns) if ns else entry.find("title")
      title = (title_el.text if title_el is not None else "") or ""
      link = ""
      link_els = entry.findall("atom:link", ns) if ns else entry.findall("link")
      for l in link_els:
        href = l.attrib.get("href")
        rel = l.attrib.get("rel", "alternate")
        if href and rel in ("alternate", ""):
          link = href
          break
      summary_el = entry.find("atom:summary", ns) or entry.find("atom:content", ns)
      summary = (summary_el.text if summary_el is not None else "") or ""
      published_el = entry.find("atom:published", ns) or entry.find("atom:updated", ns)
      pub_date = (published_el.text if published_el is not None else "") or ""
      entries.append({
          "title": title.strip(),
          "link": link.strip(),
          "summary": summary.strip(),
          "published": pub_date.strip(),
      })
    return entries
  except Exception as err:
    print(f"   ⚠️ XML fallback parse failed for {feed_url}: {err}")
    return []


# -------------------------------------------------------------
# 6. ANTHROPIC & HTML PAGE ADAPTERS
# -------------------------------------------------------------
def fetch_anthropic_official_news(timeout=6.0):
  """Specialized page adapter for Anthropic News (https://www.anthropic.com/news).
  Extracts canonical article URLs, titles, published dates, and teasers directly from the official page.
  """
  articles = []
  url = "https://www.anthropic.com/news"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
      ),
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  }

  try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
      html_content = resp.read().decode("utf-8", errors="replace")

    seen_links = set()
    link_matches = re.finditer(r'href=["\'](/(?:news|research)/[a-zA-Z0-9\-]+)["\']', html_content)

    for lm in link_matches:
      href = lm.group(1)
      if href in ("/news", "/news/announcements", "/news/features", "/news/security", "/news/policy", "/news/partnerships", "/news/safeguards", "/research/team"):
        continue
      if href in seen_links:
        continue

      start = max(0, lm.start() - 400)
      end = min(len(html_content), lm.end() + 1500)
      window = html_content[start:end]

      # Extract title
      title = None
      h3_m = re.search(r'<h3\b[^>]*>(.*?)</h3>', window)
      if h3_m:
        title = html.unescape(re.sub(r'<[^>]+>', ' ', h3_m.group(1))).strip()
      if not title:
        img_m = re.search(r'<img\b[^>]*alt=["\']([^"\']+)["\']', window)
        if img_m:
          title = html.unescape(img_m.group(1)).strip()

      if not title or len(title) < 8 or title.lower() in ("announcements", "news", "research"):
        slug = href.split("/")[-1].replace("-", " ").title()
        title = slug

      # Extract published date from <time> tag
      time_m = re.search(r'<time\b[^>]*>(.*?)</time>', window)
      pub_date_str = time_m.group(1).strip() if time_m else None

      # Extract summary teaser
      summary = ""
      p_m = re.search(r'<p\b[^>]*class=["\'][^"\']*summary[^"\']*["\'][^>]*>(.*?)</p>', window)
      if p_m:
        summary = html.unescape(re.sub(r'<[^>]+>', ' ', p_m.group(1))).strip()
      elif not summary:
        p_any = re.findall(r'<p\b[^>]*>(.*?)</p>', window)
        for p in p_any:
          p_clean = html.unescape(re.sub(r'<[^>]+>', ' ', p)).strip()
          if len(p_clean) > 35 and p_clean != title:
            summary = p_clean
            break

      if not summary:
        summary = f"Official research and engineering announcement from Anthropic on {title}."

      seen_links.add(href)
      canonical_url = f"https://www.anthropic.com{href}"
      articles.append({
          "title": title,
          "link": canonical_url,
          "summary": summary,
          "published": pub_date_str,
      })

    if articles:
      print(f"   ✓ Anthropic News (HTML page adapter): Extracted {len(articles)} official stories with metadata")
  except Exception as e:
    print(f"   ⚠️ Anthropic HTML page adapter error: {e}")

  return articles


# -------------------------------------------------------------
# 7. WEB ARTICLE BODY EXTRACTION
# -------------------------------------------------------------
def fetch_article_web_text(url, timeout=3.5, max_chars=3000):
  """Safely fetches article text from the URL, extracting main body paragraphs."""
  clean_url = normalize_url(url)
  if not clean_url:
    return ""

  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = urllib.request.Request(clean_url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
      ct = resp.headers.get("Content-Type", "")
      if "text/html" not in ct and "xml" not in ct:
        return ""
      raw_bytes = resp.read(120000)
      try:
        html_text = raw_bytes.decode("utf-8", errors="replace")
      except Exception:
        html_text = raw_bytes.decode("latin1", errors="replace")

      # Strip scripts, styles, svg, and nav
      html_text = re.sub(
          r"<(script|style|svg|nav|header|footer|aside)[^>]*>[\s\S]*?</\1>",
          " ",
          html_text,
          flags=re.IGNORECASE,
      )
      paragraphs = re.findall(
          r"<p[^>]*>([\s\S]*?)</p>", html_text, flags=re.IGNORECASE
      )
      cleaned = []
      for p in paragraphs:
        text = re.sub(r"<[^>]+>", " ", p)
        text = html.unescape(text).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) > 45 and not any(
            term in text.lower()
            for term in [
                "cookie",
                "privacy policy",
                "terms of service",
                "all rights reserved",
                "subscribe now",
                "newsletter",
            ]
        ):
          cleaned.append(text)
      if cleaned:
        return "\n\n".join(cleaned)[:max_chars].strip()
  except Exception:
    pass
  return ""


# -------------------------------------------------------------
# 8. TOPIC, COMPANY & AUDIENCE HELPERS
# -------------------------------------------------------------
def classify_topic(title, summary=""):
  """Classifies an AI news story into one of the supported editorial categories."""
  content = f"{title} {summary}".lower()
  if any(k in content for k in ["mcp", "protocol", "coding agent", "code", "copilot", "developer", "ide", "api", "sdk", "cursor", "windsurf"]):
    return "AI Coding"
  if any(k in content for k in ["agent", "autonomous", "supervision", "workflow", "tool use", "runtime"]):
    return "AI Agents"
  if any(k in content for k in ["model", "gemini", "gpt", "claude", "llama", "frontier model", "o1", "o3", "release", "benchmark", "weights"]):
    return "Model Releases"
  if any(k in content for k in ["safety", "alignment", "risk", "governance", "policy", "regulation", "evaluations", "nist", "copyright", "eu ai"]):
    return "Research & Safety"
  if any(k in content for k in ["enterprise", "business", "commercial", "funding", "startup", "revenue", "partner", "acquisition"]):
    return "AI Business"
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
  if "meta" in t or "llama" in t:
    return "meta"
  if "microsoft" in t:
    return "microsoft"
  if "nvidia" in t:
    return "nvidia"
  if "hugging face" in t or "huggingface" in t:
    return "huggingface"
  if "mistral" in t:
    return "mistral"
  if "deepseek" in t:
    return "deepseek"
  if "cohere" in t:
    return "cohere"
  if "amazon" in t or "aws" in t:
    return "amazon"
  if "apple" in t:
    return "apple"
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
    return ["Enterprises", "Developers", "AI Practitioners"]
  cleaned = who_affected_str.replace(" and ", ", ").replace(" & ", ", ")
  parts = [p.strip().title() for p in cleaned.split(",") if p.strip() and len(p.strip()) < 35]
  return parts[:4] if parts else ["Enterprises", "Developers"]


# -------------------------------------------------------------
# 9. SCORING & RANKING ENGINE
# -------------------------------------------------------------
def calculate_story_scores(article, corroboration_count=1):
  """Calculates deterministic 0-100 sub-scores and overall score based on the brief."""
  title = article.get("title", "")
  summary = article.get("summary", "")
  full_content = f"{title} {summary}".lower()
  trust_tier = article.get("trust_tier", 2)
  pub_dt = article.get("published_datetime")

  # 1. Importance (Impact, novelty, scale)
  importance = 60
  if any(w in full_content for w in ["frontier", "breakthrough", "major", "first time", "release", "benchmark"]):
    importance += 15
  if any(w in full_content for w in ["gpt-5", "claude 3.7", "claude 4", "gemini 3", "llama 4", "o3", "new model"]):
    importance += 20
  if any(w in full_content for w in ["safety treaty", "disarmament", "regulation", "law", "executive order", "nist"]):
    importance += 15
  if article.get("is_official"):
    importance += 10

  # Ensure Safety, Security, Policy, Alignment are never suppressed
  is_safety_or_policy = any(w in full_content for w in [
      "safety", "alignment", "policy", "governance", "regulation", "law",
      "executive order", "nist", "eval", "red team", "security", "treaty",
      "pre-deployment", "frontier safety"
  ])
  if is_safety_or_policy:
    importance = max(importance + 15, 75)
  importance = min(100, importance)

  # 2. Audience Relevance (Developer, Practical Tools, Enterprise)
  audience_relevance = 65
  if any(w in full_content for w in ["developer", "coding", "api", "agent", "tool", "workflow", "mcp", "open source"]):
    audience_relevance += 20
  if any(w in full_content for w in ["free", "available now", "how to", "benchmark"]):
    audience_relevance += 15
  audience_relevance = min(100, audience_relevance)

  # 3. Freshness (Exponential decay from published date, neutral 50 if missing)
  if pub_dt:
    now = datetime.now(timezone.utc)
    age_hours = max(0, (now - pub_dt).total_seconds() / 3600.0)
    if age_hours <= 6:
      freshness = 100
    elif age_hours <= 18:
      freshness = 85
    elif age_hours <= 36:
      freshness = 70
    elif age_hours <= 72:
      freshness = 50
    else:
      freshness = 25
  else:
    freshness = 50

  # 4. Coverage & Corroboration Signal (Grounded in verified multi-source coverage; neutral if single-source)
  if corroboration_count >= 4:
    coverage_signal = 95
  elif corroboration_count == 3:
    coverage_signal = 85
  elif corroboration_count == 2:
    coverage_signal = 75
  else:
    # Single-source items receive a neutral baseline (50) so niche technical research is not penalized
    coverage_signal = 50

  # 5. Source Confidence
  source_confidence = CONFIDENCE_TIER_SCORES.get(trust_tier, 80)

  # Weighted Overall Score
  cov_weight = SCORING_WEIGHTS.get("coverage_corroboration", SCORING_WEIGHTS.get("popularity_signal", 0.15))
  overall_score = round(
      SCORING_WEIGHTS["importance"] * importance +
      SCORING_WEIGHTS["audience_relevance"] * audience_relevance +
      SCORING_WEIGHTS["freshness"] * freshness +
      cov_weight * coverage_signal +
      SCORING_WEIGHTS["source_confidence"] * source_confidence,
      1
  )

  confidence_label = "high" if overall_score >= 80 else ("medium" if overall_score >= 60 else "low")

  return {
      "importance_score": importance,
      "relevance_score": audience_relevance,
      "freshness_score": freshness,
      "coverage_score": coverage_signal,
      "popularity_score": coverage_signal,  # Backward compatibility alias
      "confidence_score": source_confidence,
      "overall_score": overall_score,
      "confidence_label": confidence_label,
  }


# -------------------------------------------------------------
# 10. STORY CLUSTERING & MULTI-SOURCE DEDUPLICATION
# -------------------------------------------------------------
def stem_word(w):
  """Lightweight suffix stripping for robust headline clustering without heavy NLP dependencies."""
  return re.sub(r'(izing|ized|ize|ation|ition|ing|ed|ly|es|s|al)$', '', w)


def tokenize_title(title):
  """Extracts meaningful keyword tokens with stemming for similarity matching."""
  clean = re.sub(r"[^a-zA-Z0-9\s]", " ", title.lower())
  words = clean.split()
  stopwords = {
      "the", "a", "an", "in", "on", "at", "for", "to", "and", "of", "with",
      "by", "is", "are", "ai", "how", "what", "why", "its", "from", "into", "via"
  }
  return {stem_word(w) for w in words if w not in stopwords and len(stem_word(w)) > 2}


KNOWN_MODEL_KEYWORDS = {
    "claude": {"claude", "sonnet", "haiku", "opus"},
    "gemini": {"gemini"},
    "gpt": {"gpt", "chatgpt", "o1", "o3"},
    "llama": {"llama"},
    "mistral": {"mistral", "mixtral", "codestral", "pixtral"},
    "deepseek": {"deepseek", "r1", "v3"},
    "grok": {"grok"},
    "copilot": {"copilot"},
}

def detect_model_family(title):
  t = title.lower()
  detected = set()
  for family, kw_set in KNOWN_MODEL_KEYWORDS.items():
    if any(k in t for k in kw_set):
      detected.add(family)
  return detected


def compute_title_similarity(tokens1, tokens2):
  """Jaccard similarity on significant title tokens."""
  if not tokens1 or not tokens2:
    return 0.0
  inter = len(tokens1.intersection(tokens2))
  union = len(tokens1.union(tokens2))
  return inter / union if union > 0 else 0.0


def cluster_and_deduplicate_articles(raw_articles, similarity_threshold=0.40):
  """Clusters articles covering the same underlying announcement across publishers.
  Selects the primary / official source as lead where available.
  """
  clusters = []  # List of lists of articles

  for article in raw_articles:
    tokens = tokenize_title(article["title"])
    article_models = detect_model_family(article["title"])
    matched_cluster = None

    for cluster in clusters:
      lead_article = cluster[0]
      lead_tokens = tokenize_title(lead_article["title"])
      lead_models = detect_model_family(lead_article["title"])

      # Guard against merging different model announcements
      if article_models and lead_models and not (article_models & lead_models):
        continue

      sim = compute_title_similarity(tokens, lead_tokens)
      if sim >= similarity_threshold:
        matched_cluster = cluster
        break

    if matched_cluster is not None:
      matched_cluster.append(article)
    else:
      clusters.append([article])

  clustered_stories = []
  for cluster_idx, group in enumerate(clusters):
    # Sort group so Tier 1 (Official Lab) is preferred as lead
    group.sort(key=lambda a: (0 if a.get("is_official") else 1, a.get("trust_tier", 2)))
    lead = group[0].copy()

    related_sources = []
    seen_related = {lead["source"]}
    for other in group[1:]:
      if other["source"] not in seen_related:
        seen_related.add(other["source"])
        related_sources.append({
            "source_name": other["source"],
            "source_url": other["link"],
        })

    lead["cluster_id"] = f"cluster_{cluster_idx + 1}"
    lead["related_sources"] = related_sources
    lead["covered_by_sources_count"] = 1 + len(related_sources)

    # Calculate scores with grounded corroboration signal
    scores = calculate_story_scores(lead, corroboration_count=lead["covered_by_sources_count"])
    lead.update(scores)
    clustered_stories.append(lead)

  # Sort by overall score descending
  clustered_stories.sort(key=lambda s: s.get("overall_score", 0), reverse=True)
  return clustered_stories


# -------------------------------------------------------------
# 11. INGESTION PIPELINE
# -------------------------------------------------------------
def collect_fresh_news(max_age_hours=72, max_per_source=15):
  """Iterates through all sources in the registry, applying deduplication and freshness checks."""
  registry = load_source_registry()
  all_articles = []
  seen_urls = set()
  now = datetime.now(timezone.utc)
  cutoff_time = now - timedelta(hours=max_age_hours)

  print(f"📡 Ingesting from {len(registry)} verified sources (Freshness window: {max_age_hours}h)...")

  for source in registry:
    source_id = source["source_id"]
    name = source["name"]
    feed_url = source.get("feed_url")
    fetch_method = source.get("fetch_method", "rss")
    trust_tier = source.get("trust_tier", 2)
    is_official = source.get("is_official", False)
    source_max = source.get("max_items", max_per_source)

    entries = []
    # 1. Specialized HTML page adapters
    if fetch_method == "html_page_adapter" and source_id == "anthropic_news":
      entries = fetch_anthropic_official_news()

    # 2. Standard RSS / Atom feeds
    if not entries and feed_url:
      try:
        entries = parse_feed_with_fallback(feed_url, timeout=5.0)
      except Exception as e:
        print(f"   ⚠️ Feed error for {name}: {e}")

    source_articles = []
    for entry in entries:
      if len(source_articles) >= source_max:
        break

      raw_link = entry.get("link", "")
      clean_url = normalize_url(raw_link)
      if not clean_url or clean_url in seen_urls:
        continue

      title = (entry.get("title") or "").strip()
      if not title or len(title) < 5:
        continue

      raw_date = entry.get("published") or entry.get("updated")
      struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
      pub_dt = parse_published_datetime(raw_date, struct_time=struct_time)

      # For unofficial discovery feeds, only keep items with canonical URLs resolving to the target official site
      if source.get("source_type") == "unofficial_discovery":
        parsed_target = urllib.parse.urlparse(clean_url)
        if "anthropic.com" not in parsed_target.netloc.lower():
          continue

      # Discard if older than freshness cutoff (allow up to 14 days for Tier 1 official labs to maintain active ground truth)
      max_age_cutoff = cutoff_time
      if is_official and trust_tier == 1:
        max_age_cutoff = now - timedelta(days=14)
      if pub_dt and pub_dt < max_age_cutoff:
        continue

      summary = entry.get("summary") or entry.get("description") or ""
      clean_summary = re.sub(r"<[^>]+>", "", summary)[:320].strip()
      clean_summary = html.unescape(clean_summary)

      # Extract image if present
      img_url = ""
      if "media_content" in entry and entry["media_content"] and isinstance(entry["media_content"], list):
        first_m = entry["media_content"][0]
        if isinstance(first_m, dict) and first_m.get("url"):
          img_url = first_m["url"]
      if not img_url and "media_thumbnail" in entry and entry["media_thumbnail"] and isinstance(entry["media_thumbnail"], list):
        first_t = entry["media_thumbnail"][0]
        if isinstance(first_t, dict) and first_t.get("url"):
          img_url = first_t["url"]
      if not img_url:
        m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', summary)
        if m:
          img_url = m.group(1)

      pub_str = pub_dt.strftime("%b %d, %H:%M UTC") if pub_dt else "Date unavailable"
      seen_urls.add(clean_url)
      source_articles.append({
          "source": name,
          "source_id": source_id,
          "source_type": source.get("source_type", "publication"),
          "trust_tier": trust_tier,
          "is_official": is_official,
          "title": title,
          "link": clean_url,
          "summary": clean_summary,
          "image": img_url,
          "published_datetime": pub_dt,
          "published_at": pub_dt.isoformat() if pub_dt else None,
          "published": pub_str,
          "last_fetched_at": now.isoformat(),
      })

    print(f"   ✓ {name}: {len(source_articles)} articles collected")
    all_articles.extend(source_articles)

  print(f"📊 Total unique articles gathered across all feeds: {len(all_articles)}")
  return all_articles


# -------------------------------------------------------------
# 12. EVIDENCE PROVENANCE & ANTI-HALLUCINATION
# -------------------------------------------------------------
def validate_evidence_provenance(trends, collected_articles):
  """Ensures every evidence URL belongs strictly to the collected source article set.
  Eliminates AI hallucinations in citations.
  """
  collected_urls = {a["link"] for a in collected_articles}

  for t in trends:
    raw_evidence = t.get("evidence_urls", [])
    valid_evidence = []
    if isinstance(raw_evidence, list):
      for u in raw_evidence:
        if isinstance(u, str):
          normalized = normalize_url(u)
          if normalized in collected_urls or any(normalized.startswith(c) for c in collected_urls):
            valid_evidence.append(normalized)

    # Fallback to source article if model did not return exact URL match
    if not valid_evidence:
      matching_sources = [
          a["link"] for a in collected_articles if a.get("source") == t.get("source")
      ]
      if matching_sources:
        valid_evidence = matching_sources[:2]

    t["evidence_urls"] = valid_evidence
  return trends


# -------------------------------------------------------------
# 13. AI INTELLIGENCE SYNTHESIS (GEMINI WITH STRICT FALLBACK)
# -------------------------------------------------------------
def synthesize_with_gemini(clustered_stories):
  """Synthesizes an executive briefing using Gemini if available, with non-LLM fallback."""
  if not clustered_stories:
    return None

  prompt_articles = ""
  for idx, a in enumerate(clustered_stories[:16], 1):
    pub_str = a.get("published", "Recent")
    prompt_articles += (
        f"{idx}. [{a.get('source')}] {a.get('title')}\n"
        f"   Date: {pub_str} | URL: {a.get('link')}\n"
        f"   Summary: {a.get('summary')[:300]}\n\n"
    )

  prompt = f"""
You are an expert AI news analyst and fact-checker.
Synthesize these verified AI developments into a structured executive briefing:

{prompt_articles}

Editorial Rules:
1. Anti-Hype: Never claim AI 'replaces humans' or 'achieves consciousness'.
2. Evidence Provenance: In every trend, you MUST cite the exact source URL(s) from the input above in 'evidence_urls'.
3. Transparency: If a trend is based on an official company release, label status as 'official_claim'. If verified by tech journalists, label as 'source_linked'.
4. Deep Dive Completeness: Provide clear bulleted 'key_points' and an in-depth multi-paragraph 'detailed_analysis'.

Return JSON with this exact schema:
{{
  "takeaway": "2-sentence big-picture summary in plain English",
  "trends": [
    {{
      "title": "Clear headline in plain English",
      "what_happened": "2 sentences explaining what happened.",
      "why_it_matters": "2 sentences explaining practical impact.",
      "who_affected": "Developers, Enterprises, AI Practitioners, or Consumers",
      "source": "Primary source name",
      "status": "official_claim / source_linked",
      "evidence_urls": ["Exact source URLs from the input"]
    }}
  ]
}}
"""

  client = None
  if genai and os.environ.get("GEMINI_API_KEY"):
    try:
      client = genai.Client()
    except Exception as e:
      print(f"⚠️ Could not initialize Gemini client: {e}")

  if client:
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in models:
      try:
        print(f"🧠 Synthesizing executive briefing with {model}...")
        config = None
        if types:
          try:
            config = types.GenerateContentConfig(response_mime_type="application/json")
          except Exception:
            config = None

        response = client.models.generate_content(model=model, contents=prompt, config=config)
        raw_text = (getattr(response, "text", "") or "").strip()
        if "```" in raw_text:
          m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
          if m:
            raw_text = m.group(1).strip()
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if json_match:
          data = json.loads(json_match.group(0))
          if isinstance(data, dict) and data.get("trends"):
            print(f"✓ AI synthesis completed successfully using {model}")
            return data
      except Exception as e:
        print(f"⚠️ {model} synthesis failed: {e}")

  return None


# -------------------------------------------------------------
# 14. PAYLOAD CONSTRUCTION & EDITORIAL SECTIONS
# -------------------------------------------------------------
def extract_key_points(summary, title, source_name=""):
  """Extracts factual bullet points from the actual summary and title without generic boilerplate."""
  clean_summary = (summary or "").strip()
  sentences = [
      re.sub(r"\s+", " ", sent).strip()
      for sent in re.split(r"(?<=[.!?])\s+", clean_summary)
      if len(sent.strip()) > 20
  ]
  boilerplate_phrases = [
      "reported directly by", "verified against", "refer to the direct publication",
      "relevant to practitioners", "click here", "read more"
  ]
  valid_sentences = [
      s for s in sentences
      if not any(b in s.lower() for b in boilerplate_phrases)
  ]
  points = []
  for s in valid_sentences:
    if s not in points:
      points.append(s)
    if len(points) >= 3:
      break

  if not points:
    points.append(title.strip())
  elif len(points) == 1 and title.strip() not in points:
    points.insert(0, title.strip())

  return points[:3]


def generate_factual_why_it_matters(title, summary, topic):
  """Generates a concise, factual explanation of impact grounded in the topic and content without boilerplate."""
  # Look for causal/impact sentences in summary
  clean_summary = (summary or "").strip()
  sentences = re.split(r"(?<=[.!?])\s+", clean_summary)
  for s in sentences:
    s_clean = s.strip()
    s_lower = s_clean.lower()
    if any(k in s_lower for k in ["enables", "allows", "designed to", "aims to", "improves", "reduces", "provides", "features", "introduces"]):
      if 30 <= len(s_clean) <= 240:
        return s_clean

  # Topic-grounded contextual impact
  topic_impact_map = {
      "AI Coding": "Directly impacts developer workflows, automated test generation, and IDE code intelligence.",
      "AI Agents": "Affects autonomous task execution, runtime tool-calling reliability, and workflow orchestration.",
      "Model Releases": "Establishes new performance baselines for reasoning, latency, and context efficiency.",
      "Research & Safety": "Informs model evaluation protocols, safety alignment standards, and governance policies.",
      "AI Business": "Influences enterprise AI adoption, commercial infrastructure costs, and platform strategy.",
      "AI Tools & Ecosystem": "Expands practical integration options and tooling capabilities across production systems.",
  }
  return topic_impact_map.get(topic, "Expands practical AI tooling options and ecosystem integration across production workflows.")


def generate_detailed_analysis(summary, title):
  """Formats factual analysis from the source text without boilerplate placeholders."""
  clean_summary = (summary or "").strip()
  if clean_summary and clean_summary != title:
    return clean_summary
  return f"{title}."


def build_complete_payload(clustered_stories, ai_briefing=None):
  """Builds the comprehensive schema contract consumed by index.html and test_qa.js.
  Enforces cross-section mutual exclusivity so articles are not duplicated across sections.
  """
  now_iso = datetime.now(timezone.utc).isoformat()

  # 1. Format Top Stories (Dispatches) - capped to top 45 scored stories
  top_stories = []
  for s in clustered_stories[:45]:
    company = detect_company(s.get("title", ""), s.get("source", ""))
    topic = classify_topic(s.get("title", ""), s.get("summary", ""))
    reading_time = estimate_reading_time(s.get("summary", ""))

    tier_label = "Official Lab" if s.get("trust_tier") == 1 else (
        "Open Research" if s.get("trust_tier") == 3 else "Independent Journalism"
    )

    clean_summary = (s.get("summary") or s.get("title") or "").strip()
    key_points = extract_key_points(clean_summary, s.get("title", ""), s.get("source", ""))
    detailed_analysis = generate_detailed_analysis(clean_summary, s.get("title", ""))
    why_it_matters = generate_factual_why_it_matters(s.get("title", ""), clean_summary, topic)

    top_stories.append({
        "id": s.get("cluster_id") or f"story_{len(top_stories) + 1}",
        "title": s.get("title"),
        "one_liner": clean_summary,
        "summary": clean_summary,
        "source": s.get("source"),
        "tier": tier_label,
        "trust_tier": s.get("trust_tier", 2),
        "is_official": s.get("is_official", False),
        "published": s.get("published", "Date unavailable"),
        "published_at": s.get("published_at"),
        "last_fetched_at": s.get("last_fetched_at", now_iso),
        "link": s.get("link"),
        "image": s.get("image", ""),
        "topic": topic,
        "company": company,
        "reading_time": reading_time,
        "key_points": key_points,
        "detailed_analysis": detailed_analysis,
        "why_it_matters": why_it_matters,
        "importance_score": s.get("importance_score", 70),
        "relevance_score": s.get("relevance_score", 70),
        "freshness_score": s.get("freshness_score", 50),
        "coverage_score": s.get("coverage_score", 50),
        "popularity_score": s.get("popularity_score", 50),
        "confidence_score": s.get("confidence_score", 85),
        "overall_score": s.get("overall_score", 70.0),
        "confidence_label": s.get("confidence_label", "medium"),
        "related_sources": s.get("related_sources", []),
        "covered_by_sources_count": s.get("covered_by_sources_count", 1),
    })

  assigned_urls = set()

  # 2. Format Trends (Lead Briefing Stories)
  trends = []
  if ai_briefing and ai_briefing.get("trends"):
    for t in ai_briefing["trends"]:
      topic = classify_topic(t.get("title", ""), t.get("what_happened", ""))
      company = detect_company(t.get("title", ""), t.get("source", ""))
      reading_time = estimate_reading_time(f"{t.get('what_happened', '')} {t.get('why_it_matters', '')}")
      who_affected = t.get("who_affected", "Developers and Enterprise Teams")
      ev_urls = t.get("evidence_urls", [])

      for u in ev_urls:
        assigned_urls.add(u)

      kp = [t.get("what_happened"), t.get("why_it_matters")]
      clean_kp = [p for p in kp if p and len(p.strip()) > 10]

      trends.append({
          "title": t.get("title"),
          "what_happened": t.get("what_happened"),
          "why_it_matters": t.get("why_it_matters"),
          "who_affected": who_affected,
          "source": t.get("source", "Primary Lab"),
          "tier": "Official Lab" if "openai" in company or "deepmind" in company or "anthropic" in company else "Independent Journalism",
          "status": t.get("status", "source_linked"),
          "evidence_urls": ev_urls,
          "topic": topic,
          "company": company,
          "reading_time": reading_time,
          "audience_pills": extract_audience_pills(who_affected),
          "key_points": clean_kp if clean_kp else [t.get("title")],
          "detailed_analysis": f"{t.get('what_happened')}\n\n{t.get('why_it_matters')}",
      })
  else:
    # Deterministic Non-LLM Briefing Trends from top 3 scored stories
    for s in top_stories[:3]:
      assigned_urls.add(s["link"])
      trends.append({
          "title": s["title"],
          "what_happened": s["summary"],
          "why_it_matters": s["why_it_matters"],
          "who_affected": "Developers, AI Practitioners, and Decision Makers",
          "source": s["source"],
          "tier": s["tier"],
          "status": "official_claim" if s["is_official"] else "source_linked",
          "evidence_urls": [s["link"]],
          "topic": s["topic"],
          "company": s["company"],
          "reading_time": s["reading_time"],
          "audience_pills": ["Developers", "Enterprises"],
          "key_points": s["key_points"],
          "detailed_analysis": s["detailed_analysis"],
          "image": s.get("image", ""),
      })

  # 3. Purpose-driven curated domain sections with cross-section exclusivity
  # AI Tools: actual products, tools, assistants, platform features
  ai_tools = []
  for s in top_stories:
    if s["link"] in assigned_urls:
      continue
    is_tool = (
        s["topic"] in ("AI Tools & Ecosystem", "AI Coding") or
        any(k in s["title"].lower() for k in ["tool", "app", "release", "feature", "assist", "workflow", "platform", "extension", "plugin", "suite"])
    )
    if is_tool:
      ai_tools.append(s)
      assigned_urls.add(s["link"])
      if len(ai_tools) >= 4:
        break

  # Developer Radar: APIs, SDKs, frameworks, libraries, coding agents, MCP
  dev_radar = []
  for s in top_stories:
    if s["link"] in assigned_urls:
      continue
    is_dev = (
        s["topic"] in ("AI Coding", "AI Agents") or
        any(k in s["title"].lower() for k in ["sdk", "api", "code", "agent", "open-source", "weight", "benchmark", "mcp", "library", "framework", "repo", "github", "inference"])
    )
    if is_dev:
      dev_radar.append(s)
      assigned_urls.add(s["link"])
      if len(dev_radar) >= 4:
        break

  # Research & Safety: safety, alignment, security, policy, governance, preprints
  research_safety = []
  for s in top_stories:
    if s["link"] in assigned_urls:
      continue
    is_research = (
        s["topic"] in ("Research & Safety",) or
        s["trust_tier"] in (3, 4) or
        any(k in s["title"].lower() for k in ["safety", "alignment", "paper", "arxiv", "eval", "policy", "governance", "frontier", "benchmark", "risk", "security", "copyright", "red team", "misalignment"])
    )
    if is_research:
      research_safety.append(s)
      assigned_urls.add(s["link"])
      if len(research_safety) >= 4:
        break

  # Trending: Stories with corroborated multi-outlet coverage (covered_by_sources_count > 1) or high overall score
  trending = []
  for s in top_stories:
    if s["link"] in assigned_urls:
      continue
    if s.get("covered_by_sources_count", 1) > 1 or s.get("overall_score", 0) >= 80:
      trending.append(s)
      assigned_urls.add(s["link"])
      if len(trending) >= 4:
        break

  # The Pulse: Key quick developments from the last hours, excluding the lead briefing trend when possible
  pulse_items = []
  lead_trend_url = trends[0].get("link") if trends and "link" in trends[0] else (trends[0].get("evidence_urls", [None])[0] if trends else None)
  for s in top_stories:
    if lead_trend_url and s["link"] == lead_trend_url and len(top_stories) > 1:
      continue
    pulse_items.append({
        "title": s["title"],
        "topic": s["topic"],
        "company": s["company"],
        "published": s.get("published", "Date unavailable"),
        "what_happened": s.get("what_happened") or s.get("one_liner") or s.get("summary", ""),
        "one_liner": s.get("one_liner") or s.get("summary", ""),
        "summary": s.get("summary", ""),
        "why_it_matters": s.get("why_it_matters", ""),
        "link": s["link"],
        "source": s["source"],
        "tier": s["tier"],
    })
    if len(pulse_items) >= 4:
      break

  takeaway = (
      ai_briefing.get("takeaway")
      if ai_briefing and ai_briefing.get("takeaway")
      else "Frontier research labs and technology publications report accelerating momentum across coding agents, model releases, and evaluation benchmarks."
  )

  payload = {
      "schema_version": 2,
      "data_status": "fresh" if ai_briefing else "source_linked",
      "generated_at": now_iso,
      "last_attempt_at": now_iso,
      "takeaway": takeaway,
      "trends": trends,
      "top_stories": top_stories,
      "ai_tools": ai_tools,
      "dev_radar": dev_radar,
      "research_safety": research_safety,
      "trending": trending,
      "pulse_items": pulse_items,
  }
  return payload


# -------------------------------------------------------------
# 15. PAYLOAD VALIDATION & RESILIENT PIPELINE
# -------------------------------------------------------------
def validate_dataset_payload(payload):
  """Strict schema validation for the final dataset payload before saving."""
  if not isinstance(payload, dict):
    raise ValueError("Payload must be a dictionary")

  required_keys = [
      "schema_version", "data_status", "generated_at", "last_attempt_at",
      "takeaway", "trends", "top_stories", "ai_tools", "dev_radar",
      "research_safety", "pulse_items"
  ]
  for k in required_keys:
    if k not in payload:
      raise ValueError(f"Payload missing required top-level key: {k}")

  if not isinstance(payload["top_stories"], list) or len(payload["top_stories"]) == 0:
    raise ValueError("Payload top_stories must be a non-empty list")

  for idx, s in enumerate(payload["top_stories"][:10]):
    for field in ["title", "link", "source", "trust_tier", "overall_score"]:
      if field not in s or s[field] is None:
        raise ValueError(f"Story #{idx} missing required field '{field}'")
    if not (s["link"].startswith("http://") or s["link"].startswith("https://")):
      raise ValueError(f"Story #{idx} has invalid link: {s['link']}")

  return True


def run_pipeline(dry_run=False, max_age_hours=72, output_file="data.json"):
  """Full execution pipeline: ingest, cluster, score, synthesize, and write data.json atomically.
  Guarantees that previous valid dataset is preserved if any failure occurs.
  """
  try:
    articles = collect_fresh_news(max_age_hours=max_age_hours)
    if not articles:
      print("⚠️ No fresh articles collected across sources. Preserving last known-good data.json.")
      if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
          return json.load(f)
      return None

    clustered = cluster_and_deduplicate_articles(articles)
    print(f"📊 Story clustering complete: {len(clustered)} deduplicated story clusters.")

    ai_briefing = synthesize_with_gemini(clustered)
    if ai_briefing and "trends" in ai_briefing:
      ai_briefing["trends"] = validate_evidence_provenance(ai_briefing["trends"], articles)

    payload = build_complete_payload(clustered, ai_briefing=ai_briefing)

    # Validate payload strictly before file write
    validate_dataset_payload(payload)

    if dry_run:
      print("\n🔍 DRY-RUN MODE: data.json will NOT be written.")
      print(f"   Status: {payload['data_status']}")
      print(f"   Trends count: {len(payload['trends'])}")
      print(f"   Stories count: {len(payload['top_stories'])}")
      print(f"   Generated: {payload['generated_at']}")
      return payload

    # Atomic write to temporary file
    temp_file = f"{output_file}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
      json.dump(payload, f, indent=2)

    # Validate that temporary file reloads and passes schema validation
    with open(temp_file, "r", encoding="utf-8") as f:
      test_load = json.load(f)
      validate_dataset_payload(test_load)

    # Atomic file replacement
    os.replace(temp_file, output_file)
    print(f"✅ {output_file} written atomically! Status: {payload['data_status']}, Stories: {len(payload['top_stories'])}")
    return payload

  except Exception as e:
    print(f"❌ Pipeline execution encountered an error: {e}")
    print("🔒 Preserving previous valid dataset. No files were corrupted.")
    temp_file = f"{output_file}.tmp"
    if os.path.exists(temp_file):
      try:
        os.remove(temp_file)
      except Exception:
        pass
    if os.path.exists(output_file):
      try:
        with open(output_file, "r", encoding="utf-8") as f:
          return json.load(f)
      except Exception:
        pass
    raise e


if __name__ == "__main__":
  is_dry_run = "--dry-run" in sys.argv
  run_pipeline(dry_run=is_dry_run)
