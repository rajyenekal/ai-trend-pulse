"""
pipeline.scorer - Article Intent Classification, Calibrated Pulse Scoring, and Topic Taxonomies.
"""

from datetime import datetime, timezone
import re
import html
import urllib.parse

# -------------------------------------------------------------
# 1. ARTICLE INTENT & SIGNAL BADGES
# -------------------------------------------------------------
VALID_ARTICLE_TYPES = [
    "frontier_launch",
    "open_source_release",
    "research_paper",
    "sdk_api_update",
    "security_vulnerability",
    "policy_regulation",
    "case_study_pr",
    "opinion_commentary",
    "routine_minor_update",
]

ARTICLE_TYPE_MULTIPLIERS = {
    "frontier_launch": 1.12,
    "open_source_release": 1.12,
    "research_paper": 1.02,
    "sdk_api_update": 1.05,
    "security_vulnerability": 1.05,
    "policy_regulation": 1.00,
    "opinion_commentary": 0.80,
    "case_study_pr": 0.60,
    "routine_minor_update": 0.50,
}

SIGNAL_BADGE_MAP = {
    "frontier_launch": "Frontier Launch",
    "open_source_release": "Open Weights",
    "research_paper": "Research Paper",
    "sdk_api_update": "Developer SDK",
    "security_vulnerability": "Security & Policy",
    "policy_regulation": "Security & Policy",
    "case_study_pr": "Case Study",
    "opinion_commentary": "Analysis & Opinion",
    "routine_minor_update": "Minor Update",
    "model_breakthrough": "Breakthrough",
    "enterprise_adoption": "Enterprise Adoption",
    "general_news": "Verified Intelligence",
}


