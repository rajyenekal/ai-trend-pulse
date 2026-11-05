"""
pipeline.fetcher - Concurrent Feed Ingestion, Conditional HTTP Caching, and Telemetry.
"""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import os
import sys
import json
import re
import html
import urllib.request
import urllib.parse
import urllib.error
import socket
import gzip
import hashlib
import time
import concurrent.futures
import xml.etree.ElementTree as ET

try:
  import feedparser
except ImportError:
  feedparser = None

FEED_CACHE_FILE = ".feed_cache.json"
SOURCES_REGISTRY_FILE = "sources.json"
OUTPUT_DATA_FILE = "data.json"

PUBLISHER_ORGANIZATION_MAP = {
    "OpenAI News": "OpenAI",
    "Anthropic Official News": "Anthropic",
    "Anthropic Community Discovery (HNRSS)": "HackerNews/Community",
    "Google DeepMind": "Google",
    "Google AI Blog": "Google",
    "Microsoft AI News": "Microsoft",
    "NVIDIA Blog": "NVIDIA",
    "NVIDIA Newsroom": "NVIDIA",
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
    "LMSYS Org Blog": "LMSYS Org",
    "LMSYS Org": "LMSYS Org",
    "Latent Space": "Latent Space",
    "Hugging Face Daily Papers": "Hugging Face",
}


def load_feed_cache(cache_file=FEED_CACHE_FILE):
  """Loads the conditional HTTP feed cache (ETag, Last-Modified, cached items)."""
  if os.path.exists(cache_file):
    try:
      with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}


def save_feed_cache(cache_data, cache_file=FEED_CACHE_FILE):
  """Atomically writes feed cache to disk."""
  tmp_file = f"{cache_file}.tmp"
  try:
    with open(tmp_file, "w", encoding="utf-8") as f:
      json.dump(cache_data, f, indent=2)
    os.replace(tmp_file, cache_file)
  except Exception as e:
    if os.path.exists(tmp_file):
      try:
        os.remove(tmp_file)
      except Exception:
        pass


