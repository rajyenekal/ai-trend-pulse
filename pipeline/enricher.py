"""
Intelligence synthesis, editorial enrichment, schema payload construction,
and atomic pipeline execution.
"""

from datetime import datetime, timezone
import json
import os
import re
import sys
import traceback

try:
  from google import genai
  from google.genai import types
except ImportError:
  genai = None
  types = None

from pipeline.scorer import (
    classify_article_type,
    classify_topic,
    classify_topic_detailed,
    detect_company,
    estimate_reading_time,
    extract_audience_pills,
    generate_audience_impact,
    resolve_article_image_metadata,
    sanitize_and_format_summary,
    simplify_jargon,
    SIGNAL_BADGE_MAP,
)
from pipeline.clustering import (
    cluster_and_deduplicate_articles,
    determine_evidence_metadata,
)
from pipeline.fetcher import (
    collect_fresh_news,
    load_source_registry,
    normalize_url,
    PUBLISHER_ORGANIZATION_MAP,
)


class PipelineExecutionError(Exception):
  """Raised when an unrecoverable technical or ingestion failure occurs in run_pipeline."""
  pass


def verify_supporting_excerpt(excerpt, article):
  """Verifies whether the supporting text excerpt actually appears in the article summary or title.
  Returns True if verified, False otherwise.
  """
  if not excerpt or not isinstance(excerpt, str):
    return False
  clean_exc = excerpt.strip().lower()
  if len(clean_exc) < 8:
    return False

  def norm(s):
    return re.sub(r"[^\w\s]", "", (s or "").lower()).strip()

  norm_exc = norm(clean_exc)
  title_norm = norm(article.get("title", ""))
  summary_norm = norm(article.get("summary", ""))
  full_text_norm = norm(article.get("full_text", ""))

  if not norm_exc:
    return False

  if norm_exc in title_norm or norm_exc in summary_norm or (full_text_norm and norm_exc in full_text_norm):
    return True

  # Check if 75% of significant words in excerpt appear in summary, title, or extracted text
  exc_words = [w for w in norm_exc.split() if len(w) > 3]
  if len(exc_words) >= 4:
    target_words = set((title_norm + " " + summary_norm + " " + full_text_norm).split())
    match_count = sum(1 for w in exc_words if w in target_words)
    if match_count / len(exc_words) >= 0.75:
      return True

  return False


def validate_evidence_provenance(trends, collected_articles, synthesis_input_ids=None):
  """Ensures every trend and claim's evidence references strictly belong to the collected source article set.
  Validates paired evidence objects: exact article IDs, exact normalized URLs, and text excerpts.
  Eliminates URL-prefix matching and silent substitutions of unrelated articles.
  Resolves trusted publisher groups from metadata, excluding discovery feeds from corroboration.
  Decouples claim-level corroboration from trend-level signal diversity.
  Distinguishes single_development from emerging_theme.
  """
  if not trends or not isinstance(trends, list):
    return []

  articles_by_id = {a["article_id"]: a for a in collected_articles if a.get("article_id")}
  articles_by_url = {normalize_url(a["link"]): a for a in collected_articles if a.get("link")}
  input_ids_set = set(synthesis_input_ids) if synthesis_input_ids is not None else None

  valid_trends = []

  for t in trends:
    if not isinstance(t, dict):
      continue

    # Extract raw claims or paired evidence references
    raw_claims = t.get("claims")
    raw_evidence = t.get("evidence")
    raw_ids = t.get("evidence_article_ids", [])
    raw_urls = t.get("evidence_urls", [])

    parsed_claims = []

    if isinstance(raw_claims, list) and raw_claims:
      for c_idx, c in enumerate(raw_claims):
        if not isinstance(c, dict):
          continue
        c_text = c.get("text") or c.get("claim") or t.get("what_happened") or t.get("title") or f"Claim {c_idx + 1}"
        c_ev = c.get("evidence") or []
        if isinstance(c_ev, dict):
          c_ev = [c_ev]
        parsed_claims.append({
            "claim_id": c.get("claim_id") or f"claim_{c_idx + 1}",
            "text": c_text,
            "raw_evidence": c_ev
        })
    elif isinstance(raw_evidence, list) and raw_evidence:
      parsed_claims.append({
          "claim_id": "claim_1",
          "text": t.get("what_happened") or t.get("title") or "Primary development",
          "raw_evidence": raw_evidence
      })
    elif isinstance(raw_ids, list) and isinstance(raw_urls, list):
      # Paired legacy lists - strictly pair index-by-index only if canonical URLs match
      paired_ev = []
      min_len = min(len(raw_ids), len(raw_urls))
      for i in range(min_len):
        paired_ev.append({
            "article_id": raw_ids[i],
            "canonical_url": raw_urls[i],
            "supporting_excerpt": t.get("what_happened", "")
        })
      parsed_claims.append({
          "claim_id": "claim_1",
          "text": t.get("what_happened") or t.get("title") or "Primary development",
          "raw_evidence": paired_ev
      })

    # Validate each claim and its evidence references
    validated_claims = []
    trend_all_evidence = []
    seen_trend_article_ids = set()

    for c in parsed_claims:
      valid_claim_refs = []
      claim_seen_ids = set()

      for ref in c.get("raw_evidence", []):
        if not isinstance(ref, dict):
          continue

        aid = ref.get("article_id")
        raw_u = ref.get("canonical_url") or ref.get("url") or ref.get("link")
        if not aid or not isinstance(aid, str) or not raw_u or not isinstance(raw_u, str):
          continue

        norm_u = normalize_url(raw_u)
        if not norm_u:
          continue

        # Check 1: Article ID must exist in collected articles
        if aid not in articles_by_id:
          continue

        art = articles_by_id[aid]

        # Check 2: Exact normalized URL equality - URL must belong to that EXACT article ID
        art_norm_url = normalize_url(art.get("link", ""))
        if norm_u != art_norm_url:
          # Reject mismatched pair
          continue

        # Check 3: If synthesis_input_ids was provided, article must have been in synthesis input
        if input_ids_set is not None and aid not in input_ids_set:
          continue

        # Deduplicate within claim
        if aid in claim_seen_ids:
          continue
        claim_seen_ids.add(aid)

        # Check 4: Excerpt verification
        excerpt = ref.get("supporting_excerpt", "")
        text_verified = verify_supporting_excerpt(excerpt, art)

        # Check 5: Resolve trusted publisher info strictly from metadata, NOT AI
        pub_id = art.get("publisher_id", art.get("source_id", "unknown"))
        pub_group = art.get("publisher_group_id", pub_id)

        valid_ref = {
            "article_id": aid,
            "canonical_url": art["link"],
            "publisher_id": pub_id,
            "publisher_group_id": pub_group,
            "source_name": art.get("source", ""),
            "trust_tier": art.get("trust_tier", 2),
            "is_official": art.get("is_official", False),
            "source_type": art.get("source_type", "publication"),
            "supporting_excerpt": excerpt,
            "text_verified": text_verified,
        }
        valid_claim_refs.append(valid_ref)

        if aid not in seen_trend_article_ids:
          seen_trend_article_ids.add(aid)
          trend_all_evidence.append(valid_ref)

      if valid_claim_refs:
        # Calculate claim-level corroboration (independent publisher groups supporting THIS claim)
        claim_pubs = set()
        for r in valid_claim_refs:
          art_obj = articles_by_id[r["article_id"]]
          stype = art_obj.get("source_type", "publication")
          owns_feed = art_obj.get("publisher_owns_feed", True)
          gid = str(r["publisher_group_id"]).lower()
          # Filter out discovery channels
          if stype not in ("unofficial_discovery", "discovery") and owns_feed is not False and gid not in ("ycombinator", "hackernews"):
            claim_pubs.add(gid)

        claim_corroboration = max(1, len(claim_pubs))

        # Determine claim verification status
        lead_ref = valid_claim_refs[0]
        if lead_ref.get("is_official") or lead_ref.get("trust_tier") == 1:
          if claim_corroboration >= 2:
            c_status = "independently_corroborated"
          else:
            c_status = "official_announcement"
        elif claim_corroboration >= 2:
          c_status = "independently_corroborated"
        elif lead_ref.get("source_type") == "research" or lead_ref.get("trust_tier") == 3:
          c_status = "research_preprint"
        elif lead_ref.get("trust_tier") == 4:
          c_status = "practitioner_report"
        else:
          c_status = "single_source"

        validated_claims.append({
            "claim_id": c["claim_id"],
            "text": c["text"],
            "evidence": valid_claim_refs,
            "claim_corroboration": claim_corroboration,
            "verification_status": c_status
        })

    # If no valid evidence matched from input articles, mark unverified and omit from trusted briefing
    if not trend_all_evidence:
      t["evidence_urls"] = []
      t["evidence_article_ids"] = []
      t["evidence_objects"] = []
      t["claims"] = []
      t["evidence_status"] = "unverified"
      t["evidence_label"] = "Unverified Citation"
      t["independent_source_count"] = 0
      t["trend_signal_diversity"] = 0
      continue

    # Determine trend type: single_development vs emerging_theme
    trend_type = t.get("trend_type")
    if trend_type not in ("single_development", "emerging_theme"):
      distinct_claim_articles = [c["evidence"] for c in validated_claims if c.get("evidence")]
      if len(distinct_claim_articles) >= 2:
        trend_type = "emerging_theme"
      else:
        trend_type = "single_development"

    trend_signal_diversity = len(trend_all_evidence)

    # Decouple claim-level corroboration from trend-level diversity
    if trend_type == "emerging_theme":
      evidence_status = "emerging_theme"
      evidence_label = f"Emerging Theme ({trend_signal_diversity} Signals Across Labs)"
      theme_rel = t.get("theme_relationship") or "Cross-industry developments converging on common technical theme"
      t["theme_relationship"] = theme_rel
      max_claim_corrob = max((c.get("claim_corroboration", 1) for c in validated_claims), default=1)
      independent_source_count = max_claim_corrob
    else:
      lead_ref = trend_all_evidence[0]
      lead_art = articles_by_id[lead_ref["article_id"]]
      lead_tier = lead_art.get("trust_tier", 2)
      claim_corroboration = validated_claims[0].get("claim_corroboration", 1) if validated_claims else 1
      independent_source_count = claim_corroboration

      if lead_art.get("is_official") or lead_tier == 1:
        if claim_corroboration >= 2:
          evidence_status = "independently_corroborated"
          evidence_label = f"Official announcement + {claim_corroboration - 1} independent reports"
        else:
          evidence_status = "official_announcement"
          evidence_label = "Official Announcement"
      elif claim_corroboration >= 2:
        evidence_status = "independently_corroborated"
        evidence_label = f"Covered by {claim_corroboration} independent sources"
      elif lead_art.get("source_type") == "research" or lead_tier == 3:
        evidence_status = "research_preprint"
        evidence_label = "Research Preprint"
      elif lead_tier == 4:
        evidence_status = "practitioner_report"
        evidence_label = "Practitioner Report"
      else:
        evidence_status = "single_source"
        evidence_label = "Single-Source Report"

    t["trend_type"] = trend_type
    t["trend_signal_diversity"] = trend_signal_diversity
    t["claim_corroboration"] = independent_source_count
    t["independent_source_count"] = independent_source_count
    t["evidence_status"] = evidence_status
    t["status"] = evidence_status
    t["is_verified"] = True
    t["evidence_label"] = evidence_label
    t["claims"] = validated_claims
    t["evidence"] = trend_all_evidence
    t["evidence_objects"] = trend_all_evidence
    t["evidence_urls"] = [r["canonical_url"] for r in trend_all_evidence]
    t["evidence_article_ids"] = [r["article_id"] for r in trend_all_evidence]

    valid_trends.append(t)

  return valid_trends


