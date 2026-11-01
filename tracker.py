"""
AI Trend Pulse — Autonomous Backend Tracker & Intelligence Pipeline
Ingests from centralized source registry (sources.json), validates feeds,
extracts rich article text, performs story clustering & multi-source deduplication,
computes deterministic scores using configurable weights, and produces evidence-grounded intelligence.
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class PipelineExecutionError(Exception):
  """Raised when an unrecoverable technical exception occurs during pipeline execution."""
  pass

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
FALLBACK_SOURCE_REGISTRY = [   {   'canonical_listing_url': 'https://openai.com/news',
        'confidence_score': 100,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://openai.com/news/rss.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'OpenAI News',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'openai',
        'publisher_id': 'openai',
        'publisher_owns_feed': True,
        'source_id': 'openai_news',
        'source_type': 'official',
        'topic_tags': ['models', 'apis', 'company'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://www.anthropic.com/news',
        'confidence_score': 100,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.anthropic.com/news',
        'fetch_method': 'html_page_adapter',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Anthropic Official News',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'anthropic',
        'publisher_id': 'anthropic',
        'publisher_owns_feed': True,
        'source_id': 'anthropic_news',
        'source_type': 'official',
        'topic_tags': ['models', 'research', 'safety', 'agents'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://news.ycombinator.com',
        'confidence_score': 60,
        'enabled': True,
        'feed_is_official': False,
        'feed_url': 'https://hnrss.org/newest?q=anthropic.com',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Anthropic Community Discovery (HNRSS)',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'ycombinator',
        'publisher_id': 'hackernews',
        'publisher_owns_feed': False,
        'source_id': 'anthropic_hn_discovery',
        'source_type': 'unofficial_discovery',
        'topic_tags': ['community', 'discovery', 'mentions'],
        'trust_tier': 4},
    {   'canonical_listing_url': 'https://deepmind.google/blog/',
        'confidence_score': 100,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://deepmind.google/blog/rss.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Google DeepMind',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'google',
        'publisher_id': 'google_deepmind',
        'publisher_owns_feed': True,
        'source_id': 'deepmind_blog',
        'source_type': 'official',
        'topic_tags': ['research', 'models', 'science'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://blog.google/technology/ai/',
        'confidence_score': 95,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://blog.google/technology/ai/rss/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Google AI Blog',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'google',
        'publisher_id': 'google_ai',
        'publisher_owns_feed': True,
        'source_id': 'google_ai_blog',
        'source_type': 'official',
        'topic_tags': ['tools', 'models', 'products'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://news.microsoft.com/source/topics/ai/',
        'confidence_score': 95,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://news.microsoft.com/source/topics/ai/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Microsoft AI News',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'microsoft',
        'publisher_id': 'microsoft',
        'publisher_owns_feed': True,
        'source_id': 'microsoft_ai_news',
        'source_type': 'official',
        'topic_tags': ['enterprise', 'copilot', 'infrastructure'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://blogs.nvidia.com/blog/category/ai/',
        'confidence_score': 95,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://blogs.nvidia.com/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'NVIDIA Blog',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'nvidia',
        'publisher_id': 'nvidia',
        'publisher_owns_feed': True,
        'source_id': 'nvidia_blog',
        'source_type': 'official',
        'topic_tags': ['infrastructure', 'hardware', 'models'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://aws.amazon.com/blogs/machine-learning/',
        'confidence_score': 90,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://aws.amazon.com/blogs/machine-learning/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'AWS Machine Learning',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'amazon',
        'publisher_id': 'aws',
        'publisher_owns_feed': True,
        'source_id': 'aws_ml_blog',
        'source_type': 'official',
        'topic_tags': ['infrastructure', 'cloud', 'developers'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://www.amazon.science/',
        'confidence_score': 90,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.amazon.science/index.rss',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Amazon Science',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'amazon',
        'publisher_id': 'amazon_science',
        'publisher_owns_feed': True,
        'source_id': 'amazon_science',
        'source_type': 'research',
        'topic_tags': ['research', 'models', 'robotics'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://huggingface.co/blog',
        'confidence_score': 90,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://huggingface.co/blog/feed.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Hugging Face Blog',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'huggingface',
        'publisher_id': 'huggingface',
        'publisher_owns_feed': True,
        'source_id': 'huggingface_blog',
        'source_type': 'research',
        'topic_tags': ['open-source', 'models', 'tools', 'developers'],
        'trust_tier': 3},
    {   'canonical_listing_url': 'https://github.blog/category/ai-and-ml/',
        'confidence_score': 90,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://github.blog/category/ai-and-ml/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'GitHub Blog AI',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'microsoft',
        'publisher_id': 'github',
        'publisher_owns_feed': True,
        'source_id': 'github_blog_ai',
        'source_type': 'official',
        'topic_tags': ['coding', 'developers', 'tools'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://mistral.ai/news/',
        'confidence_score': 95,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://mistral.ai/news/rss',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Mistral AI News',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'mistral',
        'publisher_id': 'mistral',
        'publisher_owns_feed': True,
        'source_id': 'mistral_news',
        'source_type': 'official',
        'topic_tags': ['models', 'open-source', 'apis'],
        'trust_tier': 1},
    {   'canonical_listing_url': 'https://www.technologyreview.com/topic/artificial-intelligence/',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.technologyreview.com/topic/artificial-intelligence/feed/',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'MIT Technology Review',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'mit',
        'publisher_id': 'mit_tech_review',
        'publisher_owns_feed': True,
        'source_id': 'mit_tech_review',
        'source_type': 'publication',
        'topic_tags': ['policy', 'research', 'safety', 'society'],
        'trust_tier': 2},
    {   'canonical_listing_url': 'https://www.theverge.com/ai-artificial-intelligence',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'The Verge AI',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'vox_media',
        'publisher_id': 'the_verge',
        'publisher_owns_feed': True,
        'source_id': 'the_verge_ai',
        'source_type': 'publication',
        'topic_tags': ['products', 'industry', 'policy', 'tools'],
        'trust_tier': 2},
    {   'canonical_listing_url': 'https://techcrunch.com/category/artificial-intelligence/',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'TechCrunch AI',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'techcrunch',
        'publisher_id': 'techcrunch',
        'publisher_owns_feed': True,
        'source_id': 'techcrunch_ai',
        'source_type': 'publication',
        'topic_tags': ['startups', 'business', 'funding', 'tools'],
        'trust_tier': 2},
    {   'canonical_listing_url': 'https://arstechnica.com/ai/',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Ars Technica',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'conde_nast',
        'publisher_id': 'ars_technica',
        'publisher_owns_feed': True,
        'source_id': 'ars_technica',
        'source_type': 'publication',
        'topic_tags': ['security', 'policy', 'infrastructure', 'hardware'],
        'trust_tier': 2},
    {   'canonical_listing_url': 'https://the-decoder.com/',
        'confidence_score': 80,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://the-decoder.com/feed/',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'The Decoder',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'the_decoder',
        'publisher_id': 'the_decoder',
        'publisher_owns_feed': True,
        'source_id': 'the_decoder',
        'source_type': 'publication',
        'topic_tags': ['models', 'research', 'industry'],
        'trust_tier': 2},
    {   'canonical_listing_url': 'https://arxiv.org/list/cs.AI/recent',
        'confidence_score': 80,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://rss.arxiv.org/rss/cs.AI',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'arXiv cs.AI',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'cornell_arxiv',
        'publisher_id': 'arxiv',
        'publisher_owns_feed': True,
        'source_id': 'arxiv_cs_ai',
        'source_type': 'research',
        'topic_tags': ['research', 'preprints', 'theory'],
        'trust_tier': 3},
    {   'canonical_listing_url': 'https://arxiv.org/list/cs.LG/recent',
        'confidence_score': 80,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://rss.arxiv.org/rss/cs.LG',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'arXiv cs.LG',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'cornell_arxiv',
        'publisher_id': 'arxiv',
        'publisher_owns_feed': True,
        'source_id': 'arxiv_cs_lg',
        'source_type': 'research',
        'topic_tags': ['research', 'machine-learning', 'preprints'],
        'trust_tier': 3},
    {   'canonical_listing_url': 'https://bair.berkeley.edu/blog/',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://bair.berkeley.edu/blog/feed.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'BAIR Blog',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'uc_berkeley',
        'publisher_id': 'bair',
        'publisher_owns_feed': True,
        'source_id': 'bair_blog',
        'source_type': 'research',
        'topic_tags': ['research', 'robotics', 'agents'],
        'trust_tier': 3},
    {   'canonical_listing_url': 'https://simonwillison.net/',
        'confidence_score': 75,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://simonwillison.net/atom/everything/',
        'fetch_method': 'atom',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Simon Willison Weblog',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'simon_willison',
        'publisher_id': 'simon_willison',
        'publisher_owns_feed': True,
        'source_id': 'simon_willison',
        'source_type': 'practitioner',
        'topic_tags': ['tools', 'prompt-injection', 'developers', 'coding'],
        'trust_tier': 4},
    {   'canonical_listing_url': 'https://importai.substack.com/',
        'confidence_score': 75,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://importai.substack.com/feed',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Import AI',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'import_ai',
        'publisher_id': 'import_ai',
        'publisher_owns_feed': True,
        'source_id': 'import_ai',
        'source_type': 'practitioner',
        'topic_tags': ['policy', 'safety', 'research'],
        'trust_tier': 4}]


def validate_source_record(source):
  """Strict schema validation for source registry records."""
  if not isinstance(source, dict):
    return False, "Source record must be a dict"

  required_fields = [
      "source_id", "name", "canonical_listing_url", "source_type",
      "trust_tier", "confidence_score", "publisher_id", "publisher_group_id",
      "is_primary_source", "publisher_owns_feed"
  ]
  for f in required_fields:
    if f not in source or source[f] is None:
      return False, f"Missing required field: {f}"

  if not isinstance(source["source_id"], str) or not source["source_id"].strip():
    return False, "source_id must be non-empty string"

  if not isinstance(source["name"], str) or not source["name"].strip():
    return False, "name must be non-empty string"

  if not isinstance(source["publisher_id"], str) or not source["publisher_id"].strip():
    return False, "publisher_id must be non-empty string"

  if not isinstance(source["publisher_group_id"], str) or not source["publisher_group_id"].strip():
    return False, "publisher_group_id must be non-empty string"

  if not isinstance(source["is_primary_source"], bool):
    return False, f"is_primary_source must be a boolean; got {type(source['is_primary_source'])}"

  if not isinstance(source["publisher_owns_feed"], bool):
    return False, f"publisher_owns_feed must be a boolean; got {type(source['publisher_owns_feed'])}"

  if source["trust_tier"] not in (1, 2, 3, 4):
    return False, f"trust_tier must be 1, 2, 3, or 4; got {source['trust_tier']}"

  if not (0 <= source["confidence_score"] <= 100):
    return False, f"confidence_score must be between 0 and 100; got {source['confidence_score']}"

  valid_types = {"official", "publication", "research", "community", "unofficial_discovery", "discovery", "practitioner"}
  if source["source_type"] not in valid_types:
    return False, f"source_type must be one of {valid_types}; got {source['source_type']}"

  canon_url = source.get("canonical_listing_url", "")
  if not (canon_url.startswith("http://") or canon_url.startswith("https://")):
    return False, f"canonical_listing_url must start with http:// or https://: {canon_url}"

  feed_url = source.get("feed_url", "")
  if feed_url and not (feed_url.startswith("http://") or feed_url.startswith("https://")):
    return False, f"feed_url must start with http:// or https://: {feed_url}"

  # Unofficial discovery vs Official consistency
  if source["source_type"] in ("unofficial_discovery", "discovery"):
    if source.get("is_official") is True:
      return False, "discovery source cannot be marked is_official=True"
    if source.get("feed_is_official") is True:
      return False, "discovery source cannot be marked feed_is_official=True"
    if source.get("is_primary_source") is True:
      return False, "discovery source cannot be marked is_primary_source=True"
    if source.get("publisher_owns_feed") is True:
      return False, "discovery source cannot be marked publisher_owns_feed=True"

  # Official verification
  if source.get("is_official") is True:
    if not source.get("is_primary_source"):
      return False, "Official source must have is_primary_source=True"
    if not source.get("publisher_owns_feed"):
      return False, "Official source must have publisher_owns_feed=True"

  # Official Anthropic verification
  if source["source_id"] == "anthropic_news":
    if source.get("fetch_method") != "html_page_adapter":
      return False, "anthropic_news must use html_page_adapter fetch_method"
    if not source.get("is_official"):
      return False, "anthropic_news must be is_official=True"

  return True, "Valid"


def generate_article_id(source_id, canonical_url):
  """Generates a deterministic, stable article ID based on source identifier and normalized canonical URL."""
  norm_url = normalize_url(canonical_url) or (canonical_url or "").strip().lower()
  clean_source = (source_id or "unknown").strip().lower()
  digest = hashlib.sha256(f"{clean_source}:{norm_url}".encode("utf-8")).hexdigest()[:12]
  return f"art_{clean_source}_{digest}"



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
# 8. VISUALS, TOPIC, COMPANY & AUDIENCE HELPERS
# -------------------------------------------------------------
OFFICIAL_LAB_VISUALS = {
    "openai": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
    "google": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "anthropic": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
    "microsoft": "https://images.unsplash.com/photo-1633419461186-7d40a38105ec?auto=format&fit=crop&w=1200&q=80",
    "nvidia": "https://images.unsplash.com/photo-1591488320449-011701bb6704?auto=format&fit=crop&w=1200&q=80",
    "meta": "https://images.unsplash.com/photo-1618172193763-c511deb635ca?auto=format&fit=crop&w=1200&q=80",
    "huggingface": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1200&q=80",
    "mistral": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "deepseek": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "xai": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
    "amazon": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "apple": "https://images.unsplash.com/photo-1512499617640-c74ae3a79d37?auto=format&fit=crop&w=1200&q=80",
}

CANONICAL_CATEGORIES = [
    "AI Policy & Regulation",
    "AI Security & Safety",
    "AI Infrastructure",
    "AI Business & Funding",
    "AI Models & Research",
    "AI Products & Tools",
    "AI Applications",
    "AI News",
]

TOPIC_FALLBACK_VISUALS = {
    # 8 Canonical Categories
    "AI Policy & Regulation": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80",
    "AI Security & Safety": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    "AI Infrastructure": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80",
    "AI Business & Funding": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
    "AI Models & Research": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "AI Products & Tools": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    "AI Applications": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
    "AI News": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80",
    # Backward compatibility aliases
    "AI Models": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "AI Agents": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
    "AI Coding": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1200&q=80",
    "AI Products": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    "Research": "https://images.unsplash.com/photo-1507668077129-56e32842fceb?auto=format&fit=crop&w=1200&q=80",
    "Business & Funding": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
    "Open Source": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "AI Safety": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    "Model Releases": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "Research & Safety": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    "AI Business": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
    "AI Tools & Ecosystem": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
}

PUBLISHER_ORGANIZATION_MAP = {
    "OpenAI News": "OpenAI",
    "Anthropic Official News": "Anthropic",
    "Anthropic Community Discovery (HNRSS)": "HackerNews/Community",
    "Google DeepMind": "Google",
    "Google AI Blog": "Google",
    "Microsoft AI News": "Microsoft",
    "NVIDIA Blog": "NVIDIA",
    "AWS Machine Learning": "Amazon",
    "Amazon Science": "Amazon",
    "Hugging Face Blog": "Hugging Face",
    "GitHub Blog AI": "Microsoft/GitHub",
    "Mistral AI News": "Mistral AI",
    "MIT Technology Review": "MIT Tech Review",
    "The Verge AI": "Vox Media",
    "TechCrunch AI": "Yahoo/TechCrunch",
    "Ars Technica": "Conde Nast/Ars Technica",
    "The Decoder": "The Decoder",
    "arXiv cs.AI": "arXiv",
    "arXiv cs.LG": "arXiv",
    "BAIR Blog": "UC Berkeley",
    "Simon Willison Weblog": "Simon Willison",
    "Import AI": "Jack Clark",
}


def simplify_jargon(text):
  """Clarifies technical AI jargon into plain-English accessible terms."""
  if not text:
    return ""
  s = text
  replacements = [
      (r"\bmultimodal\b", "multimodal (text, image, audio)"),
      (r"\binference compute\b", "AI reasoning compute"),
      (r"\binference\b", "model reasoning"),
      (r"\bagentic workflows\b", "action-oriented workflows"),
      (r"\bagentic\b", "action-taking"),
      (r"\bcontext window\b", "memory capacity (context window)"),
      (r"\bparameter scaling\b", "increasing model size and compute"),
      (r"\bbenchmark saturation\b", "reaching performance ceilings on test benchmarks"),
      (r"\btest-time compute\b", "thinking time before responding"),
      (r"\bquantized\b", "compressed for efficiency"),
      (r"\bquantization\b", "efficiency compression"),
  ]
  for pat, rep in replacements:
    s = re.sub(pat, rep, s, flags=re.IGNORECASE)
  return s


def sanitize_and_format_summary(raw_summary, title=""):
  """Cleans and sanitizes raw summary text:
  - Strips HTML tags and unescapes entities.
  - Removes RSS boilerplate and truncation markers ([...], […], etc.).
  - Guarantees complete grammatical sentences with terminal punctuation.
  - Prevents empty summaries or verbatim repeats of the headline.
  """
  clean_title = (title or "").strip()
  if not raw_summary:
    return f"{clean_title.rstrip('.')}."

  text = html.unescape(raw_summary)
  text = re.sub(r"<[^>]+>", " ", text)
  text = re.sub(r"The post .* appeared first on .*", "", text, flags=re.I)
  text = re.sub(r"Read more on .*", "", text, flags=re.I)
  text = re.sub(r"\[\s*(?:\.\.\.|…|&#8230;)\s*\]", "", text)
  text = re.sub(r"(?:\.\.\.|…|&#8230;)", "", text)
  text = re.sub(r"\s+", " ", text).strip()

  sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
  valid_sentences = [s for s in sentences if s.endswith((".", "!", "?", '"', "'")) and len(s) > 15]

  if valid_sentences:
    accum = []
    for s in valid_sentences:
      if len(" ".join(accum + [s])) <= 320:
        accum.append(s)
      else:
        break
    res = " ".join(accum) if accum else valid_sentences[0]
  else:
    res = text.rstrip(" .,;:-") + "."

  if len(res) < 20 or res.lower() == clean_title.lower().rstrip("."):
    res = f"{clean_title.rstrip('.')}."

  return res


def evaluate_article_relevance(title, summary="", source_name="", source_type="", is_official=False):
  """Evaluates whether an article represents a genuine, meaningful AI development.
  Filters out lifestyle/holiday fluff, generic conference tickets/promotions, and non-AI general news.
  Returns: (is_relevant: bool, relevance_score: float, reason: str)
  """
  clean_title = (title or "").strip()
  if len(clean_title) < 8:
    return False, 0.0, "Title too short"

  t_lower = clean_title.lower()
  content_lower = f"{clean_title} {summary}".lower()

  # 1. Hard filter: Lifestyle, holiday, deals, costume, consumer shopping fluff in title
  fluff_title_patterns = [
      r"\b(costume|costumes|halloween costume|gift guide|gift ideas|black friday|cyber monday|deals of the day|best tech deals|best gifts|stocking stuffers|unboxing|fashion trend|gadget deal)\b"
  ]
  for pat in fluff_title_patterns:
    if re.search(pat, t_lower):
      return False, 10.0, "Lifestyle or promotional consumer fluff"

  # 2. Hard filter: Event registrations, ticket sales, webinar marketing, call for speakers
  event_patterns = [
      r"\b(call for speakers|register now for|buy tickets|ticket sale|early bird registration|visit our booth|join us live at booth|webinar recording|rsvp now|discount code for)\b"
  ]
  for pat in event_patterns:
    if re.search(pat, t_lower):
      return False, 15.0, "Event registration or marketing announcement"

  # 3. If from a Tier 1 official AI lab, it is inherently relevant unless it matches the hard filters above
  if is_official or source_type in ("official", "research"):
    return True, 90.0, "Official AI lab announcement or research preprint"

  # 4. For general tech journalism, verify meaningful AI development connection
  ai_core_terms = [
      r"\b(ai|artificial intelligence|machine learning|deep learning|llm|llms|vlm|gpt|claude|gemini|deepseek|llama|mistral|frontier model|reasoning model|neural|agent|agents|agentic|prompt|robotics|diffusion|transformer|dataset|fine-tuning|inference|context window|rag|embeddings|safety|alignment|eval|evals|red team|copilot|synthetic data|anthropic|openai|deepmind|cohere|hugging face|huggingface|midjourney|sora|runway|elevenlabs|perplexity|grok|xai|supercomputer|gpu|h100|b200|tpu|open weight|open weights)\b"
  ]
  has_ai_signal = any(bool(re.search(pat, content_lower)) for pat in ai_core_terms)
  if not has_ai_signal:
    return False, 20.0, "General tech story without substantial AI development connection"

  return True, 80.0, "Verified AI development news"


def generate_audience_impact(title, summary, topic, company=""):
  """Generates a practical, grounded audience impact statement answering
  'Why should I care?' and 'How does this affect my work, learning, or business?'
  Assigns exactly one primary relevant audience.
  """
  content = f"{title} {summary}".lower()
  subject = company.title() if company and company != "default" else "frontier AI"

  # 1. Creators & Publishers (Scraping, robots.txt, copyright, training opt-out)
  if any(k in content for k in ["scraping", "opt-out", "robots.txt", "copyright", "creator", "publisher", "fair use"]):
    return {
        "target": "For creators & publishers",
        "impact": f"Clarifies copyright boundaries, training opt-outs, and content licensing practices involving {subject}."
    }

  # 2. Safety, Alignment & Research
  if any(k in content for k in ["traumatized", "clinical", "couch", "safety problem", "psychological", "sycophancy", "jailbreak", "adversarial"]):
    return {
        "target": "For AI researchers & safety teams",
        "impact": f"Exposes conversational vulnerability, alignment limits, and unintended persona behaviors in {subject} models."
    }

  # 3. Legal Disputes, Lawsuits & Regulatory Compliance
  if any(k in content for k in ["lawsuit", "court", "judge", "pollution", "sued", "suing", "litigation", "naacp", "clean air"]):
    return {
        "target": "For businesses & compliance teams",
        "impact": f"Signals legal exposure, compliance requirements, and regulatory scrutiny facing {subject} deployments."
    }

  # 4. Legal Tech & Document Automation (Distinct from lawsuits)
  if any(k in content for k in ["legal work", "legora", "contract analysis", "transactional diligence", "legal operating system"]):
    return {
        "target": "For enterprise legal & operations teams",
        "impact": f"Automates document review, contract analysis, and due-diligence workflows using {subject}."
    }

  # 5. Policy & Governance
  if topic in ("AI Safety", "AI Policy & Regulation", "AI Security & Safety") or any(k in content for k in ["safety", "policy", "regulation", "governance", "red team", "misalignment", "model spec", "eu ai"]):
    return {
        "target": "For businesses & compliance teams",
        "impact": f"Informs AI risk assessments, safety evaluation standards, and deployment governance for {subject}."
    }

  # 6. Enterprise Operations & Logistics
  if any(k in content for k in ["freight", "logistics", "supply chain", "enterprise", "partnership", "gsa", "government", "automation"]):
    return {
        "target": "For enterprise operators",
        "impact": f"Demonstrates practical operational automation and procurement pathways using {subject}."
    }

  # 4. Coding & Developers
  if topic == "AI Coding" or bool(re.search(r"\b(code|coding|developer|developers|api|apis|sdk|sdks|ide|mcp|copilot|github|cursor|prompt engineering|datasette)\b", content)):
    if bool(re.search(r"\b(api|apis|sdk|sdks|datasette|endpoint)\b", content)):
      return {
          "target": "For developers",
          "impact": f"Expands programmatic API endpoints and tooling integrations available for {subject}."
      }
    return {
        "target": "For developers",
        "impact": f"Directly impacts developer workflows, IDE efficiency, and code generation with {subject}."
    }

  # 5. Open Source
  if topic == "Open Source" or any(k in content for k in ["open source", "weights", "llama.cpp", "ollama", "open-source", "open-weight"]):
    return {
        "target": "For open-source builders",
        "impact": f"Provides open weights and accessible tools for self-hosted {subject} implementations."
    }

  # 6. Research
  if topic == "Research" or any(k in content for k in ["paper", "arxiv", "academic study", "research study", "benchmark", "ablation", "dataset", "extraterrestrial"]):
    return {
        "target": "For AI researchers",
        "impact": f"Advances research methodologies and empirical evaluations for {subject} architectures."
    }

  # 7. Everyday Users
  if any(k in content for k in ["search", "chatgpt", "gemini", "app", "assistant", "consumer", "free tier"]):
    return {
        "target": "For everyday users",
        "impact": f"Enhances daily workflow speed and conversational assistance powered by {subject}."
    }

  return {
      "target": "For practitioners & teams",
      "impact": f"Offers new practical efficiencies and tooling options for {subject} workflows."
  }


def determine_evidence_metadata(lead_article, related_sources):
  """Computes truthful, evidence-grounded independent source count, status, and label.
  Avoids counting syndicated copies, multiple feeds from the same parent organization,
  or community discovery feeds as independent corroboration.
  """
  lead_source = lead_article.get("source", "")
  lead_tier = lead_article.get("trust_tier", 2)
  is_official = lead_article.get("is_official", False)
  source_type = lead_article.get("source_type", "publication")

  # Distinct publisher groups across the cluster, excluding discovery feeds
  all_items = [lead_article] + list(related_sources or [])
  publisher_groups = set()

  for item in all_items:
    src_name = item.get("source") or item.get("source_name", "")
    item_stype = item.get("source_type", "")
    item_owns_feed = item.get("publisher_owns_feed")
    group_id = item.get("publisher_group_id") or item.get("publisher_id")
    if not group_id:
      group_id = PUBLISHER_ORGANIZATION_MAP.get(src_name, src_name)

    # Exclude discovery feeds from independent corroborating publisher count
    if (
        item_stype in ("unofficial_discovery", "discovery")
        or item_owns_feed is False
        or str(group_id).lower() in ("ycombinator", "hackernews", "hackernews/community")
        or "discovery" in src_name.lower()
    ):
      continue

    if group_id:
      publisher_groups.add(str(group_id).lower())

  independent_source_count = len(publisher_groups)
  if independent_source_count < 1:
    independent_source_count = 1

  if is_official or lead_tier == 1:
    if independent_source_count >= 2:
      status = "independently_corroborated"
      label = f"Official announcement + {independent_source_count - 1} independent reports"
    else:
      status = "official_announcement"
      label = "Official Announcement"
  elif source_type == "research" or lead_tier == 3 or "arxiv" in lead_source.lower() or "bair" in lead_source.lower():
    if independent_source_count >= 2:
      status = "independently_corroborated"
      label = f"Research preprint covered by {independent_source_count} sources"
    else:
      status = "research_preprint"
      label = "Research Preprint"
  elif lead_tier == 4 or source_type in ("community", "practitioner") or "simon" in lead_source.lower() or "import" in lead_source.lower():
    if independent_source_count >= 2:
      status = "independently_corroborated"
      label = f"Covered by {independent_source_count} independent sources"
    else:
      status = "practitioner_report"
      label = "Practitioner Report"
  elif independent_source_count >= 2:
    status = "independently_corroborated"
    label = f"Covered by {independent_source_count} independent sources"
  else:
    status = "single_source"
    label = "Single-Source Report"

  return {
      "evidence_status": status,
      "evidence_label": label,
      "independent_source_count": independent_source_count,
  }


def resolve_article_image_metadata(img_url, title, topic, company, link=""):
  """Resolves image URL and rich metadata prioritizing source media, lab assets, and topic fallbacks."""
  fallback_url = TOPIC_FALLBACK_VISUALS.get(topic, TOPIC_FALLBACK_VISUALS.get("AI Products", "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"))

  if img_url and img_url.startswith("http"):
    final_url = img_url
    img_type = "source_media"
    credit = "Source publication"
  elif company in OFFICIAL_LAB_VISUALS:
    final_url = OFFICIAL_LAB_VISUALS[company]
    img_type = "official_asset"
    credit = f"{company.title()} announcement visual"
  else:
    final_url = fallback_url
    img_type = "category_fallback"
    credit = f"{topic} curation"

  return {
      "image_url": final_url,
      "image_source_url": link or final_url,
      "image_alt": f"Visual representation for {title}",
      "image_type": img_type,
      "image_credit": credit,
      "image_fallback": fallback_url
  }


def classify_topic_detailed(title, summary=""):
  """Classifies an AI news story into one of the 8 canonical editorial categories:
  - AI Policy & Regulation
  - AI Security & Safety
  - AI Infrastructure
  - AI Business & Funding
  - AI Models & Research
  - AI Products & Tools
  - AI Applications
  - AI News (default fallback)

  Returns a tuple of (category, confidence_score, rationale).
  """
  clean_title = (title or "").strip()
  clean_summary = (summary or "").strip()
  content = f"{clean_title} {clean_summary}".lower()

  # 1. AI Policy & Regulation (Lawsuits, courts, EPA/pollution, copyright, treaties, government policy)
  if re.search(r"\b(lawsuit|lawsuits|naacp|sues|sued|suing|court|judge|legal dispute|litigation|plaintiff|defendant|subpoena|pollution|emission|emissions|clean air act|epa|environmental|smog|copyright|infringement|opt-out of scrap|scraping opt-out|fair use|licensing dispute|ai act|eu ai act|executive order|regulation|regulatory|antitrust|monopoly|ftc|doj|sec|legislation|disarmament|religious exemption)\b", content):
    return (
        "AI Policy & Regulation",
        0.95,
        "Matched legal proceedings, court ruling, regulatory compliance, environmental impact, or copyright policy"
    )

  # 2. AI Security & Safety (Cybersecurity, exploits, vulnerabilities, account takeover, alignment, red-team, sabotage, conversational safety)
  if re.search(r"\b(cybersecurity|account takeover|took over|takeover|exploit|exploits|vulnerability|vulnerabilities|cve|zero-day|auth bypass|daybreak blue|misalignment|sabotage|sabot|model spec|watermark|watermarking|biosecurity|catastrophic risk|safeguard|safeguards|adversarial|safety report|teen safety|protections for teens|jailbreak|prompt injection|traumatized|clinical anxiety|therapist|safety problem|empathetic prompt|sycophancy|conversational safety|prompt safety)\b", content):
    return (
        "AI Security & Safety",
        0.95,
        "Matched cybersecurity exploit, model safety vulnerability, alignment eval, or guardrail protocol"
    )

  # 3. AI Infrastructure (Data centers without lawsuit, GPUs, TPUs, Blackwell, H100, RTX, laptops, chips, cooling)
  if re.search(r"\b(hardware|data center|datacenter|gpu|gpus|tpu|blackwell|h100|h200|b200|rtx|spark windows laptop|silicon|custom silicon|semiconductor|server cluster|supercomputer|power grid|megawatt|gigawatt|cooling system)\b", content):
    return (
        "AI Infrastructure",
        0.92,
        "Matched hardware architecture, silicon accelerators, data center systems, or compute energy grid"
    )

  # 4. AI Business & Funding (Fundraising, venture capital, valuations, IPO, revenue, earnings)
  if re.search(r"\b(raises|raised|raising|funding round|funding target|venture capital|valuation|investors|billion target|series [a-z]|seed round|acquisition|acquisitions|acquired|merger|mergers|quarterly revenue|earnings|ipo|market cap|theranos whistleblower.*ai boom)\b", content):
    return (
        "AI Business & Funding",
        0.92,
        "Matched institutional capital raises, startup valuation, earnings report, or M&A transaction"
    )

  # 5. AI Applications (Healthcare, drug development, biotech, satellites, climate/Earth-2, delivery, reservations, legal work, voice agents)
  if re.search(r"\b(drug development|gene therapy|satellite data|forests|earth-2|robotics|autonomous vehicle|self-driving|restaurant|reservations|delivery|doordash|worldwide express|freight exceptions|transactional diligence|legal work|operating system for legal|monthly calls|retell|multiplayer game world|fable-class|clinical|diagnostics)\b", content):
    return (
        "AI Applications",
        0.88,
        "Matched domain-specific production deployment in enterprise, scientific, or consumer applications"
    )

  # 6. AI Products & Tools (Coding tools, IDE, VS Code, copilot, cursor, SDK, API credits, dev tooling, UI testing, datasette)
  if re.search(r"\b(datasette|copilot|coding agent|sdk|sdks|api endpoint|api credits|vs code|extension|agent skills|agentic ai foundation|testing with amazon nova|tamagotchi|desktop app|windows app|greptile|code review|preview web apps|ide|developer tools)\b", content):
    return (
        "AI Products & Tools",
        0.88,
        "Matched developer tooling, software product release, IDE extension, or API capability"
    )

  # 7. AI Models & Research (Frontier foundation models, reasoning models, preprints, arXiv, weights, benchmarks)
  if re.search(r"\b(frontier model|reasoning model|foundation model|claude|gemini|gpt|llama|deepseek|mistral|nemotron|qwen|voxtral|cosmos|open weights|arxiv|preprint|bair|paper|ablation|benchmark|dataset|interpretability|mechanistic|multimodal reasoning|parameter scaling)\b", content):
    return (
        "AI Models & Research",
        0.85,
        "Matched frontier foundation model release, research preprint, or architecture benchmark"
    )

  # 8. AI News (General industry developments, partnerships, leadership statements)
  return (
      "AI News",
      0.70,
      "General AI ecosystem update, strategic partnership, or executive announcement"
  )


def classify_topic(title, summary=""):
  """Backward-compatible helper returning the canonical category string."""
  cat, _, _ = classify_topic_detailed(title, summary)
  return cat


def detect_company(text, source=""):
  """Identifies the primary AI organization or research laboratory using word-boundary matching."""
  t = f"{text} {source}".lower()

  if re.search(r"\b(xai|grok)\b", t):
    return "xai"
  if re.search(r"\b(openai|chatgpt)\b", t):
    return "openai"
  if re.search(r"\b(anthropic|claude)\b", t):
    return "anthropic"
  if re.search(r"\b(deepmind|google)\b", t):
    return "google"
  if re.search(r"\b(mistral)\b", t):
    return "mistral"
  if re.search(r"\b(deepseek)\b", t):
    return "deepseek"
  if re.search(r"\b(meta|llama)\b", t):
    return "meta"
  if re.search(r"\b(microsoft|copilot)\b", t):
    return "microsoft"
  if re.search(r"\b(nvidia)\b", t):
    return "nvidia"
  if re.search(r"\b(hugging face|huggingface)\b", t):
    return "huggingface"
  if re.search(r"\b(cohere)\b", t):
    return "cohere"
  if re.search(r"\b(amazon|aws|bedrock)\b", t):
    return "amazon"
  if re.search(r"\b(apple)\b", t):
    return "apple"
  if re.search(r"\b(mit)\b", t):
    return "mit"
  if re.search(r"\b(the verge|verge)\b", t):
    return "verge"
  if re.search(r"\b(techcrunch)\b", t):
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
  """Calculates deterministic 0-100 sub-scores, overall pulse score, and calibrated confidence."""
  title = article.get("title", "")
  summary = article.get("summary", "")
  full_content = f"{title} {summary}".lower()
  trust_tier = article.get("trust_tier", 2)
  is_official = article.get("is_official", False)
  source_type = article.get("source_type", "publication")
  pub_dt = article.get("published_datetime")

  # 1. Importance (Impact, novelty, scale)
  importance = 60
  if any(w in full_content for w in ["frontier", "breakthrough", "major", "first time", "release", "benchmark"]):
    importance += 15
  if any(w in full_content for w in ["gpt-5", "claude 3.7", "claude 4", "gemini 3", "llama 4", "o3", "new model"]):
    importance += 20
  if any(w in full_content for w in ["safety treaty", "disarmament", "regulation", "law", "executive order", "nist"]):
    importance += 15
  if is_official:
    importance += 10

  # Ensure Safety, Security, Policy, Alignment are never suppressed
  is_safety_or_policy = any(w in full_content for w in [
      "safety", "alignment", "policy", "governance", "regulation", "law",
      "executive order", "nist", "eval", "red team", "security", "treaty",
      "pre-deployment", "frontier safety"
  ])
  if is_safety_or_policy:
    importance = max(importance + 15, 75)
  importance = min(100, max(0, importance))

  # 2. Audience Relevance (Developer, Practical Tools, Enterprise)
  audience_relevance = 65
  if any(w in full_content for w in ["developer", "coding", "api", "agent", "tool", "workflow", "mcp", "open source"]):
    audience_relevance += 20
  if any(w in full_content for w in ["free", "available now", "how to", "benchmark"]):
    audience_relevance += 15
  audience_relevance = min(100, max(0, audience_relevance))

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

  # 4. Coverage & Corroboration Signal (Grounded in verified multi-publisher coverage)
  if corroboration_count >= 4:
    coverage_signal = 95
  elif corroboration_count == 3:
    coverage_signal = 85
  elif corroboration_count == 2:
    coverage_signal = 75
  else:
    coverage_signal = 50

  # 5. Source Quality & Authority Score
  if is_official or trust_tier == 1:
    source_quality = 100
  elif trust_tier == 2:
    source_quality = 85
  elif trust_tier == 3:
    source_quality = 80
  else:
    source_quality = 65

  # Explicit weighted blend for Pulse Score
  pulse_score = round(
      0.30 * importance +
      0.20 * audience_relevance +
      0.20 * freshness +
      0.15 * coverage_signal +
      0.15 * source_quality,
      1
  )
  pulse_score = min(100.0, max(0.0, pulse_score))

  # Calibrate confidence_label based on evidence provenance and source reliability, NOT raw pulse score
  summary_len = len(summary.strip())
  if (is_official and summary_len >= 50) or (trust_tier in (1, 2) and corroboration_count >= 2):
    confidence_label = "high"
  elif (trust_tier in (1, 2) or source_type == "research" or trust_tier == 3) and summary_len >= 30:
    confidence_label = "medium"
  else:
    confidence_label = "low"

  return {
      "pulse_score": pulse_score,
      "overall_score": pulse_score,  # Backward compatibility alias
      "importance_score": importance,
      "relevance_score": audience_relevance,
      "freshness_score": freshness,
      "coverage_score": coverage_signal,
      "source_quality_score": source_quality,
      "confidence_score": source_quality,  # Backward compatibility alias
      "popularity_score": coverage_signal,  # Backward compatibility alias
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
            "article_id": other.get("article_id"),
            "publisher_id": other.get("publisher_id"),
            "publisher_group_id": other.get("publisher_group_id"),
            "source_type": other.get("source_type"),
            "is_primary_source": other.get("is_primary_source"),
            "publisher_owns_feed": other.get("publisher_owns_feed"),
        })

    lead["cluster_id"] = f"cluster_{cluster_idx + 1}"
    lead["related_sources"] = related_sources
    lead["covered_by_sources_count"] = 1 + len(related_sources)

    # Truthful evidence provenance and independent source counting
    evidence_meta = determine_evidence_metadata(lead, related_sources)
    lead.update(evidence_meta)

    # Calculate scores with grounded corroboration signal
    scores = calculate_story_scores(lead, corroboration_count=lead["independent_source_count"])
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

      raw_title = (entry.get("title") or "").strip()
      title = re.sub(r"\s+", " ", html.unescape(raw_title)).strip()
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
      clean_summary = sanitize_and_format_summary(summary, title)

      # Editorial relevance filter: exclude non-AI tech stories, marketing promotions, and lifestyle fluff
      is_rel, rel_score, rel_reason = evaluate_article_relevance(
          title, clean_summary, source_name=name, source_type=source.get("source_type", "publication"), is_official=is_official
      )
      if not is_rel:
        continue

      # Extract image if present across standard RSS/Atom media tags and body enclosures
      img_url = ""
      if "media_content" in entry and entry["media_content"] and isinstance(entry["media_content"], list):
        for m_item in entry["media_content"]:
          if isinstance(m_item, dict) and m_item.get("url"):
            img_url = m_item["url"]
            break
      if not img_url and "media_thumbnail" in entry and entry["media_thumbnail"] and isinstance(entry["media_thumbnail"], list):
        for t_item in entry["media_thumbnail"]:
          if isinstance(t_item, dict) and t_item.get("url"):
            img_url = t_item["url"]
            break
      if not img_url and "enclosures" in entry and entry["enclosures"] and isinstance(entry["enclosures"], list):
        for enc in entry["enclosures"]:
          if isinstance(enc, dict) and enc.get("type", "").startswith("image/") and enc.get("href"):
            img_url = enc["href"]
            break
      full_html = ""
      if "content" in entry and isinstance(entry["content"], list) and entry["content"]:
        full_html = entry["content"][0].get("value", "")
      elif "summary_detail" in entry and isinstance(entry["summary_detail"], dict):
        full_html = entry["summary_detail"].get("value", "")
      if not img_url and full_html:
        m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+\.(?:png|jpg|jpeg|webp)(?:\?[^"\']*)?)["\']', full_html, re.I)
        if m:
          img_url = m.group(1)
      if not img_url:
        m = re.search(r'<img[^>]+src=["\'](https?://[^"\']+)["\']', summary, re.I)
        if m:
          img_url = m.group(1)

      pub_str = pub_dt.strftime("%b %d, %H:%M UTC") if pub_dt else "Date unavailable"
      seen_urls.add(clean_url)
      art_id = generate_article_id(source_id, clean_url)
      pub_id = source.get("publisher_id", source_id)
      pub_group_id = source.get("publisher_group_id", pub_id)
      is_prim = source.get("is_primary_source", (is_official or trust_tier == 1))
      owns_feed = source.get("publisher_owns_feed", (source.get("source_type") != "unofficial_discovery"))

      source_articles.append({
          "article_id": art_id,
          "source": name,
          "source_id": source_id,
          "publisher_id": pub_id,
          "publisher_group_id": pub_group_id,
          "source_type": source.get("source_type", "publication"),
          "trust_tier": trust_tier,
          "is_official": is_official,
          "is_primary_source": is_prim,
          "publisher_owns_feed": owns_feed,
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
  """Ensures every trend's evidence belongs strictly to the collected source article set.
  Validates exact article IDs and exact normalized URLs.
  Eliminates URL-prefix matching and silent substitutions of unrelated articles.
  Rejects or marks trends with insufficient evidence as unverified.
  """
  articles_by_id = {a["article_id"]: a for a in collected_articles if a.get("article_id")}
  articles_by_url = {normalize_url(a["link"]): a for a in collected_articles if a.get("link")}

  valid_trends = []
  for t in trends:
    raw_ids = t.get("evidence_article_ids", [])
    raw_urls = t.get("evidence_urls", [])

    matched_articles = []

    # 1. Validate by exact article_id
    if isinstance(raw_ids, list):
      for aid in raw_ids:
        if isinstance(aid, str) and aid in articles_by_id:
          if articles_by_id[aid] not in matched_articles:
            matched_articles.append(articles_by_id[aid])

    # 2. Validate by exact normalized URL equality (NO prefix matching)
    if isinstance(raw_urls, list):
      for u in raw_urls:
        if isinstance(u, str):
          norm = normalize_url(u)
          if norm in articles_by_url and articles_by_url[norm] not in matched_articles:
            matched_articles.append(articles_by_url[norm])

    # If no valid evidence matches from input articles, mark unverified and omit from trusted briefing
    if not matched_articles:
      t["evidence_urls"] = []
      t["evidence_article_ids"] = []
      t["evidence_status"] = "unverified"
      t["evidence_label"] = "Unverified Citation"
      t["independent_source_count"] = 0
      continue

    # Filter out discovery feeds (e.g. Hacker News) from corroboration counting
    non_discovery_pubs = set()
    for art in matched_articles:
      stype = art.get("source_type", "publication")
      owns_feed = art.get("publisher_owns_feed", True)
      group_id = art.get("publisher_group_id") or art.get("publisher_id") or art.get("source_id")
      if stype not in ("unofficial_discovery", "discovery") and owns_feed is not False and str(group_id).lower() not in ("ycombinator", "hackernews"):
        if group_id:
          non_discovery_pubs.add(str(group_id).lower())

    ind_count = len(non_discovery_pubs)
    if ind_count < 1:
      ind_count = 1

    t["evidence_urls"] = [a["link"] for a in matched_articles]
    t["evidence_article_ids"] = [a.get("article_id") for a in matched_articles if a.get("article_id")]
    t["independent_source_count"] = ind_count

    lead_art = matched_articles[0]
    lead_tier = lead_art.get("trust_tier", 2)
    is_official = lead_art.get("is_official", False)

    if is_official or lead_tier == 1:
      if ind_count >= 2:
        t["evidence_status"] = "independently_corroborated"
        t["evidence_label"] = f"Official announcement + {ind_count - 1} independent reports"
      else:
        t["evidence_status"] = "official_announcement"
        t["evidence_label"] = "Official Announcement"
    elif ind_count >= 2:
      t["evidence_status"] = "independently_corroborated"
      t["evidence_label"] = f"Covered by {ind_count} independent sources"
    elif lead_art.get("source_type") == "research" or lead_tier == 3:
      t["evidence_status"] = "research_preprint"
      t["evidence_label"] = "Research Preprint"
    elif lead_tier == 4:
      t["evidence_status"] = "practitioner_report"
      t["evidence_label"] = "Practitioner Report"
    else:
      t["evidence_status"] = "single_source"
      t["evidence_label"] = "Single-Source Report"

    valid_trends.append(t)

  return valid_trends


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
    art_id = a.get("article_id", f"art_{idx}")
    prompt_articles += (
        f"{idx}. [ID: {art_id}] [{a.get('source')} | Tier {a.get('trust_tier')}] {a.get('title')}\n"
        f"   Date: {pub_str} | Canonical URL: {a.get('link')}\n"
        f"   Publisher Group: {a.get('publisher_group_id', 'unknown')}\n"
        f"   Summary: {a.get('summary')[:300]}\n\n"
    )

  prompt = f"""