# -------------------------------------------------------------
# FALLBACK SOURCE REGISTRY
# -------------------------------------------------------------
FALLBACK_SOURCE_REGISTRY = [
    {
        'canonical_listing_url': 'https://openai.com/news',
        'confidence_score': 100,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://openai.com/news/rss.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'OpenAI News',
        'notes': 'Primary official announcement feed for OpenAI model releases, safety updates, and platform features.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'openai',
        'publisher_id': 'openai',
        'publisher_owns_feed': True,
        'source_id': 'openai_news',
        'source_type': 'official',
        'topic_tags': ['models', 'apis', 'company'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://www.anthropic.com/news',
        'confidence_score': 100,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.anthropic.com/news',
        'fetch_method': 'html_page_adapter',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Anthropic Official News',
        'notes': 'Official primary announcements extracted directly from https://www.anthropic.com/news via dedicated HTML page adapter.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'anthropic',
        'publisher_id': 'anthropic',
        'publisher_owns_feed': True,
        'source_id': 'anthropic_news',
        'source_type': 'official',
        'topic_tags': ['models', 'research', 'safety', 'agents'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://news.ycombinator.com',
        'confidence_score': 60,
        'enabled': False,
        'feed_is_official': False,
        'feed_url': 'https://hnrss.org/newest?q=anthropic.com',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Anthropic Community Discovery (HNRSS)',
        'notes': 'Unofficial community discovery feed for Anthropic mentions on Hacker News. Filtered to only keep items with canonical URLs resolving to https://www.anthropic.com/news/.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'ycombinator',
        'publisher_id': 'hackernews',
        'publisher_owns_feed': False,
        'source_id': 'anthropic_hn_discovery',
        'source_type': 'unofficial_discovery',
        'topic_tags': ['community', 'discovery', 'mentions'],
        'trust_tier': 4,
    },
    {
        'canonical_listing_url': 'https://deepmind.google/blog/',
        'confidence_score': 100,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://deepmind.google/blog/rss.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Google DeepMind',
        'notes': 'Primary official feed for Google DeepMind frontier research, Gemini releases, and scientific discoveries.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'google',
        'publisher_id': 'google_deepmind',
        'publisher_owns_feed': True,
        'source_id': 'deepmind_blog',
        'source_type': 'official',
        'topic_tags': ['research', 'models', 'science'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://blog.google/technology/ai/',
        'confidence_score': 95,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://blog.google/technology/ai/rss/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Google AI Blog',
        'notes': 'Google product and platform AI announcements across Search, Workspace, and Android.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'google',
        'publisher_id': 'google_ai',
        'publisher_owns_feed': True,
        'source_id': 'google_ai_blog',
        'source_type': 'official',
        'topic_tags': ['tools', 'models', 'products'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://news.microsoft.com/source/topics/ai/',
        'confidence_score': 95,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://news.microsoft.com/source/topics/ai/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Microsoft AI News',
        'notes': 'Official Microsoft reporting on Copilot, Azure AI, and enterprise intelligence.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'microsoft',
        'publisher_id': 'microsoft',
        'publisher_owns_feed': True,
        'source_id': 'microsoft_ai_news',
        'source_type': 'official',
        'topic_tags': ['enterprise', 'copilot', 'infrastructure'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://nvidianews.nvidia.com/cats/generative_al',
        'confidence_score': 95,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://nvidianews.nvidia.com/cats/generative_al.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'NVIDIA Newsroom',
        'notes': 'Dedicated NVIDIA Generative AI newsroom category feed for AI infrastructure, GPU compute, and foundation model partnerships.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'nvidia',
        'publisher_id': 'nvidia',
        'publisher_owns_feed': True,
        'source_id': 'nvidia_blog',
        'source_type': 'official',
        'topic_tags': ['infrastructure', 'hardware', 'models'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://aws.amazon.com/blogs/machine-learning/',
        'confidence_score': 90,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://aws.amazon.com/blogs/machine-learning/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'AWS Machine Learning',
        'notes': 'Cloud AI engineering, Bedrock updates, and foundation model infrastructure.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'amazon',
        'publisher_id': 'aws',
        'publisher_owns_feed': True,
        'source_id': 'aws_ml_blog',
        'source_type': 'official',
        'topic_tags': ['infrastructure', 'cloud', 'developers'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://www.amazon.science/',
        'confidence_score': 90,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://www.amazon.science/index.rss',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Amazon Science',
        'notes': 'Research papers and engineering insights from Amazon AGI and Alexa teams.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'amazon',
        'publisher_id': 'amazon_science',
        'publisher_owns_feed': True,
        'source_id': 'amazon_science',
        'source_type': 'research',
        'topic_tags': ['research', 'models', 'robotics'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://huggingface.co/blog',
        'confidence_score': 90,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://huggingface.co/blog/feed.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Hugging Face Blog',
        'notes': 'Open-weight models, Transformers library benchmarks, and ecosystem tutorials.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'huggingface',
        'publisher_id': 'huggingface',
        'publisher_owns_feed': True,
        'source_id': 'huggingface_blog',
        'source_type': 'research',
        'topic_tags': ['open-source', 'models', 'tools', 'developers'],
        'trust_tier': 3,
    },
    {
        'canonical_listing_url': 'https://github.blog/category/ai-and-ml/',
        'confidence_score': 90,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://github.blog/category/ai-and-ml/feed/',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'GitHub Blog AI',
        'notes': 'GitHub Copilot updates, developer workspace AI, and coding agent innovations.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'microsoft',
        'publisher_id': 'github',
        'publisher_owns_feed': True,
        'source_id': 'github_blog_ai',
        'source_type': 'official',
        'topic_tags': ['coding', 'developers', 'tools'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://mistral.ai/news/',
        'confidence_score': 95,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://mistral.ai/news/rss',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'Mistral AI News',
        'notes': 'Official releases of frontier European open and commercial models.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'mistral',
        'publisher_id': 'mistral',
        'publisher_owns_feed': True,
        'source_id': 'mistral_news',
        'source_type': 'official',
        'topic_tags': ['models', 'open-source', 'apis'],
        'trust_tier': 1,
    },
    {
        'canonical_listing_url': 'https://www.technologyreview.com/topic/artificial-intelligence/',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.technologyreview.com/topic/artificial-intelligence/feed/',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'MIT Technology Review',
        'notes': 'Independent investigative journalism, research context, and societal impact.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'mit',
        'publisher_id': 'mit_tech_review',
        'publisher_owns_feed': True,
        'source_id': 'mit_tech_review',
        'source_type': 'publication',
        'topic_tags': ['policy', 'research', 'safety', 'society'],
        'trust_tier': 2,
    },
    {
        'canonical_listing_url': 'https://www.theverge.com/ai-artificial-intelligence',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'The Verge AI',
        'notes': 'Consumer AI launches, legal battles, platform policies, and industry trends.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'vox_media',
        'publisher_id': 'the_verge',
        'publisher_owns_feed': True,
        'source_id': 'the_verge_ai',
        'source_type': 'publication',
        'topic_tags': ['products', 'industry', 'policy', 'tools'],
        'trust_tier': 2,
    },
    {
        'canonical_listing_url': 'https://techcrunch.com/category/artificial-intelligence/',
        'confidence_score': 85,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'TechCrunch AI',
        'notes': 'Venture funding, AI startups, commercial products, and executive moves.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'techcrunch',
        'publisher_id': 'techcrunch',
        'publisher_owns_feed': True,
        'source_id': 'techcrunch_ai',
        'source_type': 'publication',
        'topic_tags': ['startups', 'business', 'funding', 'tools'],
        'trust_tier': 2,
    },
    {
        'canonical_listing_url': 'https://arstechnica.com/ai/',
        'confidence_score': 85,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Ars Technica',
        'notes': 'In-depth technical reporting on AI copyright, security vulnerabilities, and chip architecture.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'conde_nast',
        'publisher_id': 'ars_technica',
        'publisher_owns_feed': True,
        'source_id': 'ars_technica',
        'source_type': 'publication',
        'topic_tags': ['security', 'policy', 'infrastructure', 'hardware'],
        'trust_tier': 2,
    },
    {
        'canonical_listing_url': 'https://the-decoder.com/',
        'confidence_score': 80,
        'enabled': True,
        'feed_is_official': True,
        'feed_url': 'https://the-decoder.com/feed/',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'The Decoder',
        'notes': 'Dedicated reporting on LLM evaluations, autonomous agents, and AI startups.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'the_decoder',
        'publisher_id': 'the_decoder',
        'publisher_owns_feed': True,
        'source_id': 'the_decoder',
        'source_type': 'publication',
        'topic_tags': ['models', 'research', 'industry'],
        'trust_tier': 2,
    },
    {
        'canonical_listing_url': 'https://arxiv.org/list/cs.AI/recent',
        'confidence_score': 80,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://rss.arxiv.org/rss/cs.AI',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'arXiv cs.AI',
        'notes': 'Open artificial intelligence preprints. Caution: Not yet peer-reviewed.',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'cornell_arxiv',
        'publisher_id': 'arxiv',
        'publisher_owns_feed': True,
        'source_id': 'arxiv_cs_ai',
        'source_type': 'research',
        'topic_tags': ['research', 'preprints', 'theory'],
        'trust_tier': 3,
    },
    {
        'canonical_listing_url': 'https://arxiv.org/list/cs.LG/recent',
        'confidence_score': 80,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://rss.arxiv.org/rss/cs.LG',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'arXiv cs.LG',
        'notes': 'Machine learning research preprints from arXiv cs.LG. Note: arXiv skips feed publications on Saturday and Sunday (skipDays).',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'cornell_arxiv',
        'publisher_id': 'arxiv',
        'publisher_owns_feed': True,
        'source_id': 'arxiv_cs_lg',
        'source_type': 'research',
        'topic_tags': ['research', 'machine-learning', 'preprints'],
        'trust_tier': 3,
    },
    {
        'canonical_listing_url': 'https://bair.berkeley.edu/blog/',
        'confidence_score': 85,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://bair.berkeley.edu/blog/feed.xml',
        'fetch_method': 'rss',
        'is_official': True,
        'is_primary_source': True,
        'name': 'BAIR Blog',
        'notes': 'Berkeley AI Research laboratory insights on agent systems and reinforcement learning.',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'uc_berkeley',
        'publisher_id': 'bair',
        'publisher_owns_feed': True,
        'source_id': 'bair_blog',
        'source_type': 'research',
        'topic_tags': ['research', 'robotics', 'agents'],
        'trust_tier': 3,
    },
    {
        'canonical_listing_url': 'https://simonwillison.net/',
        'confidence_score': 75,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://simonwillison.net/atom/everything/',
        'fetch_method': 'atom',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Simon Willison Weblog',
        'notes': 'Expert developer commentary, hands-on LLM security research, and practical agent tools.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'simon_willison',
        'publisher_id': 'simon_willison',
        'publisher_owns_feed': True,
        'source_id': 'simon_willison',
        'source_type': 'practitioner',
        'topic_tags': ['tools', 'prompt-injection', 'developers', 'coding'],
        'trust_tier': 4,
    },
    {
        'canonical_listing_url': 'https://importai.substack.com/',
        'confidence_score': 75,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://importai.substack.com/feed',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Import AI',
        'notes': 'Curated analysis by Jack Clark on frontier safety, capability scaling, and international AI governance.',
        'poll_interval_minutes': 120,
        'publisher_group_id': 'import_ai',
        'publisher_id': 'import_ai',
        'publisher_owns_feed': True,
        'source_id': 'import_ai',
        'source_type': 'practitioner',
        'topic_tags': ['policy', 'safety', 'research'],
        'trust_tier': 4,
    },
    {
        'canonical_listing_url': 'https://www.lmsys.org/blog/',
        'confidence_score': 85,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://www.lmsys.org/blog',
        'fetch_method': 'html_page_adapter',
        'is_official': True,
        'is_primary_source': True,
        'name': 'LMSYS Org',
        'notes': 'LMSYS Chatbot Arena benchmarks, leaderboards, and LLM evaluation methodology updates.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'lmsys',
        'publisher_id': 'lmsys',
        'publisher_owns_feed': True,
        'source_id': 'lmsys_org',
        'source_type': 'research',
        'topic_tags': ['benchmarks', 'evaluations', 'leaderboard'],
        'trust_tier': 3,
    },
    {
        'canonical_listing_url': 'https://www.latent.space',
        'confidence_score': 75,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://www.latent.space/feed',
        'fetch_method': 'rss',
        'is_official': False,
        'is_primary_source': False,
        'name': 'Latent Space',
        'notes': 'High-signal AI engineer publication covering infrastructure, models, and industry analysis.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'latent_space',
        'publisher_id': 'latent_space',
        'publisher_owns_feed': True,
        'source_id': 'latent_space',
        'source_type': 'practitioner',
        'topic_tags': ['engineering', 'podcasts', 'analysis'],
        'trust_tier': 4,
    },
    {
        'canonical_listing_url': 'https://huggingface.co/papers',
        'confidence_score': 85,
        'enabled': False,
        'feed_is_official': True,
        'feed_url': 'https://huggingface.co/api/daily_papers',
        'fetch_method': 'json_api_adapter',
        'is_official': False,
        'is_primary_source': True,
        'name': 'Hugging Face Daily Papers',
        'notes': 'Daily curated top research papers and arXiv highlights from the Hugging Face AI community.',
        'poll_interval_minutes': 60,
        'publisher_group_id': 'huggingface',
        'publisher_id': 'huggingface',
        'publisher_owns_feed': True,
        'source_id': 'hf_daily_papers',
        'source_type': 'research',
        'topic_tags': ['papers', 'research', 'preprints'],
        'trust_tier': 3,
    },
]


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


def load_source_registry(filepath=SOURCES_REGISTRY_FILE, include_disabled=False):
  """Loads and validates the centralized source registry, falling back to verified sources if missing.
  By default (include_disabled=False), returns ONLY enabled sources (10 sources).
  When include_disabled=True, returns all 25 configured sources.
  """
  candidates = []
  if os.path.exists(filepath):
    try:
      with open(filepath, "r", encoding="utf-8") as f:
        registry = json.load(f)
      if isinstance(registry, list) and len(registry) > 0:
        candidates = registry
    except Exception as e:
      print(f"⚠️ Error reading {filepath}: {e}", file=sys.stderr)

  if not candidates:
    candidates = FALLBACK_SOURCE_REGISTRY

  valid_sources = []
  for s in candidates:
    is_valid, reason = validate_source_record(s)
    if is_valid:
      if include_disabled or s.get("enabled", True):
        valid_sources.append(s)
    else:
      print(f"⚠️ Skipping invalid source record {s.get('source_id')}: {reason}", file=sys.stderr)

  return valid_sources


def load_all_sources(filepath=SOURCES_REGISTRY_FILE):
  """Loads all configured sources (both enabled and disabled) for validation and auditing."""
  return load_source_registry(filepath=filepath, include_disabled=True)


def normalize_url(raw_url):
  """Performs URL canonicalization: strips tracking parameters and fragments."""
  if not raw_url or not isinstance(raw_url, str):
    return ""
  clean = raw_url.strip()
  if not (clean.startswith("http://") or clean.startswith("https://")):
    return ""
  parsed = urllib.parse.urlparse(clean)
  query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
  tracking_params = {
      "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
      "ref", "ref_src", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"
  }
  filtered_params = {k: v for k, v in query_params.items() if k.lower() not in tracking_params}
  new_query = urllib.parse.urlencode(filtered_params, doseq=True)
  path = parsed.path
  if path != "/" and path.endswith("/"):
    path = path.rstrip("/")
  canonical = urllib.parse.urlunparse((parsed.scheme, parsed.netloc.lower(), path, parsed.params, new_query, ""))
  return canonical


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
# CONDITIONAL HTTP FEED PARSER
# -------------------------------------------------------------
def parse_feed_with_fallback_status(feed_url, timeout=12.0, cache=None):
  """Parses RSS/Atom feeds using conditional HTTP headers (If-None-Match, If-Modified-Since).
  Returns: (entries: list, http_status: int)
  """
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
      ),
      "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
      "Accept-Language": "en-US,en;q=0.9",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
  }

  cached_entry = cache.get(feed_url) if cache else None
  if cached_entry:
    if cached_entry.get("etag"):
      headers["If-None-Match"] = cached_entry["etag"]
    if cached_entry.get("last_modified"):
      headers["If-Modified-Since"] = cached_entry["last_modified"]

  raw_bytes = b""
  http_status = 200
  try:
    req = urllib.request.Request(feed_url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
      http_status = getattr(resp, "status", 200)

      # 304 Not Modified
      if http_status == 304:
        if cached_entry and "cached_items" in cached_entry:
          return cached_entry["cached_items"], 304

      raw_bytes = resp.read()
      if resp.headers.get("Content-Encoding") == "gzip" or raw_bytes.startswith(b"\x1f\x8b"):
        try:
          raw_bytes = gzip.decompress(raw_bytes)
        except Exception:
          pass

      # Update cache headers
      if cache is not None:
        etag = resp.headers.get("ETag")
        last_modified = resp.headers.get("Last-Modified")
        if etag or last_modified:
          if feed_url not in cache:
            cache[feed_url] = {}
          if etag:
            cache[feed_url]["etag"] = etag
          if last_modified:
            cache[feed_url]["last_modified"] = last_modified

  except urllib.error.HTTPError as e:
    if e.code == 304 and cached_entry and "cached_items" in cached_entry:
      return cached_entry["cached_items"], 304
    if feedparser:
      try:
        parsed = feedparser.parse(feed_url)
        if parsed and getattr(parsed, "entries", None):
          return parsed.entries, getattr(parsed, "status", e.code)
      except Exception:
        pass
    raise e
  except Exception as e:
    if feedparser:
      try:
        parsed = feedparser.parse(feed_url)
        if parsed and getattr(parsed, "entries", None):
          return parsed.entries, 200
      except Exception:
        pass
    raise e

  entries = []
  if feedparser:
    parsed = feedparser.parse(raw_bytes)
    if parsed and getattr(parsed, "entries", None):
      entries = parsed.entries

  if not entries:
    # Built-in ElementTree Fallback
    try:
      root = ET.fromstring(raw_bytes)
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
      else:
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
    except Exception:
      pass

  # Store parsed entries in cache
  if cache is not None and entries:
    if feed_url not in cache:
      cache[feed_url] = {}
    cache[feed_url]["cached_items"] = entries

  return entries, http_status


def parse_feed_with_fallback(feed_url, timeout=12.0):
  try:
    entries, _ = parse_feed_with_fallback_status(feed_url, timeout=timeout)
    return entries
  except Exception:
    return []


# -------------------------------------------------------------
# ANTHROPIC HTML PAGE ADAPTER
# -------------------------------------------------------------
def fetch_anthropic_official_news_with_status(timeout=12.0):
  url = "https://www.anthropic.com/news"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
      ),
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  }
  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, timeout=timeout) as resp:
    status_code = getattr(resp, "status", 200)
    raw_html = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip" or raw_html.startswith(b"\x1f\x8b"):
      raw_html = gzip.decompress(raw_html)
    html_text = raw_html.decode("utf-8", errors="replace")

  article_pattern = re.compile(r'<a\s+[^>]*href=["\'](/news/[^"\']+)["\'][^>]*>(.*?)</a>', re.DOTALL | re.IGNORECASE)
  entries = []
  seen_links = set()

  for match in article_pattern.finditer(html_text):
    path = match.group(1).split("?")[0].split("#")[0]
    if path == "/news" or path.endswith("/news/"):
      continue
    full_url = f"https://www.anthropic.com{path}"
    if full_url in seen_links:
      continue
    seen_links.add(full_url)
    slug = path.strip("/").split("/")[-1]
    title = slug.replace("-", " ").title()
    entries.append({
        "title": title,
        "link": full_url,
        "summary": f"Official news announcement from Anthropic: {title}.",
        "published": "Recent",
    })

  return entries, status_code


def fetch_anthropic_official_news(timeout=12.0):
  try:
    entries, _ = fetch_anthropic_official_news_with_status(timeout=timeout)
    return entries
  except Exception:
    return []


# -------------------------------------------------------------
# LMSYS HTML PAGE ADAPTER
# -------------------------------------------------------------
def fetch_lmsys_official_news_with_status(timeout=12.0):
  """Fetches and parses LMSYS blog posts directly from Next.js server payload."""
  url = "https://www.lmsys.org/blog"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
      ),
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9",
  }
  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, timeout=timeout) as resp:
    status_code = getattr(resp, "status", 200)
    raw_html = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip" or raw_html.startswith(b"\x1f\x8b"):
      raw_html = gzip.decompress(raw_html)
    html_text = raw_html.decode("utf-8", errors="replace")

  pattern = re.compile(
      r'\{\\?"slug\\?":\\?"([^\\"]+)\\?",\\?"title\\?":\\?"([^\\"]+)\\?"[^}]*?\\?"date\\?":\\?"([^\\"]+)\\?"[^}]*?\\?"excerpt\\?":\\?"([^\\"]+)\\?"'
  )
  matches = pattern.findall(html_text)
  entries = []
  seen_links = set()
  for slug, title, dt_str, excerpt in matches:
    clean_slug = slug.strip()
    full_url = f"https://www.lmsys.org/blog/{clean_slug}"
    if full_url in seen_links:
      continue
    seen_links.add(full_url)
    entries.append({
        "title": html.unescape(title).strip(),
        "link": full_url,
        "summary": html.unescape(excerpt).strip(),
        "published": dt_str.strip(),
    })
    if len(entries) >= 20:
      break

  return entries, status_code


def fetch_lmsys_official_news(timeout=12.0):
  try:
    entries, _ = fetch_lmsys_official_news_with_status(timeout=timeout)
    return entries
  except Exception:
    return []


# -------------------------------------------------------------
# HUGGING FACE DAILY PAPERS ADAPTER
# -------------------------------------------------------------
def fetch_hf_daily_papers_with_status(timeout=12.0):
  """Fetches curated AI research papers from Hugging Face Daily Papers open API."""
  url = "https://huggingface.co/api/daily_papers"
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
      ),
      "Accept": "application/json",
  }
  req = urllib.request.Request(url, headers=headers)
  with urllib.request.urlopen(req, timeout=timeout) as resp:
    status_code = getattr(resp, "status", 200)
    raw_bytes = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip" or raw_bytes.startswith(b"\x1f\x8b"):
      raw_bytes = gzip.decompress(raw_bytes)
    data = json.loads(raw_bytes.decode("utf-8", errors="replace"))

  entries = []
  if isinstance(data, list):
    for it in data[:25]:
      p = it.get("paper", {})
      pid = p.get("id")
      title = p.get("title")
      if not pid or not title:
        continue
      summary = p.get("summary") or ""
      pub_dt = it.get("publishedAt") or ""
      entries.append({
          "title": html.unescape(title).strip(),
          "link": f"https://huggingface.co/papers/{pid}",
          "summary": html.unescape(summary).strip(),
          "published": pub_dt,
      })

  return entries, status_code


