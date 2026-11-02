"""
pipeline.browser_fallback - Selective Browser Fallback with Crawl4AI.

Used ONLY for configured JavaScript-rendered sources where Trafilatura cannot extract content.
Controlled via ENABLE_CRAWL4AI environment variable (defaults to false).
Non-blocking: browser errors or timeouts fall back gracefully to the RSS summary without halting the pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

logger = logging.getLogger("pipeline.browser_fallback")

try:
  import crawl4ai
except ImportError:
  crawl4ai = None

DEFAULT_BROWSER_TIMEOUT = 12.0


def is_crawl4ai_available() -> bool:
  """Returns True only if crawl4ai is installed and ENABLE_CRAWL4AI is enabled."""
  enabled_flag = os.environ.get("ENABLE_CRAWL4AI", "false").lower() in ("true", "1", "yes")
  return bool(crawl4ai and enabled_flag)


async def _async_crawl_url(url: str, timeout: float = DEFAULT_BROWSER_TIMEOUT) -> str | None:
  """Asynchronously crawls a page using Crawl4AI AsyncWebCrawler."""
  if not crawl4ai:
    return None

  try:
    from crawl4ai import AsyncWebCrawler
    async with AsyncWebCrawler(verbose=False) as crawler:
      result = await asyncio.wait_for(crawler.arun(url=url), timeout=timeout)
      if result and getattr(result, "markdown", None):
        return result.markdown.strip()
      if result and getattr(result, "text", None):
        return result.text.strip()
  except asyncio.TimeoutError:
    logger.warning("Crawl4AI browser crawl timed out for %s after %.1fs", url, timeout)
  except Exception as e:
    logger.warning("Crawl4AI browser crawl error for %s: %s", url, e)
  return None


def extract_with_crawl4ai(url: str, timeout: float = DEFAULT_BROWSER_TIMEOUT) -> tuple[str | None, str]:
  """Synchronous entry point for selective Crawl4AI browser extraction.
  Returns: (text: str | None, status: str)
  Guaranteed not to raise exceptions.
  """
  if not is_crawl4ai_available():
    return None, "crawl4ai_disabled"

  try:
    # Run in asyncio event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
      text = loop.run_until_complete(_async_crawl_url(url, timeout=timeout))
      if text and len(text) >= 50:
        return text, "crawl4ai_extracted"
      return None, "crawl4ai_empty"
    finally:
      loop.close()
  except Exception as e:
    logger.warning("Failed running Crawl4AI loop for %s: %s", url, e)
    return None, "crawl4ai_failed"
