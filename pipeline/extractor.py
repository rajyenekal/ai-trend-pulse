"""
pipeline.extractor - Clean Article Extraction with Trafilatura, Local Caching, and Fault-Tolerant Fallbacks.
"""

from __future__ import annotations

from datetime import datetime, timezone
import glob
import gzip
import io
import json
import logging
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import concurrent.futures

# Auto-detect local virtualenv site-packages if running under system python
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

try:
  import trafilatura
except ImportError:
  trafilatura = None

logger = logging.getLogger("pipeline.extractor")

ARTICLE_CACHE_FILE = ".article_cache.json"
DEFAULT_EXTRACTION_TIMEOUT = 6.0
DEFAULT_MAX_WORKERS = 5
MAX_CACHE_ENTRIES = 1200
USER_AGENT = "Mozilla/5.0 (compatible; AITrendPulse/2.1; +https://github.com/rajyenekal/ai-trend-pulse)"


def load_article_cache(cache_file=ARTICLE_CACHE_FILE):
  """Loads the article extraction cache from disk."""
  if os.path.exists(cache_file):
    try:
      with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          return data
    except Exception as e:
      logger.warning("Failed to load article cache from %s: %s", cache_file, e)
      return {}
  return {}


def save_article_cache(cache_data, cache_file=ARTICLE_CACHE_FILE):
  """Atomically writes the article extraction cache to disk, pruning oldest entries if necessary."""
  if not isinstance(cache_data, dict):
    return

  # Prune cache if it exceeds MAX_CACHE_ENTRIES
  if len(cache_data) > MAX_CACHE_ENTRIES:
    # Retain the most recent entries
    sorted_items = sorted(
        cache_data.items(),
        key=lambda item: item[1].get("extracted_at", ""),
        reverse=True
    )
    cache_data = dict(sorted_items[:MAX_CACHE_ENTRIES])

  tmp_file = f"{cache_file}.tmp"
  try:
    with open(tmp_file, "w", encoding="utf-8") as f:
      json.dump(cache_data, f, indent=2)
    os.replace(tmp_file, cache_file)
  except Exception as e:
    logger.warning("Failed to save article cache to %s: %s", cache_file, e)
    if os.path.exists(tmp_file):
      try:
        os.remove(tmp_file)
      except Exception:
        pass


def fetch_raw_html(url, timeout=DEFAULT_EXTRACTION_TIMEOUT):
  """Fetches raw HTML for a webpage with strict timeouts, standard headers, and gzip decompression.
  Returns: (html_str: str | None, status_code: int | None, error_message: str | None)
  """
  req = urllib.request.Request(
      url,
      headers={
          "User-Agent": USER_AGENT,
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Encoding": "gzip, deflate",
          "Accept-Language": "en-US,en;q=0.9",
      },
  )

  # SSL context with certificate verification fallback
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  try:
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
      status_code = getattr(response, "status", 200)
      raw_bytes = response.read()

      encoding = response.headers.get("Content-Encoding", "").lower()
      if "gzip" in encoding:
        try:
          raw_bytes = gzip.decompress(raw_bytes)
        except Exception:
          pass

      # Decode bytes to text
      charset = "utf-8"
      content_type = response.headers.get("Content-Type", "")
      match = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
      if match:
        charset = match.group(1).lower()

      try:
        html_str = raw_bytes.decode(charset, errors="replace")
      except (LookupError, UnicodeDecodeError):
        html_str = raw_bytes.decode("utf-8", errors="replace")

      return html_str, status_code, None

  except urllib.error.HTTPError as e:
    return None, e.code, f"HTTPError {e.code}: {e.reason}"
  except urllib.error.URLError as e:
    return None, None, f"URLError: {e.reason}"
  except socket.timeout:
    return None, None, "Socket timeout"
  except Exception as e:
    return None, None, f"{type(e).__name__}: {str(e)}"


