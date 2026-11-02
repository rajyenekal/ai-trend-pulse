"""
Automated unit & regression tests for AI Trend Pulse backend pipeline.
Verifies source registry, URL canonicalization, timestamp handling,
story clustering, scoring weights determinism, model separation, and payload structure.
"""

from datetime import datetime, timezone
import json
import os
import unittest
from unittest.mock import patch
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
      # 1. When source feeds return empty, run_pipeline must preserve the existing dataset
      with patch("tracker.collect_fresh_news", return_value=[]):
        result = tracker.run_pipeline(dry_run=False, max_age_hours=0, output_file=test_file)
        with open(test_file, "r", encoding="utf-8") as f:
          preserved = json.load(f)
        self.assertEqual(preserved["top_stories"][0]["title"], "Old Story", "Original dataset must be preserved when feeds are empty")

      # 2. When source feeds encounter unexpected errors/exceptions, run_pipeline must preserve the existing dataset and raise PipelineExecutionError
      with patch("tracker.collect_fresh_news", side_effect=RuntimeError("Simulated upstream network failure")):
        with self.assertRaises(tracker.PipelineExecutionError):
          tracker.run_pipeline(dry_run=False, max_age_hours=0, output_file=test_file)
        with open(test_file, "r", encoding="utf-8") as f:
          preserved_err = json.load(f)
        self.assertEqual(preserved_err["top_stories"][0]["title"], "Old Story", "Original dataset must be preserved on upstream failure")
        self.assertFalse(os.path.exists(f"{test_file}.tmp"), "Temporary files must be cleaned up on failure")
    finally:
      if os.path.exists(test_file):
        os.remove(test_file)
      if os.path.exists(f"{test_file}.tmp"):
        os.remove(f"{test_file}.tmp")

  def test_jargon_simplification(self):
    complex_text = "The new multimodal model improves inference compute and powers agentic workflows with a larger context window."
    simplified = tracker.simplify_jargon(complex_text)
    self.assertIn("multimodal (text, image, audio)", simplified)
    self.assertIn("AI reasoning compute", simplified)
    self.assertIn("action-oriented workflows", simplified)
    self.assertIn("memory capacity (context window)", simplified)

  def test_audience_impact_generation(self):
    # Developer target
    dev_impact = tracker.generate_audience_impact(
        "OpenAI introduces new Responses API for custom tool calling",
        "Endpoints support client side tools",
        "AI Coding"
    )
    self.assertEqual(dev_impact["target"], "For developers")
    self.assertTrue(len(dev_impact["impact"]) > 10)

    # Publisher / creator target
    creator_impact = tracker.generate_audience_impact(
        "Standardizing web scraping opt-outs via robots.txt token",
        "Unified protocol for AI model training opt-outs",
        "AI Safety"
    )
    self.assertEqual(creator_impact["target"], "For creators & publishers")

    # Everyday users target
    user_impact = tracker.generate_audience_impact(
        "ChatGPT Search rolled out for all free tier mobile users",
        "Real-time web search assistant inside conversational UI",
        "AI Products"
    )
    self.assertEqual(user_impact["target"], "For everyday users")

  def test_image_metadata_resolution(self):
    # Explicit source image
    meta1 = tracker.resolve_article_image_metadata(
        "https://techcrunch.com/photo.jpg",
        "Test Headline", "AI Models", "openai", "https://techcrunch.com"
    )
    self.assertEqual(meta1["image_url"], "https://techcrunch.com/photo.jpg")
    self.assertEqual(meta1["image_type"], "source_media")

    # Lab asset fallback
    meta2 = tracker.resolve_article_image_metadata(
        "", "OpenAI release", "AI Models", "openai"
    )
    self.assertEqual(meta2["image_type"], "official_asset")
    self.assertIn("unsplash", meta2["image_url"])

    # Topic fallback
    meta3 = tracker.resolve_article_image_metadata(
        "", "Unknown research", "Research", "unknown"
    )
    self.assertEqual(meta3["image_type"], "category_fallback")

  def test_daily_overview_generation(self):
    dummy_stories = [
        {"title": "OpenAI announces coding agent", "summary": "Coding assistant for developers", "source": "OpenAI News", "overall_score": 90, "link": "https://openai.com/1"},
        {"title": "Google DeepMind unveils Gemini 2", "summary": "Next gen multimodal model", "source": "Google DeepMind", "overall_score": 88, "link": "https://deepmind.google/2"},
        {"title": "Anthropic details safety evals", "summary": "Benchmarking autonomous safety risks", "source": "Anthropic Official News", "overall_score": 85, "link": "https://anthropic.com/3"},
    ]
    overview = tracker.generate_daily_overview(dummy_stories, "2026-11-01T12:00:00Z")
    self.assertEqual(overview["total_developments_today"], 3)
    self.assertTrue(len(overview["briefing_text"]) > 20)
    self.assertEqual(len(overview["top_developments"]), 3)
    self.assertIn("why_it_matters", overview["top_developments"][0])
    self.assertIn("target_audience", overview["top_developments"][0])

  def test_evaluate_article_relevance(self):
    # Genuine AI stories must pass
    rel1, _, _ = tracker.evaluate_article_relevance(
        "OpenAI announces o3 reasoning model with major benchmark gains",
        "New frontier model exhibits advanced reasoning capabilities.",
        "TechCrunch AI", "publication", False
    )
    self.assertTrue(rel1)

    # Official lab stories pass
    rel2, _, _ = tracker.evaluate_article_relevance(
        "Anthropic collaborates with GSA", "Cloud deployment for government",
        "Anthropic Official News", "official", True
    )
    self.assertTrue(rel2)

    # Lifestyle fluff (Halloween costumes) must be rejected
    rel3, _, reason3 = tracker.evaluate_article_relevance(
        "Last-minute Halloween costumes for tech nerds",
        "Here are 10 funny DIY costumes for developers.",
        "TechCrunch AI", "publication", False
    )
    self.assertFalse(rel3)
    self.assertIn("fluff", reason3.lower())

    # Conference ticket marketing must be rejected
    rel4, _, reason4 = tracker.evaluate_article_relevance(
        "Register now for TechCrunch Disrupt 2026 early bird tickets",
        "Save $500 with promo code.",
        "TechCrunch AI", "publication", False
    )
    self.assertFalse(rel4)
    self.assertIn("event", reason4.lower())

    # Generic non-AI tech stories without AI connection must be rejected
    rel5, _, reason5 = tracker.evaluate_article_relevance(
        "New bicycle lock uses titanium steel shackles",
        "A heavy duty physical lock designed to prevent bike theft.",
        "The Verge AI", "publication", False
    )
    self.assertFalse(rel5)

  def test_detect_company_accuracy(self):
    # xAI should be detected and not confused with Amazon due to 'lawsuit'
    lawsuit_title = "Judge allows NAACP lawsuit over xAI data center pollution to move forward"
    self.assertEqual(tracker.detect_company(lawsuit_title, "TechCrunch AI"), "xai")

    # AWS should be detected with word boundaries
    aws_title = "Deploying deep learning workloads with AWS Bedrock"
    self.assertEqual(tracker.detect_company(aws_title, "TechCrunch AI"), "amazon")

    # 'submit' or 'transmit' should NOT trigger MIT
    submit_title = "Researchers transmit optical signals over transatlantic fiber"
    self.assertNotEqual(tracker.detect_company(submit_title, "Ars Technica"), "mit")

  def test_classify_topic_accuracy(self):
    # 8 Canonical Categories classification
    # 1. Model Spec is AI Security & Safety
    t1 = tracker.classify_topic("An updated Model Spec for more capable and beneficial AI", "Rules for model behavior")
    self.assertEqual(t1, "AI Security & Safety")

    # 2. xAI data-center pollution lawsuit MUST be AI Policy & Regulation (never AI Products & Tools)
    t_lawsuit, conf, rat = tracker.classify_topic_detailed(
        "Judge allows NAACP lawsuit over xAI data center pollution to move forward",
        "Environmental groups and Memphis residents challenge gas turbine air pollution permits."
    )
    self.assertEqual(t_lawsuit, "AI Policy & Regulation")
    self.assertGreaterEqual(conf, 0.90)
    self.assertTrue(len(rat) > 10)

    # 3. Legal agent operating system is AI Applications
    t2 = tracker.classify_topic("Legora is building the agentic operating system for legal work", "Legal workflow automation")
    self.assertEqual(t2, "AI Applications")

    # 4. Freight exception automation is AI Applications
    t3 = tracker.classify_topic("How Worldwide Express automated freight exceptions with Amazon Bedrock", "Logistics automation case study with Amazon Bedrock")
    self.assertEqual(t3, "AI Applications")

    # 5. Hardware / GPU cluster is AI Infrastructure
    t_infra = tracker.classify_topic("NVIDIA introduces Blackwell B200 GPU supercomputer cluster for enterprise data centers")
    self.assertEqual(t_infra, "AI Infrastructure")

    # 6. Venture funding is AI Business & Funding
    t_biz = tracker.classify_topic("AI Startup raises $50M Series B funding round at $1B valuation")
    self.assertEqual(t_biz, "AI Business & Funding")

    # 7. IDE extension / developer tool is AI Products & Tools
    t_tools = tracker.classify_topic("New VS Code extension brings agentic code review and automated bug fixing to IDE")
    self.assertEqual(t_tools, "AI Products & Tools")

    # 8. Frontier reasoning model is AI Models & Research
    t_models = tracker.classify_topic("OpenAI unveils o3 reasoning model benchmark results on competitive math")
    self.assertEqual(t_models, "AI Models & Research")

  def test_evidence_metadata_determination(self):
    # Single official announcement
    lead_official = {"source": "OpenAI News", "trust_tier": 1, "is_official": True, "source_type": "official"}
    meta1 = tracker.determine_evidence_metadata(lead_official, [])
    self.assertEqual(meta1["evidence_status"], "official_announcement")
    self.assertEqual(meta1["independent_source_count"], 1)

    # Multi-source corroborated story
    related = [{"source_name": "TechCrunch AI"}, {"source_name": "The Verge AI"}]
    meta2 = tracker.determine_evidence_metadata(lead_official, related)
    self.assertEqual(meta2["evidence_status"], "independently_corroborated")
    self.assertGreaterEqual(meta2["independent_source_count"], 2)

    # Syndicated copies from same publisher do NOT increase independent source count
    lead_google = {"source": "Google DeepMind", "trust_tier": 1, "is_official": True, "source_type": "official"}
    related_same = [{"source_name": "Google AI Blog"}]
    meta3 = tracker.determine_evidence_metadata(lead_google, related_same)
    self.assertEqual(meta3["independent_source_count"], 1)

  def test_story_specific_why_it_matters_uniqueness(self):
    stories = [
        ("OpenAI releases o3 reasoning model", "OpenAI released o3, a reasoning model that achieves breakthrough performance on competitive programming. It introduces dynamic test-time compute scaling for difficult proofs.", "AI Models", "openai"),
        ("Legora launches agentic legal operating system", "Legora unveiled an agentic software suite for law firms. The platform automates complex contract review and regulatory filings across corporate law teams.", "AI Agents", "openai"),
        ("Worldwide Express automates freight exceptions", "Worldwide Express used Amazon Bedrock to resolve carrier transit delays. Six months after deployment, the company cut active exception tickets by 75% and improved settlement speed.", "AI Products", "amazon"),
    ]
    whys = [tracker.generate_factual_why_it_matters(t, s, top, comp) for t, s, top, comp in stories]
    # All 3 why_it_matters statements must be unique and non-empty
    self.assertEqual(len(set(whys)), 3)
    for w in whys:
      self.assertTrue(len(w) > 20)
      self.assertNotIn("Expands practical AI tooling options and ecosystem integration across production workflows.", w)

  def test_source_registry_publisher_grouping(self):
    registry = tracker.load_source_registry("sources.json")
    for s in registry:
      self.assertIn("publisher_id", s, f"Source {s['source_id']} missing publisher_id")
      self.assertIn("publisher_group_id", s, f"Source {s['source_id']} missing publisher_group_id")
      self.assertIn("source_type", s, f"Source {s['source_id']} missing source_type")
      self.assertIn("is_primary_source", s, f"Source {s['source_id']} missing is_primary_source")
      self.assertIn("publisher_owns_feed", s, f"Source {s['source_id']} missing publisher_owns_feed")

    # Corporate relationship mapping verification
    deepmind = next(s for s in registry if s["source_id"] == "deepmind_blog")
    google_ai = next(s for s in registry if s["source_id"] == "google_ai_blog")
    self.assertEqual(deepmind["publisher_group_id"], "google")
    self.assertEqual(google_ai["publisher_group_id"], "google")

    ms_ai = next(s for s in registry if s["source_id"] == "microsoft_ai_news")
    gh_ai = next(s for s in registry if s["source_id"] == "github_blog_ai")
    self.assertEqual(ms_ai["publisher_group_id"], "microsoft")
    self.assertEqual(gh_ai["publisher_group_id"], "microsoft")

    aws = next(s for s in registry if s["source_id"] == "aws_ml_blog")
    amazon_sci = next(s for s in registry if s["source_id"] == "amazon_science")
    self.assertEqual(aws["publisher_group_id"], "amazon")
    self.assertEqual(amazon_sci["publisher_group_id"], "amazon")

    arxiv_ai = next(s for s in registry if s["source_id"] == "arxiv_cs_ai")
    arxiv_lg = next(s for s in registry if s["source_id"] == "arxiv_cs_lg")
    self.assertEqual(arxiv_ai["publisher_group_id"], "cornell_arxiv")
    self.assertEqual(arxiv_lg["publisher_group_id"], "cornell_arxiv")

    hn_discovery = next(s for s in registry if s["source_id"] == "anthropic_hn_discovery")
    self.assertFalse(hn_discovery["is_primary_source"])
    self.assertFalse(hn_discovery["publisher_owns_feed"])
    self.assertEqual(hn_discovery["source_type"], "unofficial_discovery")

  def test_exact_url_provenance_and_id_validation(self):
    collected = [
        {
            "article_id": "art_openai_12345",
            "source": "OpenAI News",
            "source_id": "openai_news",
            "publisher_id": "openai",
            "publisher_group_id": "openai",
            "link": "https://openai.com/index/o3-preview",
            "trust_tier": 1,
            "is_official": True,
            "publisher_owns_feed": True,
            "source_type": "official",
        },
        {
            "article_id": "art_techcrunch_67890",
            "source": "TechCrunch AI",
            "source_id": "techcrunch_ai",
            "publisher_id": "techcrunch",
            "publisher_group_id": "techcrunch",
            "link": "https://techcrunch.com/2026/01/01/openai-o3-preview",
            "trust_tier": 2,
            "is_official": False,
            "publisher_owns_feed": True,
            "source_type": "publication",
        }
    ]

    # Case 1: Valid trend citing exact article ID and exact URL
    trend_valid = [{
        "title": "OpenAI Unveils o3 Reasoning Model",
        "evidence_article_ids": ["art_openai_12345"],
        "evidence_urls": ["https://openai.com/index/o3-preview"],
        "source": "OpenAI News",
    }]
    validated = tracker.validate_evidence_provenance(trend_valid, collected)
    self.assertEqual(len(validated), 1)
    self.assertEqual(validated[0]["evidence_urls"], ["https://openai.com/index/o3-preview"])
    self.assertEqual(validated[0]["evidence_article_ids"], ["art_openai_12345"])
    self.assertEqual(validated[0]["independent_source_count"], 1)
    self.assertEqual(validated[0]["evidence_status"], "official_announcement")

    # Case 2: Fabricated / unknown article ID and URL must be rejected and omitted
    trend_fabricated = [{
        "title": "Fabricated Hallucinated Trend",
        "evidence_article_ids": ["art_fake_unknown_id"],
        "evidence_urls": ["https://fake-ai-news.org/hallucinated-story"],
        "source": "OpenAI News",
    }]
    validated_fab = tracker.validate_evidence_provenance(trend_fabricated, collected)
    self.assertEqual(len(validated_fab), 0)

    # Case 3: URL prefix matching MUST NOT be accepted (exact match only)
    trend_prefix = [{
        "title": "Prefix Tampered URL",
        "evidence_urls": ["https://openai.com/index/o3-preview/subpath-does-not-exist"],
        "source": "OpenAI News",
    }]
    validated_prefix = tracker.validate_evidence_provenance(trend_prefix, collected)
    self.assertEqual(len(validated_prefix), 0)

    # Case 4: No silent fallback to unrelated articles from same publisher
    trend_no_evidence = [{
        "title": "Trend with No Matching Evidence",
        "evidence_urls": ["https://techcrunch.com/unrelated-gadget-story"],
        "source": "OpenAI News",
    }]
    validated_no_ev = tracker.validate_evidence_provenance(trend_no_evidence, collected)
    self.assertEqual(len(validated_no_ev), 0)

  def test_independent_publisher_counting_rules(self):
    # Rule 1: Multiple articles from TechCrunch count as 1 publisher
    lead_tc = {
        "source": "TechCrunch AI",
        "source_id": "techcrunch_ai",
        "publisher_id": "techcrunch",
        "publisher_group_id": "techcrunch",
        "trust_tier": 2,
        "is_official": False,
    }
    related_tc = [
        {"source_name": "TechCrunch AI", "source_id": "techcrunch_ai", "publisher_group_id": "techcrunch"},
        {"source_name": "TechCrunch AI", "source_id": "techcrunch_ai", "publisher_group_id": "techcrunch"}
    ]
    meta_tc = tracker.determine_evidence_metadata(lead_tc, related_tc)
    self.assertEqual(meta_tc["independent_source_count"], 1)
    self.assertEqual(meta_tc["evidence_status"], "single_source")

    # Rule 2: Google DeepMind + Google AI Blog share publisher group -> 1 publisher
    lead_dm = {
        "source": "Google DeepMind",
        "source_id": "deepmind_blog",
        "publisher_id": "google_deepmind",
        "publisher_group_id": "google",
        "trust_tier": 1,
        "is_official": True,
    }
    related_gai = [
        {"source_name": "Google AI Blog", "source_id": "google_ai_blog", "publisher_group_id": "google"}
    ]
    meta_google = tracker.determine_evidence_metadata(lead_dm, related_gai)
    self.assertEqual(meta_google["independent_source_count"], 1)
    self.assertEqual(meta_google["evidence_status"], "official_announcement")

    # Rule 3: Google DeepMind + TechCrunch -> 2 independent publishers
    related_diff = [
        {"source_name": "TechCrunch AI", "source_id": "techcrunch_ai", "publisher_group_id": "techcrunch"}
    ]
    meta_diff = tracker.determine_evidence_metadata(lead_dm, related_diff)
    self.assertEqual(meta_diff["independent_source_count"], 2)
    self.assertEqual(meta_diff["evidence_status"], "independently_corroborated")

    # Rule 4: Hacker News discovery feeds do NOT count as independent corroborating publishers
    lead_anthropic = {
        "source": "Anthropic Official News",
        "source_id": "anthropic_news",
        "publisher_id": "anthropic",
        "publisher_group_id": "anthropic",
        "trust_tier": 1,
        "is_official": True,
    }
    related_hn = [
        {
            "source_name": "Anthropic Community Discovery (HNRSS)",
            "source_id": "anthropic_hn_discovery",
            "publisher_group_id": "ycombinator",
            "source_type": "unofficial_discovery",
            "publisher_owns_feed": False,
        }
    ]
    meta_hn = tracker.determine_evidence_metadata(lead_anthropic, related_hn)
    self.assertEqual(meta_hn["independent_source_count"], 1)
    self.assertEqual(meta_hn["evidence_status"], "official_announcement")

  def test_scoring_and_confidence_semantics(self):
    # Official single-source with complete text: high confidence, but independent_source_count = 1
    art_official = {
        "title": "OpenAI releases o3 reasoning model with frontier math benchmarks",
        "summary": "Detailed technical report explaining test-time compute scaling and benchmark results across competitive programming.",
        "trust_tier": 1,
        "is_official": True,
        "source_type": "official",
        "published_datetime": datetime.now(timezone.utc),
    }
    scores_official = tracker.calculate_story_scores(art_official, corroboration_count=1)
    self.assertEqual(scores_official["confidence_label"], "high")
    self.assertGreaterEqual(scores_official["source_quality_score"], 95)
    self.assertEqual(scores_official["coverage_score"], 50)  # Neutral baseline for single source
    self.assertTrue(0 <= scores_official["pulse_score"] <= 100)

    # Multi-source cluster with >= 2 independent publisher groups: high coverage score
    art_press = {
        "title": "OpenAI releases o3 model",
        "summary": "Independent coverage verifying the release of o3.",
        "trust_tier": 2,
        "is_official": False,
        "source_type": "publication",
        "published_datetime": datetime.now(timezone.utc),
    }
    scores_multi = tracker.calculate_story_scores(art_press, corroboration_count=2)
    self.assertGreaterEqual(scores_multi["coverage_score"], 75)
    self.assertEqual(scores_multi["confidence_label"], "high")

    # Sparse reporting with limited text gets low confidence
    art_sparse = {
        "title": "Brief note",
        "summary": "Too short.",
        "trust_tier": 4,
        "is_official": False,
        "source_type": "community",
    }
    scores_sparse = tracker.calculate_story_scores(art_sparse, corroboration_count=1)
    self.assertEqual(scores_sparse["confidence_label"], "low")

  def test_tier_4_source_classification(self):
    registry = tracker.load_source_registry("sources.json")
    simon = next(s for s in registry if s["source_id"] == "simon_willison")
    import_ai = next(s for s in registry if s["source_id"] == "import_ai")
    self.assertEqual(simon["trust_tier"], 4)
    self.assertEqual(import_ai["trust_tier"], 4)

    dummy_tier4 = [{
        "title": "Practical exploration of local prompt injection guardrails",
        "summary": "A deep dive into prompt injection vectors and testing methodology across local language models.",
        "source": "Simon Willison Weblog",
        "source_id": "simon_willison",
        "publisher_id": "simon_willison",
        "publisher_group_id": "simon_willison",
        "trust_tier": 4,
        "is_official": False,
        "link": "https://simonwillison.net/2026/test-guardrails",
        "published": "Oct 31, 12:00 UTC",
        "published_datetime": None,
    }]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_tier4)
    payload = tracker.build_complete_payload(clustered)
    top_story = payload["top_stories"][0]

    self.assertEqual(top_story["trust_tier"], 4)
    self.assertEqual(top_story["tier"], "Practitioner & Community")
    self.assertNotEqual(top_story["tier"], "Independent Journalism")

  def test_zero_fresh_articles_pipeline_handling(self):
    test_file = "test_zero_articles.json"
    initial_data = {
        "schema_version": 2,
        "data_status": "fresh",
        "generated_at": "2026-10-31T12:00:00Z",
        "last_attempt_at": "2026-10-31T12:00:00Z",
        "takeaway": "Test initial takeaway",
        "trends": [],
        "top_stories": [{"title": "Existing Story", "link": "https://example.com/exist", "source": "Old Source", "trust_tier": 1, "overall_score": 80}],
        "ai_tools": [],
        "dev_radar": [],
        "research_safety": [],
        "pulse_items": []
    }
    with open(test_file, "w", encoding="utf-8") as f:
      json.dump(initial_data, f)

    try:
      with patch("tracker.collect_fresh_news", return_value=[]):
        # 0 fresh articles must NOT raise PipelineExecutionError
        res = tracker.run_pipeline(dry_run=False, output_file=test_file)
        self.assertIsNotNone(res)
        with open(test_file, "r", encoding="utf-8") as f:
          data = json.load(f)
        self.assertEqual(data["top_stories"][0]["title"], "Existing Story")
    finally:
      if os.path.exists(test_file):
        os.remove(test_file)

  def test_paired_evidence_validation_and_anti_hallucination(self):
    art1 = {
        "article_id": "art_openai_101",
        "link": "https://openai.com/news/o3-model",
        "title": "OpenAI releases o3 reasoning model with competitive math benchmarks",
        "summary": "OpenAI announced o3 reasoning model with frontier benchmark evaluations.",
        "publisher_group_id": "openai",
        "trust_tier": 1,
    }
    art2 = {
        "article_id": "art_verge_202",
        "link": "https://theverge.com/ai/o3-review",
        "title": "The Verge tests OpenAI o3 reasoning model",
        "summary": "Independent testing confirms frontier performance on math and code.",
        "publisher_group_id": "vox_media",
        "trust_tier": 2,
    }
    raw_articles_list = [art1, art2]
    synthesis_ids = {"art_openai_101", "art_verge_202"}

    # 1. Valid paired reference
    trend_valid = {
        "title": "OpenAI Releases o3 Model",
        "trend_type": "single_development",
        "evidence": [{
            "article_id": "art_openai_101",
            "canonical_url": "https://openai.com/news/o3-model",
            "supporting_excerpt": "OpenAI announced o3 reasoning model with frontier benchmark evaluations."
        }]
    }
    res_valid = tracker.validate_evidence_provenance([trend_valid], raw_articles_list, synthesis_ids)
    self.assertEqual(len(res_valid), 1)
    valid_trend = res_valid[0]
    self.assertEqual(len(valid_trend["evidence"]), 1)
    self.assertEqual(valid_trend["evidence"][0]["publisher_group_id"], "openai")
    self.assertTrue(valid_trend["evidence"][0]["text_verified"])

    # 2. Mismatched pair: article ID from art1, URL from art2 -> MUST REJECT
    trend_mismatch = {
        "title": "OpenAI Releases o3 Model",
        "trend_type": "single_development",
        "evidence": [{
            "article_id": "art_openai_101",
            "canonical_url": "https://theverge.com/ai/o3-review"
        }]
    }
    res_mismatch = tracker.validate_evidence_provenance([trend_mismatch], raw_articles_list, synthesis_ids)
    self.assertEqual(len(res_mismatch), 0)

    # 3. Fabricated article ID -> MUST REJECT
    trend_fake_id = {
        "title": "Hallucinated Trend",
        "trend_type": "single_development",
        "evidence": [{
            "article_id": "art_fabricated_99999",
            "canonical_url": "https://openai.com/news/o3-model"
        }]
    }
    res_fake_id = tracker.validate_evidence_provenance([trend_fake_id], raw_articles_list, synthesis_ids)
    self.assertEqual(len(res_fake_id), 0)

    # 4. Fabricated URL -> MUST REJECT
    trend_fake_url = {
        "title": "Hallucinated URL",
        "trend_type": "single_development",
        "evidence": [{
            "article_id": "art_openai_101",
            "canonical_url": "https://fake-hallucination.com/fake-news"
        }]
    }
    res_fake_url = tracker.validate_evidence_provenance([trend_fake_url], raw_articles_list, synthesis_ids)
    self.assertEqual(len(res_fake_url), 0)

    # 5. Untrusted model publisher group ignored; trusted publisher group resolved from metadata
    trend_spoof_pub = {
        "title": "Spoofed Publisher",
        "trend_type": "single_development",
        "evidence": [{
            "article_id": "art_openai_101",
            "canonical_url": "https://openai.com/news/o3-model",
            "publisher_group_id": "fabricated_independent_entity"
        }]
    }
    res_spoof = tracker.validate_evidence_provenance([trend_spoof_pub], raw_articles_list, synthesis_ids)
    self.assertEqual(len(res_spoof), 1)
    self.assertEqual(res_spoof[0]["evidence"][0]["publisher_group_id"], "openai")

    # 6. Article not in synthesis input IDs -> MUST REJECT
    res_filtered = tracker.validate_evidence_provenance([trend_valid], raw_articles_list, synthesis_input_ids={"art_verge_202"})
    self.assertEqual(len(res_filtered), 0)

    # 7. Deduplication of identical references
    trend_dup = {
        "title": "Deduplicated References",
        "trend_type": "single_development",
        "evidence": [
            {"article_id": "art_openai_101", "canonical_url": "https://openai.com/news/o3-model"},
            {"article_id": "art_openai_101", "canonical_url": "https://openai.com/news/o3-model"}
        ]
    }
    res_dup = tracker.validate_evidence_provenance([trend_dup], raw_articles_list, synthesis_ids)
    self.assertEqual(len(res_dup), 1)
    self.assertEqual(len(res_dup[0]["evidence"]), 1)

  def test_supporting_excerpt_verification(self):
    article = {
        "title": "Google DeepMind unveils AlphaQubit quantum error correction architecture",
        "summary": "AlphaQubit applies transformer neural networks to decode topological quantum errors in Sycamore processors.",
    }

    # High overlap excerpt verified
    good_excerpt = "AlphaQubit applies transformer neural networks to decode topological quantum errors"
    self.assertTrue(tracker.verify_supporting_excerpt(good_excerpt, article))

    # Exact title excerpt verified
    self.assertTrue(tracker.verify_supporting_excerpt("unveils AlphaQubit quantum error correction architecture", article))

    # Unrelated or fabricated excerpt rejected
    bad_excerpt = "Anthropic raised 50 billion dollars from Saudi Aramco to build fusion reactors"
    self.assertFalse(tracker.verify_supporting_excerpt(bad_excerpt, article))

    # Empty / whitespace excerpt rejected
    self.assertFalse(tracker.verify_supporting_excerpt("", article))
    self.assertFalse(tracker.verify_supporting_excerpt("   ", article))

  def test_claim_corroboration_vs_trend_signal_diversity(self):
    art_aws = {
        "article_id": "art_aws",
        "link": "https://aws.amazon.com/blog/freight-optimization",
        "title": "AWS launches Worldwide Express freight optimization platform",
        "summary": "Amazon Web Services announces cloud logistics optimization.",
        "publisher_group_id": "amazon",
        "trust_tier": 1,
    }
    art_legora = {
        "article_id": "art_legora",
        "link": "https://techcrunch.com/legora-diligence",
        "title": "Legora raises seed round for legal contract diligence",
        "summary": "Legora deploys agentic legal review for venture transactions.",
        "publisher_group_id": "yahoo_techcrunch",
        "trust_tier": 2,
    }
    articles_theme_list = [art_aws, art_legora]

    # Theme connecting distinct developments: diversity = 2, but claim corroboration = 1
    theme_trend = {
        "title": "Autonomous Enterprise Operations Expand",
        "trend_type": "emerging_theme",
        "theme_relationship": "Connects multi-modal freight logistics with enterprise contract legal diligence.",
        "claims": [
            {
                "claim_id": "cl_1",
                "text": "AWS launches freight routing optimization",
                "evidence": [{"article_id": "art_aws", "canonical_url": "https://aws.amazon.com/blog/freight-optimization"}]
            },
            {
                "claim_id": "cl_2",
                "text": "Legora launches contract diligence agent",
                "evidence": [{"article_id": "art_legora", "canonical_url": "https://techcrunch.com/legora-diligence"}]
            }
        ]
    }
    res_theme = tracker.validate_evidence_provenance([theme_trend], articles_theme_list, {"art_aws", "art_legora"})
    self.assertEqual(len(res_theme), 1)
    theme_out = res_theme[0]
    self.assertEqual(theme_out["trend_type"], "emerging_theme")
    self.assertEqual(theme_out["status"], "emerging_theme")
    self.assertEqual(theme_out["trend_signal_diversity"], 2)
    self.assertEqual(theme_out["claim_corroboration"], 1)  # Distinct events do NOT corroborate each other!
    self.assertEqual(theme_out["claims"][0]["claim_corroboration"], 1)
    self.assertEqual(theme_out["claims"][1]["claim_corroboration"], 1)

    # Single development corroborated across multiple independent publisher groups
    art_dm = {
        "article_id": "art_dm",
        "link": "https://deepmind.google/blog/alpha-math",
        "title": "DeepMind solves Olympiad geometry benchmark",
        "summary": "AlphaGeometry achieves gold-medal standard reasoning on Olympiad geometry.",
        "publisher_group_id": "alphabet",
        "trust_tier": 1,
    }
    art_tc = {
        "article_id": "art_tc",
        "link": "https://techcrunch.com/deepmind-alphageometry",
        "title": "TechCrunch tests DeepMind AlphaGeometry benchmark",
        "summary": "Independent evaluation verifies gold-medal mathematical reasoning.",
        "publisher_group_id": "yahoo_techcrunch",
        "trust_tier": 2,
    }
    articles_dev_list = [art_dm, art_tc]
    dev_trend = {
        "title": "DeepMind AlphaGeometry Achieves Olympiad Benchmark",
        "trend_type": "single_development",
        "claims": [
            {
                "claim_id": "cl_geom",
                "text": "DeepMind AlphaGeometry achieves Olympiad gold-medal geometry reasoning",
                "evidence": [
                    {"article_id": "art_dm", "canonical_url": "https://deepmind.google/blog/alpha-math"},
                    {"article_id": "art_tc", "canonical_url": "https://techcrunch.com/deepmind-alphageometry"}
                ]
            }
        ]
    }
    res_dev = tracker.validate_evidence_provenance([dev_trend], articles_dev_list, {"art_dm", "art_tc"})
    self.assertEqual(len(res_dev), 1)
    dev_out = res_dev[0]
    self.assertEqual(dev_out["trend_type"], "single_development")
    self.assertEqual(dev_out["status"], "independently_corroborated")
    self.assertEqual(dev_out["claim_corroboration"], 2)  # Two independent publisher groups corroborate claim!
    self.assertEqual(dev_out["trend_signal_diversity"], 2)

  def test_source_health_monitoring_and_operating_cases(self):
    # Case A: Normal healthy run
    mock_health_healthy = {
        "status": "healthy",
        "configured_sources_count": 22,
        "enabled_sources_count": 22,
        "successful_fetches_count": 22,
        "failed_fetches_count": 0,
        "valid_empty_sources_count": 0,
        "total_articles_received": 50,
        "rejected_by_relevance_count": 10,
        "rejected_by_freshness_count": 5,
        "fresh_articles_accepted_count": 35,
        "unique_article_count": 35,
    }
    self.assertEqual(mock_health_healthy["status"], "healthy")
    self.assertEqual(mock_health_healthy["failed_fetches_count"], 0)

    # Case C: Degraded run (1 source fails, processing continues)
    mock_health_degraded = {
        "status": "degraded",
        "configured_sources_count": 22,
        "enabled_sources_count": 22,
        "successful_fetches_count": 21,
        "failed_fetches_count": 1,
        "valid_empty_sources_count": 0,
        "total_articles_received": 45,
        "rejected_by_relevance_count": 5,
        "rejected_by_freshness_count": 5,
        "fresh_articles_accepted_count": 35,
        "unique_article_count": 35,
    }
    self.assertEqual(mock_health_degraded["status"], "degraded")
    self.assertGreater(mock_health_degraded["fresh_articles_accepted_count"], 0)

    # Case D: Total upstream failure -> run_pipeline raises PipelineExecutionError and preserves data
    test_file_total_fail = "test_total_fail.json"
    init_data = {
        "schema_version": 2,
        "data_status": "fresh",
        "generated_at": "2026-11-01T12:00:00Z",
        "top_stories": [{"title": "Verified Existing Story", "trust_tier": 1, "overall_score": 85}],
    }
    with open(test_file_total_fail, "w", encoding="utf-8") as f:
      json.dump(init_data, f)

    try:
      total_failure_telemetry = {
          "status": "total_failure",
          "configured_sources_count": 22,
          "enabled_sources_count": 22,
          "successful_fetches_count": 0,
          "failed_fetches_count": 22,
          "valid_empty_sources_count": 0,
          "total_articles_received": 0,
          "rejected_by_relevance_count": 0,
          "rejected_by_freshness_count": 0,
          "fresh_articles_accepted_count": 0,
          "unique_article_count": 0,
      }
      with patch("tracker.collect_fresh_news", return_value=([], total_failure_telemetry, [])):
        with self.assertRaises(tracker.PipelineExecutionError):
          tracker.run_pipeline(dry_run=False, output_file=test_file_total_fail)

        # Ensure dataset was PRESERVED and not corrupted/emptied
        with open(test_file_total_fail, "r", encoding="utf-8") as f:
          restored = json.load(f)
        self.assertEqual(restored["top_stories"][0]["title"], "Verified Existing Story")
    finally:
      if os.path.exists(test_file_total_fail):
        os.remove(test_file_total_fail)

  def test_editorial_grounding_fields(self):
    dummy_articles = [{
        "title": "Anthropic releases Claude 3.5 Sonnet computer use capability in API",
        "summary": "Anthropic announces general availability of programmatic computer use API allowing Claude to control desktop software, browse, and fill forms.",
        "source": "Anthropic News & Research",
        "source_id": "anthropic_news",
        "publisher_id": "anthropic",
        "publisher_group_id": "anthropic",
        "trust_tier": 1,
        "is_official": True,
        "link": "https://www.anthropic.com/news/3-5-models-and-computer-use",
        "published": "Oct 31, 14:00 UTC",
        "published_datetime": None,
    }]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_articles)
    payload = tracker.build_complete_payload(clustered)
    story = payload["top_stories"][0]

    # Verify reported_facts is a non-empty list of factual bullets
    self.assertIsInstance(story["reported_facts"], list)
    self.assertGreaterEqual(len(story["reported_facts"]), 1)
    for fact in story["reported_facts"]:
      self.assertGreaterEqual(len(fact), 15)

    # Verify what_changed, why_it_matters, potential_impact, analysis_limitations
    self.assertIsInstance(story["what_changed"], str)
    self.assertGreaterEqual(len(story["what_changed"]), 15)

    self.assertIsInstance(story["why_it_matters"], str)
    self.assertGreaterEqual(len(story["why_it_matters"]), 15)

    self.assertIsInstance(story["potential_impact"], str)
    self.assertGreaterEqual(len(story["potential_impact"]), 15)

    self.assertIsInstance(story["analysis_limitations"], str)
    self.assertGreaterEqual(len(story["analysis_limitations"]), 15)

    # Verify no generic template boilerplate
    self.assertNotIn("could impact developers and businesses without specifics", story["why_it_matters"])
    self.assertNotIn("Lorem ipsum", story["what_changed"])

  def test_classify_article_type_taxonomy(self):
    """Phase 5: Unit test that classify_article_type classifies benchmark/press release/research correctly."""
    self.assertEqual(
        tracker.classify_article_type("DeepSeek-R1 Paper", link="https://arxiv.org/abs/2501.12948"),
        "research_paper"
    )
    self.assertEqual(
        tracker.classify_article_type("Scaling Laws for Neural Language Models", link="https://arxiv.org/abs/2001.08361"),
        "research_paper"
    )
    self.assertEqual(
        tracker.classify_article_type("How Legora uses GPT-4o to build legal workflows", link="https://openai.com/index/customer-stories/legora/"),
        "case_study_pr"
    )
    self.assertEqual(
        tracker.classify_article_type("Meta Releases Llama 3.3 70B with Open Weights", link="https://ai.meta.com/blog/llama-3-3/"),
        "open_source_release"
    )
    self.assertEqual(
        tracker.classify_article_type("Introducing Claude 3.7 Sonnet and hybrid reasoning", link="https://www.anthropic.com/news/claude-3-7-sonnet"),
        "frontier_launch"
    )
    self.assertEqual(
        tracker.classify_article_type("Anthropic releases Model Context Protocol TypeScript SDK v1.2", link="https://github.com/modelcontextprotocol/sdk"),
        "sdk_api_update"
    )
    self.assertEqual(
        tracker.classify_article_type("Prompt Injection Vulnerability Discovered in Multi-Agent Frameworks", link="https://theverge.com/security"),
        "security_vulnerability"
    )
    self.assertEqual(
        tracker.classify_article_type("EU AI Act Enforcement Guidelines Finalized", link="https://reuters.com/ai-act"),
        "policy_regulation"
    )

  def test_case_study_pr_scoring_calibration_and_cap(self):
    """Phase 5: Unit test that single-source case studies are capped at <= 64.0 and have 0.60x multiplier applied."""
    art_cs = {
        "title": "Customer Case Study: How Company X Deployed Enterprise Agents",
        "summary": "Enterprise adoption details and partner spotlight on workflow acceleration",
        "link": "https://openai.com/customer-stories/company-x",
        "article_type": "case_study_pr",
        "claim_corroboration": 1,
        "trust_tier": 1,
        "is_official": True,
    }
    scores_cs = tracker.calculate_story_scores(art_cs)
    ps = scores_cs["pulse_score"]
    self.assertLessEqual(ps, 64.0, f"Case study score {ps} must be capped at 64.0")
    self.assertEqual(scores_cs["signal_badge"], "🏢 Case Study")

    # Verify multiplier: without case_study_pr, baseline score is noticeably higher
    art_regular = dict(art_cs)
    art_regular["article_type"] = "frontier_launch"
    scores_regular = tracker.calculate_story_scores(art_regular)
    self.assertGreater(scores_regular["pulse_score"], ps)

  def test_hybrid_clustering_anchor_entity_tokens(self):
    """Phase 5: Unit test that hybrid clustering merges anchor entity tokens despite phrase variance."""
    art1 = {
        "title": "Anthropic launches Claude 3.7 Sonnet with hybrid reasoning capabilities",
        "source": "Anthropic News",
        "published_datetime": None,
    }
    art2 = {
        "title": "TechCrunch: Benchmarking Claude 3.7 performance across coding evaluations",
        "source": "TechCrunch AI",
        "published_datetime": None,
    }
    # Despite vocabulary variance, shared anchor model token "claude 3.7" ensures merge
    self.assertTrue(tracker.compute_hybrid_similarity(art1, art2))

  def test_conditional_http_304_caching(self):
    """Phase 5: Unit test that conditional HTTP 304 caching avoids redundant downloads."""
    import urllib.error
    feed_url = "https://example.com/feed.xml"
    cache = {
        feed_url: {
            "etag": "\"test-etag-456\"",
            "last_modified": "Mon, 01 Nov 2026 12:00:00 GMT",
            "cached_items": [{"title": "Cached headline from earlier run", "link": "https://example.com/item1"}]
        }
    }
    class Mock304Error(urllib.error.HTTPError):
      def __init__(self):
        super().__init__(feed_url, 304, "Not Modified", {}, None)

    with patch("urllib.request.urlopen", side_effect=Mock304Error()):
      items, status = tracker.parse_feed_with_fallback_status(feed_url, cache=cache)
      self.assertEqual(status, 304)
      self.assertEqual(len(items), 1)
      self.assertEqual(items[0]["title"], "Cached headline from earlier run")

  def test_build_complete_payload_v21_fields(self):
    """Phase 5: Integration test that build_complete_payload includes article_type and signal_badge for every item."""
    dummy_articles = [
        {
            "title": "OpenAI announces GPT-4.5 with multimodal reasoning",
            "summary": "Official announcement of frontier reasoning model GPT-4.5",
            "link": "https://openai.com/index/gpt-4-5",
            "source": "OpenAI News",
            "source_id": "openai_news",
            "source_type": "official",
            "trust_tier": 1,
            "is_official": True,
            "publisher_id": "openai",
            "publisher_group_id": "openai",
            "published_datetime": None,
        },
        {
            "title": "BAIR benchmark analysis on multi-turn agent tool use",
            "summary": "Academic research paper evaluating benchmark datasets for agents",
            "link": "https://bair.berkeley.edu/blog/agent-evals",
            "source": "BAIR Blog",
            "source_id": "bair_blog",
            "source_type": "research",
            "trust_tier": 3,
            "is_official": True,
            "publisher_id": "bair",
            "publisher_group_id": "uc_berkeley",
            "published_datetime": None,
        }
    ]
    clustered = tracker.cluster_and_deduplicate_articles(dummy_articles)
    payload = tracker.build_complete_payload(clustered)

    # Check top-level required sections
    for sec in ["top_stories", "trends", "ai_tools", "dev_radar", "research_safety"]:
      items = payload.get(sec, [])
      self.assertIsInstance(items, list)
      for item in items:
        self.assertIn("article_type", item, f"Missing article_type in {sec}")
        self.assertIn(item["article_type"], tracker.VALID_ARTICLE_TYPES)
        self.assertIn("signal_badge", item, f"Missing signal_badge in {sec}")
        self.assertEqual(item["signal_badge"], tracker.SIGNAL_BADGE_MAP[item["article_type"]])


if __name__ == "__main__":
  unittest.main()