def fetch_hf_daily_papers(timeout=12.0):
  try:
    entries, _ = fetch_hf_daily_papers_with_status(timeout=timeout)
    return entries
  except Exception:
    return []


# -------------------------------------------------------------
# FETCH WITH RETRY & TELEMETRY
# -------------------------------------------------------------
def fetch_source_feed(source, timeout=12.0, cache=None, max_retries=2):
  """Fetches a single source feed with retry logic and detailed health telemetry.
  Returns: (entries: list, health_record: dict)
  """
  source_id = source.get("source_id", "unknown")
  name = source.get("name", source_id)
  feed_url = source.get("feed_url", "")
  fetch_method = source.get("fetch_method", "rss")
  now_iso = datetime.now(timezone.utc).isoformat()

  health = {
      "source_id": source_id,
      "name": name,
      "last_attempt_at": now_iso,
      "last_success_at": None,
      "fetch_status": "failed",
      "http_status": None,
      "articles_received": 0,
      "articles_accepted": 0,
      "error_type": None,
      "error_message": None,
  }

  entries = []
  last_exception = None

  for attempt in range(max_retries + 1):
    try:
      if fetch_method == "html_page_adapter" and source_id == "anthropic_news":
        entries, status = fetch_anthropic_official_news_with_status(timeout=timeout)
        health["http_status"] = status
      elif fetch_method == "html_page_adapter" and source_id == "lmsys_org":
        entries, status = fetch_lmsys_official_news_with_status(timeout=timeout)
        health["http_status"] = status
      elif (fetch_method == "json_api_adapter" or source_id == "hf_daily_papers"):
        entries, status = fetch_hf_daily_papers_with_status(timeout=timeout)
        health["http_status"] = status
      elif fetch_method == "rsshub":
        from .rsshub_collector import fetch_rsshub_feed
        entries, status = fetch_rsshub_feed(source, timeout=timeout, cache=cache)
        health["http_status"] = status
      elif feed_url:
        entries, status = parse_feed_with_fallback_status(feed_url, timeout=timeout, cache=cache)
        health["http_status"] = status
      else:
        raise ValueError("Source has no feed_url or recognized fetch_method")

      health["articles_received"] = len(entries)
      health["last_success_at"] = now_iso
      health["fetch_status"] = "success" if (entries or health["http_status"] == 304) else "empty"
      health["error_type"] = None
      health["error_message"] = None
      return entries, health

    except urllib.error.HTTPError as e:
      last_exception = e
      health["http_status"] = e.code
      health["error_type"] = "HTTPError"
      health["error_message"] = f"HTTP {e.code}: {e.reason}"
      # Only retry on 5xx errors
      if 500 <= e.code < 600 and attempt < max_retries:
        time.sleep(0.5 * (2 ** attempt))
        continue
      break

    except (urllib.error.URLError, socket.timeout) as e:
      last_exception = e
      health["error_type"] = "Timeout" if isinstance(e, socket.timeout) else "URLError"
      health["error_message"] = str(e)
      if attempt < max_retries:
        time.sleep(0.5 * (2 ** attempt))
        continue
      break

    except Exception as e:
      last_exception = e
      health["error_type"] = type(e).__name__
      health["error_message"] = str(e)
      break

  return entries, health


