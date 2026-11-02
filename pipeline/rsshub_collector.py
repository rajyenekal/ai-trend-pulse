"""
pipeline.rsshub_collector - Optional RSSHub Feed Collector with Verified Route Handling.

Fetches and normalizes feeds from RSSHub instances for routes without native RSS.
Non-blocking: failures in optional RSSHub routes do not stop core pipeline ingestion.
"""

from __future__ import annotations

from datetime import datetime, timezone
import glob
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
import xml.etree.ElementTree as ET

# Auto-detect local virtualenv site-packages if running under system python
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

try:
  import feedparser
except ImportError:
  feedparser = None

logger = logging.getLogger("pipeline.rsshub_collector")

DEFAULT_RSSHUB_BASE_URL = "https://rsshub.app"
USER_AGENT = "Mozilla/5.0 (compatible; AITrendPulse/2.1; +https://github.com/rajyenekal/ai-trend-pulse)"


def build_rsshub_feed_url(source: dict) -> str:
  """Builds a verified RSSHub URL from source configuration.
  Supports direct feed_url or route path combination with configured RSSHUB_BASE_URL.
  """
  feed_url = source.get("feed_url")
  if feed_url and (feed_url.startswith("http://") or feed_url.startswith("https://")):
    return feed_url

  route = source.get("rsshub_route") or ""
  if not route:
    return ""

  base_url = os.environ.get("RSSHUB_BASE_URL", DEFAULT_RSSHUB_BASE_URL).rstrip("/")
  clean_route = "/" + route.lstrip("/")
  return f"{base_url}{clean_route}"


def parse_rsshub_xml_fallback(xml_content: str) -> list[dict]:
  """Fallback XML parser for RSS/Atom feeds when feedparser is unavailable."""
  entries = []
  try:
    root = ET.fromstring(xml_content)
  except Exception as e:
    logger.warning("Failed to parse RSSHub XML with ElementTree: %s", e)
    return entries

  # Check RSS 2.0 channel items
  channel = root.find("channel")
  if channel is not None:
    for item in channel.findall("item"):
      title = (item.findtext("title") or "").strip()
      link = (item.findtext("link") or "").strip()
      desc = (item.findtext("description") or "").strip()
      pub_date = (item.findtext("pubDate") or "").strip()
      if title and link:
        entries.append({
            "title": title,
            "link": link,
            "summary": desc,
            "published": pub_date,
        })
    return entries

  # Check Atom entries
  atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
  for entry in root.findall("atom:entry", atom_ns) or root.findall("entry"):
    title = (entry.findtext("atom:title", namespaces=atom_ns) or entry.findtext("title") or "").strip()
    link_el = entry.find("atom:link", namespaces=atom_ns) or entry.find("link")
    link = link_el.get("href", "") if link_el is not None else ""
    summary = (entry.findtext("atom:summary", namespaces=atom_ns) or entry.findtext("summary") or "").strip()
    pub_date = (entry.findtext("atom:published", namespaces=atom_ns) or entry.findtext("atom:updated", namespaces=atom_ns) or "").strip()
    if title and link:
      entries.append({
          "title": title,
          "link": link,
          "summary": summary,
          "published": pub_date,
      })

  return entries


def fetch_rsshub_feed(source: dict, timeout: float = 10.0, cache: dict = None) -> tuple[list[dict], int | None]:
  """Fetches and parses an RSSHub feed for a configured source.
  Returns: (entries: list[dict], http_status: int | None)
  Guaranteed not to raise unhandled exceptions; returns empty list on network or parse failure.
  """
  feed_url = build_rsshub_feed_url(source)
  if not feed_url:
    logger.warning("Source %s has no valid RSSHub feed URL or route", source.get("source_id"))
    return [], 400

  req = urllib.request.Request(
      feed_url,
      headers={
          "User-Agent": USER_AGENT,
          "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
      },
  )

  # Check HTTP conditional cache (ETag / Last-Modified)
  cache_key = f"rsshub_{feed_url}"
  cached_entry = cache.get(cache_key) if cache is not None else None
  if cached_entry:
    if cached_entry.get("etag"):
      req.add_header("If-None-Match", cached_entry["etag"])
    if cached_entry.get("last_modified"):
      req.add_header("If-Modified-Since", cached_entry["last_modified"])

  # Standard SSL context with certificate and hostname verification
  ctx = ssl.create_default_context()
  try:
    import certifi
    ctx.load_verify_locations(cafile=certifi.where())
  except Exception:
    pass

  try:
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
      status = resp.status
      if status == 304 and cached_entry:
        return cached_entry.get("entries", []), 304

      raw_bytes = resp.read()
      etag = resp.headers.get("ETag")
      last_modified = resp.headers.get("Last-Modified")

      # Parse content
      text = raw_bytes.decode("utf-8", errors="replace")
      entries = []

      if feedparser:
        parsed = feedparser.parse(text)
        for e in parsed.entries:
          title = getattr(e, "title", "").strip()
          link = getattr(e, "link", "").strip()
          summary = getattr(e, "summary", getattr(e, "description", "")).strip()
          published = getattr(e, "published", getattr(e, "updated", "")).strip()
          if title and link:
            entries.append({
                "title": title,
                "link": link,
                "summary": summary,
                "published": published,
            })
      else:
        entries = parse_rsshub_xml_fallback(text)

      # Update cache
      if cache is not None:
        cache[cache_key] = {
            "etag": etag,
            "last_modified": last_modified,
            "entries": entries,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

      return entries, status

  except urllib.error.HTTPError as e:
    if e.code == 304 and cached_entry:
      return cached_entry.get("entries", []), 304
    logger.warning("RSSHub HTTPError for %s (%s): %s", source.get("source_id"), feed_url, e)
    return [], e.code
  except Exception as e:
    logger.warning("RSSHub fetch failed for %s (%s): %s", source.get("source_id"), feed_url, e)
    return [], None

