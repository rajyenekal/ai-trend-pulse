"""Tests for AI Trend Pulse Editorial Curation, Noise Filtering & Ranking.
Validates:
- Event clustering and deduplication with independent publisher attribution
- Classification and penalties for vendor case studies and routine minor updates
- Preservation and floor protection for frontier foundation models
- Publisher diversity enforcement across briefing and top developments
- Explainable score reason codes
- Grounded editorial summaries without raw arXiv headers or generic boilerplate
- Schema backward compatibility
"""

import unittest
from datetime import datetime, timezone

from pipeline.clustering import (
    cluster_and_deduplicate_articles,
    compute_hybrid_similarity,
)
from pipeline.fetcher import normalize_url
from pipeline.enricher import (
    build_complete_payload,
    generate_daily_overview,
    generate_editorial_trio,
    sanitize_and_format_summary,
    validate_dataset_payload,
)
from pipeline.scorer import (
    calculate_story_scores,
    classify_article_type,
)


class TestEditorialCuration(unittest.TestCase):
  """Unit and regression tests for high-signal editorial curation pipeline."""

  def test_case_study_classification_and_penalty(self):
    """Vendor case studies and promotional customer stories must be classified as case_study_pr
    and capped below top development eligibility.
    """
    sample_pr_titles = [
        "How Retell AI powers voice agents with AWS Bedrock",
        "Greptile transforms code review workflows for enterprise teams",
        "Worldwide Express streamlines freight logistics using generative AI",
        "Customer Story: Healthcare system deploys LLMs for triage",
    ]

    for title in sample_pr_titles:
      art_type = classify_article_type(
          title=title,
          summary="Case study on how the company integrated foundation models to automate operations.",
          url="https://aws.amazon.com/blogs/machine-learning/customer-retell-ai",
          source_type="publication",
          is_official=True,
      )
      self.assertEqual(
          art_type,
          "case_study_pr",
          f"Expected '{title}' to be classified as 'case_study_pr', got '{art_type}'",
      )

    # Verify single-source case study scoring cap
    scored = calculate_story_scores(
        {
            "title": "How Worldwide Express deploys AI for logistics",
            "summary": "Customer case study detailing logistics automation.",
            "source": "AWS Machine Learning Blog",
            "trust_tier": 1,
            "is_official": True,
            "article_type": "case_study_pr",
        },
        corroboration_count=1,
    )
    self.assertLessEqual(
        scored["overall_score"],
        62.0,
        "Single-source case study score must be capped at <= 62.0",
    )
    self.assertFalse(
        scored["eligible_for_top_developments"],
        "Single-source case study must not be eligible for top developments",
    )
    self.assertFalse(
        scored["eligible_for_briefing"],
        "Single-source case study must not be eligible for briefing",
    )
    self.assertTrue(
        any("case_study_penalty" in r for r in scored["score_reasons"]),
        "Expected case_study_penalty in score reasons",
    )

  def test_routine_minor_update_penalty(self):
    """Routine minor version patches and peripheral updates must be penalized and capped."""
    routine_titles = [
        "NVIDIA GeForce NOW adds 5 new games for the weekend",
        "GeForce Game Ready Driver 552.12 released with bug fixes",
        "Library v0.1.4 released with minor documentation fixes",
    ]

    for title in routine_titles:
      art_type = classify_article_type(
          title=title,
          summary="Routine bug fixes and maintenance release.",
          url="https://blogs.nvidia.com/blog/geforce-now-thursday-nov-2026",
          source_type="publication",
          is_official=True,
      )
      self.assertEqual(
          art_type,
          "routine_minor_update",
          f"Expected '{title}' to be classified as 'routine_minor_update', got '{art_type}'",
      )

    scored = calculate_story_scores(
        {
            "title": "GeForce NOW adds 5 new games for the weekend",
            "summary": "Weekly gaming updates on streaming catalog.",
            "source": "NVIDIA Blog",
            "trust_tier": 1,
            "is_official": True,
            "article_type": "routine_minor_update",
        },
        corroboration_count=1,
    )
    self.assertLessEqual(
        scored["overall_score"],
        52.0,
        "Routine minor update must be capped at <= 52.0",
    )
    self.assertFalse(
        scored["eligible_for_top_developments"],
        "Routine minor update must not be eligible for top developments",
    )
    self.assertTrue(
        any("routine_minor_penalty" in r for r in scored["score_reasons"]),
        "Expected routine_minor_penalty in score reasons",
    )

  def test_frontier_launch_preservation_and_floor(self):
    """Frontier foundation model launches from Tier 1 labs must maintain high priority
    and protected floors, outranking customer stories.
    """
    frontier_releases = [
        (
            "Gemini 4 Carbon: Scalable reasoning for complex tasks",
            "Google DeepMind",
            "google",
        ),
        (
            "Genie 4: Generative interactive environments from video",
            "Google DeepMind",
            "google",
        ),
        (
            "Mistral releases Voxtral 3 multimodal audio model",
            "Mistral AI",
            "mistral",
        ),
        (
            "Anthropic announces Claude 3.7 Sonnet with hybrid reasoning",
            "Anthropic",
            "anthropic",
        ),
    ]

    for title, source, lab in frontier_releases:
      art_type = classify_article_type(
          title=title,
          summary="New foundation model release with benchmark results and technical specifications.",
          url=f"https://{lab}.com/news/{lab}-model-launch",
          source_type="publication",
          is_official=True,
      )
      self.assertEqual(
          art_type,
          "frontier_launch",
          f"Expected '{title}' to be 'frontier_launch', got '{art_type}'",
      )

      scored = calculate_story_scores(
          {
              "title": title,
              "summary": "Major foundation model release achieving new benchmark highs.",
              "source": source,
              "trust_tier": 1,
              "is_official": True,
              "article_type": "frontier_launch",
          },
          corroboration_count=1,
      )
      self.assertGreaterEqual(
          scored["overall_score"],
          82.0,
          f"Frontier release '{title}' must have protected floor >= 82.0, got {scored['overall_score']}",
      )
      self.assertTrue(
          scored["eligible_for_top_developments"],
          f"Frontier release '{title}' must be eligible for top developments",
      )
      self.assertTrue(
          scored["eligible_for_briefing"],
          f"Frontier release '{title}' must be eligible for briefing",
      )

  def test_uncurated_arxiv_preprint_cap(self):
    """Uncorroborated arXiv preprints must not dominate top developments over major releases."""
    scored = calculate_story_scores(
        {
            "title": "Theoretical Bounds on Transformer Attention Entropy",
            "summary": "arXiv:2610.12345 Abstract: We analyze attention entropy scaling in toy transformers.",
            "source": "arXiv cs.AI",
            "trust_tier": 3,
            "is_official": False,
            "article_type": "research_paper",
        },
        corroboration_count=1,
    )
    self.assertLessEqual(
        scored["overall_score"],
        73.0,
        "Single-source arXiv preprint must be capped at <= 73.0",
    )
    self.assertTrue(
        any("uncorroborated_arxiv_cap" in r for r in scored["score_reasons"])
    )

    # But corroborated research with multi-outlet independent coverage can score higher
    corroborated = calculate_story_scores(
        {
            "title": "Breakthrough Quantum Error Correction in Neural Decoders",
            "summary": "Multi-institution research paper published and independently reviewed.",
            "source": "arXiv cs.AI",
            "trust_tier": 3,
            "is_official": False,
            "article_type": "research_paper",
        },
        corroboration_count=3,
    )
    self.assertGreater(
        corroborated["overall_score"],
        73.0,
        "Corroborated research should be allowed to exceed the single-source preprint cap",
    )

  def test_event_clustering_and_deduplication(self):
    """Articles on the same event must be grouped, tracking first_published_at and latest_updated_at."""
    now_iso = datetime.now(timezone.utc).isoformat()
    articles = [
        {
            "article_id": "art_1",
            "title": "Google DeepMind unveils Gemini 4 Carbon foundation model",
            "summary": "Google today introduced Gemini 4 Carbon with breakthrough benchmark reasoning.",
            "link": "https://deepmind.google/discover/blog/gemini-4-carbon/",
            "source": "Google DeepMind",
            "source_id": "deepmind",
            "publisher_group_id": "google",
            "trust_tier": 1,
            "is_official": True,
            "published": "2026-11-02T10:00:00Z",
            "published_at": "2026-11-02T10:00:00Z",
        },
        {
            "article_id": "art_2",
            "title": (
                "DeepMind announces Gemini 4 Carbon with advanced reasoning"
            ),
            "summary": (
                "Google DeepMind's Gemini 4 Carbon sets new state-of-the-art on"
                " reasoning benchmarks."
            ),
            "link": "https://techcrunch.com/2026/11/02/google-gemini-4-carbon/",
            "source": "TechCrunch",
            "source_id": "techcrunch",
            "publisher_group_id": "techcrunch",
            "trust_tier": 2,
            "is_official": False,
            "published": "2026-11-02T11:30:00Z",
            "published_at": "2026-11-02T11:30:00Z",
        },
    ]

    clusters = cluster_and_deduplicate_articles(articles)
    self.assertEqual(
        len(clusters), 1, "Expected 2 articles on Gemini 4 Carbon to be clustered into 1 event"
    )

    lead = clusters[0]
    self.assertEqual(lead["first_published_at"], "2026-11-02T10:00:00Z")
    self.assertEqual(lead["latest_updated_at"], "2026-11-02T11:30:00Z")
    self.assertGreaterEqual(lead["independent_source_count"], 2)
    self.assertGreaterEqual(lead["independent_publisher_count"], 2)

  def test_publisher_diversity_enforcement(self):
    """Top developments must not be dominated by a single publisher group."""
    stories = []
    # Create 8 stories from AWS (e.g. AWS Machine Learning Blog)
    for i in range(8):
      stories.append({
          "title": f"AWS announces Cloud AI Feature {i+1}",
          "summary": f"Amazon Web Services updates Cloud AI infrastructure module {i+1}.",
          "link": f"https://aws.amazon.com/blogs/machine-learning/update-{i+1}",
          "source": "AWS Machine Learning Blog",
          "trust_tier": 1,
          "is_official": True,
          "article_type": "sdk_api_update",
          "overall_score": 85.0 - i,
          "pulse_score": 85.0 - i,
          "independent_source_count": 1,
          "eligible_for_top_developments": True,
          "eligible_for_briefing": True,
      })

    # Create 3 stories from OpenAI and 3 from Anthropic
    for i in range(3):
      stories.append({
          "title": f"OpenAI Frontier Development {i+1}",
          "summary": f"OpenAI releases model benchmark update {i+1}.",
          "link": f"https://openai.com/news/update-{i+1}",
          "source": "OpenAI News",
          "trust_tier": 1,
          "is_official": True,
          "article_type": "frontier_launch",
          "overall_score": 84.0 - i,
          "pulse_score": 84.0 - i,
          "independent_source_count": 1,
          "eligible_for_top_developments": True,
          "eligible_for_briefing": True,
      })
      stories.append({
          "title": f"Anthropic Claude Capability {i+1}",
          "summary": f"Anthropic expands Claude safety evaluation {i+1}.",
          "link": f"https://anthropic.com/news/claude-{i+1}",
          "source": "Anthropic News",
          "trust_tier": 1,
          "is_official": True,
          "article_type": "frontier_launch",
          "overall_score": 83.0 - i,
          "pulse_score": 83.0 - i,
          "independent_source_count": 1,
          "eligible_for_top_developments": True,
          "eligible_for_briefing": True,
      })

    now_iso = datetime.now(timezone.utc).isoformat()
    overview = generate_daily_overview(stories, now_iso)
    top_devs = overview["top_developments"]

    # Verify AWS does not have more than 2 items in top_developments
    aws_count = sum(1 for d in top_devs if "AWS" in d.get("source", ""))
    self.assertLessEqual(
        aws_count,
        2,
        f"Publisher diversity violation: AWS has {aws_count} items in top developments (max allowed: 2)",
    )

  def test_summary_grounding_and_no_raw_arxiv_headers(self):
    """Raw arXiv headers must be cleaned, and boilerplate category templates eliminated."""
    raw_arxiv_summary = (
        "arXiv:2610.40758v1 Announce Type: new Abstract: In this paper we"
        " demonstrate that recursive self-correction can achieve 91% accuracy"
        " on MATH-500 benchmarks without test-time leakage."
    )
    cleaned = sanitize_and_format_summary(
        raw_arxiv_summary, "Recursive Self-Correction"
    )
    self.assertNotIn("arXiv:", cleaned)
    self.assertNotIn("Announce Type:", cleaned)
    self.assertNotIn("Abstract:", cleaned)

    _, what_changed, why_it_matters, potential_impact = generate_editorial_trio(
        title="Mistral releases Voxtral 3 multimodal audio model",
        clean_summary="Mistral AI announced Voxtral 3, an open-weights speech and audio foundation model with 8B parameters.",
        category="AI Models & Research",
        company="Mistral",
    )
    # Ensure why_it_matters is entity-grounded and does not use the deprecated generic boilerplate
    self.assertNotIn("Advances foundational reasoning capabilities", why_it_matters)
    self.assertIn("Mistral", why_it_matters)

  def test_schema_backward_compatibility(self):
    """Generated payload must conform to dataset schema and preserve existing contract."""
    clustered = [
        {
            "article_id": "test_1",
            "cluster_id": "cluster_1",
            "title": "Gemini 4 Carbon Announced by Google DeepMind",
            "summary": "Google DeepMind has officially unveiled Gemini 4 Carbon.",
            "link": "https://deepmind.google/gemini-4",
            "source": "Google DeepMind",
            "trust_tier": 1,
            "is_official": True,
            "published": "2026-11-02T10:00:00Z",
            "published_at": "2026-11-02T10:00:00Z",
            "overall_score": 88.0,
            "pulse_score": 88.0,
            "article_type": "frontier_launch",
            "score_reasons": ["frontier_launch_tier1", "high_novelty"],
            "independent_source_count": 2,
            "independent_publisher_count": 2,
        }
    ]

    payload = build_complete_payload(clustered)
    self.assertTrue(validate_dataset_payload(payload))
    self.assertIn("top_stories", payload)
    self.assertIn("research_safety", payload)
    self.assertIn("top_developments", payload)
    self.assertIn("score_reasons", payload["top_stories"][0])
    self.assertIn("first_published_at", payload["top_stories"][0])
    self.assertIn("latest_updated_at", payload["top_stories"][0])


if __name__ == "__main__":
  unittest.main()
