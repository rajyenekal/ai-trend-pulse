"""
src.ingestion.rsshub_collector - RSSHub Ingestion Export Interface.
"""

from pipeline.rsshub_collector import (
    build_rsshub_feed_url,
    fetch_rsshub_feed,
    parse_rsshub_xml_fallback,
)