def synthesize_with_gemini(clustered_stories):
  """Synthesizes an executive briefing using Gemini if available, with non-LLM fallback."""
  if not clustered_stories:
    return None

  prompt_articles = ""
  for idx, a in enumerate(clustered_stories[:16], 1):
    pub_str = a.get("published", "Recent")
    art_id = a.get("article_id", f"art_{idx}")
    summary_text = (a.get("full_text") or a.get("summary") or "")[:400]
    prompt_articles += (
        f"{idx}. [ID: {art_id}] [{a.get('source')} | Tier {a.get('trust_tier')}] {a.get('title')}\n"
        f"   Date: {pub_str} | Canonical URL: {a.get('link')}\n"
        f"   Publisher Group: {a.get('publisher_group_id', 'unknown')}\n"
        f"   Summary: {summary_text}\n\n"
    )

  prompt = f"""
You are an expert AI news analyst and fact-checker.
Synthesize these verified AI developments into a structured executive briefing:

{prompt_articles}

Editorial Rules:
1. Anti-Hype: Never claim AI 'replaces humans' or 'achieves consciousness'.
2. Strict Grounding: Base every trend strictly on the provided articles above. Never speculate, invent capabilities, or cite outside events.
3. Paired Evidence References: Every claim MUST cite paired evidence references with exact article IDs and exact canonical URLs from above.
4. Trend Classification: Label trend_type as 'single_development' (one real-world event/claim) or 'emerging_theme' (connecting multiple distinct developments).
5. Transparency: Distinguish official company announcements from independent journalism reports.
6. Provide article_type from: frontier_launch, open_source_release, research_paper, sdk_api_update, security_vulnerability, policy_regulation, case_study_pr, opinion_commentary.
7. Concise Framing: Provide exactly one sentence for what_changed, one sentence for why_it_matters, and one actionable potential_impact sentence.

Return JSON with this exact schema:
{{
  "takeaway": "2-sentence big-picture summary in plain English",
  "trends": [
    {{
      "title": "Clear headline in plain English",
      "trend_type": "single_development OR emerging_theme",
      "theme_relationship": "Explanation if emerging_theme",
      "article_type": "frontier_launch | open_source_release | research_paper | sdk_api_update | security_vulnerability | policy_regulation | case_study_pr | opinion_commentary",
      "what_happened": "1 sentence explaining what happened.",
      "why_it_matters": "1 sentence explaining practical impact.",
      "who_affected": "Developers, Enterprises, AI Practitioners, or Consumers",
      "source": "Primary source name",
      "claims": [
        {{
          "claim_id": "claim_1",
          "text": "Specific factual claim made in the story",
          "evidence": [
            {{
              "article_id": "Exact art_... ID from input",
              "canonical_url": "Exact canonical URL from input",
              "supporting_excerpt": "Verbatim sentence or phrase from the article summary"
            }}
          ]
        }}
      ]
    }}
  ]
}}
"""

  client = None
  if genai and os.environ.get("GEMINI_API_KEY"):
    try:
      client = genai.Client()
    except Exception as e:
      print(f"⚠️ Could not initialize Gemini client: {e}")

  if client:
    models = ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in models:
      try:
        print(f"🧠 Synthesizing executive briefing with {model}...")
        config = None
        if types:
          try:
            config = types.GenerateContentConfig(response_mime_type="application/json")
          except Exception:
            config = None

        response = client.models.generate_content(model=model, contents=prompt, config=config)
        raw_text = (getattr(response, "text", "") or "").strip()
        if "```" in raw_text:
          m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
          if m:
            raw_text = m.group(1).strip()
        json_match = re.search(r"\{[\s\S]*\}", raw_text)
        if json_match:
          data = json.loads(json_match.group(0))
          if isinstance(data, dict) and data.get("trends"):
            print(f"✓ AI synthesis completed successfully using {model}")
            return data
      except Exception as e:
        print(f"⚠️ {model} synthesis failed: {e}")

  return None


def extract_key_points(summary, title, source_name="", why_it_matters="", category="", company=""):
  """Extracts factual bullet points from the actual summary and title without generic boilerplate or title duplicates."""
  clean_summary = (summary or "").strip()
  clean_title = (title or "").strip()

  def norm(s):
    return re.sub(r"[^\w\s]", "", (s or "").lower()).strip()

  norm_title = norm(clean_title)

  sentences = [
      re.sub(r"\s+", " ", sent).strip()
      for sent in re.split(r"(?<=[.!?])\s+", clean_summary)
      if len(sent.strip()) > 20
  ]
  boilerplate_phrases = [
      "reported directly by", "verified against", "refer to the direct publication",
      "relevant to practitioners", "click here", "read more"
  ]
  valid_sentences = [
      s for s in sentences
      if not any(b in s.lower() for b in boilerplate_phrases) and norm(s) != norm_title
  ]
  points = []
  for s in valid_sentences:
    if not any(norm(s) == norm(p) or norm(s) in norm(p) or norm(p) in norm(s) for p in points):
      points.append(s)
    if len(points) >= 3:
      break

  # If why_it_matters is available and distinct, use it as a takeaway bullet
  if len(points) < 3 and why_it_matters:
    clean_why = why_it_matters.strip()
    if norm(clean_why) != norm_title and not any(norm(clean_why) in norm(p) for p in points):
      points.append(clean_why)

  # Fallback: NEVER insert the verbatim title into bullet points
  if not points:
    if clean_summary and norm(clean_summary) != norm_title:
      points.append(clean_summary)
    else:
      points.append(f"Strategic development announced in {category or 'AI'}.")

  return points[:3]