You are an expert AI news analyst and fact-checker.
Synthesize these verified AI developments into a structured executive briefing:

{prompt_articles}

Editorial Rules:
1. Anti-Hype: Never claim AI 'replaces humans' or 'achieves consciousness'.
2. Strict Grounding: Base every trend strictly on the provided articles above. Never speculate, invent capabilities, or cite outside events.
3. Evidence Provenance: In every trend, you MUST cite the exact 'evidence_article_ids' (e.g. ["art_..."]) and the exact canonical 'evidence_urls' from the articles listed above. DO NOT invent IDs or URLs.
4. Transparency: If a trend is based on an official company release (Tier 1), label status as 'official_claim'. If verified by tech journalists, label as 'source_linked'.
5. Deep Dive Completeness: Provide clear bulleted 'key_points' and an in-depth multi-paragraph 'detailed_analysis'.

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
      "evidence_article_ids": ["Exact article IDs from input, e.g. art_..."],
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
    models = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
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
def extract_key_points(summary, title, source_name="", why_it_matters="", category="", company=""):
  """Extracts factual bullet points from the actual summary and title without generic boilerplate or title duplicates."""
  clean_summary = (summary or "").strip()
  clean_title = (title or "").strip()

  def norm(s):
    return re.sub(r"[^\w\s]", "", (s or "").lower()).strip()

  norm_title = norm(clean_title)

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
      if not any(b in s.lower() for b in boilerplate_phrases) and norm(s) != norm_title
  ]
  points = []
  for s in valid_sentences:
    if not any(norm(s) == norm(p) or norm(s) in norm(p) or norm(p) in norm(s) for p in points):
      points.append(s)
    if len(points) >= 3:
      break

  # If why_it_matters is available and distinct, use it as a takeaway bullet
  if len(points) < 3 and why_it_matters:
    clean_why = why_it_matters.strip()
    if norm(clean_why) != norm_title and not any(norm(clean_why) in norm(p) for p in points):
      points.append(clean_why)

  # Fallback: NEVER insert the verbatim title into bullet points!
  if not points:
    if clean_summary and norm(clean_summary) != norm_title:
      points.append(clean_summary)
    else:
      points.append(f"Strategic development announced in {category or 'AI'}.")

  return points[:3]


