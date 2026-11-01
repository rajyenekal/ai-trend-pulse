"""
Automated unit & regression tests for AI Trend Pulse backend pipeline.
Verifies source registry, URL canonicalization, timestamp handling,
story clustering, scoring weights determinism, and payload structure.
"""

from datetime import datetime, timezone
import json
import os
import unittest
import tracker


class TestBackendPipeline(unittest.TestCase):

  def test_source_registry_loading(self):
    registry = tracker.load_source_registry("sources.json")
    self.assertIsInstance(registry, list)
    self.assertGreaterEqual(len(registry), 8)

    # Ensure required keys exist in every source record
    required_keys = {"source_id", "name", "canonical_listing_url", "source_type", "trust_tier"}
    for source in registry:
      for key in required_keys:
        self.assertIn(key, source, f"Source missing required key: {key}")

    # Check Anthropic is represented in the registry
    anthropic_source = next((s for s in registry if s["source_id"] == "anthropic_news"), None)
    self.assertIsNotNone(anthropic_source, "Anthropic must be represented in sources.json")
    self.assertTrue(anthropic_source["is_official"])

  def test_url_normalization(self):
    # Tracking parameters must be stripped
    url_with_tracking = "https://techcrunch.com/article/ai-agents?utm_source=twitter&utm_medium=social&ref=aitrend#section-1"
    clean = tracker.normalize_url(url_with_tracking)
    self.assertEqual(clean, "https://techcrunch.com/article/ai-agents")

    # Functional query parameters must be preserved
    url_functional = "https://example.com/search?q=machine+learning&page=2"
    clean_functional = tracker.normalize_url(url_functional)
    self.assertEqual(clean_functional, "https://example.com/search?q=machine+learning&page=2")

    # Non-http/https schemes must be rejected
    self.assertEqual(tracker.normalize_url("javascript:alert(1)"), "")
    self.assertEqual(tracker.normalize_url(""), "")

  def test_timestamp_parsing_no_fake_dates(self):
    # Missing date must return None, NEVER current time or fake date
    self.assertIsNone(tracker.parse_published_datetime(None))
    self.assertIsNone(tracker.parse_published_datetime(""))
    self.assertIsNone(tracker.parse_published_datetime("   "))

    # Valid RFC-2822
    rfc_date = "Sat, 31 Oct 2026 14:30:00 GMT"
    dt = tracker.parse_published_datetime(rfc_date)
    self.assertIsNotNone(dt)
    self.assertEqual(dt.year, 2026)
    self.assertEqual(dt.month, 10)
    self.assertEqual(dt.day, 31)
    self.assertEqual(dt.hour, 14)

    # Valid ISO-8601
    iso_date = "2026-10-31T18:00:00Z"
    dt2 = tracker.parse_published_datetime(iso_date)
    self.assertIsNotNone(dt2)
    self.assertEqual(dt2.year, 2026)
    self.assertEqual(dt2.month, 10)

  def test_story_clustering_and_deduplication(self):
    raw_articles = [
        {
            "source": "OpenAI News",
            "is_official": True,
            "trust_tier": 1,
            "title": "Introducing Standardized Web Scraping Opt-Out Protocols for AI",
            "link": "https://openai.com/news/standardized-opt-outs",
            "summary": "OpenAI announces robots.txt policy token standardization.",
            "published_datetime": datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
            "published": "Oct 31, 12:00 UTC",
        },
        {
            "source": "The Verge AI",
            "is_official": False,
            "trust_tier": 2,
            "title": "OpenAI and rivals agree on standard web scraping opt-out protocol",
            "link": "https://theverge.com/ai/standardized-web-scraping-opt-outs",
            "summary": "Tech giants agree to follow robots.txt signals for AI training.",
            "published_datetime": datetime(2026, 10, 31, 13, 0, tzinfo=timezone.utc),
            "published": "Oct 31, 13:00 UTC",
        },
        {
            "source": "Google DeepMind",
            "is_official": True,
            "trust_tier": 1,
            "title": "New Frontier Model Architecture for Quantum Chemistry Simulations",
            "link": "https://deepmind.google/blog/quantum-chemistry-model",
            "summary": "DeepMind releases paper on quantum simulation using specialized neural networks.",
            "published_datetime": datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc),
            "published": "Oct 31, 10:00 UTC",
        },
    ]

    clustered = tracker.cluster_and_deduplicate_articles(raw_articles)
    # The two OpenAI scraping articles should be merged into 1 cluster
    self.assertEqual(len(clustered), 2, "Expected 2 clusters from 3 articles with 1 duplicate event")

    # Find the scraping story cluster
    scraping_cluster = next((c for c in clustered if "Scraping" in c["title"]), None)
    self.assertIsNotNone(scraping_cluster)
    # Preferred lead must be the Tier 1 official announcement
    self.assertEqual(scraping_cluster["source"], "OpenAI News")
    self.assertEqual(scraping_cluster["covered_by_sources_count"], 2)
    self.assertEqual(len(scraping_cluster["related_sources"]), 1)
    self.assertEqual(scraping_cluster["related_sources"][0]["source_name"], "The Verge AI")

  def test_scoring_determinism_and_weights(self):
    article = {
        "title": "Major Frontier Model Release with Coding Agent Capabilities",
        "summary": "A brand new open source model with full MCP support for developers.",
        "trust_tier": 1,
        "is_official": True,
        "published_datetime": datetime.now(timezone.utc),
    }

    scores1 = tracker.calculate_story_scores(article, corroboration_count=2)
    scores2 = tracker.calculate_story_scores(article, corroboration_count=2)

    self.assertEqual(scores1["overall_score"], scores2["overall_score"])
    self.assertGreaterEqual(scores1["overall_score"], 0)
    self.assertLessEqual(scores1["overall_score"], 100)
    self.assertIn(scores1["confidence_label"], ["high", "medium", "low"])

  def test_payload_builder_contract(self):
    dummy_articles = [
        {
            "title": "Test AI Story",
            "summary": "Test summary",
            "source": "OpenAI News",
            "trust_tier": 1,
            "is_official": True,
            "link": "https://openai.com/test",
            "published": "Oct 31, 12:00 UTC",
            "published_datetime": datetime.now(timezone.utc),
        }
    ]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_articles)
    payload = tracker.build_complete_payload(clustered)

    self.assertIn("trends", payload)
    self.assertIn("top_stories", payload)
    self.assertIn("takeaway", payload)
    self.assertIn("generated_at", payload)
    self.assertIn("ai_tools", payload)
    self.assertIn("dev_radar", payload)
    self.assertIn("research_safety", payload)
    self.assertIn("pulse_items", payload)


if __name__ == "__main__":
  unittest.main()
