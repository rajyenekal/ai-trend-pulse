"""
pipeline - Modular AI Trend Pulse Ingestion, Scoring, Clustering, and Synthesis Package.
"""

from .scorer import (
    VALID_ARTICLE_TYPES,
    ARTICLE_TYPE_MULTIPLIERS,
    SIGNAL_BADGE_MAP,
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
)

from .clustering import (
    stem_word,
    tokenize_title,
    detect_model_family,
    extract_anchor_entities,
    compute_overlap_coefficient,
    compute_title_similarity,
    compute_hybrid_similarity,
    cluster_and_deduplicate_articles,
    determine_evidence_metadata,
)

from .fetcher import (
    FALLBACK_SOURCE_REGISTRY,
    load_source_registry,
    load_all_sources,
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

from .enricher import (
    verify_supporting_excerpt,
    validate_evidence_provenance,
    synthesize_with_gemini,
    generate_editorial_trio,
    generate_reported_facts,
    generate_potential_impact_statement,
    generate_analysis_limitations,
    extract_key_points,
    extract_affected_stakeholders,
    generate_daily_overview,
    build_complete_payload,
    validate_dataset_payload,
    PipelineExecutionError,
    run_pipeline,
)

from .extractor import (
    ARTICLE_CACHE_FILE,
    load_article_cache,
    save_article_cache,
    fetch_raw_html,
    extract_article_content,
    extract_articles_batch,
    compute_extraction_telemetry,
    is_safe_public_url,
)

from .developer_scorer import (
    calculate_developer_trend_score,
)

from .github_collector import (
    GITHUB_SNAPSHOTS_FILE,
    load_github_snapshots,
    save_github_snapshots,
    calculate_historical_growth,
    collect_github_developer_trends,
)