def classify_article_type(title, summary="", link="", source_type="", is_official=False, **kwargs):
  """Deterministically classifies an article into one of the canonical intent types.
  Inspects URL slugs, headline patterns, content keywords, and publisher metadata.
  Never defaults an official source blindly to frontier_launch.
  """
  link = link or kwargs.get("url", "")
  t_low = (title or "").lower()
  s_low = (summary or "").lower()
  u_low = (link or "").lower()
  combined = f"{t_low} {s_low}"

  # 1. Routine Non-AI Noise, Peripheral Gaming, or Pure Macroeconomics Check
  noise_gaming_keywords = [
      "geforce now", "gfn thursday", "phantom blade", "game ready driver",
      "gaming treats", "slice into gfn", "gaming laptops gain new", "rtx spark windows laptops gain"
  ]
  if any(k in t_low for k in noise_gaming_keywords):
    return "routine_minor_update"
  if any(k in t_low for k in ["digital economy to hit", "southeast asia’s digital economy to hit"]):
    return "opinion_commentary"

  # 2. Vendor PR / Customer Case Study Check (Must precede model checks to catch enterprise customer blogs)
  case_study_url_patterns = [
      r"/customer", r"/customers", r"/case-stud", r"/stories/", r"partners-with",
      r"/index/customer", r"/index/stories", r"/index/retell", r"/index/greptile",
      r"/index/harvey", r"/index/legora", r"how-.*-(automated|built|uses|scaled|reduced)"
  ]
  if any(re.search(p, u_low) for p in case_study_url_patterns):
    return "case_study_pr"

  case_study_keywords = [
      "case study", "customer story", "customer spotlight", "partner spotlight",
      "partners with", "partnering with", "customer success", "customer testimonial",
      "enterprise customer", "how worldwide express", "freight exceptions",
      "powers 100m monthly calls", "powers legal work", "takes bug detection beyond code review",
      "a concrete vision: saint-gobain", "saint-gobain and microsoft discovery",
      "before the ambulance arrives: how ai is helping the nhs",
      "greptile transforms", "transforms code review", "streamlines freight",
      "customer story:"
  ]
  if any(k in t_low for k in case_study_keywords):
    return "case_study_pr"

  if re.search(r"\b(how\s+.+\s+)?(transforms|streamlines|automates|accelerates|powers|deploys|scales|uses)\b.*(code review|freight|logistics|workflows|operations|triage|billing)", t_low):
    return "case_study_pr"

  if re.search(r"how\s+.+\s+(automated|automates|streamlined|streamlines|transforms|transformed|uses|deploys|builds|scales|powers|accelerated|improved|reduced|cuts|rethink)\b", t_low):
    return "case_study_pr"

  if re.search(r"^[a-z0-9_\-\s]+\s+(uses|partners with|teams with|adopts|powers|deploys)\s+(openai|aws|google|microsoft|anthropic|bedrock|azure)\b", t_low):
    return "case_study_pr"

  if "building the" in t_low and ("operating system for" in t_low or "platform for" in t_low):
    return "case_study_pr"

  # 3. Security Vulnerability / Exploit / Red-Teaming / Alignment Failures / Safety Evals
  sec_keywords = [
      "cve-", "vulnerability", "vulnerabilities", "jailbreak", "prompt injection",
      "exploit", "backdoor", "red team", "red-team", "attack vector",
      "adversarial attack", "sandbox escape", "data leak", "malicious payload",
      "detect frontier model misalignment", "frontier model misalignment", "misalignment",
      "safety eval", "safety evals", "safety risks", "alignment risks"
  ]
  if any(k in combined for k in sec_keywords):
    return "security_vulnerability"

  # 4. Policy & Regulation / Legal / Standards / Data Governance
  policy_keywords = [
      "regulation", "legislation", "lawsuit", "sues", "sued", "court", "copyright",
      "antitrust", "eu ai act", "executive order", "ftc", "doj", "senate", "congress",
      "ban", "compliance", "standards body", "treaty", "legal challenge", "regulators",
      "clean air act", "opt out of scraping", "opt-out of scraping", "scraping standard"
  ]
  if any(k in combined for k in policy_keywords):
    return "policy_regulation"

  # 5. Research Papers & Preprints (arXiv, BAIR, academic source_type, or explicitly marked papers)
  if "arxiv.org" in u_low or "bair.berkeley.edu" in u_low or source_type == "research":
    return "research_paper"
  if any(k in t_low for k in ["paper", "preprint", "empirical study"]):
    return "research_paper"

  # 6. Open-Source & Open-Weight Releases
  os_keywords = [
      "open weight", "open-weight", "open source", "open-source", "weights released",
      "weights available", "apache 2.0", "mit license", "github repo", "hugging face",
      "huggingface.co", "model weights", "checkpoint", "ollama", "vllm", "gguf",
      "finetuning", "fine-tuned", "open release", "open computer use"
  ]
  if any(k in combined for k in os_keywords):
    return "open_source_release"

  # 7. Frontier Foundation Model Launches & World Simulation Milestones
  frontier_models = [
      "gpt-5", "gpt-4.5", "gpt-4", "o1", "o3", "o4", "claude 3.7", "claude 4", "gemini 2",
      "gemini 3", "gemini 4", "deepseek-v3", "deepseek-r1", "llama 4", "qwen 2.5", "qwen 3",
      "mistral large", "grok 3", "frontier model", "foundation model", "flagship model",
      "reasoning model", "genie 4", "world simulation", "gemini 4 carbon", "voxtral"
  ]
  if any(k in t_low for k in frontier_models) and not any(k in t_low for k in ["api pricing", "api rate limit", "sdk update", "python library"]):
    return "frontier_launch"
  if any(k in t_low for k in ["unveils new model", "releases new model", "next-generation model", "next frontier model"]):
    return "frontier_launch"

  # 8. Developer SDK / API Updates / Runtimes / Protocols
  sdk_keywords = [
      "api", "sdk", "endpoint", "pricing", "rate limit", "developer platform",
      "token pricing", "cli", "function calling", "tool use", "mcp server",
      "model context protocol", "dev kit", "playground", "developer tools",
      "python library", "node library", "rest api", "session endpoints",
      "agentcore runtime", "voice agent sdk", "agent skills"
  ]
  if any(k in t_low for k in ["api", "sdk", "pricing", "developer", "mcp", "endpoint", "tool use", "agent skills"]):
    return "sdk_api_update"
  if any(k in combined for k in ["pricing drop", "price cut", "api release", "sdk update", "mcp protocol", "session endpoints", "runtime session"]):
    return "sdk_api_update"

  # 9. Opinion, Commentary, Routine Minor Patches
  if re.search(r"\bv?\d+\.\d+\.[1-9][a-z0-9]*\b", t_low):
    return "routine_minor_update"
  if source_type in ("community", "practitioner") or "simonwillison.net" in u_low or "importai" in u_low:
    return "opinion_commentary"
  if any(k in t_low for k in ["opinion", "why i think", "essay", "speculation", "editorial"]):
    return "opinion_commentary"

  # Contextual Fallback for Official Blogs: Never blind frontier_launch
  if is_official:
    if any(k in combined for k in ["agent", "runtime", "tool", "sdk", "api", "endpoint"]):
      return "sdk_api_update"
    if any(k in combined for k in ["collaborat", "partner", "program", "initiative", "support"]):
      return "opinion_commentary"
    return "sdk_api_update"

  return "opinion_commentary"