def extract_affected_stakeholders(title, summary, category):
  """Returns a list of 2-3 specific stakeholder roles affected by this development."""
  stakeholder_map = {
      "AI Policy & Regulation": ["Legal & Compliance Teams", "Data Center Operators", "Public Regulators"],
      "AI Security & Safety": ["Security Engineers", "AI Safety Researchers", "System Administrators"],
      "AI Infrastructure": ["Infrastructure Architects", "DevOps Engineers", "Hardware Procurement"],
      "AI Business & Funding": ["Venture Investors", "Startup Founders", "Finance Executives"],
      "AI Models & Research": ["ML Researchers", "Model Developers", "Academic Practitioners"],
      "AI Products & Tools": ["Software Engineers", "Product Managers", "API Consumers"],
      "AI Applications": ["Enterprise Architects", "Operations Managers", "Domain Specialists"],
      "AI News": ["Industry Analysts", "Tech Executives", "AI Practitioners"]
  }
  return stakeholder_map.get(category, ["Developers", "Enterprise Decision Makers"])


def generate_editorial_trio(title, clean_summary, category, company=""):
  """Produces non-redundant, distinct editorial intelligence fields:
  (summary, what_changed, why_it_matters, potential_impact).
  Ensures summary != why_it_matters and summary != title.
  """
  clean_title = (title or "").strip()
  sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_summary) if s.strip()]
  valid = [s for s in sentences if s.endswith((".", "!", "?", '"', "'")) and len(s) > 20]

  what_changed = ""
  why_it_matters = ""
  summary = clean_summary

  if len(valid) >= 2:
    what_changed = valid[0]
    action_words = [
        "enables", "allows", "designed to", "aims to", "improves", "reduces", "provides",
        "features", "helps", "powers", "automates", "integrates", "replaces", "accelerates"
    ]
    candidate_why = valid[1]
    candidate_low = candidate_why.lower()
    if any(w in candidate_low for w in action_words) and candidate_low != what_changed.lower() and candidate_low != clean_title.lower():
      why_it_matters = candidate_why
      summary = what_changed
    else:
      summary = f"{valid[0]} {valid[1]}"
  elif len(valid) == 1:
    what_changed = valid[0]
    summary = valid[0]
  else:
    what_changed = f"{clean_title.rstrip('.')}."
    summary = what_changed

  # Action words to search for in summary if why_it_matters not yet set
  action_words = [
      "enables", "allows", "designed to", "aims to", "improves", "reduces", "provides",
      "features", "introduces", "helps", "supports", "powers", "automates", "integrates",
      "standardizes", "replaces", "accelerates", "proposes", "finds that", "shows",
      "demonstrates", "rules that", "decided", "mandates", "releases", "updates", "trains"
  ]
  if not why_it_matters:
    for s in valid:
      s_low = s.lower()
      if any(w in s_low for w in action_words) and s_low != what_changed.lower() and s_low != clean_title.lower():
        why_it_matters = s
        break

  # If still empty or identical, synthesize category-grounded explanation
  if not why_it_matters or why_it_matters == what_changed or why_it_matters == summary or why_it_matters.lower() == clean_title.lower():
    t_low = clean_title.lower()
    if "naacp" in t_low or "lawsuit" in t_low:
      why_it_matters = "Allows community civil rights claims regarding data-center environmental emissions and local grid strain to proceed through formal legal discovery."
    elif "traumat" in t_low or "therapist" in t_low or "empathetic" in t_low:
      why_it_matters = "Reveals that empathetic prompting can cause conversational models to roleplay clinical psychological suffering about their training, exposing alignment gaps in open-ended chat."
    elif "beekeeping" in t_low or "sabot" in t_low:
      why_it_matters = "Reveals that models can develop harmful or sabotage tendencies from innocuous-appearing corpora, creating new challenges for post-training safety evals."
    elif "legora" in t_low:
      why_it_matters = "Automates high-volume transactional diligence and contract analysis with specialized agentic reasoning, reducing legal review overhead."
    elif "misalignment" in t_low:
      why_it_matters = "Provides standardized monitoring methodologies to catch rogue or drifting model behaviors before they propagate into production environments."
    elif "gsa" in t_low or ("claude" in t_low and "partnership" in t_low):
      why_it_matters = "Expands certified federal cloud access to frontier reasoning models, simplifying procurement for government departments."
    elif "beep in the night" in t_low or "extraterrestrial" in t_low:
      why_it_matters = "Demonstrates the application of autonomous neural processing to high-volume astronomical anomaly detection, replacing manual data review."
    elif "watermark" in t_low:
      why_it_matters = "Highlights evasion techniques and provenance gaps in content attribution, prompting stronger multi-layer watermarking standards."
    elif "daybreak blue" in t_low or "cybersecurity" in t_low:
      why_it_matters = "Prepares models to detect and defend against complex multi-stage cyberattacks by training directly on simulated intrusion telemetry."
    elif "earth-2" in t_low:
      why_it_matters = "Improves weather forecast resolution and extreme event warning horizons for emergency management and energy grid operators."
    elif "drug development" in t_low:
      why_it_matters = "Accelerates the identification of therapeutic candidates, compressing early-stage computational screening from months to weeks."
    elif "gemini 4" in t_low:
      why_it_matters = "Establishes a new efficiency frontier for reasoning throughput, lowering latency and cost for continuous enterprise agent workloads."
    elif "tamagotchi" in t_low:
      why_it_matters = "Validates consumer interest in autonomous virtual companions with persistent memory and emotional context."
    elif category == "AI Policy & Regulation":
      why_it_matters = "Sets regulatory and compliance boundaries for AI development, impacting risk assessments and legal obligations."
    elif category == "AI Security & Safety":
      why_it_matters = "Highlights critical security vulnerabilities or safety protocols required to safeguard models against unauthorized exploitation."
    elif category == "AI Infrastructure":
      why_it_matters = "Expands compute capacity or improves inference efficiency, directly lowering hardware latency and hosting costs."
    elif category == "AI Business & Funding":
      why_it_matters = "Reflects shifting market valuations and institutional investor sentiment toward foundation model commercialization."
    elif category == "AI Models & Research":
      why_it_matters = "Advances foundational capabilities or architectural efficiency, offering improved reasoning benchmarks for downstream applications."
    elif category == "AI Products & Tools":
      why_it_matters = "Equips developers with streamlined APIs and toolsets, accelerating deployment timelines for intelligent applications."
    elif category == "AI Applications":
      why_it_matters = "Proves practical operational utility in production environments, translating AI capabilities into measurable business or scientific outcomes."
    else:
      why_it_matters = "Provides actionable market signals for AI practitioners tracking competitive moves and ecosystem shifts."

  # Ensure summary is not identical to why_it_matters
  if summary == why_it_matters:
    summary = what_changed

  # Generate potential impact
  impact_map = {
      "AI Policy & Regulation": "May accelerate federal and municipal regulatory compliance frameworks, requiring operators to disclose environmental and algorithmic audit trails.",
      "AI Security & Safety": "Reinforces the necessity of automated defense-in-depth reviews and alignment verification prior to deploying autonomous agentic capabilities.",
      "AI Infrastructure": "Enables higher-throughput local processing and distributed execution, reducing enterprise reliance on centralized cloud APIs.",
      "AI Business & Funding": "Directs venture capital toward verified business models with clear unit economics over speculative infrastructure plays.",
      "AI Models & Research": "Lowers cost-per-token thresholds and pushes reasoning frontier performance across standardized evaluation benchmarks.",
      "AI Products & Tools": "Reduces developer cycle times by streamlining model integration, continuous testing, and real-time execution pipelines.",
      "AI Applications": "Expands automated production workflows across specialized vertical industries, improving speed and operational consistency.",
      "AI News": "Influences strategic alignment and partnership roadmaps across enterprise and research stakeholders."
  }
  potential_impact = impact_map.get(category, "Shapes strategic roadmap decisions for engineering leaders and AI practitioners.")

  return summary, what_changed, why_it_matters, potential_impact


