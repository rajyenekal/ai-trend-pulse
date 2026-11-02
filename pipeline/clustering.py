"""
pipeline.clustering - Hybrid Lexical + Entity Semantic Clustering and Deduplication.
"""

from datetime import datetime, timezone
import re
from .scorer import calculate_story_scores, classify_article_type
from .fetcher import PUBLISHER_ORGANIZATION_MAP

# -------------------------------------------------------------
# 1. ANCHOR ENTITIES & TOKENIZATION
# -------------------------------------------------------------
ANCHOR_ENTITY_TOKENS = {
    "gpt", "gpt-4", "gpt-4o", "gpt-5", "chatgpt", "o1", "o3", "o3-mini", "o4",
    "claude", "claude 3.7", "claude 3.5", "sonnet", "haiku", "opus",
    "gemini", "gemini 2.0", "gemini 1.5", "gemini 4", "gemini-flash", "gemini-pro",
    "genie", "genie 4", "world simulation",
    "llama", "llama-3", "llama-3.3", "llama 3.3", "llama-4",
    "deepseek", "deepseek-r1", "deepseek r1", "deepseek-v3", "r1", "v3",
    "mistral", "mixtral", "codestral", "pixtral", "voxtral", "voxtral 3",
    "qwen", "qwen-2.5", "qwen 2.5", "qwen 3",
    "grok", "grok-2", "grok-3",
    "copilot", "sora", "midjourney", "stable diffusion",
    "codex", "streamvibe", "mcp", "model context protocol",
}

KNOWN_MODEL_KEYWORDS = {
    "claude": {"claude", "sonnet", "haiku", "opus"},
    "gemini": {"gemini"},
    "genie": {"genie"},
    "gpt": {"gpt", "chatgpt", "o1", "o3", "o4"},
    "llama": {"llama"},
    "mistral": {"mistral", "mixtral", "codestral", "pixtral", "voxtral"},
    "deepseek": {"deepseek", "r1", "v3"},
    "grok": {"grok"},
    "copilot": {"copilot"},
    "qwen": {"qwen"},
}


def stem_word(w):
  """Lightweight suffix stripping for robust headline clustering without heavy NLP dependencies."""
  return re.sub(r'(izing|ized|ize|ation|ition|ing|ed|ly|es|s|al)$', '', w)


def tokenize_title(title):
  """Extracts meaningful keyword tokens with stemming for similarity matching."""
  clean = re.sub(r"[^a-zA-Z0-9\s\.\-]", " ", title.lower())
  words = clean.split()
  stopwords = {
      "the", "a", "an", "in", "on", "at", "for", "to", "and", "of", "with",
      "by", "is", "are", "ai", "how", "what", "why", "its", "from", "into", "via",
      "new", "releases", "announces", "introduces", "unveils"
  }
  tokens = set()
  for w in words:
    w_clean = w.strip(".-")
    if not w_clean or w_clean in stopwords:
      continue
    if w_clean in ANCHOR_ENTITY_TOKENS:
      tokens.add(w_clean)
    else:
      stemmed = stem_word(w_clean)
      if len(stemmed) > 2:
        tokens.add(stemmed)
  return tokens


def detect_model_family(title):
  t = title.lower()
  detected = set()
  for family, kw_set in KNOWN_MODEL_KEYWORDS.items():
    if any(k in t for k in kw_set):
      detected.add(family)
  return detected


def extract_anchor_entities(title):
  """Extracts specific model names or product anchor entities."""
  t = title.lower()
  found = set()
  for entity in ANCHOR_ENTITY_TOKENS:
    if re.search(r'\b' + re.escape(entity) + r'\b', t):
      found.add(entity)
  return found


def compute_title_similarity(tokens1, tokens2):
  """Standard Jaccard similarity on significant title tokens."""
  if not tokens1 or not tokens2:
    return 0.0
  inter = len(tokens1.intersection(tokens2))
  union = len(tokens1.union(tokens2))
  return inter / union if union > 0 else 0.0


def compute_overlap_coefficient(tokens1, tokens2):
  """Overlap coefficient = |A ∩ B| / min(|A|, |B|)."""
  if not tokens1 or not tokens2:
    return 0.0
  inter = len(tokens1.intersection(tokens2))
  min_len = min(len(tokens1), len(tokens2))
  return inter / min_len if min_len > 0 else 0.0