# -------------------------------------------------------------
# 2. CALIBRATED PULSE SCORING FORMULA
# -------------------------------------------------------------
def calculate_story_scores(article, corroboration_count=1):
  """Calculates explainable, deterministic 0-100 sub-scores, calibrated overall pulse score,
  human-readable score reason codes, article intent classification, and publication eligibility.
  """
  title = article.get("title", "")
  summary = article.get("summary", "")
  link = article.get("link", "")
  full_content = f"{title} {summary}".lower()
  trust_tier = article.get("trust_tier", 2)
  is_official = article.get("is_official", False)
  source_type = article.get("source_type", "publication")
  pub_dt = article.get("published_datetime")

  # Classify article intent type
  article_type = article.get("article_type")
  if not article_type or article_type not in VALID_ARTICLE_TYPES:
    article_type = classify_article_type(title, summary, link, source_type, is_official)

  signal_badge = SIGNAL_BADGE_MAP.get(article_type, "Verified Intelligence")
  score_reasons = []

  # 1. Real-World Impact (0-100)
  impact = 50
  if article_type == "frontier_launch":
    impact += 40
    score_reasons.append("+ Frontier foundation model milestone (+40 impact)")
  elif article_type == "open_source_release":
    impact += 35
    score_reasons.append("+ Open-weights / open-source capability release (+35 impact)")
  elif article_type in ("security_vulnerability", "policy_regulation"):
    impact += 30
    score_reasons.append(f"+ Material {article_type.replace('_', ' ')} development (+30 impact)")
  elif article_type == "sdk_api_update":
    impact += 25
    score_reasons.append("+ Actionable developer SDK / runtime tooling (+25 impact)")
  elif article_type == "research_paper":
    impact += 15
    score_reasons.append("+ Empirical research preprint / benchmark evaluation (+15 impact)")
  elif article_type == "case_study_pr":
    impact -= 25
    score_reasons.append("- Vendor promotional customer case study (-25 impact)")
  elif article_type == "routine_minor_update":
    impact -= 30
    score_reasons.append("- Routine minor patch / peripheral non-AI topic (-30 impact)")

  if any(w in full_content for w in ["gpt-5", "claude 3.7", "claude 4", "gemini 4", "llama 4", "o3", "deepseek-r1"]):
    impact = min(100, impact + 10)
  impact = min(100, max(0, impact))

  # 2. Novelty & Significance (0-100)
  novelty = 55
  if any(w in full_content for w in ["breakthrough", "frontier model", "world simulation", "next frontier", "novel architecture", "new generation"]):
    novelty += 30
    score_reasons.append("+ Novel capability / major architectural milestone (+30 novelty)")
  elif article_type == "case_study_pr":
    novelty -= 25
    score_reasons.append("- Repackaged customer implementation (-25 novelty)")
  elif article_type == "routine_minor_update":
    novelty -= 25
  novelty = min(100, max(0, novelty))

  # 2.5 Technical Significance & Breakthrough Depth (0-100)
  tech_significance = 60
  breakthrough_kw = [
      "novel architecture", "state-of-the-art", "sota", "open-weights", "open-source weights",
      "speculative decoding", "radix cache", "kv cache", "distillation", "benchmark breakthrough",
      "inference speedup", "reasoning model", "rlvr", "test-time compute", "linear attention",
      "distributed serving", "quantization", "jailbreak", "adversarial attack", "agentic rl"
  ]
  routine_survey_kw = [
      "a brief survey", "a review of", "systematic review", "incremental", "preliminary study",
      "workshop", "a note on", "case study:", "customer spotlight"
  ]
  matched_breakthroughs = [w for w in breakthrough_kw if w in full_content]
  if matched_breakthroughs:
    tech_significance = min(100, 75 + len(matched_breakthroughs) * 8)
    score_reasons.append(f"+ Demonstrable technical significance: {', '.join(matched_breakthroughs[:2])} (+{min(25, len(matched_breakthroughs)*8)} tech)")
  elif any(w in full_content for w in routine_survey_kw):
    tech_significance = max(25, tech_significance - 25)
    score_reasons.append("- Incremental survey / routine overview without novel implementation (-25 tech)")
  elif article_type in ("case_study_pr", "routine_minor_update"):
    tech_significance = 35

  # Research Quality Safeguards for Preprints (arXiv / preprints)
  if article_type == "research_paper" or "arxiv.org" in (link or "").lower():
    if not matched_breakthroughs and corroboration_count < 2:
      # Penalize routine incremental preprints without proven technical breakthroughs
      impact = max(25, impact - 20)
      novelty = max(25, novelty - 20)
      tech_significance = max(30, tech_significance - 20)
      score_reasons.append("- Routine uncorroborated preprint without verifiable breakthrough signals (-20 research quality)")

  # 3. Evidence Quality & Authority (0-100)
  if is_official or trust_tier == 1:
    evidence = 100
    score_reasons.append("+ Official primary lab source (100 authority)")
  elif trust_tier == 2:
    evidence = 85
    score_reasons.append("+ Independent technology journalism desk (85 authority)")
  elif trust_tier == 3:
    evidence = 75
    score_reasons.append("+ Academic research repository (75 authority)")
  else:
    evidence = 65

  if corroboration_count >= 3:
    evidence = min(100, evidence + 15)
    score_reasons.append(f"+ Corroborated by {corroboration_count} independent publishers (+15 evidence)")
  elif corroboration_count == 2:
    evidence = min(100, evidence + 10)
    score_reasons.append("+ Corroborated by 2 independent publishers (+10 evidence)")
  elif not is_official and article_type == "research_paper":
    evidence = max(40, evidence - 5)
    score_reasons.append("- Single-source unreviewed preprint (-5 evidence)")

  # 4. Actionability for Builders & Teams (0-100)
  if article_type in ("sdk_api_update", "open_source_release"):
    actionability = 90
    score_reasons.append("+ Direct developer actionability / runnable tooling (90 actionability)")
  elif article_type in ("frontier_launch", "policy_regulation"):
    actionability = 75
  elif article_type == "case_study_pr":
    actionability = 45
  else:
    actionability = 60

  # 5. Core AI Relevance (0-100)
  if article_type in ("frontier_launch", "open_source_release", "sdk_api_update", "research_paper", "security_vulnerability"):
    ai_relevance = 95
  elif article_type == "case_study_pr":
    ai_relevance = 65
  elif article_type == "routine_minor_update":
    ai_relevance = 30
    score_reasons.append("- Peripheral non-core topic (-40 AI relevance)")
  else:
    ai_relevance = 70

  # 6. Freshness (0-100)
  if pub_dt:
    now = datetime.now(timezone.utc)
    age_hours = max(0, (now - pub_dt).total_seconds() / 3600.0)
    if age_hours <= 6:
      freshness = 100
    elif age_hours <= 18:
      freshness = 85
    elif age_hours <= 36:
      freshness = 70
    elif age_hours <= 72:
      freshness = 50
    else:
      freshness = 25
  else:
    freshness = 50

  # 7. Coverage Signal
  if corroboration_count >= 4:
    coverage_signal = 95
  elif corroboration_count == 3:
    coverage_signal = 85
  elif corroboration_count == 2:
    coverage_signal = 75
  else:
    coverage_signal = 50

  source_quality = evidence

  # Calibrated Composite Formula:
  # 0.25 * Impact + 0.20 * Novelty + 0.20 * Tech_Significance + 0.15 * Evidence + 0.10 * Actionability + 0.10 * AI_Relevance
  base_score = (
      0.25 * impact +
      0.20 * novelty +
      0.20 * tech_significance +
      0.15 * evidence +
      0.10 * actionability +
      0.10 * ai_relevance
  )

  # Apply Intent Multiplier
  multiplier = ARTICLE_TYPE_MULTIPLIERS.get(article_type, 1.0)
  raw_score = base_score * multiplier

  # Editorial Floor & Ceiling Safeguards:
  # 1. Single-source case study PR is strictly capped at 62.0 so it never crowds out top developments.
  if article_type == "case_study_pr" and corroboration_count < 3:
    final_score = min(raw_score, 62.0)
    score_reasons.append("- [case_study_penalty] Single-source vendor PR capped at 62.0 ceiling")
  # 2. Routine minor updates / peripheral gaming capped at 52.0.
  elif article_type == "routine_minor_update":
    final_score = min(raw_score, 52.0)
    score_reasons.append("- [routine_minor_penalty] Routine minor update capped at 52.0 ceiling")
  # 3. Single-source uncorroborated arXiv preprints without breakthroughs capped at 64.0 to protect signal.
  elif article_type == "research_paper" and corroboration_count < 2 and not matched_breakthroughs:
    final_score = min(raw_score, 64.0)
    score_reasons.append("- [uncorroborated_arxiv_cap] Single-source routine research preprint capped at 64.0 ceiling")
  elif article_type == "research_paper" and corroboration_count < 2:
    final_score = min(raw_score, 73.0)
    score_reasons.append("- [uncorroborated_arxiv_cap] Single-source research preprint capped at 73.0 ceiling")
  # 4. Official frontier foundation model announcements guaranteed floor of 82.0.
  elif article_type == "frontier_launch" and (is_official or trust_tier == 1):
    final_score = min(100.0, max(raw_score, 82.0))
    score_reasons.append("+ [frontier_launch_tier1] Official frontier foundation model milestone protected floor 82.0")
  else:
    final_score = min(100.0, max(0.0, raw_score))

  final_score = min(100.0, max(0.0, final_score))

  pulse_score = round(final_score, 1)

  # Confidence Label
  summary_len = len(summary.strip())
  if (is_official and summary_len >= 50) or (trust_tier in (1, 2) and corroboration_count >= 2):
    confidence_label = "high"
  elif (trust_tier in (1, 2) or source_type == "research" or trust_tier == 3) and summary_len >= 30:
    confidence_label = "medium"
  else:
    confidence_label = "low"

  # Publication Eligibility Flags
  eligible_for_top = (
      pulse_score >= 72.0 and
      article_type not in ("case_study_pr", "routine_minor_update", "opinion_commentary")
  )
  eligible_for_briefing = (
      pulse_score >= 80.0 and
      article_type in ("frontier_launch", "open_source_release", "sdk_api_update", "security_vulnerability")
  )

  return {
      "pulse_score": pulse_score,
      "overall_score": pulse_score,  # Backward compatibility alias
      "importance_score": round(impact, 1),
      "relevance_score": round(ai_relevance, 1),
      "freshness_score": round(freshness, 1),
      "coverage_score": round(coverage_signal, 1),
      "source_quality_score": round(source_quality, 1),
      "confidence_score": round(source_quality, 1),  # Backward compatibility alias
      "popularity_score": round(coverage_signal, 1),  # Backward compatibility alias
      "novelty_score": round(novelty, 1),
      "technical_significance_score": round(tech_significance, 1),
      "actionability_score": round(actionability, 1),
      "confidence_label": confidence_label,
      "article_type": article_type,
      "signal_badge": signal_badge,
      "score_reasons": score_reasons,
      "eligible_for_top_developments": eligible_for_top,
      "eligible_for_briefing": eligible_for_briefing,
  }