def extract_article_content(
    url,
    fallback_summary="",
    timeout=DEFAULT_EXTRACTION_TIMEOUT,
    cache=None,
    force_refresh=False,
):
  """Extracts clean article text and metadata using Trafilatura with cache lookup and safe fallback.
  Guarantees:
  - If URL is invalid, empty, or extraction fails, returns fallback_summary.
  - If Trafilatura is not installed, returns fallback_summary with 'library_unavailable'.
  - Never raises an unhandled exception or interrupts the caller.
  """
  now_iso = datetime.now(timezone.utc).isoformat()
  fallback_text = (fallback_summary or "").strip()

  if not url or not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
    return {
        "url": url or "",
        "text": fallback_text,
        "title": None,
        "author": None,
        "published_date": None,
        "extraction_status": "invalid_url",
        "extracted_at": now_iso,
        "content_length": len(fallback_text),
    }

  # 1. Check in-memory / disk cache
  if cache is not None and not force_refresh:
    cached_record = cache.get(url)
    if cached_record and isinstance(cached_record, dict) and cached_record.get("text"):
      cached_copy = dict(cached_record)
      cached_copy["extraction_status"] = "cached"
      return cached_copy

  # 2. Check if trafilatura is available
  if trafilatura is None:
    record = {
        "url": url,
        "text": fallback_text,
        "title": None,
        "author": None,
        "published_date": None,
        "extraction_status": "library_unavailable",
        "extracted_at": now_iso,
        "content_length": len(fallback_text),
    }
    if cache is not None:
      cache[url] = record
    return record

  # 3. Fetch raw HTML with strict timeout
  html_str, http_status, err_msg = fetch_raw_html(url, timeout=timeout)
  if not html_str:
    record = {
        "url": url,
        "text": fallback_text,
        "title": None,
        "author": None,
        "published_date": None,
        "extraction_status": "fetch_failed" if not fallback_text else "fallback_summary",
        "extracted_at": now_iso,
        "content_length": len(fallback_text),
        "error": err_msg,
    }
    if cache is not None:
      cache[url] = record
    return record

  # 4. Extract clean article text with Trafilatura
  try:
    extracted_text = trafilatura.extract(
        html_str,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )

    extracted_title = None
    extracted_author = None
    extracted_date = None

    try:
      metadata = trafilatura.extract_metadata(html_str)
      if metadata:
        extracted_title = getattr(metadata, "title", None)
        extracted_author = getattr(metadata, "author", None)
        extracted_date = getattr(metadata, "date", None)
    except Exception:
      pass

    # Validate extracted text quality
    if extracted_text and len(extracted_text.strip()) >= 50:
      clean_extracted = re.sub(r"\n{3,}", "\n\n", extracted_text.strip())
      record = {
          "url": url,
          "text": clean_extracted,
          "title": extracted_title,
          "author": extracted_author,
          "published_date": str(extracted_date) if extracted_date else None,
          "extraction_status": "extracted",
          "extracted_at": now_iso,
          "content_length": len(clean_extracted),
      }
    else:
      # Extracted text too short or empty -> fallback to summary
      record = {
          "url": url,
          "text": fallback_text,
          "title": extracted_title,
          "author": extracted_author,
          "published_date": str(extracted_date) if extracted_date else None,
          "extraction_status": "fallback_summary",
          "extracted_at": now_iso,
          "content_length": len(fallback_text),
      }

    if cache is not None:
      cache[url] = record
    return record

  except Exception as e:
    logger.warning("Trafilatura extraction error on %s: %s", url, e)
    record = {
        "url": url,
        "text": fallback_text,
        "title": None,
        "author": None,
        "published_date": None,
        "extraction_status": "fallback_summary",
        "extracted_at": now_iso,
        "content_length": len(fallback_text),
        "error": str(e),
    }
    if cache is not None:
      cache[url] = record
    return record


def extract_articles_batch(
    articles,
    max_workers=DEFAULT_MAX_WORKERS,
    timeout=DEFAULT_EXTRACTION_TIMEOUT,
    cache_file=ARTICLE_CACHE_FILE,
):
  """Concurrently extracts full article text for a list of article dicts using ThreadPoolExecutor.
  Updates each article dict in place with 'full_text' and 'extraction_status'.
  Preserves existing 'summary' without disruption.
  Atomically updates and saves the article cache upon completion.
  """
  if not articles:
    return articles

  cache = load_article_cache(cache_file)
  new_cache_entries = 0

  def _process_single(article):
    url = article.get("link") or article.get("url") or ""
    summary = article.get("summary") or ""
    result = extract_article_content(url, fallback_summary=summary, timeout=timeout, cache=cache)
    return article, result

  with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(_process_single, a) for a in articles]
    for future in concurrent.futures.as_completed(futures):
      try:
        art, res = future.result()
        art["full_text"] = res.get("text", art.get("summary", ""))
        art["extraction_status"] = res.get("extraction_status", "unknown")
        if res.get("author"):
          art["author"] = res.get("author")
        if res.get("extraction_status") == "extracted":
          new_cache_entries += 1
      except Exception as e:
        logger.warning("Error in batch article extraction: %s", e)

  # Atomically save updated cache
  save_article_cache(cache, cache_file)
  return articles
