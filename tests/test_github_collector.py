"""
tests.test_github_collector - Unit Tests for GitHub Developer Trends Collection,
Historical Snapshots, Growth Calculations, and Independent Developer Scoring.
"""

from datetime import datetime, timezone, timedelta
import glob
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Auto-detect local virtualenv site-packages if running under system python
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

from pipeline.developer_scorer import calculate_developer_trend_score
from pipeline.github_collector import (
    load_github_snapshots,
    save_github_snapshots,
    calculate_historical_growth,
    collect_github_developer_trends,
    MAX_SNAPSHOT_DAYS,
    MAX_OBSERVATIONS_PER_REPO,
)
from pipeline.enricher import validate_dataset_payload, build_complete_payload


class TestDeveloperScorer(unittest.TestCase):

  def test_high_growth_score(self):
    now_iso = datetime.now(timezone.utc).isoformat()
    score, explanation = calculate_developer_trend_score(
        stars=3500,
        forks=420,
        stars_gained_24h=120,
        stars_gained_7d=500,
        updated_at=now_iso,
    )
    self.assertGreaterEqual(score, 75.0)
    self.assertLessEqual(score, 100.0)
    self.assertIn("Breakout", explanation)
    self.assertIn("Active commit activity", explanation)

  def test_cold_start_null_growth_score(self):
    now_iso = datetime.now(timezone.utc).isoformat()
    score, explanation = calculate_developer_trend_score(
        stars=1500,
        forks=120,
        stars_gained_24h=None,
        stars_gained_7d=None,
        updated_at=now_iso,
    )
    # Assigns neutral baseline without crashing
    self.assertGreaterEqual(score, 40.0)
    self.assertLessEqual(score, 75.0)
    self.assertIn("Growth baseline accumulating", explanation)

  def test_stale_repo_penalized(self):
    stale_date = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    score_active, _ = calculate_developer_trend_score(
        stars=2000, forks=200, stars_gained_24h=10, updated_at=datetime.now(timezone.utc).isoformat()
    )
    score_stale, _ = calculate_developer_trend_score(
        stars=2000, forks=200, stars_gained_24h=10, updated_at=stale_date
    )
    self.assertGreater(score_active, score_stale)

  def test_score_bounds(self):
    for stars in [0, 10, 500, 50000]:
      for forks in [0, 5, 200, 10000]:
        score, _ = calculate_developer_trend_score(stars=stars, forks=forks)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)


class TestHistoricalGrowthCalculation(unittest.TestCase):

  def test_exact_growth_when_snapshots_present(self):
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    t_24h_ago = (now - timedelta(hours=24)).isoformat()
    t_7d_ago = (now - timedelta(days=7)).isoformat()

    snapshots = {
        "example/ai-repo": [
            {"timestamp": t_7d_ago, "stars": 1000, "forks": 100},
            {"timestamp": t_24h_ago, "stars": 1150, "forks": 120},
        ]
    }

    g_24h, g_7d = calculate_historical_growth("example/ai-repo", current_stars=1200, snapshots_dict=snapshots, reference_dt=now)
    self.assertEqual(g_24h, 50)   # 1200 - 1150
    self.assertEqual(g_7d, 200)   # 1200 - 1000

  def test_null_growth_when_no_snapshot_in_window(self):
    now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    # Snapshot is only 2 hours ago (not in 18-30h window)
    t_2h_ago = (now - timedelta(hours=2)).isoformat()

    snapshots = {
        "example/ai-repo": [
            {"timestamp": t_2h_ago, "stars": 1190, "forks": 120},
        ]
    }

    g_24h, g_7d = calculate_historical_growth("example/ai-repo", current_stars=1200, snapshots_dict=snapshots, reference_dt=now)
    # Strictly None, never fabricated!
    self.assertIsNone(g_24h)
    self.assertIsNone(g_7d)

  def test_missing_repo_returns_null(self):
    g_24h, g_7d = calculate_historical_growth("nonexistent/repo", current_stars=500, snapshots_dict={})
    self.assertIsNone(g_24h)
    self.assertIsNone(g_7d)


class TestSnapshotPersistence(unittest.TestCase):

  def test_save_and_load_snapshots(self):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
      tmp_path = tmp.name

    try:
      test_data = {
          "last_updated": "2026-11-02T10:00:00Z",
          "snapshots": {
              "test/repo": [
                  {"timestamp": datetime.now(timezone.utc).isoformat(), "stars": 500, "forks": 50}
              ]
          }
      }
      save_github_snapshots(test_data, snapshot_file=tmp_path)
      loaded = load_github_snapshots(snapshot_file=tmp_path)
      self.assertIn("test/repo", loaded["snapshots"])
      self.assertEqual(loaded["snapshots"]["test/repo"][0]["stars"], 500)
    finally:
      if os.path.exists(tmp_path):
        os.remove(tmp_path)

  def test_snapshot_pruning_beyond_max_days(self):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
      tmp_path = tmp.name

    try:
      now = datetime.now(timezone.utc)
      old_date = (now - timedelta(days=MAX_SNAPSHOT_DAYS + 10)).isoformat()
      recent_date = (now - timedelta(days=2)).isoformat()

      test_data = {
          "snapshots": {
              "test/repo": [
                  {"timestamp": old_date, "stars": 100, "forks": 10},
                  {"timestamp": recent_date, "stars": 200, "forks": 20},
              ]
          }
      }
      save_github_snapshots(test_data, snapshot_file=tmp_path)
      loaded = load_github_snapshots(snapshot_file=tmp_path)
      records = loaded["snapshots"]["test/repo"]
      self.assertEqual(len(records), 1)
      self.assertEqual(records[0]["stars"], 200)
    finally:
      if os.path.exists(tmp_path):
        os.remove(tmp_path)