# -------------------------------------------------------------
# 3. TEXT & TOPIC HELPERS
# -------------------------------------------------------------
def simplify_jargon(text):
  """Clarifies technical AI jargon into plain-English accessible terms."""
  if not text:
    return ""
  s = text
  replacements = [
      (r"\bmultimodal\b", "multimodal (text, image, audio)"),
      (r"\binference compute\b", "AI reasoning compute"),
      (r"\binference\b", "model reasoning"),
      (r"\bagentic workflows\b", "action-oriented workflows"),
      (r"\bagentic\b", "action-taking"),
      (r"\bcontext window\b", "memory capacity (context window)"),
      (r"\bparameter scaling\b", "increasing model size and compute"),
      (r"\bbenchmark saturation\b", "reaching performance ceilings on test benchmarks"),
      (r"\btest-time compute\b", "thinking time before responding"),
      (r"\bquantized\b", "compressed for efficiency"),
      (r"\bquantization\b", "efficiency compression"),
  ]
  for pat, rep in replacements:
    s = re.sub(pat, rep, s, flags=re.IGNORECASE)
  return s


def sanitize_and_format_summary(raw_summary, title=""):
  """Cleans and sanitizes raw summary text:
  - Strips HTML tags and unescapes entities.
  - Removes RSS boilerplate and truncation markers ([...], […], etc.).
  - Guarantees complete grammatical sentences with terminal punctuation.
  - Prevents empty summaries or verbatim repeats of the headline.
  """
  clean_title = (title or "").strip()
  if not raw_summary:
    return f"{clean_title.rstrip('.')}."

  text = html.unescape(raw_summary)
  text = re.sub(r"<[^>]+>", " ", text)
  # Strip arXiv announcement prefixes and abstract headers
  text = re.sub(r"arXiv:\S+\s+(?:Announce Type:\s*\S+\s*)?Abstract:\s*", "", text, flags=re.I)
  text = re.sub(r"Announce Type:\s*\S+\s*Abstract:\s*", "", text, flags=re.I)
  text = re.sub(r"^Abstract:\s*", "", text, flags=re.I)
  text = re.sub(r"The post .* appeared first on .*", "", text, flags=re.I)
  text = re.sub(r"Read more on .*", "", text, flags=re.I)
  text = re.sub(r"\[\s*(?:\.\.\.|…|&#8230;)\s*\]", "", text)
  text = re.sub(r"(?:\.\.\.|…|&#8230;)", "", text)
  text = re.sub(r"\s+", " ", text).strip()

  sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
  valid_sentences = [s for s in sentences if s.endswith((".", "!", "?", '"', "'")) and len(s) > 15]

  if valid_sentences:
    accum = []
    for s in valid_sentences:
      if len(" ".join(accum + [s])) <= 320:
        accum.append(s)
      else:
        break
    res = " ".join(accum) if accum else valid_sentences[0]
  else:
    res = text.rstrip(" .,;:-") + "."

  if len(res) < 20 or res.lower() == clean_title.lower().rstrip("."):
    res = f"{clean_title.rstrip('.')}."

  return res


