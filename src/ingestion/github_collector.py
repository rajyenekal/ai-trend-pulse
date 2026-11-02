"""
src.ingestion.github_collector - AI Developer Trends Ingestion Export Interface.
"""

from pipeline.github_collector import (
    GITHUB_SNAPSHOTS_FILE,
    load_github_snapshots,
    save_github_snapshots,
    calculate_historical_growth,
    fetch_github_api,
    collect_github_developer_trends,
)

