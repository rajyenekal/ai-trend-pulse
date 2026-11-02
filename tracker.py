#!/usr/bin/env python3
"""
AI Trend Pulse — Ingestion, Evaluation, Clustering, Scoring & Publication Engine
v2.1 High-Signal Modular Architecture

Backward-compatible entry point delegating to modular pipeline components:
- pipeline.fetcher: Concurrent fetching, HTTP 304 conditional cache, source registry
- pipeline.clustering: Anchor-entity tokenization, hybrid similarity clustering, deduplication
- pipeline.scorer: 8-intent classification, calibrated pulse scoring, safety/policy floor
- pipeline.enricher: Paired evidence verification, Gemini synthesis, payload building
"""

import sys

# Re-export all pipeline capabilities for complete backwards compatibility
from pipeline.scorer import (
    VALID_ARTICLE_TYPES,
    ARTICLE_TYPE_MULTIPLIERS,
    SIGNAL_BADGE_MAP,
    TOPIC_IMAGE_REGISTRY,
    classify_article_type,
    calculate_story_scores,
    evaluate_article_relevance,
    classify_topic,
    classify_topic_detailed,
    detect_company,
    simplify_jargon,
    estimate_reading_time,
    extract_audience_pills,
    resolve_article_image_metadata,
    sanitize_and_format_summary,
    generate_audience_impact,
)

from pipeline.clustering import (
    stem_word,
    tokenize_title,
    detect_model_family,
    KNOWN_MODEL_KEYWORDS,
    extract_anchor_entities,
    compute_overlap_coefficient,
    compute_title_similarity,
    compute_hybrid_similarity,
    cluster_and_deduplicate_articles,
    determine_evidence_metadata,
)

from pipeline.fetcher import (
    SOURCES_REGISTRY_FILE,
    OUTPUT_DATA_FILE,
    FEED_CACHE_FILE,
    FALLBACK_SOURCE_REGISTRY,
    PUBLISHER_ORGANIZATION_MAP,
    load_source_registry,
    validate_source_record,
    normalize_url,
    parse_published_datetime,
    generate_article_id,
    load_feed_cache,
    save_feed_cache,
    parse_feed_with_fallback_status,
    parse_feed_with_fallback,
    fetch_anthropic_official_news_with_status,
    fetch_anthropic_official_news,
    fetch_source_feed,
    collect_fresh_news,
)

from pipeline.enricher import (
    verify_supporting_excerpt,
    validate_evidence_provenance,
    synthesize_with_gemini,
    generate_editorial_trio,
    generate_reported_facts,
    generate_potential_impact_statement,
    generate_analysis_limitations,
    extract_key_points,
    extract_affected_stakeholders,
    generate_factual_why_it_matters,
    generate_detailed_analysis,
    generate_daily_overview,
    build_complete_payload,
    validate_dataset_payload,
    PipelineExecutionError,
    run_pipeline,
)

from pipeline.extractor import (
    ARTICLE_CACHE_FILE,
    load_article_cache,
    save_article_cache,
    fetch_raw_html,
    extract_article_content,
    extract_articles_batch,
)

from pipeline.developer_scorer import (
    calculate_developer_trend_score,
)

from pipeline.github_collector import (
    GITHUB_SNAPSHOTS_FILE,
    load_github_snapshots,
    save_github_snapshots,
    calculate_historical_growth,
    collect_github_developer_trends,
)

if __name__ == "__main__":
  is_dry_run = "--dry-run" in sys.argv
  try:
    run_pipeline(dry_run=is_dry_run)
  except PipelineExecutionError as err:
    print(f"FATAL: Pipeline execution failed: {err}", file=sys.stderr)
    sys.exit(1)
  except Exception as err:
    print(f"FATAL: Unexpected failure: {err}", file=sys.stderr)
    sys.exit(1)
