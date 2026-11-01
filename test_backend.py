"""
Automated unit & regression tests for AI Trend Pulse backend pipeline.
Verifies source registry, URL canonicalization, timestamp handling,
story clustering, scoring weights determinism, model separation, and payload structure.
"""

from datetime import datetime, timezone
import json
import os
import unittest
import tracker


class TestBackendPipeline(unittest.TestCase):

  def test_source_registry_loading_and_classification(self):
    registry = tracker.load_source_registry("sources.json")
    self.assertIsInstance(registry, list)
    self.assertGreaterEqual(len(registry), 20)

    # Ensure required keys exist in every source record
    required_keys = {"source_id", "name", "canonical_listing_url", "source_type", "trust_tier"}
    for source in registry:
      for key in required_keys:
        self.assertIn(key, source, f"Source missing required key: {key}")

    # Check Anthropic Official is classified as Tier 1 official
    anthropic_official = next((s for s in registry if s["source_id"] == "anthropic_news"), None)
    self.assertIsNotNone(anthropic_official, "Anthropic official must be in sources.json")
    self.assertTrue(anthropic_official["is_official"])
    self.assertTrue(anthropic_official["feed_is_official"])
    self.assertEqual(anthropic_official["trust_tier"], 1)

    # Check Anthropic HNRSS discovery bridge is classified as unofficial discovery
    anthropic_discovery = next((s for s in registry if s["source_id"] == "anthropic_hn_discovery"), None)
    self.assertIsNotNone(anthropic_discovery, "Anthropic HNRSS discovery must be in sources.json")
    self.assertFalse(anthropic_discovery["is_official"])
    self.assertFalse(anthropic_discovery["feed_is_official"])
    self.assertEqual(anthropic_discovery["source_type"], "unofficial_discovery")
    self.assertEqual(anthropic_discovery["trust_tier"], 4)

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

  def test_timestamp_parsing_and_date_unavailable(self):
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

    # Common article format e.g. Oct 28, 2026
    dt3 = tracker.parse_published_datetime("Oct 28, 2026")
    self.assertIsNotNone(dt3)
    self.assertEqual(dt3.year, 2026)
    self.assertEqual(dt3.month, 10)
    self.assertEqual(dt3.day, 28)

  def test_clustering_rules_and_model_separation(self):
    test_articles = [
        # 1. Syndicated copies of the exact same announcement
        {
            "source": "OpenAI News",
            "is_official": True,
            "trust_tier": 1,
            "title": "Standardizing Web Scraping Opt-Outs for AI Training",
            "link": "https://openai.com/scraping",
            "summary": "Shared policy token in robots.txt for AI training preferences.",
        },
        {
            "source": "The Verge AI",
            "is_official": False,
            "trust_tier": 2,
            "title": "Tech giants agree to standardize web scraping opt-out protocols for AI training",
            "link": "https://theverge.com/scraping",
            "summary": "Industry consensus on robots.txt opt out.",
        },
        {
            "source": "TechCrunch AI",
            "is_official": False,
            "trust_tier": 2,
            "title": "Major AI developers standardize web scraping opt-outs via robots.txt",
            "link": "https://techcrunch.com/scraping",
            "summary": "Publishers get single standard for training opt out.",
        },

        # 2. Same company, totally different stories (MUST NOT MERGE)
        {
            "source": "OpenAI News",
            "is_official": True,
            "trust_tier": 1,
            "title": "OpenAI announces educational literacy program with non-profit partners",
            "link": "https://openai.com/literacy",
            "summary": "Expanding AI literacy tools for primary schools.",
        },

        # 3. Different models (Claude vs Gemini) (MUST NOT MERGE)
        {
            "source": "Anthropic Official News",
            "is_official": True,
            "trust_tier": 1,
            "title": "Introducing Claude 3.7 Sonnet with hybrid reasoning architecture",
            "link": "https://anthropic.com/claude-3-7-sonnet",
            "summary": "New frontier model featuring hybrid thinking and instant responses.",
        },
        {
            "source": "Google DeepMind",
            "is_official": True,
            "trust_tier": 1,
            "title": "Introducing Gemini 2.0 Flash Thinking for complex reasoning",
            "link": "https://deepmind.google/gemini-2-flash",
            "summary": "Google announces multimodal reasoning model.",
        },

        # 4. Generic headlines (MUST NOT MERGE)
        {
            "source": "Hugging Face Blog",
            "is_official": True,
            "trust_tier": 3,
            "title": "New open source AI model outperforms proprietary benchmarks",
            "link": "https://huggingface.co/model1",
            "summary": "Open weight model sets new community benchmark.",
        },
        {
            "source": "Amazon Science",
            "is_official": True,
            "trust_tier": 1,
            "title": "New vision AI model achieves state of the art on medical imaging",
            "link": "https://amazon.science/vision",
            "summary": "Medical imaging architecture benchmarked on clinical datasets.",
        },
    ]

    clusters = tracker.cluster_and_deduplicate_articles(test_articles, similarity_threshold=0.40)

    # 8 raw articles should form exactly 6 clusters:
    # 1 cluster for the 3 scraping articles + 5 independent clusters
    self.assertEqual(len(clusters), 6, f"Expected 6 clusters, got {len(clusters)}")

    # Verify scraping cluster
    scraping_cluster = next((c for c in clusters if "Scraping" in c["title"]), None)
    self.assertIsNotNone(scraping_cluster)
    self.assertEqual(scraping_cluster["source"], "OpenAI News")  # Lead must be official lab
    self.assertEqual(scraping_cluster["covered_by_sources_count"], 3)
    self.assertEqual(len(scraping_cluster["related_sources"]), 2)

    # Verify Claude and Gemini are in separate clusters
    claude_cluster = next((c for c in clusters if "Claude" in c["title"]), None)
    gemini_cluster = next((c for c in clusters if "Gemini" in c["title"]), None)
    self.assertIsNotNone(claude_cluster)
    self.assertIsNotNone(gemini_cluster)
    self.assertNotEqual(claude_cluster["link"], gemini_cluster["link"])

  def test_scoring_determinism_and_safety_protection(self):
    # Safety and policy story
    safety_article = {
        "title": "Frontier AI Safety Framework and Misalignment Detection Standards",
        "summary": "New evaluation suite for autonomous agents and catastrophic risk oversight.",
        "trust_tier": 1,
        "is_official": True,
        "published_datetime": datetime.now(timezone.utc),
    }

    # Should have protected importance score (>= 75)
    scores = tracker.calculate_story_scores(safety_article, corroboration_count=1)
    self.assertGreaterEqual(scores["importance_score"], 75)
    self.assertEqual(scores["popularity_score"], 50)  # Neutral baseline for single source

    # Determinism
    scores_repeat = tracker.calculate_story_scores(safety_article, corroboration_count=1)
    self.assertEqual(scores["overall_score"], scores_repeat["overall_score"])

  def test_payload_builder_contract_and_pulse_items(self):
    dummy_articles = [
        {
            "title": "Test AI Story",
            "summary": "Detailed summary of test development.",
            "source": "OpenAI News",
            "trust_tier": 1,
            "is_official": True,
            "link": "https://openai.com/test",
            "published": "Date unavailable",
            "published_datetime": None,
        }
    ]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_articles)
    payload = tracker.build_complete_payload(clustered)

    self.assertIn("trends", payload)
    self.assertIn("top_stories", payload)
    self.assertIn("pulse_items", payload)
    self.assertIn("ai_tools", payload)
    self.assertIn("dev_radar", payload)
    self.assertIn("research_safety", payload)

    # Verify pulse item has non-empty summary and date
    p_item = payload["pulse_items"][0]
    self.assertTrue(len(p_item["what_happened"]) > 0, "Pulse item must have non-empty summary")
    self.assertEqual(p_item["published"], "Date unavailable")


if __name__ == "__main__":
  unittest.main()