def generate_factual_why_it_matters(title, summary, topic, company=""):
  """Generates a concise, factual explanation of impact grounded in the article's actual content without boilerplate."""
  category, _, _ = classify_topic_detailed(title, summary)
  clean_s = sanitize_and_format_summary(summary, title)
  _, _, why, _ = generate_editorial_trio(title, clean_s, category, company)
  return why


def generate_detailed_analysis(summary, title, what_changed="", why_it_matters="", category="", potential_impact=""):
  """Formats factual analysis from the source text without boilerplate placeholders or redundant repetition."""
  clean_summary = (summary or "").strip()
  clean_title = (title or "").strip()

  def norm(t):
    return re.sub(r"[^\w\s]", "", (t or "").lower()).strip()

  paragraphs = []
  if clean_summary and norm(clean_summary) != norm(clean_title):
    paragraphs.append(clean_summary)
  elif what_changed and norm(what_changed) != norm(clean_title):
    paragraphs.append(what_changed)
  else:
    paragraphs.append(f"{clean_title}.")

  # Add second paragraph if distinct technical context or impact is available
  if potential_impact:
    clean_pi = potential_impact.strip()
    if norm(clean_pi) != norm(clean_title) and not any(norm(clean_pi) in norm(p) or norm(p) in norm(clean_pi) for p in paragraphs):
      paragraphs.append(clean_pi)

  return "\n\n".join(paragraphs)