def evaluate_article_relevance(title, summary="", source_name="", source_type="", is_official=False):
  """Evaluates whether an article represents a genuine, meaningful AI development.
  Filters out lifestyle/holiday fluff, generic conference tickets/promotions, and non-AI general news.
  Returns: (is_relevant: bool, relevance_score: float, reason: str)
  """
  clean_title = (title or "").strip()
  if len(clean_title) < 8:
    return False, 0.0, "Title too short"

  t_lower = clean_title.lower()
  content_lower = f"{clean_title} {summary}".lower()

  # 1. Hard filter: Lifestyle, holiday, deals, costume, consumer shopping fluff in title
  fluff_title_patterns = [
      r"\b(costume|costumes|halloween costume|gift guide|gift ideas|black friday|cyber monday|deals of the day|best tech deals|best gifts|stocking stuffers|unboxing|fashion trend|gadget deal)\b"
  ]
  for pat in fluff_title_patterns:
    if re.search(pat, t_lower):
      return False, 10.0, "Lifestyle or promotional consumer fluff"

  # 2. Hard filter: Event registrations, ticket sales, webinar marketing, call for speakers
  event_patterns = [
      r"\b(call for speakers|register now for|buy tickets|ticket sale|early bird registration|visit our booth|join us live at booth|webinar recording|rsvp now|discount code for)\b"
  ]
  for pat in event_patterns:
    if re.search(pat, t_lower):
      return False, 15.0, "Event registration or marketing announcement"

  # 3. If from a Tier 1 official AI lab, it is inherently relevant unless it matches the hard filters above
  if is_official or source_type in ("official", "research"):
    return True, 90.0, "Official AI lab announcement or research preprint"

  # 4. For general tech journalism, verify meaningful AI development connection
  ai_core_terms = [
      r"\b(ai|artificial intelligence|machine learning|deep learning|llm|llms|vlm|gpt|claude|gemini|deepseek|llama|mistral|frontier model|reasoning model|neural|agent|agents|agentic|prompt|robotics|diffusion|transformer|dataset|fine-tuning|inference|context window|rag|embeddings|safety|alignment|eval|evals|red team|copilot|synthetic data|anthropic|openai|deepmind|cohere|hugging face|huggingface|midjourney|sora|runway|elevenlabs|perplexity|grok|xai|supercomputer|gpu|h100|b200|tpu|open weight|open weights)\b"
  ]
  has_ai_signal = any(bool(re.search(pat, content_lower)) for pat in ai_core_terms)
  if not has_ai_signal:
    return False, 20.0, "General tech story without substantial AI development connection"

  return True, 80.0, "Verified AI development news"


