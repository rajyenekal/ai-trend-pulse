"""
tests.test_v22_audit_corrections - Comprehensive Verification for P0/P1 Production Audit Corrections:
1. Extracted article body reaches AI enhancement.
2. AI enhancement uses full body rather than only RSS description.
3. Missing extraction is clearly identified.
4. AI failure does not break ingestion.
5. Fallback output is never falsely labelled AI-generated.
6. Per-article content is available when Read More is opened.
7. Homepage data remains lightweight.
8. No generic placeholder explanations are published.
9. Cross-article duplicated explanations are detected.
10. Editorial classification calibration (open-source models vs commentary vs policy).
11. SSRF prevention for localhost, private IPs, and metadata services.
12. Extraction telemetry correctly distinguishes full extractions from cached fallbacks.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import json
import tempfile
import sys
import glob

# Auto-detect local virtualenv site-packages
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

from pipeline.extractor import (
    is_safe_public_url,
    extract_article_content,
    extract_articles_batch,
    compute_extraction_telemetry,
)
from pipeline.enricher import (
    generate_article_ai_enhancement,
    generate_deterministic_editorial_enhancement,
    build_complete_payload,
)
from pipeline.scorer import (
    classify_article_type,
    classify_impact_level,
)


class TestV22AuditCorrections(unittest.TestCase):

  def test_1_extracted_body_reaches_ai_enhancement(self):
    """Verifies that actual full_text from extraction reaches the enhancement engine."""
    story = {
        "title": "Anthropic Unveils Claude 3.7",
        "source": "Anthropic News",
        "category": "Frontier Models",
        "summary": "Short RSS teaser.",
        "full_text": "Claude 3.7 introduces hybrid test-time compute. In empirical evaluations across GSM8K, the architecture achieved a landmark 94.2% accuracy while maintaining a sub-50ms token latency on optimized infrastructure.",
        "extracted_content": {
            "text": "Claude 3.7 introduces hybrid test-time compute. In empirical evaluations across GSM8K, the architecture achieved a landmark 94.2% accuracy while maintaining a sub-50ms token latency on optimized infrastructure.",
            "extraction_status": "extracted",
            "word_count": 32,
        }
    }
    enhancement = generate_article_ai_enhancement(story, story.get("extracted_content"), enable_llm=False)
    # The enhancement must contain details from the full text (e.g. 94.2% or test-time compute)
    combined = " ".join([
        enhancement.get("ai_overview", ""),
        enhancement.get("ai_what_happened", ""),
        " ".join(enhancement.get("ai_key_details", [])),
        enhancement.get("ai_technical_breakdown", ""),
    ])
    self.assertTrue("94.2%" in combined or "test-time compute" in combined)
    self.assertNotIn("Short RSS teaser", enhancement.get("ai_overview", ""))

  def test_2_ai_enhancement_uses_actual_article_body_not_just_rss(self):
    """Verifies that enhancement extracts from the full body rather than relying solely on the RSS summary."""
    story = {
        "title": "DeepSeek-R1 Architecture Details",
        "source": "DeepSeek",
        "category": "AI Research",
        "summary": "DeepSeek announced new research.",
        "full_text": "DeepSeek-R1 bypasses traditional supervised fine-tuning by applying pure reinforcement learning directly on the base checkpoint. The resulting reasoning behaviors emerge spontaneously through thousands of training iterations.",
    }
    res = generate_article_ai_enhancement(story, enable_llm=False)
    combined = " ".join([
        res.get("ai_overview", ""),
        res.get("ai_what_happened", ""),
        res.get("ai_technical_breakdown", ""),
    ] + res.get("ai_key_details", []))
    self.assertIn("reinforcement learning", combined)

  def test_3_missing_extraction_clearly_identified(self):
    """Verifies that fallback summaries and extraction failures are explicitly tracked."""
    articles = [
        {"title": "Story 1", "extraction_status": "extracted", "word_count": 450},
        {"title": "Story 2", "extraction_status": "fallback_summary", "word_count": 25},
        {"title": "Story 3", "extraction_status": "cached_fallback", "word_count": 22},
        {"title": "Story 4", "extraction_status": "ssrf_blocked", "word_count": 0},
    ]
    telemetry = compute_extraction_telemetry(articles)
    self.assertEqual(telemetry["successful_full_body_extractions"], 1)
    self.assertEqual(telemetry["rss_only_fallbacks"], 2)
    self.assertEqual(telemetry["blocked_pages"], 1)

  def test_4_ai_failure_does_not_break_ingestion(self):
    """Simulates Gemini throwing an unhandled API error and verifies clean fallback."""
    story = {
        "title": "NVIDIA Blackwell Ultra Announcement",
        "source": "NVIDIA Newsroom",
        "category": "AI Infrastructure",
        "summary": "NVIDIA introduced Blackwell Ultra with 288GB HBM3e memory.",
        "full_text": "NVIDIA Blackwell Ultra integrates 288GB of high-bandwidth HBM3e memory delivering 8 terabytes per second memory throughput.",
    }
    with patch("pipeline.enricher.genai") as mock_genai:
      mock_client = MagicMock()
      mock_client.models.generate_content.side_effect = RuntimeError("ResourceExhausted: 429 Quota Exceeded")
      mock_genai.Client.return_value = mock_client
      with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_test_key"}):
        res = generate_article_ai_enhancement(story, enable_llm=True)
        self.assertIsNotNone(res)
        self.assertIn("ai_overview", res)
        self.assertIn("ai_key_details", res)
        # Provenance must state fallback
        self.assertFalse(res.get("is_llm_generated"))
        self.assertEqual(res.get("enhancement_source"), "editorial_synthesis")

  def test_5_fallback_output_never_falsely_labelled_ai_generated(self):
    """Verifies that deterministic synthesis is never tagged as is_llm_generated=True."""
    story = {
        "title": "OpenAI Introduces Projects",
        "source": "OpenAI News",
        "category": "Developer Tools",
        "summary": "OpenAI rolled out workspace organization.",
        "full_text": "ChatGPT Projects enables teams to centralize chats, custom instructions, and files in shared workspaces.",
    }
    res = generate_deterministic_editorial_enhancement(story, story["full_text"])
    self.assertFalse(res["is_llm_generated"])
    self.assertEqual(res["enhancement_source"], "editorial_synthesis")
    self.assertEqual(res["enhancement_label"], "Editorial Synthesis")
    self.assertNotEqual(res["enhancement_label"], "AI-Enhanced Analysis")

  def test_6_per_article_json_available_and_stored(self):
    """Verifies that build_complete_payload writes individual articles/<id>.json files."""
    sample_article = {
        "title": "Google DeepMind AlphaFold 3 Update",
        "source": "Google DeepMind",
        "category": "AI Research",
        "summary": "DeepMind released code for AlphaFold 3.",
        "full_text": "AlphaFold 3 code and model weights are now openly accessible for academic research, predicting joint structures of proteins, DNA, RNA, and ligands.",
        "pulse_score": 88.0,
        "trust_tier": 1,
        "is_official": True,
        "link": "https://deepmind.google/discover/blog/alphafold-3-open-science/",
        "image": "https://deepmind.google/image.jpg",
    }
    payload = build_complete_payload([sample_article], ai_briefing=None)
    self.assertGreater(len(payload["top_stories"]), 0)
    story = payload["top_stories"][0]
    self.assertIn("article_url", story)
    article_path = story["article_url"]
    self.assertTrue(os.path.exists(article_path), f"File {article_path} must exist on disk")

    with open(article_path, "r", encoding="utf-8") as f:
      saved_rec = json.load(f)
    self.assertEqual(saved_rec["title"], story["title"])
    self.assertIn("ai_overview", saved_rec)
    self.assertIn("ai_key_details", saved_rec)
    self.assertIn("original_source_url", saved_rec)

  def test_7_homepage_data_remains_lightweight(self):
    """Verifies that top_stories in payload contain article_url pointers rather than excessive nested blobs."""
    sample_article = {
        "title": "AWS Bedrock Model Evaluation Service",
        "source": "AWS Machine Learning",
        "category": "Developer Tools",
        "summary": "Amazon announced automated Bedrock evaluations.",
        "pulse_score": 76.0,
        "trust_tier": 1,
        "is_official": True,
        "link": "https://aws.amazon.com/blogs/machine-learning/bedrock-eval/",
    }
    payload = build_complete_payload([sample_article], ai_briefing=None)
    story = payload["top_stories"][0]
    self.assertTrue(story["article_url"].startswith("articles/"))

  def test_8_no_generic_placeholder_explanations(self):
    """Verifies that forbidden generic templates are completely eliminated."""
    forbidden_phrases = [
        "Signals actionable market shifts",
        "foundational architectural optimizations",
        "published new technical details on",
    ]
    story = {
        "title": "Mistral AI Releases NeMo",
        "source": "Mistral AI",
        "category": "Open Source AI",
        "summary": "Mistral releases a new lightweight model.",
        "full_text": "Mistral NeMo is a 12B parameter model built in collaboration with NVIDIA, offering an expanded 128k context window.",
    }
    res = generate_article_ai_enhancement(story, enable_llm=False)
    combined_output = " ".join([
        res.get("ai_overview", ""),
        res.get("ai_what_happened", ""),
        res.get("ai_why_it_matters", ""),
        res.get("ai_technical_breakdown", ""),
        " ".join(res.get("ai_key_details", [])),
    ])
    for bad_phrase in forbidden_phrases:
      self.assertNotIn(bad_phrase.lower(), combined_output.lower(), f"Forbidden boilerplate phrase '{bad_phrase}' found in output!")

  def test_9_cross_article_differentiation(self):
    """Verifies that two different stories receive distinct, content-relevant why_it_matters statements."""
    story_a = {
        "title": "Anthropic Publishes Claude Constitutional AI Evals",
        "source": "Anthropic News",
        "category": "AI Safety",
        "summary": "Anthropic published red-teaming evals on alignment.",
        "full_text": "Our new evaluations measure sycophancy, deception, and power-seeking tendencies in frontier reasoning models.",
    }
    story_b = {
        "title": "NVIDIA Blackwell GPU Supercomputing Cluster Online",
        "source": "NVIDIA Newsroom",
        "category": "AI Infrastructure",
        "summary": "NVIDIA announced the DGX SuperPOD cluster.",
        "full_text": "The cluster provides 100 exaflops of AI compute to power trillion-parameter generative models.",
    }
    res_a = generate_article_ai_enhancement(story_a, enable_llm=False)
    res_b = generate_article_ai_enhancement(story_b, enable_llm=False)
    self.assertNotEqual(res_a["ai_why_it_matters"], res_b["ai_why_it_matters"])
    self.assertNotEqual(res_a["ai_overview"], res_b["ai_overview"])

  def test_10_editorial_classification_calibration(self):
    """Verifies that open source, policy, and developer tools are correctly distinguished."""
    # 1. Policy/legal discussing open source must be policy_regulation, NOT open_source_release
    t1 = "Open source AI models face new compliance hurdles under EU AI Act"
    self.assertEqual(classify_article_type(t1), "policy_regulation")

    # 2. Commentary/opinion discussing open source must be opinion_commentary, NOT open_source_release
    t2 = "Why open source AI will win in the enterprise: An analysis"
    self.assertEqual(classify_article_type(t2), "opinion_commentary")

    # 3. Actual model weights release must be open_source_release
    t3 = "DeepSeek releases open weights for DeepSeek-V3 under MIT license"
    self.assertEqual(classify_article_type(t3), "open_source_release")

    # 4. Consumer product from official lab must not be blindly classified as sdk_api_update
    t4 = "Introducing ChatGPT search in desktop apps"
    self.assertEqual(classify_article_type(t4, is_official=True), "frontier_launch")

    # 5. Developer tools/APIs
    t5 = "Anthropic announces new Python SDK and MCP server"
    self.assertEqual(classify_article_type(t5, is_official=True), "sdk_api_update")

    # 6. Case studies never get Breakthrough or Major
    self.assertEqual(classify_impact_level(65.0, article_type="case_study_pr"), "Notable")
    self.assertEqual(classify_impact_level(50.0, article_type="routine_minor_update"), "Notable")

  def test_11_ssrf_protection(self):
    """Verifies that localhost, private IP ranges, link-local metadata addresses are blocked."""
    # Localhost
    safe, msg = is_safe_public_url("http://localhost:8080/metrics")
    self.assertFalse(safe)
    self.assertIn("internal", msg.lower())

    # IPv4 loopback
    safe, msg = is_safe_public_url("http://127.0.0.1:3000")
    self.assertFalse(safe)

    # IPv4 private RFC 1918
    safe, msg = is_safe_public_url("http://10.0.0.1/admin")
    self.assertFalse(safe)

    safe, msg = is_safe_public_url("http://192.168.1.1/secret")
    self.assertFalse(safe)

    safe, msg = is_safe_public_url("http://172.16.0.5/internal")
    self.assertFalse(safe)

    # AWS/Cloud metadata service
    safe, msg = is_safe_public_url("http://169.254.169.254/latest/meta-data/")
    self.assertFalse(safe)

    # Valid public HTTPS domain syntax
    safe, _ = is_safe_public_url("https://www.anthropic.com/news")
    self.assertTrue(safe)


if __name__ == "__main__":
  unittest.main()