def extract_affected_stakeholders(title, summary, category):
  """Returns a list of 2-3 specific stakeholder roles affected by this development."""
  stakeholder_map = {
      "AI Policy & Regulation": ["Legal & Compliance Teams", "Data Center Operators", "Public Regulators"],
      "AI Security & Safety": ["Security Engineers", "AI Safety Researchers", "System Administrators"],
      "AI Infrastructure": ["Infrastructure Architects", "DevOps Engineers", "Hardware Procurement"],
      "AI Business & Funding": ["Venture Investors", "Startup Founders", "Finance Executives"],
      "AI Models & Research": ["ML Researchers", "Model Developers", "Academic Practitioners"],
      "AI Products & Tools": ["Software Engineers", "Product Managers", "API Consumers"],
      "AI Applications": ["Enterprise Architects", "Operations Managers", "Domain Specialists"],
      "AI News": ["Industry Analysts", "Tech Executives", "AI Practitioners"]
  }
  return stakeholder_map.get(category, ["Developers", "Enterprise Decision Makers"])


def generate_reported_facts(title, clean_summary, source_name=""):
  """Extracts 2-3 verifiable, declarative factual assertions from the source text and headline.
  Never generates generic boilerplate or repeats the entire title verbatim.
  """
  clean_title = (title or "").strip()
  clean_s = (clean_summary or "").strip()

  def norm(s):
    return re.sub(r"[^\w\s]", "", (s or "").lower()).strip()

  sentences = [
      re.sub(r"\s+", " ", sent).strip()
      for sent in re.split(r"(?<=[.!?])\s+", clean_s)
      if len(sent.strip()) > 20
  ]

  facts = []
  norm_title = norm(clean_title)

  action_verbs = [
      "announced", "released", "introduced", "published", "unveiled", "launched",
      "filed", "ruled", "measured", "achieved", "trained", "deployed", "evaluated",
      "demonstrated", "proposes", "finds that", "shows", "expands", "secures"
  ]

  for s in sentences:
    if norm(s) != norm_title and not any(norm(s) in norm(f) or norm(f) in norm(s) for f in facts):
      # Prioritize sentences with action verbs or specific numbers/metrics
      if any(v in s.lower() for v in action_verbs) or re.search(r"\d", s):
        facts.append(s)
      elif len(facts) < 2:
        facts.append(s)
    if len(facts) >= 3:
      break

  # If not enough facts extracted from summary sentences, derive factual assertion from title
  if len(facts) < 2:
    if source_name and source_name not in clean_title:
      facts.append(f"{source_name} reported that {clean_title.rstrip('.')}.")
    else:
      facts.append(f"Primary documentation confirms: {clean_title.rstrip('.')}.")

  return facts[:3]


def generate_potential_impact_statement(title, clean_summary, category, company=""):
  """Generates an analytical projection explicitly labeled as a prospective possibility.
  Distinguishes prospective possibilities from verified current facts.
  """
  comp_str = f" for {company.title()}" if company and company != "default" else ""
  category_projections = {
      "AI Policy & Regulation": "Analytical Projection: Potential regulatory compliance rules may mandate formal algorithmic audits and environmental emission reporting for data-center operators.",
      "AI Security & Safety": "Analytical Projection: Deployment teams may implement stricter defense-in-depth reviews and alignment evaluations prior to granting models autonomous system access.",
      "AI Infrastructure": "Analytical Projection: Expanded compute capacity may reduce inference latency thresholds and lower token costs across enterprise cloud workloads.",
      "AI Business & Funding": "Analytical Projection: Capital reallocation may prioritize foundation model commercialization with verified unit economics over speculative infrastructure.",
      "AI Models & Research": "Analytical Projection: Architectural improvements may establish new performance ceilings on standard reasoning benchmarks while compressing parameter footprints.",
      "AI Products & Tools": "Analytical Projection: Streamlined developer APIs may shorten delivery cycles for intelligent workflows and native agentic integrations.",
      "AI Applications": "Analytical Projection: Domain-specific production deployments may automate transactional workflows and improve operational throughput across enterprise verticals.",
      "AI News": "Analytical Projection: Strategic industry alignment may accelerate technical collaboration and standardized evaluation practices across frontier labs."
  }
  return category_projections.get(category, f"Analytical Projection: May shape strategic roadmap decisions and operational choices{comp_str}.")


def generate_analysis_limitations(clean_summary, trust_tier=2, is_official=False, corroboration_count=1, source_type="publication"):
  """Provides explicit epistemic bounds and limitations for the story analysis.
  Identifies missing evidence, single-source dependencies, or peer-review status.
  """
  if is_official or trust_tier == 1:
    return "Epistemic Limitation: Findings reflect first-party vendor claims and metrics; independent third-party reproduction and benchmark validation remain pending."
  elif source_type == "research" or trust_tier == 3:
    return "Epistemic Limitation: Based on an academic preprint / open research paper; claims have not completed formal peer review or broad independent reproduction."
  elif trust_tier == 4:
    return "Epistemic Limitation: Independent practitioner report; observations reflect specific test setups, local system configurations, and personal developer evaluation."
  elif corroboration_count >= 2:
    return "Epistemic Limitation: Independently corroborated across multiple reporting outlets; production performance will vary depending on deployed infrastructure and workload characteristics."
  else:
    return "Epistemic Limitation: Single-source tech trade reporting; awaiting further vendor confirmation, formal technical documentation, or secondary corroboration."


def generate_editorial_trio(title, clean_summary, category, company=""):
  """Produces non-redundant, distinct editorial intelligence fields:
  (summary, what_changed, why_it_matters, potential_impact).
  Ensures summary != why_it_matters and summary != title.
  Eliminates repetitive category boilerplate templates.
  """
  clean_title = (title or "").strip()
  # 1. Clean arXiv abstract boilerplate, download text, or image captions
  clean_summary = re.sub(r"^arXiv:\S+\s+(?:Announce Type:\s*\S+\s*)?Abstract:\s*", "", clean_summary or "", flags=re.IGNORECASE)
  clean_summary = re.sub(r"^(?:Cover image for|An illustration of|Download PDF|View on arXiv)\s*.*?(?:\.|\n)", "", clean_summary, flags=re.IGNORECASE)
  clean_summary = clean_summary.strip()

  sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_summary) if s.strip()]
  valid = [s for s in sentences if s.endswith((".", "!", "?", '"', "'")) and len(s) > 20]

  what_changed = ""
  why_it_matters = ""
  summary = clean_summary

  if len(valid) >= 2:
    what_changed = valid[0]
    action_words = [
        "enables", "allows", "designed to", "aims to", "improves", "reduces", "provides",
        "features", "helps", "powers", "automates", "integrates", "replaces", "accelerates", "proposes", "introduces"
    ]
    candidate_why = valid[1]
    candidate_low = candidate_why.lower()
    if any(w in candidate_low for w in action_words) and candidate_low != what_changed.lower() and candidate_low != clean_title.lower():
      why_it_matters = candidate_why
      summary = what_changed
    else:
      summary = f"{valid[0]} {valid[1]}"
  elif len(valid) == 1:
    what_changed = valid[0]
    summary = valid[0]
  else:
    what_changed = f"{clean_title.rstrip('.')}."
    summary = what_changed

  # Action words to search for in summary if why_it_matters not yet set
  action_words = [
      "enables", "allows", "designed to", "aims to", "improves", "reduces", "provides",
      "features", "introduces", "helps", "supports", "powers", "automates", "integrates",
      "standardizes", "replaces", "accelerates", "proposes", "finds that", "shows",
      "demonstrates", "rules that", "decided", "mandates", "releases", "updates", "trains"
  ]
  if not why_it_matters:
    for s in valid:
      s_low = s.lower()
      if any(w in s_low for w in action_words) and s_low != what_changed.lower() and s_low != clean_title.lower():
        why_it_matters = s
        break

  # If still empty or identical, synthesize dynamic story-grounded explanation
  if not why_it_matters or why_it_matters == what_changed or why_it_matters == summary or why_it_matters.lower() == clean_title.lower():
    subj = company.title() if company and company != "default" else ""
    if not subj:
      for m in ["OpenAI", "Anthropic", "Google", "DeepMind", "Microsoft", "Meta", "Mistral", "AWS", "NVIDIA", "Hugging Face"]:
        if m.lower() in clean_title.lower():
          subj = m
          break

    if category == "AI Policy & Regulation":
      why_it_matters = f"Sets legal liability boundaries and compliance standards for organizations deploying {subj or 'AI systems'}."
    elif category == "AI Security & Safety":
      why_it_matters = f"Exposes alignment boundaries and vulnerability surfaces, necessitating automated pre-deployment red teaming."
    elif category == "AI Models & Research":
      why_it_matters = f"Establishes a new empirical benchmark and architectural baseline for {subj or 'frontier'} foundation models."
    elif category == "AI Products & Tools":
      why_it_matters = f"Enables developers to integrate {subj or 'intelligent agent'} capabilities directly into production workflows."
    elif category == "AI Applications":
      why_it_matters = f"Demonstrates operational automation and measurable business efficiency using {subj or 'modern AI'}."
    elif category == "AI Infrastructure":
      why_it_matters = f"Expands compute capacity or improves inference efficiency, lowering latency and hardware hosting costs."
    elif category == "AI Business & Funding":
      why_it_matters = f"Reflects shifting market valuations and institutional investor sentiment toward foundation model commercialization."
    else:
      why_it_matters = f"Signals actionable market shifts and infrastructure priorities across the {subj or 'AI'} ecosystem."

  # Ensure summary is not identical to why_it_matters
  if summary == why_it_matters:
    summary = what_changed

  potential_impact = generate_potential_impact_statement(title, clean_summary, category, company)

  return summary, what_changed, why_it_matters, potential_impact