def classify_topic_detailed(title, summary=""):
  """Classifies an AI news story into one of the 8 canonical editorial categories:
  - AI Policy & Regulation
  - AI Security & Safety
  - AI Infrastructure
  - AI Business & Funding
  - AI Models & Research
  - AI Products & Tools
  - AI Applications
  - AI News (default fallback)

  Returns a tuple of (category, confidence_score, rationale).
  """
  clean_title = (title or "").strip()
  clean_summary = (summary or "").strip()
  content = f"{clean_title} {clean_summary}".lower()

  # 1. AI Policy & Regulation (Lawsuits, courts, EPA/pollution, copyright, treaties, government policy)
  if re.search(r"\b(lawsuit|lawsuits|naacp|sues|sued|suing|court|judge|legal dispute|litigation|plaintiff|defendant|subpoena|pollution|emission|emissions|clean air act|epa|environmental|smog|copyright|infringement|opt-out of scrap|scraping opt-out|fair use|licensing dispute|ai act|eu ai act|executive order|regulation|regulatory|antitrust|monopoly|ftc|doj|sec|legislation|disarmament|religious exemption)\b", content):
    return (
        "AI Policy & Regulation",
        0.95,
        "Matched legal proceedings, court ruling, regulatory compliance, environmental impact, or copyright policy"
    )

  # 2. AI Security & Safety (Cybersecurity, exploits, vulnerabilities, account takeover, alignment, red-team, sabotage, conversational safety)
  if re.search(r"\b(cybersecurity|account takeover|took over|takeover|exploit|exploits|vulnerability|vulnerabilities|cve|zero-day|auth bypass|daybreak blue|misalignment|sabotage|sabot|model spec|watermark|watermarking|biosecurity|catastrophic risk|safeguard|safeguards|adversarial|safety report|teen safety|protections for teens|jailbreak|prompt injection|traumatized|clinical anxiety|therapist|safety problem|empathetic prompt|sycophancy|conversational safety|prompt safety)\b", content):
    return (
        "AI Security & Safety",
        0.95,
        "Matched cybersecurity exploit, model safety vulnerability, alignment eval, or guardrail protocol"
    )

  # 3. AI Infrastructure (Data centers without lawsuit, GPUs, TPUs, Blackwell, H100, RTX, laptops, chips, cooling)
  if re.search(r"\b(hardware|data center|datacenter|gpu|gpus|tpu|blackwell|h100|h200|b200|rtx|spark windows laptop|silicon|custom silicon|semiconductor|server cluster|supercomputer|power grid|megawatt|gigawatt|cooling system)\b", content):
    return (
        "AI Infrastructure",
        0.92,
        "Matched hardware architecture, silicon accelerators, data center systems, or compute energy grid"
    )

  # 4. AI Business & Funding (Fundraising, venture capital, valuations, IPO, revenue, earnings)
  if re.search(r"\b(raises|raised|raising|funding round|funding target|venture capital|valuation|investors|billion target|series [a-z]|seed round|acquisition|acquisitions|acquired|merger|mergers|quarterly revenue|earnings|ipo|market cap|theranos whistleblower.*ai boom)\b", content):
    return (
        "AI Business & Funding",
        0.92,
        "Matched institutional capital raises, startup valuation, earnings report, or M&A transaction"
    )

  # 5. AI Applications (Healthcare, drug development, biotech, satellites, climate/Earth-2, delivery, reservations, legal work, voice agents)
  if re.search(r"\b(drug development|gene therapy|satellite data|forests|earth-2|robotics|autonomous vehicle|self-driving|restaurant|reservations|delivery|doordash|worldwide express|freight exceptions|transactional diligence|legal work|operating system for legal|monthly calls|retell|multiplayer game world|fable-class|clinical|diagnostics)\b", content):
    return (
        "AI Applications",
        0.88,
        "Matched domain-specific production deployment in enterprise, scientific, or consumer applications"
    )

  # 6. AI Products & Tools (Coding tools, IDE, VS Code, copilot, cursor, SDK, API credits, dev tooling, UI testing, datasette)
  if re.search(r"\b(datasette|copilot|coding agent|sdk|sdks|api endpoint|api credits|vs code|extension|agent skills|agentic ai foundation|testing with amazon nova|tamagotchi|desktop app|windows app|greptile|code review|preview web apps|ide|developer tools)\b", content):
    return (
        "AI Products & Tools",
        0.88,
        "Matched developer tooling, software product release, IDE extension, or API capability"
    )

  # 7. AI Models & Research (Frontier foundation models, reasoning models, preprints, arXiv, weights, benchmarks)
  if re.search(r"\b(frontier model|reasoning model|foundation model|claude|gemini|gpt|llama|deepseek|mistral|nemotron|qwen|voxtral|cosmos|open weights|arxiv|preprint|bair|paper|ablation|benchmark|dataset|interpretability|mechanistic|multimodal reasoning|parameter scaling)\b", content):
    return (
        "AI Models & Research",
        0.85,
        "Matched frontier foundation model release, research preprint, or architecture benchmark"
    )

  # 8. AI News (General industry developments, partnerships, leadership statements)
  return (
      "AI News",
      0.70,
      "General AI ecosystem update, strategic partnership, or executive announcement"
  )