class TestGitHubCollector(unittest.TestCase):

  def setUp(self):
    self.mock_api_payload = {
        "total_count": 1,
        "items": [
            {
                "full_name": "modelcontextprotocol/servers",
                "name": "servers",
                "owner": {"login": "modelcontextprotocol"},
                "html_url": "https://github.com/modelcontextprotocol/servers",
                "description": "Model Context Protocol servers for AI assistants",
                "stargazers_count": 14200,
                "forks_count": 1650,
                "language": "TypeScript",
                "topics": ["ai", "mcp", "agents"],
                "license": {"spdx_id": "MIT"},
                "created_at": "2024-11-25T12:00:00Z",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "pushed_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

  def test_collect_github_developer_trends_success(self):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
      tmp_snap = tmp.name

    try:
      with patch("pipeline.github_collector.fetch_github_api", return_value=(self.mock_api_payload, 200, None)):
        trends = collect_github_developer_trends(
            queries=["topic:mcp"],
            limit=5,
            snapshot_file=tmp_snap,
        )
        self.assertEqual(len(trends), 1)
        r = trends[0]
        self.assertEqual(r["repository"], "modelcontextprotocol/servers")
        self.assertEqual(r["stars"], 14200)
        self.assertEqual(r["forks"], 1650)
        self.assertEqual(r["language"], "TypeScript")
        self.assertEqual(r["license"], "MIT")
        self.assertIn("developer_trend_score", r)
        self.assertGreater(r["developer_trend_score"], 0.0)
        # Cold start returns None for 24h growth (never fabricated)
        self.assertIsNone(r["stars_gained_24h"])

        # Check that snapshot was saved
        snapshots = load_github_snapshots(snapshot_file=tmp_snap)
        self.assertIn("modelcontextprotocol/servers", snapshots["snapshots"])
    finally:
      if os.path.exists(tmp_snap):
        os.remove(tmp_snap)

  def test_rate_limit_fallback_graceful(self):
    fallback_payload = {
        "developer_trends": [
            {
                "repository": "saved/cached-repo",
                "url": "https://github.com/saved/cached-repo",
                "description": "Saved repository",
                "stars": 800,
                "forks": 90,
                "language": "Python",
                "developer_trend_score": 65.0,
                "stars_gained_24h": None,
                "stars_gained_7d": None,
            }
        ]
    }
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
      tmp_fallback = tmp.name
      with open(tmp_fallback, "w", encoding="utf-8") as f:
        json.dump(fallback_payload, f)

    try:
      # Simulate HTTP 403 Rate Limit
      with patch("pipeline.github_collector.fetch_github_api", return_value=(None, 403, "HTTP 403: Rate Limit Exceeded")):
        trends = collect_github_developer_trends(
            queries=["topic:ai-agent"],
            fallback_data_file=tmp_fallback,
        )
        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0]["repository"], "saved/cached-repo")
    finally:
      if os.path.exists(tmp_fallback):
        os.remove(tmp_fallback)


class TestPayloadIntegration(unittest.TestCase):

  def test_validate_payload_with_developer_trends(self):
    dummy_articles = [
        {
            "id": "c1",
            "article_id": "art_1",
            "title": "Anthropic Announces Claude 3.5 Sonnet",
            "link": "https://anthropic.com/news/claude-3-5",
            "source": "Anthropic Official News",
            "trust_tier": 1,
            "overall_score": 92.0,
            "pulse_score": 92.0,
            "category": "AI Models & Research",
            "topic": "AI Models & Research",
            "what_changed": "Claude 3.5 Sonnet released.",
            "why_it_matters": "Sets new coding benchmarks.",
            "evidence_status": "single_source",
            "evidence_label": "Official Lab Announcement",
            "independent_source_count": 1,
            "company": "Anthropic",
            "key_points": ["Point 1"],
            "detailed_analysis": "Detailed text",
            "published": "Nov 02, 10:00 UTC",
            "summary": "Summary text",
        }
    ]

    dev_trends = [
        {
            "repository": "vllm-project/vllm",
            "url": "https://github.com/vllm-project/vllm",
            "stars": 32000,
            "forks": 4800,
            "language": "Python",
            "developer_trend_score": 88.5,
            "stars_gained_24h": 45,
            "stars_gained_7d": 320,
            "score_explanation": "Breakout velocity",
            "description": "High-throughput LLM serving",
        }
    ]

    payload = build_complete_payload(dummy_articles, developer_trends=dev_trends)
    self.assertIn("developer_trends", payload)
    self.assertEqual(len(payload["developer_trends"]), 1)
    self.assertTrue(validate_dataset_payload(payload))


if __name__ == "__main__":
  unittest.main()