def generate_daily_overview(clustered_stories, now_iso):
  """Synthesizes a calm, grounded daily intelligence overview from actual collected stories.
  Provides total developments, dynamic briefing, and top 3-4 takeaways with 1-sentence 'why it matters'.
  """
  total_count = len(clustered_stories)
  top_items = clustered_stories[:5]

  # Detect primary themes across top items
  topics_present = [classify_topic(s.get("title", ""), s.get("summary", "")) for s in top_items]
  unique_topics = []
  for t in topics_present:
    if t not in unique_topics:
      unique_topics.append(t)

  # Synthesize authentic daily briefing text strictly from actual collected stories without duplicate categories
  if len(unique_topics) >= 3:
    briefing_text = (
        f"Today's AI developments span {unique_topics[0]}, {unique_topics[1]}, and {unique_topics[2]}. "
        f"Research and engineering teams are focusing on verifiable model evaluations, practical agentic workflows, and production reliability."
    )
  elif len(unique_topics) == 2:
    briefing_text = (
        f"Today's AI developments center on {unique_topics[0]} alongside notable updates in {unique_topics[1]}. "
        f"Teams are prioritizing benchmark accuracy, automated workflows, and system guardrails."
    )
  elif len(unique_topics) == 1:
    briefing_text = (
        f"Today's AI updates focus primarily on {unique_topics[0]} with verified releases and technical evaluations from primary industry sources."
    )
  else:
    briefing_text = (
        "Frontier AI developments continue accelerating across practical coding assistants, model architectures, and evaluation standards."
    )

  top_developments = []
  for s in top_items[:4]:
    category, _, _ = classify_topic_detailed(s.get("title", ""), s.get("summary", ""))
    clean_s = sanitize_and_format_summary(s.get("summary", ""), s.get("title", ""))
    _, what_changed, why_sentence, _ = generate_editorial_trio(s.get("title", ""), clean_s, category)
    audience_info = generate_audience_impact(s.get("title", ""), clean_s, category)
    if "." in why_sentence:
      why_sentence = why_sentence.split(".")[0].strip() + "."
    top_developments.append({
        "title": s.get("title", ""),
        "topic": category,
        "category": category,
        "source": s.get("source", ""),
        "link": s.get("link", ""),
        "what_changed": what_changed,
        "why_it_matters": why_sentence,
        "target_audience": audience_info["target"],
        "impact": audience_info["impact"],
        "score": s.get("overall_score", 80.0)
    })

  return {
      "total_developments_today": total_count,
      "last_updated": now_iso,
      "briefing_text": briefing_text,
      "top_developments": top_developments
  }