def classify_topic(title, summary=""):
  """Backward-compatible helper returning the canonical category string."""
  cat, _, _ = classify_topic_detailed(title, summary)
  return cat


OFFICIAL_LAB_VISUALS = {
    "openai": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
    "google": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "anthropic": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
    "microsoft": "https://images.unsplash.com/photo-1633419461186-7d40a38105ec?auto=format&fit=crop&w=1200&q=80",
    "nvidia": "https://images.unsplash.com/photo-1591488320449-011701bb6704?auto=format&fit=crop&w=1200&q=80",
    "meta": "https://images.unsplash.com/photo-1618172193763-c511deb635ca?auto=format&fit=crop&w=1200&q=80",
    "huggingface": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1200&q=80",
    "mistral": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "deepseek": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "xai": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
    "amazon": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "apple": "https://images.unsplash.com/photo-1512499617640-c74ae3a79d37?auto=format&fit=crop&w=1200&q=80",
}

TOPIC_FALLBACK_VISUALS = {
    "AI Policy & Regulation": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80",
    "AI Security & Safety": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    "AI Infrastructure": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1200&q=80",
    "AI Business & Funding": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
    "AI Models & Research": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "AI Products & Tools": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    "AI Applications": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
    "AI News": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80",
    # Backward compatibility aliases
    "AI Models": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "AI Agents": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1200&q=80",
    "AI Coding": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1200&q=80",
    "AI Products": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
    "Research": "https://images.unsplash.com/photo-1507668077129-56e32842fceb?auto=format&fit=crop&w=1200&q=80",
    "Business & Funding": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
    "Open Source": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
    "AI Safety": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    "Model Releases": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1200&q=80",
    "Research & Safety": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
    "AI Business": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
    "AI Tools & Ecosystem": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80",
}

TOPIC_IMAGE_REGISTRY = TOPIC_FALLBACK_VISUALS


def detect_company(text, source=""):
  """Identifies the primary AI organization or research laboratory using word-boundary matching."""
  t = f"{text} {source}".lower()

  if re.search(r"\b(xai|grok)\b", t):
    return "xai"
  if re.search(r"\b(openai|chatgpt)\b", t):
    return "openai"
  if re.search(r"\b(anthropic|claude)\b", t):
    return "anthropic"
  if re.search(r"\b(deepmind|google)\b", t):
    return "google"
  if re.search(r"\b(mistral)\b", t):
    return "mistral"
  if re.search(r"\b(deepseek)\b", t):
    return "deepseek"
  if re.search(r"\b(meta|llama)\b", t):
    return "meta"
  if re.search(r"\b(microsoft|copilot)\b", t):
    return "microsoft"
  if re.search(r"\b(nvidia)\b", t):
    return "nvidia"
  if re.search(r"\b(hugging face|huggingface)\b", t):
    return "huggingface"
  if re.search(r"\b(cohere)\b", t):
    return "cohere"
  if re.search(r"\b(amazon|aws|bedrock)\b", t):
    return "amazon"
  if re.search(r"\b(apple)\b", t):
    return "apple"
  if re.search(r"\b(mit)\b", t):
    return "mit"
  if re.search(r"\b(the verge|verge)\b", t):
    return "verge"
  if re.search(r"\b(techcrunch)\b", t):
    return "techcrunch"
  return "default"


def estimate_reading_time(text):
  """Calculates estimated reading time in minutes."""
  words = len((text or "").split())
  minutes = max(1, round(words / 160))
  return f"{minutes} min read"


def extract_audience_pills(who_affected_str):
  """Extracts clean, scannable audience badge tags."""
  if not who_affected_str:
    return ["Enterprises", "Developers", "AI Practitioners"]
  cleaned = who_affected_str.replace(" and ", ", ").replace(" & ", ", ")
  parts = [p.strip().title() for p in cleaned.split(",") if p.strip() and len(p.strip()) < 35]
  return parts[:4] if parts else ["Enterprises", "Developers"]