def generate_factual_why_it_matters(title, summary, topic, company=""):
  """Generates a concise, factual explanation of impact grounded in the article's actual content without boilerplate."""
  category, _, _ = classify_topic_detailed(title, summary)
  clean_s = sanitize_and_format_summary(summary, title)
  _, _, why, _ = generate_editorial_trio(title, clean_s, category, company)
  return why


def generate_detailed_analysis(summary, title, what_changed="", why_it_matters="", category="", potential_impact=""):
  """Formats factual analysis from the source text without boilerplate placeholders or redundant repetition."""
  clean_summary = (summary or "").strip()
  clean_title = (title or "").strip()

  def norm(t):
    return re.sub(r"[^\w\s]", "", (t or "").lower()).strip()

  paragraphs = []
  if clean_summary and norm(clean_summary) != norm(clean_title):
    paragraphs.append(clean_summary)
  elif what_changed and norm(what_changed) != norm(clean_title):
    paragraphs.append(what_changed)
  else:
    paragraphs.append(f"{clean_title}.")

  # Add second paragraph if distinct technical context or impact is available
  if potential_impact:
    clean_pi = potential_impact.strip()
    if norm(clean_pi) != norm(clean_title) and not any(norm(clean_pi) in norm(p) or norm(p) in norm(clean_pi) for p in paragraphs):
      paragraphs.append(clean_pi)

  return "\n\n".join(paragraphs)


def compute_recency_score(story, now_dt=None):
  """Computes a recency-weighted ranking priority score (preserving original pulse_score for display).
  Applies boost for recent 24-72h developments and decay for week-old stories.
  """
  base = float(story.get("pulse_score") or story.get("overall_score") or 70.0)
  pub_iso = story.get("published_at") or story.get("published_datetime")
  if not pub_iso:
    return base
  if not now_dt:
    now_dt = datetime.now(timezone.utc)
  try:
    if isinstance(pub_iso, str):
      clean_iso = pub_iso.replace("Z", "+00:00")
      if clean_iso in ("Recent", "Date unavailable"):
        return base
      dt = datetime.fromisoformat(clean_iso)
    elif hasattr(pub_iso, "tzinfo"):
      dt = pub_iso if pub_iso.tzinfo else pub_iso.replace(tzinfo=timezone.utc)
    else:
      return base
    age_hours = (now_dt - dt).total_seconds() / 3600.0
    if age_hours <= 24:
      return base + 15.0
    elif age_hours <= 48:
      return base + 10.0
    elif age_hours <= 72:
      return base + 5.0
    elif age_hours <= 120:
      return base - 5.0
    elif age_hours <= 168:
      return base - 15.0
    else:
      return base - 35.0
  except Exception:
    return base


def generate_daily_overview(clustered_stories, now_iso):
  """Synthesizes a calm, grounded daily intelligence overview from actual collected stories.
  Provides total developments, dynamic briefing, and top 10-15 high-signal developments with publisher diversity.
  """
  total_count = len(clustered_stories)
  try:
    now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
  except Exception:
    now_dt = datetime.now(timezone.utc)

  ranked_stories = sorted(clustered_stories, key=lambda s: compute_recency_score(s, now_dt), reverse=True)

  # Detect primary themes across top items
  top_items = ranked_stories[:5]
  topics_present = [classify_topic(s.get("title", ""), s.get("summary", "")) for s in top_items]
  unique_topics = []
  for t in topics_present:
    if t not in unique_topics:
      unique_topics.append(t)

  # Synthesize authentic daily briefing text strictly from actual collected stories without duplicate categories
  if len(unique_topics) >= 3:
    briefing_text = (
        f"Today's AI developments span {unique_topics[0]}, {unique_topics[1]}, and {unique_topics[2]}. "
        f"Research and engineering teams are focusing on verifiable model evaluations, practical agentic workflows, and production reliability."
    )
  elif len(unique_topics) == 2:
    briefing_text = (
        f"Today's AI developments center on {unique_topics[0]} alongside notable updates in {unique_topics[1]}. "
        f"Teams are prioritizing benchmark accuracy, automated workflows, and system guardrails."
    )
  elif len(unique_topics) == 1:
    briefing_text = (
        f"Today's AI updates focus primarily on {unique_topics[0]} with verified releases and technical evaluations from primary industry sources."
    )
  else:
    briefing_text = (
        "Frontier AI developments continue accelerating across practical coding assistants, model architectures, and evaluation standards."
    )

  # Select top 5-7 genuinely important developments with publisher diversity (target 5-7, max 7)
  top_developments = []
  publisher_counts = {}
  MAX_TOP_PER_PUB = 1

  for s in ranked_stories:
    if len(top_developments) >= 7:
      break

    pulse_val = s.get("pulse_score", s.get("overall_score", 0.0))
    # Strictly require pulse_score >= 70.0 and must not be routine minor update or promotional case study
    if pulse_val < 70.0:
      continue

    art_type = s.get("article_type")
    if not art_type:
      is_off = s.get("is_official", False) or any(k in s.get("source", "").lower() for k in ["official", "deepmind", "openai", "anthropic", "mistral", "aws", "microsoft", "google"])
      art_type = classify_article_type(
          s.get("title", ""), s.get("summary", ""), s.get("link", ""), s.get("source_type", "official" if is_off else "publication"), is_off
      )
    # Strictly exclude single-source vendor case studies and routine minor updates from top developments
    if art_type in ("case_study_pr", "routine_minor_update", "opinion_commentary") and s.get("independent_source_count", 1) < 2 and not s.get("is_official"):
      continue

    src = s.get("source", "")
    pub = PUBLISHER_ORGANIZATION_MAP.get(src, src)
    # Allow 2nd story from same publisher ONLY if it is an exceptional breakthrough (pulse_score >= 88)
    if publisher_counts.get(pub, 0) >= MAX_TOP_PER_PUB and pulse_val < 88.0:
      continue

    publisher_counts[pub] = publisher_counts.get(pub, 0) + 1

    category, _, _ = classify_topic_detailed(s.get("title", ""), s.get("summary", ""))
    clean_s = sanitize_and_format_summary(s.get("summary", ""), s.get("title", ""))
    _, what_changed, why_sentence, _ = generate_editorial_trio(s.get("title", ""), clean_s, category)
    audience_info = generate_audience_impact(s.get("title", ""), clean_s, category)
    if "." in why_sentence:
      why_sentence = why_sentence.split(".")[0].strip() + "."

    sig_badge = s.get("signal_badge") or SIGNAL_BADGE_MAP.get(art_type, "📰 AI Update")

    top_developments.append({
        "title": s.get("title", ""),
        "topic": category,
        "category": category,
        "source": s.get("source", ""),
        "link": s.get("link", ""),
        "article_type": art_type,
        "signal_badge": sig_badge,
        "what_changed": what_changed,
        "why_it_matters": why_sentence,
        "target_audience": audience_info["target"],
        "impact": audience_info["impact"],
        "score": pulse_val,
        "score_reasons": s.get("score_reasons", []),
    })

  return {
      "total_developments_today": total_count,
      "last_updated": now_iso,
      "briefing_text": briefing_text,
      "top_developments": top_developments
  }