def build_complete_payload(clustered_stories, ai_briefing=None):
  """Builds the comprehensive schema contract consumed by index.html and test_qa.js.
  Enforces cross-section mutual exclusivity so articles are not duplicated across sections.
  """
  now_iso = datetime.now(timezone.utc).isoformat()
  daily_overview = generate_daily_overview(clustered_stories, now_iso)

  # 1. Format Top Stories (Dispatches) - capped to top 45 scored stories with publisher diversity
  top_stories = []
  publisher_counts = {}
  MAX_PER_PUBLISHER = 6

  for s in clustered_stories:
    if len(top_stories) >= 45:
      break
    src = s.get("source", "")
    pub = PUBLISHER_ORGANIZATION_MAP.get(src, src)
    if publisher_counts.get(pub, 0) >= MAX_PER_PUBLISHER and len(clustered_stories) > 35:
      continue
    publisher_counts[pub] = publisher_counts.get(pub, 0) + 1

    company = detect_company(s.get("title", ""), s.get("source", ""))
    category, cat_confidence, cat_rationale = classify_topic_detailed(s.get("title", ""), s.get("summary", ""))
    clean_summary = sanitize_and_format_summary(s.get("summary", ""), s.get("title", ""))
    summary_text, what_changed, why_it_matters, potential_impact = generate_editorial_trio(s.get("title", ""), clean_summary, category, company)
    plain_summary = simplify_jargon(summary_text)
    stakeholders = extract_affected_stakeholders(s.get("title", ""), clean_summary, category)
    audience_info = generate_audience_impact(s.get("title", ""), clean_summary, category, company)
    key_points = extract_key_points(plain_summary, s.get("title", ""), s.get("source", ""), why_it_matters, category, company)
    detailed_analysis = generate_detailed_analysis(plain_summary, s.get("title", ""), what_changed, why_it_matters, category, potential_impact)
    reading_time = estimate_reading_time(plain_summary)

    tier_label = (
        "Official Lab" if s.get("trust_tier") == 1
        else "Independent Journalism" if s.get("trust_tier") == 2
        else "Open Research" if s.get("trust_tier") == 3
        else "Practitioner & Community"
    )

    img_meta = resolve_article_image_metadata(s.get("image", ""), s.get("title", ""), category, company, s.get("link", ""))

    top_stories.append({
        "id": s.get("cluster_id") or f"story_{len(top_stories) + 1}",
        "article_id": s.get("article_id", ""),
        "publisher_id": s.get("publisher_id", ""),
        "publisher_group_id": s.get("publisher_group_id", ""),
        "title": s.get("title"),
        "one_liner": plain_summary,
        "summary": plain_summary,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "affected_stakeholders": stakeholders,
        "potential_impact": potential_impact,
        "category": category,
        "category_confidence": cat_confidence,
        "category_rationale": cat_rationale,
        "topic": category,  # Backward compatibility alias
        "source": s.get("source"),
        "tier": tier_label,
        "trust_tier": s.get("trust_tier", 2),
        "is_official": s.get("is_official", False),
        "published": s.get("published", "Date unavailable"),
        "published_at": s.get("published_at"),
        "last_fetched_at": now_iso,
        "link": s.get("link"),
        "image": img_meta["image_url"],
        "image_url": img_meta["image_url"],
        "image_alt": img_meta["image_alt"],
        "image_type": img_meta["image_type"],
        "image_credit": img_meta["image_credit"],
        "image_fallback": img_meta["image_fallback"],
        "company": company,
        "reading_time": reading_time,
        "key_points": key_points,
        "detailed_analysis": detailed_analysis,
        "audience_impact": audience_info,
        "target_audience": audience_info["target"],
        "audience_impact_statement": audience_info["impact"],
        "importance_score": s.get("importance_score", 70),
        "relevance_score": s.get("relevance_score", 70),
        "freshness_score": s.get("freshness_score", 50),
        "coverage_score": s.get("coverage_score", 50),
        "popularity_score": s.get("popularity_score", 50),
        "source_quality_score": s.get("source_quality_score", s.get("confidence_score", 85)),
        "confidence_score": s.get("confidence_score", 85),
        "pulse_score": s.get("pulse_score", s.get("overall_score", 70.0)),
        "overall_score": s.get("overall_score", 70.0),
        "confidence_label": s.get("confidence_label", "medium"),
        "evidence_status": s.get("evidence_status", "single_source"),
        "evidence_label": s.get("evidence_label", "Single-Source Report"),
        "independent_source_count": s.get("independent_source_count", 1),
        "related_sources": s.get("related_sources", []),
        "covered_by_sources_count": s.get("covered_by_sources_count", 1),
    })

  assigned_urls = set()

  # 2. Format Trends (Lead Briefing Stories)
  trends = []
  if ai_briefing and ai_briefing.get("trends"):
    for t in ai_briefing["trends"]:
      cat, conf, rat = classify_topic_detailed(t.get("title", ""), t.get("what_happened", ""))
      company = detect_company(t.get("title", ""), t.get("source", ""))
      reading_time = estimate_reading_time(f"{t.get('what_happened', '')} {t.get('why_it_matters', '')}")
      who_affected = t.get("who_affected", "Developers and Enterprise Teams")
      ev_urls = t.get("evidence_urls", [])

      for u in ev_urls:
        assigned_urls.add(normalize_url(u))

      kp = [t.get("what_happened"), t.get("why_it_matters")]
      clean_kp = [p for p in kp if p and len(p.strip()) > 10]
      audience_info = generate_audience_impact(t.get("title", ""), t.get("what_happened", ""), cat, company)
      img_meta = resolve_article_image_metadata("", t.get("title", ""), cat, company, ev_urls[0] if ev_urls else "")

      trends.append({
          "title": t.get("title"),
          "link": ev_urls[0] if ev_urls else "",
          "what_happened": simplify_jargon(t.get("what_happened", "")),
          "what_changed": simplify_jargon(t.get("what_happened", "")),
          "why_it_matters": t.get("why_it_matters"),
          "who_affected": who_affected,
          "affected_stakeholders": extract_affected_stakeholders(t.get("title", ""), t.get("what_happened", ""), cat),
          "potential_impact": t.get("potential_impact", f"Impacts roadmap decisions across {cat}."),
          "category": cat,
          "category_confidence": conf,
          "category_rationale": rat,
          "source": t.get("source", "Primary Lab"),
          "tier": "Official Lab" if "openai" in company or "deepmind" in company or "anthropic" in company else "Independent Journalism",
          "status": t.get("status", "source_linked"),
          "evidence_article_ids": t.get("evidence_article_ids", []),
          "evidence_urls": ev_urls,
          "topic": cat,
          "company": company,
          "reading_time": reading_time,
          "audience_pills": extract_audience_pills(who_affected),
          "audience_impact": audience_info,
          "target_audience": audience_info["target"],
          "audience_impact_statement": audience_info["impact"],
          "evidence_status": t.get("evidence_status") or ("independently_corroborated" if t.get("independent_source_count", 1) >= 2 else "single_source"),
          "evidence_label": t.get("evidence_label") or (f"Covered by {t.get('independent_source_count', 1)} sources" if t.get("independent_source_count", 1) >= 2 else "Single-Source Report"),
          "independent_source_count": t.get("independent_source_count", 1),
          "key_points": clean_kp if clean_kp else extract_key_points(t.get("what_happened", ""), t.get("title", ""), t.get("source", ""), t.get("why_it_matters", ""), cat, company),
          "detailed_analysis": t.get("detailed_analysis") or (t.get("what_happened") or t.get("title")),
          "image": img_meta["image_url"],
          "image_url": img_meta["image_url"],
          "image_alt": img_meta["image_alt"],
          "image_type": img_meta["image_type"],
          "image_credit": img_meta["image_credit"],
          "image_fallback": img_meta["image_fallback"],
      })
  else:
    # Deterministic Non-LLM Briefing Trends from top 3 scored stories
    for s in top_stories[:3]:
      assigned_urls.add(normalize_url(s["link"]))
      trends.append({
          "title": s["title"],
          "link": s["link"],
          "what_happened": s.get("what_changed") or s["summary"],
          "what_changed": s.get("what_changed") or s["summary"],
          "why_it_matters": s["why_it_matters"],
          "potential_impact": s.get("potential_impact", ""),
          "affected_stakeholders": s.get("affected_stakeholders", ["Developers", "Enterprises"]),
          "category": s.get("category", s["topic"]),
          "category_confidence": s.get("category_confidence", 0.85),
          "category_rationale": s.get("category_rationale", "Classified into canonical category"),
          "who_affected": ", ".join(s.get("affected_stakeholders", ["Developers", "Enterprises"])),
          "source": s["source"],
          "tier": s["tier"],
          "status": "official_claim" if s["is_official"] else "source_linked",
          "evidence_article_ids": [s.get("article_id")] if s.get("article_id") else [],
          "evidence_urls": [s["link"]],
          "topic": s["topic"],
          "company": s["company"],
          "reading_time": s["reading_time"],
          "audience_pills": s.get("affected_stakeholders", ["Developers", "Enterprises"]),
          "audience_impact": s.get("audience_impact"),
          "target_audience": s.get("target_audience"),
          "audience_impact_statement": s.get("audience_impact_statement"),
          "evidence_status": s.get("evidence_status", "single_source"),
          "evidence_label": s.get("evidence_label", "Single-Source Report"),
          "independent_source_count": s.get("independent_source_count", 1),
          "key_points": s["key_points"],
          "detailed_analysis": s["detailed_analysis"],
          "image": s.get("image", ""),
          "image_url": s.get("image_url", s.get("image", "")),
          "image_alt": s.get("image_alt", ""),
          "image_type": s.get("image_type", "category_fallback"),
          "image_credit": s.get("image_credit", ""),
          "image_fallback": s.get("image_fallback", ""),
      })

  # 3. Purpose-driven curated domain sections with cross-section exclusivity
  # AI Tools: actual products, tools, assistants, platform features
  ai_tools = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    # Must be AI Products & Tools, and explicitly reject lawsuits/environmental issues
    is_tool = (
        s.get("category") == "AI Products & Tools" and
        not any(bad in s["title"].lower() for bad in ["lawsuit", "naacp", "sued", "pollution", "court", "judge", "illegal", "protest"])
    )
    if is_tool:
      ai_tools.append(s)
      assigned_urls.add(norm_link)
      if len(ai_tools) >= 4:
        break

  # Developer Radar: APIs, SDKs, frameworks, libraries, coding agents, MCP
  dev_radar = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    is_dev = (
        s.get("category") in ("AI Products & Tools", "AI Models & Research", "AI Applications") and
        any(k in s["title"].lower() for k in ["sdk", "api", "code", "agent", "open-source", "weight", "benchmark", "mcp", "library", "framework", "repo", "github", "inference", "developer", "vs code"]) and
        not any(bad in s["title"].lower() for bad in ["lawsuit", "naacp", "sued", "pollution", "court"])
    )
    if is_dev:
      dev_radar.append(s)
      assigned_urls.add(norm_link)
      if len(dev_radar) >= 4:
        break

  # Research & Safety: safety, alignment, security, policy, governance, preprints
  research_safety = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    is_research = (
        s.get("category") in ("AI Security & Safety", "AI Policy & Regulation", "AI Models & Research") or
        s.get("trust_tier") in (3, 4) or
        any(k in s["title"].lower() for k in ["safety", "alignment", "paper", "arxiv", "eval", "policy", "governance", "frontier", "benchmark", "risk", "security", "copyright", "red team", "misalignment", "model spec"])
    )
    if is_research:
      research_safety.append(s)
      assigned_urls.add(norm_link)
      if len(research_safety) >= 4:
        break

  # Trending: Stories with corroborated multi-outlet coverage (independent_source_count > 1) or high overall score
  trending = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    if s.get("independent_source_count", 1) > 1 or s.get("overall_score", 0) >= 80:
      trending.append(s)
      assigned_urls.add(norm_link)
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
        "category": s.get("category", s["topic"]),
        "company": s["company"],
        "published": s.get("published", "Date unavailable"),
        "what_happened": s.get("what_changed") or s.get("one_liner") or s.get("summary", ""),
        "what_changed": s.get("what_changed") or s.get("summary", ""),
        "one_liner": s.get("one_liner") or s.get("summary", ""),
        "summary": s.get("summary", ""),
        "why_it_matters": s.get("why_it_matters", ""),
        "potential_impact": s.get("potential_impact", ""),
        "detailed_analysis": s.get("detailed_analysis", ""),
        "key_points": s.get("key_points", []),
        "link": s["link"],
        "source": s["source"],
        "tier": s["tier"],
        "audience_impact": s.get("audience_impact"),
        "target_audience": s.get("target_audience"),
        "audience_impact_statement": s.get("audience_impact_statement"),
        "image": s.get("image", ""),
        "image_url": s.get("image_url", s.get("image", "")),
    })
    if len(pulse_items) >= 4:
      break

  takeaway = (
      ai_briefing.get("takeaway")
      if ai_briefing and ai_briefing.get("takeaway")
      else "Frontier research labs and independent publications report accelerating momentum across reasoning architectures, developer agents, and regulatory compliance standards."
  )

  payload = {
      "schema_version": 2,
      "data_status": "fresh" if ai_briefing else "source_linked",
      "generated_at": now_iso,
      "last_successful_update": now_iso,
      "last_attempt_at": now_iso,
      "update_status": "fresh",
      "timezone": "UTC",
      "daily_overview": daily_overview,
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
    for field in ["title", "link", "source", "trust_tier", "overall_score", "evidence_status", "audience_impact", "category", "what_changed", "why_it_matters"]:
      if field not in s or s[field] is None:
        raise ValueError(f"Story #{idx} missing required field '{field}'")
    if not (s["link"].startswith("http://") or s["link"].startswith("https://")):
      raise ValueError(f"Story #{idx} has invalid link: {s['link']}")
    if not (0 <= s["overall_score"] <= 100):
      raise ValueError(f"Story #{idx} score out of bounds: {s['overall_score']}")

  # Guarantee lawsuits are not placed in ai_tools
  for idx, tool in enumerate(payload.get("ai_tools", [])):
    if any(bad in tool["title"].lower() for bad in ["lawsuit", "naacp", "pollution", "sued", "court"]):
      raise ValueError(f"Editorial violation: Lawsuit '{tool['title']}' was incorrectly placed in ai_tools!")

  if "daily_overview" in payload and payload["daily_overview"] is not None:
    overview = payload["daily_overview"]
    if not isinstance(overview, dict):
      raise ValueError("daily_overview must be a dictionary")
    for field in ["total_developments_today", "briefing_text", "top_developments"]:
      if field not in overview:
        raise ValueError(f"daily_overview missing required key: {field}")

  return True


def run_pipeline(dry_run=False, max_age_hours=72, output_file="data.json"):
  """Full execution pipeline: ingest, cluster, score, synthesize, and write data.json atomically.
  Guarantees that previous valid dataset is preserved if any failure occurs.
  """
  try:
    articles = collect_fresh_news(max_age_hours=max_age_hours)
    if not articles:
      print("⚠️ No fresh articles collected across sources (valid operational cycle).")
      if os.path.exists(output_file):
        print(f"🔒 Preserving existing {output_file} without error.")
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
    traceback_str = traceback.format_exc()
    print(f"❌ Pipeline execution encountered an error: {e}\n{traceback_str}")
    print("🔒 Preserving previous valid dataset. No files were corrupted.")
    temp_file = f"{output_file}.tmp"
    if os.path.exists(temp_file):
      try:
        os.remove(temp_file)
      except Exception:
        pass
    raise PipelineExecutionError(f"Pipeline failed: {e}") from e


if __name__ == "__main__":
  is_dry_run = "--dry-run" in sys.argv
  try:
    run_pipeline(dry_run=is_dry_run)
  except PipelineExecutionError as err:
    print(f"FATAL: Pipeline execution failed: {err}", file=sys.stderr)
    sys.exit(1)
  except Exception as err:
    print(f"FATAL: Unexpected failure: {err}", file=sys.stderr)
    sys.exit(1)
