"""
tests.test_source_expansion - Unit Tests for Phase 4: RSSHub Feed Expansion and Crawl4AI Browser Fallback.
"""

from __future__ import annotations

import glob
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Auto-detect local virtualenv site-packages if running under system python
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

from pipeline.rsshub_collector import (
    build_rsshub_feed_url,
    parse_rsshub_xml_fallback,
    fetch_rsshub_feed,
)
from pipeline.browser_fallback import (
    is_crawl4ai_available,
    extract_with_crawl4ai,
)
from pipeline.extractor import extract_article_content


class TestRSSHubCollector(unittest.TestCase):

  def test_build_rsshub_feed_url_direct(self):
    source = {"feed_url": "https://custom-rsshub.example/route"}
    self.assertEqual(build_rsshub_feed_url(source), "https://custom-rsshub.example/route")

  def test_build_rsshub_feed_url_from_route(self):
    source = {"rsshub_route": "/huggingface/blog"}
    url = build_rsshub_feed_url(source)
    self.assertIn("https://rsshub.app/huggingface/blog", url)

  def test_parse_rsshub_xml_fallback(self):
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>RSSHub Test Feed</title>
        <item>
          <title>DeepSeek Announces V3 Architecture</title>
          <link>https://example.com/deepseek-v3</link>
          <description>DeepSeek V3 achieves frontier efficiency.</description>
          <pubDate>Mon, 02 Nov 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    entries = parse_rsshub_xml_fallback(sample_xml)
    self.assertEqual(len(entries), 1)
    self.assertEqual(entries[0]["title"], "DeepSeek Announces V3 Architecture")
    self.assertEqual(entries[0]["link"], "https://example.com/deepseek-v3")
    self.assertIn("frontier efficiency", entries[0]["summary"])

  def test_fetch_rsshub_feed_failure_non_blocking(self):
    source = {
        "source_id": "test_rsshub",
        "rsshub_route": "/invalid/route",
    }
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
      entries, status = fetch_rsshub_feed(source, timeout=1.0)
      self.assertEqual(entries, [])
      self.assertIsNone(status)


class TestCrawl4AIFallback(unittest.TestCase):

  def test_disabled_by_default(self):
    with patch.dict(os.environ, {"ENABLE_CRAWL4AI": "false"}):
      self.assertFalse(is_crawl4ai_available())
      text, status = extract_with_crawl4ai("https://example.com")
      self.assertIsNone(text)
      self.assertEqual(status, "crawl4ai_disabled")

  def test_enabled_mock_extraction(self):
    with patch.dict(os.environ, {"ENABLE_CRAWL4AI": "true"}), \
         patch("pipeline.browser_fallback.crawl4ai", MagicMock()), \
         patch("pipeline.browser_fallback._async_crawl_url", return_value="Rendered content from Crawl4AI browser exceeding minimum required extraction character count"):
      text, status = extract_with_crawl4ai("https://example.com/js-app")
      self.assertEqual(status, "crawl4ai_extracted")
      self.assertIn("Rendered content", text)

  def test_trafilatura_fallback_to_crawl4ai_when_empty(self):
    empty_html = "<html><body><div id='root'></div></body></html>"
    with patch("pipeline.extractor.fetch_raw_html", return_value=(empty_html, 200, None)), \
         patch("pipeline.extractor.trafilatura.extract", return_value=""), \
         patch("pipeline.browser_fallback.is_crawl4ai_available", return_value=True), \
         patch("pipeline.browser_fallback.extract_with_crawl4ai", return_value=("Browser extracted clean article text that exceeds minimum length", "crawl4ai_extracted")):
      res = extract_article_content("https://example.com/spa-article", fallback_summary="Summary")
      self.assertEqual(res["extraction_status"], "crawl4ai_extracted")
      self.assertIn("Browser extracted", res["text"])


if __name__ == "__main__":
  unittest.main()