def build_complete_payload(clustered_stories, ai_briefing=None, source_health_summary=None, source_health_details=None, developer_trends=None):
  """Builds the comprehensive schema contract consumed by index.html and test_qa.js.
  Enforces cross-section mutual exclusivity so articles are not duplicated across sections.
  Populates article_type and signal_badge for v2.1 high-signal intelligence.
  """
  now_iso = datetime.now(timezone.utc).isoformat()
  daily_overview = generate_daily_overview(clustered_stories, now_iso)

  # 1. Format Top Stories (Curated Updates) - targeted to 12-18 high-signal updates (max 18) with source diversity
  top_stories = []
  publisher_counts = {}
  MAX_PER_PUBLISHER = 2

  try:
    now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
  except Exception:
    now_dt = datetime.now(timezone.utc)

  ranked_stories = sorted(clustered_stories, key=lambda s: compute_recency_score(s, now_dt), reverse=True)

  for s in ranked_stories:
    if len(top_stories) >= 18:
      break

    pulse_val = s.get("pulse_score", s.get("overall_score", 0.0))
    # Editorial quality floor: exclude low-signal stories when baseline is met
    if pulse_val < 65.0 and len(top_stories) >= 12:
      continue

    src = s.get("source", "")
    pub = PUBLISHER_ORGANIZATION_MAP.get(src, src)
    # Source Dominance Protection:
    # Cap at 2 per publisher, but allow a 3rd slot ONLY if pulse_score >= 85 (major Tier 1 announcement or breakthrough)
    pub_limit = 3 if (pulse_val >= 85.0 and (s.get("is_official") or s.get("trust_tier") == 1)) else MAX_PER_PUBLISHER
    if publisher_counts.get(pub, 0) >= pub_limit and len(clustered_stories) > 15:
      continue

    publisher_counts[pub] = publisher_counts.get(pub, 0) + 1

    company = detect_company(s.get("title", ""), s.get("source", ""))
    category, cat_confidence, cat_rationale = classify_topic_detailed(s.get("title", ""), s.get("summary", ""))
    clean_summary = sanitize_and_format_summary(s.get("summary", ""), s.get("title", ""))
    summary_text, what_changed, why_it_matters, potential_impact = generate_editorial_trio(s.get("title", ""), clean_summary, category, company)
    plain_summary = simplify_jargon(summary_text)
    stakeholders = extract_affected_stakeholders(s.get("title", ""), clean_summary, category)
    audience_info = generate_audience_impact(s.get("title", ""), clean_summary, category, company)
    key_points = extract_key_points(plain_summary, s.get("title", ""), s.get("source", ""), why_it_matters, category, company)
    detailed_analysis = generate_detailed_analysis(plain_summary, s.get("title", ""), what_changed, why_it_matters, category, potential_impact)
    reading_time = estimate_reading_time(plain_summary)

    tier_label = (
        "Official Lab" if s.get("trust_tier") == 1
        else "Independent Journalism" if s.get("trust_tier") == 2
        else "Open Research" if s.get("trust_tier") == 3
        else "Practitioner & Community"
    )

    art_type = classify_article_type(
        s.get("title", ""), clean_summary, s.get("link", ""), s.get("source_type", "publication"), s.get("is_official", False)
    )
    sig_badge = s.get("signal_badge") or SIGNAL_BADGE_MAP.get(art_type, "📰 AI Update")

    img_meta = resolve_article_image_metadata(s.get("image", ""), s.get("title", ""), category, company, s.get("link", ""))

    reported_facts = generate_reported_facts(s.get("title", ""), clean_summary, s.get("source", ""))
    limitations = generate_analysis_limitations(
        clean_summary,
        trust_tier=s.get("trust_tier", 2),
        is_official=s.get("is_official", False),
        corroboration_count=s.get("independent_source_count", 1),
        source_type=s.get("source_type", "publication")
    )

    story_obj = {
        "id": s.get("cluster_id") or f"story_{len(top_stories) + 1}",
        "article_id": s.get("article_id", ""),
        "publisher_id": s.get("publisher_id", ""),
        "publisher_group_id": s.get("publisher_group_id", ""),
        "article_type": art_type,
        "signal_badge": sig_badge,
        "title": s.get("title"),
        "one_liner": plain_summary,
        "summary": plain_summary,
        "reported_facts": reported_facts,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "affected_stakeholders": stakeholders,
        "potential_impact": potential_impact,
        "analysis_limitations": limitations,
        "claim_corroboration": s.get("independent_source_count", 1),
        "trend_signal_diversity": 1,
        "category": category,
        "category_confidence": cat_confidence,
        "category_rationale": cat_rationale,
        "topic": category,  # Backward compatibility alias
        "source": s.get("source"),
        "tier": tier_label,
        "trust_tier": s.get("trust_tier", 2),
        "is_official": s.get("is_official", False),
        "published": s.get("published", "Date unavailable"),
        "published_at": s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None),
        "last_fetched_at": now_iso,
        "link": s.get("link"),
        "image": img_meta["image_url"],
        "image_url": img_meta["image_url"],
        "image_alt": img_meta["image_alt"],
        "image_type": img_meta["image_type"],
        "image_credit": img_meta["image_credit"],
        "image_fallback": img_meta["image_fallback"],
        "company": company,
        "reading_time": reading_time,
        "key_points": key_points,
        "detailed_analysis": detailed_analysis,
        "audience_impact": audience_info,
        "target_audience": audience_info["target"],
        "audience_impact_statement": audience_info["impact"],
        "importance_score": s.get("importance_score", 70),
        "relevance_score": s.get("relevance_score", 70),
        "freshness_score": s.get("freshness_score", 50),
        "coverage_score": s.get("coverage_score", 50),
        "popularity_score": s.get("popularity_score", 50),
        "source_quality_score": s.get("source_quality_score", s.get("confidence_score", 85)),
        "confidence_score": s.get("confidence_score", 85),
        "pulse_score": s.get("pulse_score", s.get("overall_score", 70.0)),
        "overall_score": s.get("overall_score", 70.0),
        "confidence_label": s.get("confidence_label", "medium"),
        "evidence_status": s.get("evidence_status", "single_source"),
        "evidence_label": s.get("evidence_label", "Single-Source Report"),
        "independent_source_count": s.get("independent_source_count", 1),
        "independent_publisher_count": s.get("independent_publisher_count", s.get("independent_source_count", 1)),
        "score_reasons": s.get("score_reasons", []),
        "first_published_at": s.get("first_published_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
        "latest_updated_at": s.get("latest_updated_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
        "eligible_for_top_developments": s.get("eligible_for_top_developments", True),
        "eligible_for_briefing": s.get("eligible_for_briefing", True),
        "related_sources": s.get("related_sources", []),
        "covered_by_sources_count": s.get("covered_by_sources_count", 1),
    }
    top_stories.append(story_obj)

  assigned_urls = set()

  # 2. Format Trends (Lead Briefing Stories)
  trends = []
  if ai_briefing and ai_briefing.get("trends"):
    for t in ai_briefing["trends"]:
      cat, conf, rat = classify_topic_detailed(t.get("title", ""), t.get("what_happened", ""))
      company = detect_company(t.get("title", ""), t.get("source", ""))
      reading_time = estimate_reading_time(f"{t.get('what_happened', '')} {t.get('why_it_matters', '')}")
      who_affected = t.get("who_affected", "Developers and Enterprise Teams")
      ev_urls = t.get("evidence_urls", [])

      for u in ev_urls:
        assigned_urls.add(normalize_url(u))

      kp = [t.get("what_happened"), t.get("why_it_matters")]
      clean_kp = [p for p in kp if p and len(p.strip()) > 10]
      audience_info = generate_audience_impact(t.get("title", ""), t.get("what_happened", ""), cat, company)
      img_meta = resolve_article_image_metadata("", t.get("title", ""), cat, company, ev_urls[0] if ev_urls else "")

      trend_art_type = t.get("article_type") or classify_article_type(
          t.get("title", ""), t.get("what_happened", ""), ev_urls[0] if ev_urls else "", "publication", False
      )
      trend_sig_badge = SIGNAL_BADGE_MAP.get(trend_art_type, "📰 AI Update")

      trends.append({
          "title": t.get("title"),
          "link": ev_urls[0] if ev_urls else "",
          "trend_type": t.get("trend_type", "single_development"),
          "article_type": trend_art_type,
          "signal_badge": trend_sig_badge,
          "theme_relationship": t.get("theme_relationship", ""),
          "claims": t.get("claims", []),
          "evidence_objects": t.get("evidence_objects", []),
          "what_happened": simplify_jargon(t.get("what_happened", "")),
          "what_changed": simplify_jargon(t.get("what_happened", "")),
          "why_it_matters": t.get("why_it_matters"),
          "who_affected": who_affected,
          "affected_stakeholders": extract_affected_stakeholders(t.get("title", ""), t.get("what_happened", ""), cat),
          "potential_impact": t.get("potential_impact", f"Impacts roadmap decisions across {cat}."),
          "category": cat,
          "category_confidence": conf,
          "category_rationale": rat,
          "source": t.get("source", "Primary Lab"),
          "tier": "Official Lab" if "openai" in company or "deepmind" in company or "anthropic" in company else "Independent Journalism",
          "status": t.get("status", "source_linked"),
          "evidence_article_ids": t.get("evidence_article_ids", []),
          "evidence_urls": ev_urls,
          "topic": cat,
          "company": company,
          "reading_time": reading_time,
          "audience_pills": extract_audience_pills(who_affected),
          "audience_impact": audience_info,
          "target_audience": audience_info["target"],
          "audience_impact_statement": audience_info["impact"],
          "claim_corroboration": t.get("claim_corroboration", t.get("independent_source_count", 1)),
          "trend_signal_diversity": t.get("trend_signal_diversity", len(ev_urls) or 1),
          "evidence_status": t.get("evidence_status") or ("independently_corroborated" if t.get("independent_source_count", 1) >= 2 else "single_source"),
          "evidence_label": t.get("evidence_label") or (f"Covered by {t.get('independent_source_count', 1)} sources" if t.get("independent_source_count", 1) >= 2 else "Single-Source Report"),
          "independent_source_count": t.get("independent_source_count", 1),
          "key_points": clean_kp if clean_kp else extract_key_points(t.get("what_happened", ""), t.get("title", ""), t.get("source", ""), t.get("why_it_matters", ""), cat, company),
          "detailed_analysis": t.get("detailed_analysis") or (t.get("what_happened") or t.get("title")),
          "image": img_meta["image_url"],
          "image_url": img_meta["image_url"],
          "image_alt": img_meta["image_alt"],
          "image_type": img_meta["image_type"],
          "image_credit": img_meta["image_credit"],
          "image_fallback": img_meta["image_fallback"],
      })
  else:
    # Deterministic Non-LLM Briefing Trends: top 3-5 high-signal stories with publisher diversity
    briefing_pubs = set()
    for s in top_stories:
      if len(trends) >= 5:
        break
      if not s.get("eligible_for_briefing", True):
        continue
      pub = s.get("publisher_group_id") or PUBLISHER_ORGANIZATION_MAP.get(s.get("source", ""), s.get("source", ""))
      if pub in briefing_pubs and len(top_stories) > 10:
        continue
      briefing_pubs.add(pub)
      assigned_urls.add(normalize_url(s["link"]))
      claims = [
          {
              "claim_id": "claim_1",
              "text": s.get("what_changed") or s["summary"],
              "evidence": [
                  {
                      "article_id": s.get("article_id", ""),
                      "canonical_url": s["link"],
                      "publisher_id": s.get("publisher_id", ""),
                      "publisher_group_id": s.get("publisher_group_id", s.get("publisher_id", "")),
                      "source_name": s["source"],
                      "trust_tier": s.get("trust_tier", 2),
                      "is_official": s.get("is_official", False),
                      "supporting_excerpt": s.get("summary", ""),
                      "text_verified": True,
                  }
              ],
              "claim_corroboration": s.get("independent_source_count", 1),
              "verification_status": s.get("evidence_status", "single_source")
          }
      ]
      trends.append({
          "title": s["title"],
          "link": s["link"],
          "trend_type": "single_development",
          "article_type": s.get("article_type", "frontier_launch"),
          "signal_badge": s.get("signal_badge", "🚀 Frontier Launch"),
          "trend_signal_diversity": 1,
          "claim_corroboration": s.get("independent_source_count", 1),
          "independent_publisher_count": s.get("independent_publisher_count", s.get("independent_source_count", 1)),
          "published_at": s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None),
          "first_published_at": s.get("first_published_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
          "latest_updated_at": s.get("latest_updated_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
          "score_reasons": s.get("score_reasons", []),
          "claims": claims,
          "evidence_objects": claims[0]["evidence"],
          "what_happened": s.get("what_changed") or s["summary"],
          "what_changed": s.get("what_changed") or s["summary"],
          "why_it_matters": s["why_it_matters"],
          "reported_facts": s.get("reported_facts", []),
          "potential_impact": s.get("potential_impact", ""),
          "analysis_limitations": s.get("analysis_limitations", ""),
          "affected_stakeholders": s.get("affected_stakeholders", ["Developers", "Enterprises"]),
          "category": s.get("category", s["topic"]),
          "category_confidence": s.get("category_confidence", 0.85),
          "category_rationale": s.get("category_rationale", "Classified into canonical category"),
          "who_affected": ", ".join(s.get("affected_stakeholders", ["Developers", "Enterprises"])),
          "source": s["source"],
          "tier": s["tier"],
          "status": "official_claim" if s["is_official"] else "source_linked",
          "evidence_article_ids": [s.get("article_id")] if s.get("article_id") else [],
          "evidence_urls": [s["link"]],
          "topic": s["topic"],
          "company": s["company"],
          "reading_time": s["reading_time"],
          "audience_pills": s.get("affected_stakeholders", ["Developers", "Enterprises"]),
          "audience_impact": s.get("audience_impact"),
          "target_audience": s.get("target_audience"),
          "audience_impact_statement": s.get("audience_impact_statement"),
          "evidence_status": s.get("evidence_status", "single_source"),
          "evidence_label": s.get("evidence_label", "Single-Source Report"),
          "independent_source_count": s.get("independent_source_count", 1),
          "key_points": s["key_points"],
          "detailed_analysis": s["detailed_analysis"],
          "image": s.get("image", ""),
          "image_url": s.get("image_url", s.get("image", "")),
          "image_alt": s.get("image_alt", ""),
          "image_type": s.get("image_type", "category_fallback"),
          "image_credit": s.get("image_credit", ""),
          "image_fallback": s.get("image_fallback", ""),
      })

    # Backfill to at least 3 if strict filters left trends < 3
    if len(trends) < 3:
      for s in top_stories:
        if len(trends) >= 3:
          break
        if any(t["link"] == s["link"] for t in trends):
          continue
        assigned_urls.add(normalize_url(s["link"]))
        claims = [
            {
                "claim_id": "claim_1",
                "text": s.get("what_changed") or s["summary"],
                "evidence": [
                    {
                        "article_id": s.get("article_id", ""),
                        "canonical_url": s["link"],
                        "publisher_id": s.get("publisher_id", ""),
                        "publisher_group_id": s.get("publisher_group_id", s.get("publisher_id", "")),
                        "source_name": s["source"],
                        "trust_tier": s.get("trust_tier", 2),
                        "is_official": s.get("is_official", False),
                        "supporting_excerpt": s.get("summary", ""),
                        "text_verified": True,
                    }
                ],
                "claim_corroboration": s.get("independent_source_count", 1),
                "verification_status": s.get("evidence_status", "single_source")
            }
        ]
        trends.append({
            "title": s["title"],
            "link": s["link"],
            "trend_type": "single_development",
            "article_type": s.get("article_type", "frontier_launch"),
            "signal_badge": s.get("signal_badge", "🚀 Frontier Launch"),
            "trend_signal_diversity": 1,
            "claim_corroboration": s.get("independent_source_count", 1),
            "independent_publisher_count": s.get("independent_publisher_count", s.get("independent_source_count", 1)),
            "published_at": s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None),
            "first_published_at": s.get("first_published_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
            "latest_updated_at": s.get("latest_updated_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
            "score_reasons": s.get("score_reasons", []),
            "claims": claims,
            "evidence_objects": claims[0]["evidence"],
            "what_happened": s.get("what_changed") or s["summary"],
            "what_changed": s.get("what_changed") or s["summary"],
            "why_it_matters": s["why_it_matters"],
            "reported_facts": s.get("reported_facts", []),
            "potential_impact": s.get("potential_impact", ""),
            "analysis_limitations": s.get("analysis_limitations", ""),
            "affected_stakeholders": s.get("affected_stakeholders", ["Developers", "Enterprises"]),
            "category": s.get("category", s["topic"]),
            "category_confidence": s.get("category_confidence", 0.85),
            "category_rationale": s.get("category_rationale", "Classified into canonical category"),
            "who_affected": ", ".join(s.get("affected_stakeholders", ["Developers", "Enterprises"])),
            "source": s["source"],
            "tier": s["tier"],
            "status": "official_claim" if s["is_official"] else "source_linked",
            "evidence_article_ids": [s.get("article_id")] if s.get("article_id") else [],
            "evidence_urls": [s["link"]],
            "topic": s["topic"],
            "company": s["company"],
            "reading_time": s["reading_time"],
            "audience_pills": s.get("affected_stakeholders", ["Developers", "Enterprises"]),
            "audience_impact": s.get("audience_impact"),
            "target_audience": s.get("target_audience"),
            "audience_impact_statement": s.get("audience_impact_statement"),
            "evidence_status": s.get("evidence_status", "single_source"),
            "evidence_label": s.get("evidence_label", "Single-Source Report"),
            "independent_source_count": s.get("independent_source_count", 1),
            "key_points": s["key_points"],
            "detailed_analysis": s["detailed_analysis"],
            "image": s.get("image", ""),
            "image_url": s.get("image_url", s.get("image", "")),
            "image_alt": s.get("image_alt", ""),
            "image_type": s.get("image_type", "category_fallback"),
            "image_credit": s.get("image_credit", ""),
            "image_fallback": s.get("image_fallback", ""),
        })

  # 3. Purpose-driven curated domain sections with cross-section exclusivity
  # AI Tools: actual products, tools, assistants, platform features
  ai_tools = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    # Must be AI Products & Tools, or tool/platform/assistant keywords, rejecting lawsuits
    title_lower = s["title"].lower()
    is_tool = (
        (s.get("category") in ("AI Products & Tools", "AI Applications") or
         any(k in title_lower for k in ["tool", "agent", "platform", "assistant", "copilot", "app", "bedrock", "sagemaker", "antigravity", "crawl4ai"])) and
        not any(bad in title_lower for bad in ["lawsuit", "naacp", "sued", "pollution", "court", "judge", "illegal", "protest"])
    )
    if is_tool:
      ai_tools.append(s)
      assigned_urls.add(norm_link)
      if len(ai_tools) >= 4:
        break

  # If exclusive assignment left ai_tools empty, draw from top_stories matching tool criteria
  if not ai_tools:
    for s in top_stories:
      title_lower = s["title"].lower()
      is_tool = (
          (s.get("category") in ("AI Products & Tools", "AI Applications", "AI News") or
           any(k in title_lower for k in ["tool", "agent", "platform", "assistant", "copilot", "app", "bedrock", "sagemaker", "antigravity", "crawl4ai"])) and
          not any(bad in title_lower for bad in ["lawsuit", "naacp", "sued", "pollution", "court", "judge", "illegal", "protest"])
      )
      if is_tool and not any(t["link"] == s["link"] for t in ai_tools):
        ai_tools.append(s)
        if len(ai_tools) >= 3:
          break

  # Developer Radar: APIs, SDKs, frameworks, libraries, coding agents, MCP
  dev_radar = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    title_lower = s["title"].lower()
    is_dev = (
        s.get("category") in ("AI Products & Tools", "AI Models & Research", "AI Applications", "AI Infrastructure", "AI News") and
        any(k in title_lower for k in ["sdk", "api", "code", "agent", "open-source", "open source", "weight", "benchmark", "mcp", "library", "framework", "repo", "github", "inference", "developer", "vs code", "distillation", "sglang", "vllm"]) and
        not any(bad in title_lower for bad in ["lawsuit", "naacp", "sued", "pollution", "court"])
    )
    if is_dev:
      dev_radar.append(s)
      assigned_urls.add(norm_link)
      if len(dev_radar) >= 4:
        break

  # If exclusive assignment left dev_radar empty, draw from top_stories matching dev criteria
  if not dev_radar:
    for s in top_stories:
      title_lower = s["title"].lower()
      is_dev = (
          any(k in title_lower for k in ["sdk", "api", "code", "agent", "open-source", "open source", "weight", "benchmark", "mcp", "library", "framework", "repo", "github", "inference", "developer", "distillation", "cloud"]) and
          not any(bad in title_lower for bad in ["lawsuit", "naacp", "sued", "pollution", "court"])
      )
      if is_dev and not any(r["link"] == s["link"] for r in dev_radar):
        dev_radar.append(s)
        if len(dev_radar) >= 3:
          break

  # Research & Safety: safety, alignment, security, policy, governance, preprints
  research_safety = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    title_lower = s["title"].lower()
    is_research = (
        s.get("category") in ("AI Security & Safety", "AI Policy & Regulation", "AI Models & Research") or
        s.get("trust_tier") in (3, 4) or
        any(k in title_lower for k in ["safety", "alignment", "paper", "arxiv", "eval", "policy", "governance", "frontier", "benchmark", "risk", "security", "copyright", "red team", "misalignment", "model spec", "defense"])
    )
    if is_research:
      research_safety.append(s)
      assigned_urls.add(norm_link)
      if len(research_safety) >= 4:
        break

  # Fallback for research_safety if empty
  if not research_safety:
    for s in top_stories:
      title_lower = s["title"].lower()
      is_research = (
          s.get("category") in ("AI Security & Safety", "AI Policy & Regulation", "AI Models & Research") or
          any(k in title_lower for k in ["safety", "alignment", "paper", "arxiv", "eval", "policy", "governance", "benchmark", "risk", "security", "defense"])
      )
      if is_research and not any(r["link"] == s["link"] for r in research_safety):
        research_safety.append(s)
        if len(research_safety) >= 3:
          break

  # Trending: Stories with corroborated multi-outlet coverage (independent_source_count > 1) or high overall score
  trending = []
  for s in top_stories:
    norm_link = normalize_url(s["link"])
    if norm_link in assigned_urls:
      continue
    if s.get("independent_source_count", 1) > 1 or s.get("overall_score", 0) >= 80:
      trending.append(s)
      assigned_urls.add(norm_link)
      if len(trending) >= 4:
        break

  # The Pulse: Key quick developments from the last hours
  pulse_items = []
  lead_trend_url = trends[0].get("link") if trends and "link" in trends[0] else (trends[0].get("evidence_urls", [None])[0] if trends else None)
  for s in top_stories:
    if lead_trend_url and s["link"] == lead_trend_url and len(top_stories) > 1:
      continue
    pulse_items.append({
        "title": s["title"],
        "topic": s["topic"],
        "category": s.get("category", s["topic"]),
        "article_type": s.get("article_type", "frontier_launch"),
        "signal_badge": s.get("signal_badge", "🚀 Frontier Launch"),
        "company": s["company"],
        "published": s.get("published", "Date unavailable"),
        "published_at": s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None),
        "first_published_at": s.get("first_published_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
        "latest_updated_at": s.get("latest_updated_at") or s.get("published_at") or (s.get("published_datetime").isoformat() if hasattr(s.get("published_datetime"), "isoformat") else None) or s.get("published"),
        "what_happened": s.get("what_changed") or s.get("one_liner") or s.get("summary", ""),
        "what_changed": s.get("what_changed") or s.get("summary", ""),
        "one_liner": s.get("one_liner") or s.get("summary", ""),
        "summary": s.get("summary", ""),
        "why_it_matters": s.get("why_it_matters", ""),
        "potential_impact": s.get("potential_impact", ""),
        "detailed_analysis": s.get("detailed_analysis", ""),
        "key_points": s.get("key_points", []),
        "link": s["link"],
        "source": s["source"],
        "tier": s["tier"],
        "audience_impact": s.get("audience_impact"),
        "target_audience": s.get("target_audience"),
        "audience_impact_statement": s.get("audience_impact_statement"),
        "image": s.get("image", ""),
        "image_url": s.get("image_url", s.get("image", "")),
    })
    if len(pulse_items) >= 4:
      break

  takeaway = (
      ai_briefing.get("takeaway")
      if ai_briefing and ai_briefing.get("takeaway")
      else "Frontier research labs and independent publications report accelerating momentum across reasoning architectures, developer agents, and regulatory compliance standards."
  )

  payload = {
      "schema_version": 2,
      "data_status": "fresh" if ai_briefing else "source_linked",
      "generated_at": now_iso,
      "last_successful_update": now_iso,
      "last_attempt_at": now_iso,
      "update_status": "fresh",
      "timezone": "UTC",
      "daily_overview": daily_overview,
      "top_developments": daily_overview.get("top_developments", []),
      "takeaway": takeaway,
      "trends": trends,
      "top_stories": top_stories,
      "all_updates": top_stories,
      "research_worth_reading": research_safety,
      "ai_tools": ai_tools,
      "dev_radar": dev_radar,
      "research_safety": research_safety,
      "trending": trending,
      "pulse_items": pulse_items,
      "developer_trends": developer_trends if developer_trends is not None else [],
      "source_health_summary": source_health_summary,
      "source_health_details": source_health_details or [],
  }
  return payload


def validate_dataset_payload(payload):
  """Strict schema validation for the final dataset payload before saving."""
  if not isinstance(payload, dict):
    raise ValueError("Payload must be a dictionary")

  required_keys = [
      "schema_version", "data_status", "generated_at", "last_attempt_at",
      "takeaway", "trends", "top_stories", "ai_tools", "dev_radar",
      "research_safety", "pulse_items"
  ]
  for k in required_keys:
    if k not in payload:
      raise ValueError(f"Payload missing required top-level key: {k}")

  if not isinstance(payload["top_stories"], list) or len(payload["top_stories"]) == 0:
    raise ValueError("Payload top_stories must be a non-empty list")

  for idx, s in enumerate(payload["top_stories"][:10]):
    for field in ["title", "link", "source", "trust_tier", "overall_score", "evidence_status", "audience_impact", "category", "what_changed", "why_it_matters"]:
      if field not in s or s[field] is None:
        raise ValueError(f"Story #{idx} missing required field '{field}'")
    if not (s["link"].startswith("http://") or s["link"].startswith("https://")):
      raise ValueError(f"Story #{idx} has invalid link: {s['link']}")
    if not (0 <= s["overall_score"] <= 100):
      raise ValueError(f"Story #{idx} score out of bounds: {s['overall_score']}")

  # Guarantee lawsuits are not placed in ai_tools
  for idx, tool in enumerate(payload.get("ai_tools", [])):
    if any(bad in tool["title"].lower() for bad in ["lawsuit", "naacp", "pollution", "sued", "court"]):
      raise ValueError(f"Editorial violation: Lawsuit '{tool['title']}' was incorrectly placed in ai_tools!")

  if "daily_overview" in payload and payload["daily_overview"] is not None:
    overview = payload["daily_overview"]
    if not isinstance(overview, dict):
      raise ValueError("daily_overview must be a dictionary")
    for field in ["total_developments_today", "briefing_text", "top_developments"]:
      if field not in overview:
        raise ValueError(f"daily_overview missing required key: {field}")

  # Validate source health summary if present
  if "source_health_summary" in payload and payload["source_health_summary"] is not None:
    health = payload["source_health_summary"]
    if not isinstance(health, dict):
      raise ValueError("source_health_summary must be a dictionary")
    for field in ["configured_sources_count", "enabled_sources_count", "successful_fetches_count", "failed_fetches_count", "status"]:
      if field not in health:
        raise ValueError(f"source_health_summary missing required key: {field}")

  # Validate trend attributes
  for idx, t in enumerate(payload.get("trends", [])):
    if "trend_type" in t and t["trend_type"] not in ("single_development", "emerging_theme"):
      raise ValueError(f"Trend #{idx} has invalid trend_type: {t['trend_type']}")
    if "trend_signal_diversity" in t and (not isinstance(t["trend_signal_diversity"], int) or t["trend_signal_diversity"] < 1):
      raise ValueError(f"Trend #{idx} has invalid trend_signal_diversity")

  # Validate developer_trends if present
  if "developer_trends" in payload and payload["developer_trends"] is not None:
    if not isinstance(payload["developer_trends"], list):
      raise ValueError("developer_trends must be a list")
    for idx, repo in enumerate(payload["developer_trends"][:10]):
      for field in ["repository", "url", "stars", "forks", "developer_trend_score"]:
        if field not in repo:
          raise ValueError(f"Developer trend #{idx} missing required field '{field}'")
      if not (0.0 <= repo["developer_trend_score"] <= 100.0):
        raise ValueError(f"Developer trend #{idx} score out of bounds: {repo['developer_trend_score']}")
      if repo.get("stars_gained_24h") is not None and not isinstance(repo["stars_gained_24h"], int):
        raise ValueError(f"Developer trend #{idx} stars_gained_24h must be int or None")

  return True


def run_pipeline(dry_run=False, max_age_hours=72, output_file="data.json"):
  """Full execution pipeline: ingest, cluster, score, synthesize, and write data.json atomically.
  Tracks source health across 5 operating cases (A-E).
  Guarantees that previous valid dataset is preserved if any failure occurs.
  Total upstream source failure raises PipelineExecutionError to fail CI/CD automation.
  """
  try:
    tracker_mod = sys.modules.get("tracker")
    fetcher_fn = getattr(tracker_mod, "collect_fresh_news", collect_fresh_news) if tracker_mod else collect_fresh_news
    try:
      collect_res = fetcher_fn(max_age_hours=max_age_hours, return_health=True)
    except TypeError:
      # In case caller/mock doesn't accept return_health parameter
      collect_res = fetcher_fn(max_age_hours=max_age_hours)
    if isinstance(collect_res, tuple) and len(collect_res) == 3:
      articles, health_summary, health_details = collect_res
    else:
      articles = collect_res or []
      health_summary = {
          "configured_sources_count": len(load_source_registry()),
          "enabled_sources_count": len(load_source_registry()),
          "successful_fetches_count": len(load_source_registry()) if articles else 0,
          "failed_fetches_count": 0,
          "valid_empty_sources_count": 0 if articles else len(load_source_registry()),
          "total_articles_received": len(articles),
          "rejected_by_relevance_count": 0,
          "rejected_by_freshness_count": 0,
          "fresh_articles_accepted_count": len(articles),
          "unique_article_count": len(articles),
          "status": "healthy" if articles else "valid_zero_articles",
          "checked_at": datetime.now(timezone.utc).isoformat(),
      }
      health_details = []

    # Case D: Total Upstream Failure -> Fail GitHub Actions with non-zero exit!
    if health_summary.get("status") == "total_failure":
      print(f"❌ TOTAL UPSTREAM FAILURE: All {health_summary.get('enabled_sources_count')} enabled sources failed.")
      print("🔒 Preserving previous valid dataset without corruption.")
      raise PipelineExecutionError(
          f"Total upstream source failure: all {health_summary.get('enabled_sources_count')} enabled sources failed to fetch."
      )

    # Case B & Case E: No usable fresh articles
    if not articles:
      agg_status = health_summary.get("status", "valid_zero_articles")
      print(f"⚠️ No fresh articles collected across sources ({agg_status}).")
      if os.path.exists(output_file):
        print(f"🔒 Preserving existing {output_file} without error.")
        with open(output_file, "r", encoding="utf-8") as f:
          prev_payload = json.load(f)
        prev_payload["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
        prev_payload["source_health_summary"] = health_summary
        prev_payload["source_health_details"] = health_details
        if not dry_run:
          temp_file = f"{output_file}.tmp"
          with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(prev_payload, f, indent=2)
          os.replace(temp_file, output_file)
        return prev_payload
      return None

    clustered = cluster_and_deduplicate_articles(articles)
    print(f"📊 Story clustering complete: {len(clustered)} deduplicated story clusters.")

    # Phase 2: Trafilatura clean article extraction for lead clusters
    try:
      from .extractor import extract_articles_batch
      extract_articles_batch(clustered[:16], max_workers=5, timeout=5.0)
    except Exception as exc:
      print(f"   ⚠️ Article extraction notice: {exc} (falling back to feed summaries)")

    # Synthesis input IDs for verification
    synthesis_input_ids = [a["article_id"] for a in clustered[:16] if a.get("article_id")]
    ai_briefing = synthesize_with_gemini(clustered)
    if ai_briefing and "trends" in ai_briefing:
      ai_briefing["trends"] = validate_evidence_provenance(
          ai_briefing["trends"], articles, synthesis_input_ids=synthesis_input_ids
      )

    # Phase 3: AI Developer Trends collection with snapshot tracking
    developer_trends = []
    try:
      from .github_collector import collect_github_developer_trends
      developer_trends = collect_github_developer_trends(fallback_data_file=output_file)
      print(f"🐙 GitHub Developer Trends complete: {len(developer_trends)} AI repositories scored.")
    except Exception as exc:
      print(f"   ⚠️ GitHub Developer Trends notice: {exc} (preserving previous if present)")

    payload = build_complete_payload(
        clustered,
        ai_briefing=ai_briefing,
        source_health_summary=health_summary,
        source_health_details=health_details,
        developer_trends=developer_trends,
    )

    # Validate payload strictly before file write
    validate_dataset_payload(payload)

    if dry_run:
      print("\n🔍 DRY-RUN MODE: data.json will NOT be written.")
      print(f"   Status: {payload['data_status']}")
      print(f"   Trends count: {len(payload['trends'])}")
      print(f"   Stories count: {len(payload['top_stories'])}")
      print(f"   Generated: {payload['generated_at']}")
      return payload

    # Atomic write to temporary file
    temp_file = f"{output_file}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
      json.dump(payload, f, indent=2)

    # Validate that temporary file reloads and passes schema validation
    with open(temp_file, "r", encoding="utf-8") as f:
      test_load = json.load(f)
      validate_dataset_payload(test_load)

    # Atomic file replacement
    os.replace(temp_file, output_file)
    print(f"✅ {output_file} written atomically! Status: {payload['data_status']}, Stories: {len(payload['top_stories'])}")
    return payload

  except Exception as e:
    traceback_str = traceback.format_exc()
    print(f"❌ Pipeline execution encountered an error: {e}\n{traceback_str}")
    print("🔒 Preserving previous valid dataset. No files were corrupted.")
    temp_file = f"{output_file}.tmp"
    if os.path.exists(temp_file):
      try:
        os.remove(temp_file)
      except Exception:
        pass
    if isinstance(e, PipelineExecutionError):
      raise e
    raise PipelineExecutionError(f"Pipeline failed: {e}") from e