# -------------------------------------------------------------
# CONCURRENT COLLECTION & PIPELINE INGESTION
# -------------------------------------------------------------
def collect_fresh_news(max_age_hours=72, max_per_source=15, return_health=False):
  """Collects fresh news across all sources using ThreadPoolExecutor(max_workers=10),
  applying deduplication, freshness filtering, relevance checks, and telemetry tracking.
  """
  from .scorer import evaluate_article_relevance, sanitize_and_format_summary

  registry = load_source_registry()
  all_articles = []
  seen_urls = set()
  now = datetime.now(timezone.utc)
  cutoff_time = now - timedelta(hours=max_age_hours)

  feed_cache = load_feed_cache()
  source_health_details = []
  total_received = 0
  rejected_relevance = 0
  rejected_freshness = 0
  fresh_accepted = 0
  successful_fetches = 0
  failed_fetches = 0
  valid_empty = 0
  enabled_count = 0

  enabled_sources = [s for s in registry if s.get("enabled", True)]
  print(f"📡 Concurrently ingesting from {len(enabled_sources)} verified sources (Pool: 10 workers)...")

  # Concurrently fetch all enabled source feeds
  fetched_results = {}
  with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    future_to_source = {
        executor.submit(fetch_source_feed, s, timeout=12.0, cache=feed_cache): s
        for s in enabled_sources
    }
    for future in concurrent.futures.as_completed(future_to_source):
      s = future_to_source[future]
      try:
        entries, health = future.result()
        fetched_results[s["source_id"]] = (entries, health)
      except Exception as e:
        fetched_results[s["source_id"]] = ([], {
            "source_id": s["source_id"],
            "name": s.get("name", s["source_id"]),
            "fetch_status": "failed",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "articles_received": 0,
            "articles_accepted": 0,
            "last_attempt_at": now.isoformat(),
            "last_success_at": None,
            "http_status": None,
        })

  # Save updated feed cache
  save_feed_cache(feed_cache)

  # Process results in deterministic registry order
  for source in enabled_sources:
    enabled_count += 1
    source_id = source["source_id"]
    name = source["name"]
    trust_tier = source.get("trust_tier", 2)
    is_official = source.get("is_official", False)
    source_max = source.get("max_items", max_per_source)

    entries, health = fetched_results.get(source_id, ([], {}))

    if health.get("fetch_status") == "failed":
      failed_fetches += 1
      print(f"   ⚠️ Feed error for {name}: {health.get('error_type')} - {health.get('error_message')}")
    else:
      successful_fetches += 1
      if health.get("fetch_status") == "empty":
        valid_empty += 1

    total_received += len(entries)
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

      if source.get("source_type") == "unofficial_discovery":
        parsed_target = urllib.parse.urlparse(clean_url)
        if "anthropic.com" not in parsed_target.netloc.lower():
          continue

      max_age_cutoff = cutoff_time
      if is_official and trust_tier == 1:
        max_age_cutoff = now - timedelta(days=14)
      if pub_dt and pub_dt < max_age_cutoff:
        rejected_freshness += 1
        continue

      summary = entry.get("summary") or entry.get("description") or ""
      clean_summary = sanitize_and_format_summary(summary, title)

      is_rel, rel_score, rel_reason = evaluate_article_relevance(
          title, clean_summary, source_name=name, source_type=source.get("source_type", "publication"), is_official=is_official
      )
      if not is_rel:
        rejected_relevance += 1
        continue

      article_id = generate_article_id(source_id, clean_url)
      pub_display = pub_dt.strftime("%b %d, %H:%M UTC") if pub_dt else "Recent"

      art_dict = {
          "article_id": article_id,
          "title": title,
          "summary": clean_summary,
          "link": clean_url,
          "source": name,
          "source_id": source_id,
          "publisher_id": source.get("publisher_id", source_id),
          "publisher_group_id": source.get("publisher_group_id", source_id),
          "is_primary_source": source.get("is_primary_source", True),
          "publisher_owns_feed": source.get("publisher_owns_feed", True),
          "source_type": source.get("source_type", "publication"),
          "trust_tier": trust_tier,
          "is_official": is_official,
          "published": pub_display,
          "published_at": pub_dt.isoformat() if pub_dt else None,
          "published_datetime": pub_dt,
          "relevance_score": rel_score,
      }
      seen_urls.add(clean_url)
      source_articles.append(art_dict)
      all_articles.append(art_dict)
      fresh_accepted += 1

    health["articles_accepted"] = len(source_articles)
    source_health_details.append(health)

  # Aggregate status determination
  if enabled_count > 0 and failed_fetches == enabled_count:
    status_label = "total_failure"
  elif failed_fetches > 0:
    status_label = "degraded"
  elif total_received > 0 and len(all_articles) == 0:
    status_label = "all_content_filtered"
  elif len(all_articles) == 0:
    status_label = "valid_zero_articles"
  else:
    status_label = "healthy"

  health_summary = {
      "status": status_label,
      "configured_sources_count": len(registry),
      "enabled_sources_count": enabled_count,
      "successful_fetches_count": successful_fetches,
      "failed_fetches_count": failed_fetches,
      "valid_empty_sources_count": valid_empty,
      "total_articles_received": total_received,
      "rejected_by_relevance_count": rejected_relevance,
      "rejected_by_freshness_count": rejected_freshness,
      "fresh_articles_accepted_count": fresh_accepted,
      "unique_article_count": len(all_articles),
  }

  print(f"✅ Ingestion complete: {len(all_articles)} fresh articles accepted across {successful_fetches}/{enabled_count} healthy feeds (status: {status_label}).")

  if return_health:
    return all_articles, health_summary, source_health_details
  return all_articles