def compute_hybrid_similarity(art1, art2, similarity_threshold=0.38):
  """Evaluates hybrid lexical + entity/semantic similarity between two articles.
  Returns True if the stories should be merged into the same cluster.
  """
  u1 = (art1.get("link") or "").strip().rstrip("/")
  u2 = (art2.get("link") or "").strip().rstrip("/")
  if u1 and u2 and u1.lower() == u2.lower():
    return True

  title1 = art1.get("title", "")
  title2 = art2.get("title", "")

  # Model family guard: do not merge if explicitly conflicting model families are detected
  models1 = detect_model_family(title1)
  models2 = detect_model_family(title2)
  if models1 and models2 and not (models1 & models2):
    return False

  tokens1 = tokenize_title(title1)
  tokens2 = tokenize_title(title2)

  # Check 1: Lexical Jaccard similarity >= threshold
  jaccard_sim = compute_title_similarity(tokens1, tokens2)
  if jaccard_sim >= similarity_threshold:
    return True

  # Check 2: Shared specific anchor entity + lower threshold (0.20) or overlap >= 0.25 within 48h
  entities1 = extract_anchor_entities(title1)
  entities2 = extract_anchor_entities(title2)
  shared_entities = entities1.intersection(entities2)
  if shared_entities:
    dt1 = art1.get("published_datetime")
    dt2 = art2.get("published_datetime")
    within_48h = True
    if dt1 and dt2:
      within_48h = abs((dt1 - dt2).total_seconds()) / 3600.0 <= 48.0
    if within_48h:
      overlap = compute_overlap_coefficient(tokens1, tokens2)
      if jaccard_sim >= 0.20 or overlap >= 0.25:
        return True

  # Check 3: Semantic embedding cosine similarity (if precomputed on articles)
  emb1 = art1.get("_embedding")
  emb2 = art2.get("_embedding")
  if emb1 and emb2 and isinstance(emb1, list) and isinstance(emb2, list):
    dt1 = art1.get("published_datetime")
    dt2 = art2.get("published_datetime")
    within_36h = True
    if dt1 and dt2:
      diff_hours = abs((dt1 - dt2).total_seconds()) / 3600.0
      within_36h = diff_hours <= 36.0
    if within_36h:
      # Compute dot product (normalized cosine)
      dot = sum(a * b for a, b in zip(emb1, emb2))
      if dot >= 0.82:
        return True

  return False


# -------------------------------------------------------------
# 2. EVIDENCE METADATA & PUBLISHER GROUPING
# -------------------------------------------------------------
def determine_evidence_metadata(lead_article, related_sources):
  """Computes truthful, evidence-grounded independent source count, status, and label.
  Avoids counting syndicated copies, multiple feeds from the same parent organization,
  or community discovery feeds as independent corroboration.
  """
  lead_source = lead_article.get("source", "")
  lead_tier = lead_article.get("trust_tier", 2)
  is_official = lead_article.get("is_official", False)
  source_type = lead_article.get("source_type", "publication")

  # Distinct publisher groups across the cluster, excluding discovery feeds
  all_items = [lead_article] + list(related_sources or [])
  publisher_groups = set()

  for item in all_items:
    src_name = item.get("source") or item.get("source_name", "")
    item_stype = item.get("source_type", "")
    item_owns_feed = item.get("publisher_owns_feed")
    group_id = item.get("publisher_group_id") or item.get("publisher_id")
    if not group_id:
      group_id = PUBLISHER_ORGANIZATION_MAP.get(src_name, src_name)

    # Exclude discovery feeds from independent corroborating publisher count
    if (
        item_stype in ("unofficial_discovery", "discovery")
        or item_owns_feed is False
        or str(group_id).lower() in ("ycombinator", "hackernews", "hackernews/community")
        or "discovery" in (src_name or "").lower()
    ):
      continue

    if group_id:
      publisher_groups.add(str(group_id).lower())

  independent_source_count = len(publisher_groups)
  if independent_source_count < 1:
    independent_source_count = 1

  if is_official or lead_tier == 1:
    if independent_source_count >= 2:
      status = "independently_corroborated"
      label = f"Official announcement + {independent_source_count - 1} independent reports"
    else:
      status = "official_announcement"
      label = "Official Announcement"
  elif source_type == "research" or lead_tier == 3 or "arxiv" in (lead_source or "").lower() or "bair" in (lead_source or "").lower():
    if independent_source_count >= 2:
      status = "independently_corroborated"
      label = f"Research preprint covered by {independent_source_count} sources"
    else:
      status = "research_preprint"
      label = "Research Preprint"
  elif lead_tier == 4 or source_type in ("community", "practitioner") or "simon" in (lead_source or "").lower() or "import" in (lead_source or "").lower():
    if independent_source_count >= 2:
      status = "independently_corroborated"
      label = f"Covered by {independent_source_count} independent sources"
    else:
      status = "practitioner_report"
      label = "Practitioner Report"
  elif independent_source_count >= 2:
    status = "independently_corroborated"
    label = f"Covered by {independent_source_count} independent sources"
  else:
    status = "single_source"
    label = "Single-Source Report"

  return {
      "evidence_status": status,
      "evidence_label": label,
      "independent_source_count": independent_source_count,
  }


