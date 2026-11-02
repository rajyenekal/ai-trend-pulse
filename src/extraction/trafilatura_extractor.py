"""
src.extraction.trafilatura_extractor - Clean Article Extraction Interface
Wraps pipeline.extractor for modular source ingestion.
"""

from __future__ import annotations

from pipeline.extractor import (
    ARTICLE_CACHE_FILE,
    DEFAULT_EXTRACTION_TIMEOUT,
    DEFAULT_MAX_WORKERS,
    load_article_cache,
    save_article_cache,
    fetch_raw_html,
    extract_article_content,
    extract_articles_batch,
)

def extract_article(url: str, fallback_summary: str = "", timeout: float = DEFAULT_EXTRACTION_TIMEOUT) -> str:
  """Extracts clean article text from a URL with fallback to the existing summary.
  Returns the extracted or fallback text string.
  """
  result = extract_article_content(url, fallback_summary=fallback_summary, timeout=timeout)
  return result.get("text") or fallback_summary
