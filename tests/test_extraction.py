"""
tests.test_extraction - Unit Tests for Trafilatura Article Extraction, Caching, and Fallbacks.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import json
import tempfile
import sys
import glob

# Auto-detect local virtualenv site-packages if running under system python
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

from pipeline.extractor import (
    load_article_cache,
    save_article_cache,
    fetch_raw_html,
    extract_article_content,
    extract_articles_batch,
    MAX_CACHE_ENTRIES,
)


class TestTrafilaturaExtraction(unittest.TestCase):

  def setUp(self):
    self.sample_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Anthropic Introduces Claude 3.5 Sonnet</title>
        <meta name="author" content="Anthropic Research Team">
      </head>
      <body>
        <header>
          <nav><a href="/">Home</a><a href="/pricing">Pricing</a></nav>
        </header>
        <article>
          <h1>Anthropic Introduces Claude 3.5 Sonnet</h1>
          <p>Today, we are announcing Claude 3.5 Sonnet, our latest frontier AI model that delivers groundbreaking performance across coding, reasoning, and visual perception benchmarks.</p>
          <p>Claude 3.5 Sonnet operates at twice the speed of Claude 3 Opus while matching or exceeding industry-leading accuracy across graduate-level reasoning evaluations.</p>
        </article>
        <footer>
          <p>Copyright 2026 Anthropic PBC. All rights reserved.</p>
        </footer>
      </body>
    </html>
    """

  def test_extract_clean_html_success(self):
    with patch("pipeline.extractor.fetch_raw_html", return_value=(self.sample_html, 200, None)):
      res = extract_article_content(
          "https://www.anthropic.com/news/claude-3-5-sonnet",
          fallback_summary="Fallback summary text.",
          timeout=5.0,
      )
      self.assertEqual(res["url"], "https://www.anthropic.com/news/claude-3-5-sonnet")
      self.assertEqual(res["extraction_status"], "extracted")
      self.assertIn("Claude 3.5 Sonnet", res["text"])
      self.assertIn("groundbreaking performance", res["text"])
      self.assertNotIn("Copyright 2026", res["text"])  # footer stripped
      self.assertNotIn("Pricing", res["text"])  # nav stripped
      self.assertGreater(res["content_length"], 50)

  def test_cache_lookup_avoids_network(self):
    cache = {
        "https://example.com/cached-article": {
            "url": "https://example.com/cached-article",
            "text": "Previously extracted high-quality article content from cache.",
            "title": "Cached Title",
            "author": "Cache Author",
            "published_date": "2026-11-02",
            "extraction_status": "extracted",
            "extracted_at": "2026-11-02T08:00:00Z",
            "content_length": 62,
        }
    }
    with patch("pipeline.extractor.fetch_raw_html") as mock_fetch:
      res = extract_article_content(
          "https://example.com/cached-article",
          fallback_summary="Fallback summary.",
          cache=cache,
      )
      mock_fetch.assert_not_called()
      self.assertEqual(res["extraction_status"], "cached")
      self.assertEqual(res["text"], "Previously extracted high-quality article content from cache.")

  def test_fetch_failure_falls_back_to_summary(self):
    with patch("pipeline.extractor.fetch_raw_html", return_value=(None, 404, "HTTPError 404: Not Found")):
      res = extract_article_content(
          "https://example.com/missing-page",
          fallback_summary="Reliable fallback summary from RSS feed.",
          timeout=5.0,
      )
      self.assertEqual(res["extraction_status"], "fallback_summary")
      self.assertEqual(res["text"], "Reliable fallback summary from RSS feed.")
      self.assertIn("404", res.get("error", ""))

  def test_empty_content_falls_back_to_summary(self):
    empty_html = "<html><body><div></div></body></html>"
    with patch("pipeline.extractor.fetch_raw_html", return_value=(empty_html, 200, None)):
      res = extract_article_content(
          "https://example.com/empty-page",
          fallback_summary="Fallback summary when page is empty.",
      )
      self.assertEqual(res["extraction_status"], "fallback_summary")
      self.assertEqual(res["text"], "Fallback summary when page is empty.")

  def test_invalid_url_handling(self):
    res = extract_article_content(
        "",
        fallback_summary="Fallback summary for empty url.",
    )
    self.assertEqual(res["extraction_status"], "invalid_url")
    self.assertEqual(res["text"], "Fallback summary for empty url.")

    res2 = extract_article_content(
        "not-a-valid-url",
        fallback_summary="Fallback summary for invalid url.",
    )
    self.assertEqual(res2["extraction_status"], "invalid_url")
    self.assertEqual(res2["text"], "Fallback summary for invalid url.")

  def test_library_unavailable_graceful_degradation(self):
    with patch("pipeline.extractor.trafilatura", None):
      res = extract_article_content(
          "https://example.com/article",
          fallback_summary="Fallback summary when trafilatura is missing.",
      )
      self.assertEqual(res["extraction_status"], "library_unavailable")
      self.assertEqual(res["text"], "Fallback summary when trafilatura is missing.")

  def test_extract_articles_batch(self):
    articles = [
        {"link": "https://example.com/a1", "summary": "Summary 1", "title": "Title 1"},
        {"link": "https://example.com/a2", "summary": "Summary 2", "title": "Title 2"},
    ]
    with patch("pipeline.extractor.fetch_raw_html", return_value=(self.sample_html, 200, None)), \
         patch("pipeline.extractor.save_article_cache") as mock_save:
      results = extract_articles_batch(articles, max_workers=2, timeout=5.0)
      self.assertEqual(len(results), 2)
      for art in results:
        self.assertIn("full_text", art)
        self.assertIn("extraction_status", art)
        self.assertEqual(art["extraction_status"], "extracted")
        self.assertIn("Claude 3.5 Sonnet", art["full_text"])
      mock_save.assert_called_once()

  def test_ssl_context_uses_standard_verification(self):
    import ssl
    with patch("urllib.request.urlopen") as mock_urlopen:
      mock_urlopen.side_effect = Exception("Simulated network stop")
      fetch_raw_html("https://example.com/test", timeout=1.0)
      self.assertTrue(mock_urlopen.called)
      context = mock_urlopen.call_args[1].get("context")
      self.assertIsNotNone(context)
      self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
      self.assertTrue(context.check_hostname)

  def test_cache_disk_persistence(self):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
      tmp_path = tmp.name

    try:
      test_cache = {
          "https://example.com/item1": {
              "url": "https://example.com/item1",
              "text": "Saved content",
              "extracted_at": "2026-11-02T12:00:00Z",
          }
      }
      save_article_cache(test_cache, cache_file=tmp_path)
      loaded = load_article_cache(cache_file=tmp_path)
      self.assertEqual(loaded["https://example.com/item1"]["text"], "Saved content")
    finally:
      if os.path.exists(tmp_path):
        os.remove(tmp_path)

  def test_cache_pruning_on_max_entries(self):
    test_cache = {}
    for i in range(MAX_CACHE_ENTRIES + 50):
      url = f"https://example.com/item{i}"
      test_cache[url] = {
          "url": url,
          "text": f"Content {i}",
          "extracted_at": f"2026-11-01T{i%24:02d}:00:00Z",
      }

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
      tmp_path = tmp.name

    try:
      save_article_cache(test_cache, cache_file=tmp_path)
      loaded = load_article_cache(cache_file=tmp_path)
      self.assertLessEqual(len(loaded), MAX_CACHE_ENTRIES)
    finally:
      if os.path.exists(tmp_path):
        os.remove(tmp_path)


if __name__ == "__main__":
  unittest.main()