# -------------------------------------------------------------
# 3. STORY CLUSTERING & MULTI-SOURCE DEDUPLICATION
# -------------------------------------------------------------
def cluster_and_deduplicate_articles(raw_articles, similarity_threshold=0.38):
  """Clusters articles covering the same underlying announcement across publishers.
  Employs hybrid lexical + entity overlap similarity.
  Selects the primary / official source as lead where available.
  """
  clusters = []  # List of lists of articles

  for article in raw_articles:
    matched_cluster = None
    for cluster in clusters:
      lead_article = cluster[0]
      if compute_hybrid_similarity(article, lead_article, similarity_threshold=similarity_threshold):
        matched_cluster = cluster
        break

    if matched_cluster is not None:
      matched_cluster.append(article)
    else:
      clusters.append([article])

  clustered_stories = []
  for cluster_idx, group in enumerate(clusters):
    # Sort group so Tier 1 (Official Lab) is preferred as lead
    group.sort(key=lambda a: (0 if a.get("is_official") else 1, a.get("trust_tier", 2)))
    lead = group[0].copy()

    related_sources = []
    seen_related = {lead["source"]}
    for other in group[1:]:
      if other["source"] not in seen_related:
        seen_related.add(other["source"])
        related_sources.append({
            "source_name": other["source"],
            "source_url": other["link"],
            "article_id": other.get("article_id"),
            "publisher_id": other.get("publisher_id"),
            "publisher_group_id": other.get("publisher_group_id"),
            "source_type": other.get("source_type"),
            "is_primary_source": other.get("is_primary_source"),
            "publisher_owns_feed": other.get("publisher_owns_feed"),
        })

    lead["cluster_id"] = f"cluster_{cluster_idx + 1}"
    lead["related_sources"] = related_sources
    lead["covered_by_sources_count"] = 1 + len(related_sources)

    # Truthful evidence provenance and independent source counting
    evidence_meta = determine_evidence_metadata(lead, related_sources)
    lead.update(evidence_meta)
    lead["independent_publisher_count"] = evidence_meta.get("independent_source_count", 1)

    # First publication & latest update tracking across cluster
    pub_times = [it.get("published_at") or it.get("published") for it in group if it.get("published_at") or it.get("published")]
    lead["first_published_at"] = pub_times[0] if pub_times else lead.get("published")
    lead["latest_updated_at"] = pub_times[-1] if pub_times else lead.get("published")

    # Deterministically classify article intent type based on lead metadata
    lead["article_type"] = classify_article_type(
        lead.get("title", ""), lead.get("summary", ""), lead.get("link", ""), lead.get("source_type", "publication"), lead.get("is_official", False)
    )

    # Calculate scores with grounded corroboration signal and intent multipliers
    scores = calculate_story_scores(lead, corroboration_count=lead["independent_source_count"])
    lead.update(scores)
    clustered_stories.append(lead)

  # Sort by overall score descending
  clustered_stories.sort(key=lambda s: s.get("overall_score", 0), reverse=True)
  return clustered_stories
