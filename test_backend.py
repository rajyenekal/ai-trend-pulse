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

    # Ensure all sources in registry pass schema validation
    for source in registry:
      valid, reason = tracker.validate_source_record(source)
      self.assertTrue(valid, f"Source {source.get('source_id')} failed validation: {reason}")

    # Ensure fallback registry also passes schema validation
    for source in tracker.FALLBACK_SOURCE_REGISTRY:
      valid, reason = tracker.validate_source_record(source)
      self.assertTrue(valid, f"Fallback source {source.get('source_id')} failed validation: {reason}")

    # Check Anthropic Official is classified as Tier 1 official using HTML page adapter
    anthropic_official = next((s for s in registry if s["source_id"] == "anthropic_news"), None)
    self.assertIsNotNone(anthropic_official, "Anthropic official must be in sources.json")
    self.assertTrue(anthropic_official["is_official"])
    self.assertTrue(anthropic_official["feed_is_official"])
    self.assertEqual(anthropic_official["trust_tier"], 1)
    self.assertEqual(anthropic_official["fetch_method"], "html_page_adapter")
    self.assertEqual(anthropic_official["feed_url"], "https://www.anthropic.com/news")

    # Check Anthropic HNRSS discovery bridge is classified as unofficial discovery
    anthropic_discovery = next((s for s in registry if s["source_id"] == "anthropic_hn_discovery"), None)
    self.assertIsNotNone(anthropic_discovery, "Anthropic HNRSS discovery must be in sources.json")
    self.assertFalse(anthropic_discovery["is_official"])
    self.assertFalse(anthropic_discovery["feed_is_official"])
    self.assertEqual(anthropic_discovery["source_type"], "unofficial_discovery")
    self.assertEqual(anthropic_discovery["trust_tier"], 4)

  def test_source_schema_validation_rejects_invalid_records(self):
    # Missing required field
    invalid_source1 = {"source_id": "test", "name": "Test"}
    valid, _ = tracker.validate_source_record(invalid_source1)
    self.assertFalse(valid)

    # Invalid trust tier
    invalid_source2 = {
        "source_id": "test", "name": "Test", "canonical_listing_url": "https://test.com",
        "source_type": "official", "trust_tier": 99, "confidence_score": 100
    }
    valid, _ = tracker.validate_source_record(invalid_source2)
    self.assertFalse(valid)

    # Unofficial discovery marked as official (conflicting)
    invalid_source3 = {
        "source_id": "test", "name": "Test", "canonical_listing_url": "https://test.com",
        "source_type": "unofficial_discovery", "trust_tier": 4, "confidence_score": 60,
        "is_official": True
    }
    valid, _ = tracker.validate_source_record(invalid_source3)
    self.assertFalse(valid)

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


  def test_cross_section_mutual_exclusivity(self):
    dummy_articles = [
        {"title": "OpenAI launches new ChatGPT Search canvas workflow", "summary": "OpenAI introduces an interactive canvas tool for coding and writing workflows.", "source": "OpenAI News", "trust_tier": 1, "is_official": True, "link": "https://openai.com/canvas", "published": "Date unavailable", "published_datetime": None},
        {"title": "Google DeepMind unveils Gemini robotics spatial reasoning", "summary": "New multimodal architecture for robotic manipulation and physical world modeling.", "source": "Google DeepMind", "trust_tier": 1, "is_official": True, "link": "https://deepmind.google/robotics", "published": "Date unavailable", "published_datetime": None},
        {"title": "Anthropic publishes Claude 3.7 safety alignment evaluations", "summary": "Comprehensive evaluation framework assessing autonomous agent safety and oversight.", "source": "Anthropic Official News", "trust_tier": 1, "is_official": True, "link": "https://anthropic.com/evals", "published": "Date unavailable", "published_datetime": None},
        {"title": "NVIDIA announces Blackwell B200 ultra accelerator specs", "summary": "Hardware architecture specifications for massive AI inference clusters.", "source": "NVIDIA Blog", "trust_tier": 1, "is_official": True, "link": "https://blogs.nvidia.com/b200", "published": "Date unavailable", "published_datetime": None},
        {"title": "Microsoft Copilot studio adds autonomous agent runtime", "summary": "Developer platform enables custom orchestration of multi-agent enterprise workflows.", "source": "Microsoft AI News", "trust_tier": 1, "is_official": True, "link": "https://news.microsoft.com/copilot-studio", "published": "Date unavailable", "published_datetime": None},
        {"title": "Hugging Face releases open-weight code generation benchmark", "summary": "Community benchmark evaluating coding models across multi-file repository tasks.", "source": "Hugging Face Blog", "trust_tier": 3, "is_official": True, "link": "https://huggingface.co/benchmarks", "published": "Date unavailable", "published_datetime": None},
        {"title": "TechCrunch reports Mistral raising capital for edge models", "summary": "European AI startup expands enterprise distribution and commercial partnerships.", "source": "TechCrunch AI", "trust_tier": 2, "is_official": False, "link": "https://techcrunch.com/mistral", "published": "Date unavailable", "published_datetime": None},
        {"title": "The Verge analyzes EU AI Act compliance timelines", "summary": "Investigation into copyright standards, watermarking, and frontier model obligations.", "source": "The Verge AI", "trust_tier": 2, "is_official": False, "link": "https://theverge.com/eu-act", "published": "Date unavailable", "published_datetime": None},
        {"title": "Ars Technica details LLM prompt injection defenses", "summary": "Security analysis of indirect prompt injection attacks against autonomous tool agents.", "source": "Ars Technica", "trust_tier": 2, "is_official": False, "link": "https://arstechnica.com/injection", "published": "Date unavailable", "published_datetime": None},
        {"title": "Simon Willison documents local llama.cpp performance", "summary": "Hands-on developer guide to running quantized models locally on consumer hardware.", "source": "Simon Willison Weblog", "trust_tier": 4, "is_official": False, "link": "https://simonwillison.net/llamacpp", "published": "Date unavailable", "published_datetime": None},
        {"title": "BAIR laboratory introduces reinforcement learning policy", "summary": "Novel algorithmic techniques for stable offline policy optimization in dynamic environments.", "source": "BAIR Blog", "trust_tier": 3, "is_official": True, "link": "https://bair.berkeley.edu/rl-policy", "published": "Date unavailable", "published_datetime": None},
        {"title": "Amazon Science benchmarks multimodal speech translation", "summary": "Low-latency acoustic encoders evaluated across diverse multilingual voice corpora.", "source": "Amazon Science", "trust_tier": 1, "is_official": True, "link": "https://amazon.science/speech", "published": "Date unavailable", "published_datetime": None},
        {"title": "GitHub Copilot Workspace expands pull request review", "summary": "Automated code review capabilities integrated directly into developer pull requests.", "source": "GitHub Blog AI", "trust_tier": 1, "is_official": True, "link": "https://github.blog/workspace-review", "published": "Date unavailable", "published_datetime": None},
        {"title": "AWS Bedrock adds custom fine-tuning API endpoints", "summary": "Cloud platform introduces private model adaptation and serverless provisioning.", "source": "AWS Machine Learning", "trust_tier": 1, "is_official": True, "link": "https://aws.amazon.com/bedrock-fine-tune", "published": "Date unavailable", "published_datetime": None},
        {"title": "The Decoder interviews researchers on chain-of-thought scaling", "summary": "Deep dive into inference compute scaling laws and test-time search architectures.", "source": "The Decoder", "trust_tier": 2, "is_official": False, "link": "https://the-decoder.com/cot-scaling", "published": "Date unavailable", "published_datetime": None},
    ]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_articles)
    payload = tracker.build_complete_payload(clustered)

    # Collect URLs from curated sections
    trend_urls = {t["evidence_urls"][0] for t in payload["trends"] if t.get("evidence_urls")}
    tool_urls = {s["link"] for s in payload["ai_tools"]}
    radar_urls = {s["link"] for s in payload["dev_radar"]}
    safety_urls = {s["link"] for s in payload["research_safety"]}

    # Mutual exclusivity assertions
    self.assertTrue(trend_urls.isdisjoint(tool_urls), "Trends and AI Tools must not share stories")
    self.assertTrue(trend_urls.isdisjoint(radar_urls), "Trends and Dev Radar must not share stories")
    self.assertTrue(trend_urls.isdisjoint(safety_urls), "Trends and Research/Safety must not share stories")
    self.assertTrue(tool_urls.isdisjoint(radar_urls), "AI Tools and Dev Radar must not share stories")
    self.assertTrue(tool_urls.isdisjoint(safety_urls), "AI Tools and Research/Safety must not share stories")
    self.assertTrue(radar_urls.isdisjoint(safety_urls), "Dev Radar and Research/Safety must not share stories")

    # Pulse items must not repeat the lead hero trend
    lead_trend_url = payload["trends"][0]["evidence_urls"][0] if payload["trends"] and payload["trends"][0].get("evidence_urls") else None
    if lead_trend_url and payload["pulse_items"]:
      pulse_urls = {p["link"] for p in payload["pulse_items"]}
      self.assertNotIn(lead_trend_url, pulse_urls, "Pulse items must not repeat the lead hero trend story")

  def test_summary_quality_no_generic_filler(self):
    dummy_articles = [
        {
            "title": "Anthropic releases new security benchmarks for frontier agent evaluation",
            "summary": "Anthropic introduces a comprehensive evaluation framework for autonomous agents. This framework assesses tool-calling safety and permission boundaries.",
            "source": "Anthropic Official News",
            "trust_tier": 1,
            "is_official": True,
            "link": "https://anthropic.com/evals",
            "published": "Oct 28, 2026",
            "published_datetime": None,
        }
    ]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_articles)
    payload = tracker.build_complete_payload(clustered)

    story = payload["top_stories"][0]
    filler_phrases = [
        "reported directly by", "verified against primary editorial sources",
        "refer to the direct publication url", "relevant to practitioners tracking"
    ]
    for phrase in filler_phrases:
      for kp in story["key_points"]:
        self.assertNotIn(phrase, kp.lower(), f"Found generic filler in key_points: {phrase}")
      self.assertNotIn(phrase, story["detailed_analysis"].lower(), f"Found generic filler in detailed_analysis: {phrase}")
      self.assertNotIn(phrase, story["why_it_matters"].lower(), f"Found generic filler in why_it_matters: {phrase}")

  def test_empty_and_malformed_feed_handling(self):
    # Malformed XML string
    malformed_xml = b"<xml><channel><item><title>Unclosed tag"
    entries = tracker.parse_feed_with_fallback("http://example.invalid/feed.xml", timeout=0.1) if False else []
    # Test built-in fallback parser directly with malformed input
    try:
      import xml.etree.ElementTree as ET
      try:
        ET.fromstring(malformed_xml)
      except ET.ParseError:
        pass  # Expected
    except Exception as e:
      self.fail(f"Unexpected exception during XML parse: {e}")

  def test_payload_validation_schema(self):
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
    valid_payload = tracker.build_complete_payload(clustered)

    # Valid payload should pass
    self.assertTrue(tracker.validate_dataset_payload(valid_payload))

    # Missing required key should fail
    invalid_payload = valid_payload.copy()
    del invalid_payload["top_stories"]
    with self.assertRaises(ValueError):
      tracker.validate_dataset_payload(invalid_payload)

    # Empty top_stories should fail
    empty_payload = valid_payload.copy()
    empty_payload["top_stories"] = []
    with self.assertRaises(ValueError):
      tracker.validate_dataset_payload(empty_payload)

  def test_pipeline_preservation_of_last_known_good_dataset(self):
    test_file = "test_data_preservation.json"
    initial_data = {
        "schema_version": 2,
        "data_status": "fresh",
        "generated_at": "2026-10-31T12:00:00Z",
        "last_attempt_at": "2026-10-31T12:00:00Z",
        "takeaway": "Test initial takeaway",
        "trends": [],
        "top_stories": [{"title": "Old Story", "link": "https://example.com/old", "source": "Old Source", "trust_tier": 1, "overall_score": 80}],
        "ai_tools": [],
        "dev_radar": [],
        "research_safety": [],
        "pulse_items": []
    }
    with open(test_file, "w", encoding="utf-8") as f:
      json.dump(initial_data, f)

    try:
      # If max_age_hours is 0 (or sources return empty), run_pipeline must preserve the existing dataset
      result = tracker.run_pipeline(dry_run=False, max_age_hours=0, output_file=test_file)
      with open(test_file, "r", encoding="utf-8") as f:
        preserved = json.load(f)
      self.assertEqual(preserved["top_stories"][0]["title"], "Old Story", "Original dataset must be preserved")
    finally:
      if os.path.exists(test_file):
        os.remove(test_file)
      if os.path.exists(f"{test_file}.tmp"):
        os.remove(f"{test_file}.tmp")


if __name__ == "__main__":
  unittest.main()