def resolve_article_image_metadata(img_url, title, topic, company, link=""):
  """Resolves image URL and rich metadata prioritizing source media, lab assets, and topic fallbacks."""
  fallback_url = TOPIC_FALLBACK_VISUALS.get(
      topic,
      TOPIC_FALLBACK_VISUALS.get("AI Products", "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80")
  )

  if img_url and img_url.startswith("http"):
    final_url = img_url
    img_type = "source_media"
    credit = "Source publication"
  elif company in OFFICIAL_LAB_VISUALS:
    final_url = OFFICIAL_LAB_VISUALS[company]
    img_type = "official_asset"
    credit = f"{company.title()} announcement visual"
  else:
    final_url = fallback_url
    img_type = "category_fallback"
    credit = f"{topic} curation"

  return {
      "image_url": final_url,
      "image_source_url": link or final_url,
      "image_alt": f"Visual representation for {title}",
      "image_type": img_type,
      "image_credit": credit,
      "image_fallback": fallback_url
  }


def generate_audience_impact(title, summary, topic, company=""):
  """Generates a practical, grounded audience impact statement answering
  'Why should I care?' and 'How does this affect my work, learning, or business?'
  Assigns exactly one primary relevant audience.
  """
  content = f"{title} {summary}".lower()
  subject = company.title() if company and company != "default" else "frontier AI"

  # 1. Creators & Publishers (Scraping, robots.txt, copyright, training opt-out)
  if any(k in content for k in ["scraping", "opt-out", "robots.txt", "copyright", "creator", "publisher", "fair use"]):
    return {
        "target": "For creators & publishers",
        "impact": f"Clarifies copyright boundaries, training opt-outs, and content licensing practices involving {subject}."
    }

  # 2. Safety, Alignment & Research
  if any(k in content for k in ["traumatized", "clinical", "couch", "safety problem", "psychological", "sycophancy", "jailbreak", "adversarial"]):
    return {
        "target": "For AI researchers & safety teams",
        "impact": f"Exposes conversational vulnerability, alignment limits, and unintended persona behaviors in {subject} models."
    }

  # 3. Legal Disputes, Lawsuits & Regulatory Compliance
  if any(k in content for k in ["lawsuit", "court", "judge", "pollution", "sued", "suing", "litigation", "naacp", "clean air"]):
    return {
        "target": "For businesses & compliance teams",
        "impact": f"Signals legal exposure, compliance requirements, and regulatory scrutiny facing {subject} deployments."
    }

  # 4. Legal Tech & Document Automation (Distinct from lawsuits)
  if any(k in content for k in ["legal work", "legora", "contract analysis", "transactional diligence", "legal operating system"]):
    return {
        "target": "For enterprise legal & operations teams",
        "impact": f"Automates document review, contract analysis, and due-diligence workflows using {subject}."
    }

  # 5. Policy & Governance
  if topic in ("AI Safety", "AI Policy & Regulation", "AI Security & Safety") or any(k in content for k in ["safety", "policy", "regulation", "governance", "red team", "misalignment", "model spec", "eu ai"]):
    return {
        "target": "For businesses & compliance teams",
        "impact": f"Informs AI risk assessments, safety evaluation standards, and deployment governance for {subject}."
    }

  # 6. Enterprise Operations & Logistics
  if any(k in content for k in ["freight", "logistics", "supply chain", "enterprise", "partnership", "gsa", "government", "automation"]):
    return {
        "target": "For enterprise operators",
        "impact": f"Demonstrates practical operational automation and procurement pathways using {subject}."
    }

  # 7. Coding & Developers
  if topic == "AI Coding" or bool(re.search(r"\b(code|coding|developer|developers|api|apis|sdk|sdks|ide|mcp|copilot|github|cursor|prompt engineering|datasette)\b", content)):
    if bool(re.search(r"\b(api|apis|sdk|sdks|datasette|endpoint)\b", content)):
      return {
          "target": "For developers",
          "impact": f"Expands programmatic API endpoints and tooling integrations available for {subject}."
      }
    return {
        "target": "For developers",
        "impact": f"Directly impacts developer workflows, IDE efficiency, and code generation with {subject}."
    }

  # 8. Open Source
  if topic == "Open Source" or any(k in content for k in ["open source", "weights", "llama.cpp", "ollama", "open-source", "open-weight"]):
    return {
        "target": "For open-source builders",
        "impact": f"Provides open weights and accessible tools for self-hosted {subject} implementations."
    }

  # 9. Research
  if topic == "Research" or any(k in content for k in ["paper", "arxiv", "academic study", "research study", "benchmark", "ablation", "dataset", "extraterrestrial"]):
    return {
        "target": "For AI researchers",
        "impact": f"Advances research methodologies and empirical evaluations for {subject} architectures."
    }

  # 10. Everyday Users
  if any(k in content for k in ["search", "chatgpt", "gemini", "app", "assistant", "consumer", "free tier"]):
    return {
        "target": "For everyday users",
        "impact": f"Enhances daily workflow speed and conversational assistance powered by {subject}."
    }

  return {
      "target": "For practitioners & teams",
      "impact": f"Offers new practical efficiencies and tooling options for {subject} workflows."
  }
