"""
pipeline.github_collector - AI Developer Trends Ingestion, Snapshot Tracking & Growth Analytics.

Connects to GitHub API for curated AI developer topics, maintains historical snapshots
in .github_snapshots.json, calculates verified 24h/7d star growth (null when missing),
and computes independent developer trend scores.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import glob
import json
import logging
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

# Auto-detect local virtualenv site-packages if running under system python
for _site in (
    glob.glob(os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages"))
    + glob.glob(os.path.join(os.path.dirname(__file__), ".venv", "lib", "python*", "site-packages"))
):
  if os.path.isdir(_site) and _site not in sys.path:
    sys.path.insert(0, _site)

from .developer_scorer import calculate_developer_trend_score

logger = logging.getLogger("pipeline.github_collector")

GITHUB_SNAPSHOTS_FILE = ".github_snapshots.json"
DEFAULT_TIMEOUT = 10.0
MAX_SNAPSHOT_DAYS = 35
MAX_OBSERVATIONS_PER_REPO = 100
USER_AGENT = "AI-Trend-Pulse-Developer-Trends/2.1 (+https://github.com/rajyenekal/ai-trend-pulse)"

AI_SEARCH_QUERIES = [
    "topic:ai-agent stars:>50",
    "topic:rag stars:>50",
    "topic:mcp stars:>50",
    "topic:llm stars:>100",
    "topic:coding-assistant stars:>50",
]


def load_github_snapshots(snapshot_file=GITHUB_SNAPSHOTS_FILE, fallback_data_file=None) -> dict:
  """Loads historical repository snapshots from disk, seeding from data.json if cold."""
  if os.path.exists(snapshot_file):
    try:
      with open(snapshot_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict) and data.get("snapshots"):
          return data
    except Exception as e:
      logger.warning("Failed to load GitHub snapshots from %s: %s", snapshot_file, e)

  # Cold start recovery: seed from committed data.json if available
  seeded = {"last_updated": None, "snapshots": {}}
  if fallback_data_file and os.path.exists(fallback_data_file):
    try:
      with open(fallback_data_file, "r", encoding="utf-8") as f:
        p = json.load(f)
        if isinstance(p, dict) and p.get("developer_trends"):
          for item in p["developer_trends"]:
            repo = item.get("repository")
            stars = item.get("stars")
            forks = item.get("forks")
            ts = item.get("collected_at") or item.get("updated_at")
            if repo and stars is not None and ts:
              seeded["snapshots"].setdefault(repo, []).append({
                  "timestamp": ts,
                  "stars": stars,
                  "forks": forks or 0,
              })
          if seeded["snapshots"]:
            seeded["last_updated"] = p.get("generated_at")
    except Exception as e:
      logger.warning("Failed seeding snapshots from fallback %s: %s", fallback_data_file, e)

  return seeded


def save_github_snapshots(snapshot_data: dict, snapshot_file=GITHUB_SNAPSHOTS_FILE):
  """Atomically writes historical repository snapshots to disk with time-window pruning."""
  if not isinstance(snapshot_data, dict):
    return

  now = datetime.now(timezone.utc)
  cutoff_time = now - timedelta(days=MAX_SNAPSHOT_DAYS)
  snapshots = snapshot_data.get("snapshots", {})

  # Prune entries older than MAX_SNAPSHOT_DAYS or exceeding MAX_OBSERVATIONS_PER_REPO
  pruned_snapshots = {}
  for repo, records in snapshots.items():
    valid_records = []
    for rec in records:
      ts_str = rec.get("timestamp")
      if ts_str:
        try:
          rec_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
          if rec_dt.tzinfo is None:
            rec_dt = rec_dt.replace(tzinfo=timezone.utc)
          if rec_dt >= cutoff_time:
            valid_records.append(rec)
        except Exception:
          pass
    if valid_records:
      # Keep up to MAX_OBSERVATIONS_PER_REPO newest
      pruned_snapshots[repo] = valid_records[-MAX_OBSERVATIONS_PER_REPO:]

  snapshot_data["snapshots"] = pruned_snapshots
  snapshot_data["last_updated"] = now.isoformat()

  tmp_file = f"{snapshot_file}.tmp"
  try:
    with open(tmp_file, "w", encoding="utf-8") as f:
      json.dump(snapshot_data, f, indent=2)
    os.replace(tmp_file, snapshot_file)
  except Exception as e:
    logger.warning("Failed to save GitHub snapshots to %s: %s", snapshot_file, e)
    if os.path.exists(tmp_file):
      try:
        os.remove(tmp_file)
      except Exception:
        pass


def calculate_historical_growth(
    repo_name: str,
    current_stars: int,
    snapshots_dict: dict,
    reference_dt: datetime = None,
) -> tuple[int | None, int | None]:
  """Calculates stars_gained_24h and stars_gained_7d based exclusively on recorded historical snapshots.
  Strict rules:
  - If no historical snapshot exists within the target time window, returns None.
  - Never fabricates or estimates growth values.
  Returns: (stars_gained_24h, stars_gained_7d)
  """
  if not snapshots_dict or repo_name not in snapshots_dict:
    return None, None

  records = snapshots_dict[repo_name]
  if not records or len(records) < 1:
    return None, None

  now = reference_dt or datetime.now(timezone.utc)

  closest_24h_diff = float("inf")
  snapshot_24h = None

  closest_7d_diff = float("inf")
  snapshot_7d = None

  # 24h window: 18h to 30h ago (ideal: 24h)
  # 7d window: 144h to 204h ago (6 to 8.5 days ago, ideal: 168h)
  for rec in records:
    ts_str = rec.get("timestamp")
    if not ts_str:
      continue
    try:
      rec_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
      if rec_dt.tzinfo is None:
        rec_dt = rec_dt.replace(tzinfo=timezone.utc)
      hours_ago = (now - rec_dt).total_seconds() / 3600.0

      if 18.0 <= hours_ago <= 30.0:
        diff = abs(hours_ago - 24.0)
        if diff < closest_24h_diff:
          closest_24h_diff = diff
          snapshot_24h = rec

      if 144.0 <= hours_ago <= 204.0:
        diff = abs(hours_ago - 168.0)
        if diff < closest_7d_diff:
          closest_7d_diff = diff
          snapshot_7d = rec
    except Exception:
      continue

  stars_gained_24h = None
  if snapshot_24h and "stars" in snapshot_24h:
    delta_24 = current_stars - int(snapshot_24h["stars"])
    stars_gained_24h = max(0, delta_24)

  stars_gained_7d = None
  if snapshot_7d and "stars" in snapshot_7d:
    delta_7d = current_stars - int(snapshot_7d["stars"])
    stars_gained_7d = max(0, delta_7d)

  return stars_gained_24h, stars_gained_7d


def fetch_github_api(endpoint_url: str, token: str = None, timeout: float = DEFAULT_TIMEOUT):
  """Performs an authenticated or unauthenticated GET request to the GitHub REST API.
  Handles HTTP 403 Rate Limits, network errors, and returns JSON payload.
  """
  req = urllib.request.Request(endpoint_url)
  req.add_header("User-Agent", USER_AGENT)
  req.add_header("Accept", "application/vnd.github+json")

  if token:
    req.add_header("Authorization", f"Bearer {token}")

  # Standard SSL context with certificate and hostname verification
  ctx = ssl.create_default_context()
  try:
    import certifi
    ctx.load_verify_locations(cafile=certifi.where())
  except Exception:
    pass

  try:
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
      body = resp.read().decode("utf-8")
      return json.loads(body), resp.status, None
  except urllib.error.HTTPError as e:
    err_body = ""
    try:
      err_body = e.read().decode("utf-8", errors="replace")
    except Exception:
      pass
    remaining = e.headers.get("X-RateLimit-Remaining") if e.headers else None
    reset_ts = e.headers.get("X-RateLimit-Reset") if e.headers else None
    msg = f"HTTP {e.code}: {e.reason} (Remaining: {remaining}, Reset: {reset_ts})"
    return None, e.code, msg
  except Exception as e:
    return None, None, f"{type(e).__name__}: {str(e)}"


def collect_github_developer_trends(
    queries: list[str] = None,
    limit: int = 8,
    snapshot_file: str = GITHUB_SNAPSHOTS_FILE,
    token: str = None,
    fallback_data_file: str = "data.json",
) -> list[dict]:
  """Collects emerging AI developer repositories from GitHub API.
  Records current star snapshots, calculates verified historical growth,
  scores each repository, and returns a validated list of 5-8 developer trend records.
  Gracefully falls back to existing snapshot data or data.json on rate limit or network failure.
  """
  now_iso = datetime.now(timezone.utc).isoformat()
  raw_token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
  gh_token = None
  if raw_token and isinstance(raw_token, str):
    clean = raw_token.strip()
    if clean and clean not in ("true", "false", "None"):
      gh_token = clean

  queries_to_run = queries or AI_SEARCH_QUERIES

  snapshot_data = load_github_snapshots(snapshot_file, fallback_data_file=fallback_data_file)
  snapshots_dict = snapshot_data.setdefault("snapshots", {})

  collected_repos = {}
  rate_limit_encountered = False

  for q in queries_to_run:
    if rate_limit_encountered:
      break
    params = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": 10})
    url = f"https://api.github.com/search/repositories?{params}"

    data, status, err = fetch_github_api(url, token=gh_token)
    if not data or status != 200:
      logger.warning("GitHub query failed for '%s': %s", q, err)
      if status in (403, 429):
        print(f"⚠️ GitHub API rate limit reached: {err}")
        rate_limit_encountered = True
      continue

    items = data.get("items", [])
    for item in items:
      repo_full = item.get("full_name")
      if not repo_full or repo_full in collected_repos:
        continue

      stars = int(item.get("stargazers_count", 0))
      forks = int(item.get("forks_count", 0))
      updated_at = item.get("pushed_at") or item.get("updated_at")
      created_at = item.get("created_at")

      desc = (item.get("description") or "").lower()
      name_low = (item.get("name") or "").lower()
      combined_text = f"{name_low} {desc} {' '.join(item.get('topics', []))}"

      # Filter scam / spam / unrelated crypto spikes
      spam_kw = ["airdrop", "crypto", "token", "presale", "free-money", "telegram", "faucet", "casino"]
      if any(k in combined_text for k in spam_kw):
        continue

      # Filter artificial star spikes (botting signature: thousands of stars with near-zero forks)
      if stars >= 1000 and (forks / max(stars, 1)) < 0.005:
        continue

      # Filter inactive / abandoned repos (> 180 days stale)
      if updated_at:
        try:
          up_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
          if up_dt.tzinfo is None:
            up_dt = up_dt.replace(tzinfo=timezone.utc)
          if (datetime.now(timezone.utc) - up_dt).total_seconds() > 180 * 86400:
            continue
        except Exception:
          pass

      # Record observation into snapshot history
      repo_snapshots = snapshots_dict.setdefault(repo_full, [])
      # Append new observation if at least 1 hour since last observation
      should_append = True
      if repo_snapshots:
        last_obs = repo_snapshots[-1]
        try:
          last_dt = datetime.fromisoformat(last_obs["timestamp"].replace("Z", "+00:00"))
          if (datetime.now(timezone.utc) - last_dt).total_seconds() < 1800:  # 30 mins
            should_append = False
            # Update latest observation stars in place
            last_obs["stars"] = stars
            last_obs["forks"] = forks
        except Exception:
          pass

      if should_append:
        repo_snapshots.append({
            "timestamp": now_iso,
            "stars": stars,
            "forks": forks,
        })

      # Calculate verified growth from historical snapshots
      stars_24h, stars_7d = calculate_historical_growth(repo_full, stars, snapshots_dict)

      # Calculate independent developer trend score
      score, explanation = calculate_developer_trend_score(
          stars=stars,
          forks=forks,
          stars_gained_24h=stars_24h,
          stars_gained_7d=stars_7d,
          updated_at=updated_at,
          created_at=created_at,
      )

      record = {
          "repository": repo_full,
          "name": item.get("name", repo_full.split("/")[-1]),
          "owner": item.get("owner", {}).get("login", repo_full.split("/")[0]),
          "url": item.get("html_url", f"https://github.com/{repo_full}"),
          "description": (item.get("description") or "Open-source AI tool or framework").strip(),
          "stars": stars,
          "forks": forks,
          "language": item.get("language") or "Python",
          "topics": item.get("topics", [])[:6],
          "license": item.get("license", {}).get("spdx_id") if item.get("license") else None,
          "stars_gained_24h": stars_24h,
          "stars_gained_7d": stars_7d,
          "developer_trend_score": score,
          "score_explanation": explanation,
          "created_at": created_at,
          "updated_at": updated_at,
          "collected_at": now_iso,
      }
      collected_repos[repo_full] = record

  # If collection succeeded for some repos, persist snapshots
  if collected_repos:
    save_github_snapshots(snapshot_data, snapshot_file)
    # Sort by developer_trend_score descending
    sorted_trends = sorted(collected_repos.values(), key=lambda r: r["developer_trend_score"], reverse=True)
    return sorted_trends[:limit]

  # Fallback: if collection returned 0 items (e.g. rate limit, offline), preserve existing developer_trends
  logger.info("Preserving last-known-good developer trends from %s", fallback_data_file)
  if os.path.exists(fallback_data_file):
    try:
      with open(fallback_data_file, "r", encoding="utf-8") as f:
        existing_payload = json.load(f)
        if isinstance(existing_payload, dict) and existing_payload.get("developer_trends"):
          return existing_payload["developer_trends"][:limit]
    except Exception as e:
      logger.warning("Failed to load fallback developer trends: %s", e)

  # Secondary fallback: reconstruct from persisted snapshots if available
  if snapshots_dict:
    reconstructed = []
    for repo_full, records in snapshots_dict.items():
      if not records:
        continue
      latest = records[-1]
      stars = latest.get("stars", 0)
      forks = latest.get("forks", 0)
      stars_24h, stars_7d = calculate_historical_growth(repo_full, stars, snapshots_dict)
      score, explanation = calculate_developer_trend_score(
          stars=stars,
          forks=forks,
          stars_gained_24h=stars_24h,
          stars_gained_7d=stars_7d,
      )
      reconstructed.append({
          "repository": repo_full,
          "name": repo_full.split("/")[-1],
          "owner": repo_full.split("/")[0],
          "url": f"https://github.com/{repo_full}",
          "description": "Open-source AI tool or framework",
          "stars": stars,
          "forks": forks,
          "language": "Python",
          "topics": ["ai", "open-source"],
          "license": None,
          "stars_gained_24h": stars_24h,
          "stars_gained_7d": stars_7d,
          "developer_trend_score": score,
          "score_explanation": explanation,
          "created_at": None,
          "updated_at": latest.get("timestamp"),
          "collected_at": latest.get("timestamp") or now_iso,
      })
    if reconstructed:
      reconstructed.sort(key=lambda r: r["developer_trend_score"], reverse=True)
      return reconstructed[:limit]

  return []
