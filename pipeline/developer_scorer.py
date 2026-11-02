"""
pipeline.developer_scorer - Independent AI Developer Trend Scoring System.

Completely decoupled from editorial news Pulse Score.
Calibrates score based on real repository growth velocity, maintenance recency,
community fork engagement, and adoption baseline.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math


def calculate_developer_trend_score(
    stars: int,
    forks: int,
    stars_gained_24h: int = None,
    stars_gained_7d: int = None,
    updated_at: str = None,
    created_at: str = None,
) -> tuple[float, str]:
  """Calculates an independent Developer Trend Score (0.0 to 100.0) and human-readable explanation.

  Scoring Breakdown:
  1. Velocity (0 - 40 pts): Verified star growth rate. If historical data is missing, assigns neutral 15 pts.
  2. Recency & Maintenance (0 - 25 pts): Time since last push.
  3. Community Engagement (0 - 20 pts): Fork-to-star ratio demonstrating developer adoption vs passive stars.
  4. Maturity Scale (0 - 15 pts): Logarithmic scale preventing vanity dominance while rewarding proven stability.

  Returns: (score: float, explanation: str)
  """
  stars = max(0, int(stars or 0))
  forks = max(0, int(forks or 0))

  # 1. Velocity Component (0 - 40 pts)
  velocity_points = 0.0
  velocity_note = ""

  if stars_gained_24h is not None:
    if stars_gained_24h >= 100:
      velocity_points = 40.0
      velocity_note = f"Breakout 24h star growth (+{stars_gained_24h})"
    elif stars_gained_24h >= 50:
      velocity_points = 34.0 + min(6.0, (stars_gained_24h - 50) * 0.12)
      velocity_note = f"Rapid 24h adoption (+{stars_gained_24h} stars)"
    elif stars_gained_24h >= 20:
      velocity_points = 25.0 + (stars_gained_24h - 20) * 0.3
      velocity_note = f"Solid 24h star momentum (+{stars_gained_24h} stars)"
    elif stars_gained_24h >= 5:
      velocity_points = 15.0 + (stars_gained_24h - 5) * 0.6
      velocity_note = f"Steady daily growth (+{stars_gained_24h} stars)"
    elif stars_gained_24h > 0:
      velocity_points = 8.0 + stars_gained_24h * 1.4
      velocity_note = f"Moderate daily growth (+{stars_gained_24h} stars)"
    else:
      velocity_points = 5.0
      velocity_note = "Flat 24h star growth"
  elif stars_gained_7d is not None and stars_gained_7d > 0:
    # 7-day fallback if 24h window was missed
    daily_avg = stars_gained_7d / 7.0
    velocity_points = min(35.0, 10.0 + daily_avg * 1.5)
    velocity_note = f"7-day growth momentum (+{stars_gained_7d} stars)"
  else:
    # Cold start: No historical snapshots yet
    velocity_points = 15.0
    velocity_note = "Growth baseline accumulating (historical window pending)"

  # 2. Recency & Maintenance Component (0 - 25 pts)
  recency_points = 0.0
  recency_note = ""
  if updated_at:
    try:
      # Parse ISO timestamp
      clean_ts = updated_at.replace("Z", "+00:00")
      up_dt = datetime.fromisoformat(clean_ts)
      if up_dt.tzinfo is None:
        up_dt = up_dt.replace(tzinfo=timezone.utc)
      hours_ago = max(0.0, (datetime.now(timezone.utc) - up_dt).total_seconds() / 3600.0)

      if hours_ago <= 24.0:
        recency_points = 25.0
        recency_note = "Active commit activity in the last 24h"
      elif hours_ago <= 72.0:
        recency_points = 20.0
        recency_note = "Updated within past 3 days"
      elif hours_ago <= 168.0:  # 7 days
        recency_points = 15.0
        recency_note = "Updated within past week"
      elif hours_ago <= 720.0:  # 30 days
        recency_points = 8.0
        recency_note = "Updated this month"
      else:
        recency_points = 2.0
        recency_note = "Maintenance activity paused (>30 days ago)"
    except Exception:
      recency_points = 12.0
      recency_note = "Maintenance status available"
  else:
    recency_points = 10.0
    recency_note = "Recent activity date unconfirmed"

  # 3. Community Engagement / Fork Ratio (0 - 20 pts)
  fork_ratio = forks / max(stars, 1)
  engagement_points = 0.0
  if fork_ratio >= 0.12:
    engagement_points = 20.0  # High developer implementation & contribution
  elif fork_ratio >= 0.08:
    engagement_points = 16.0
  elif fork_ratio >= 0.04:
    engagement_points = 12.0
  elif fork_ratio >= 0.01:
    engagement_points = 8.0
  else:
    engagement_points = 4.0

  # 4. Maturity & Scale Baseline (0 - 15 pts)
  # Logarithmic scale so large repos don't overpower emerging ones
  if stars > 0:
    maturity_points = min(15.0, round(math.log10(stars) * 3.5, 1))
  else:
    maturity_points = 0.0

  total_score = round(min(100.0, max(0.0, velocity_points + recency_points + engagement_points + maturity_points)), 1)
  explanation = f"{velocity_note}; {recency_note}."

  return total_score, explanation
