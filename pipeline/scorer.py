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
]

ARTICLE_TYPE_MULTIPLIERS = {
    "frontier_launch": 1.12,
    "open_source_release": 1.12,
    "research_paper": 1.05,
    "sdk_api_update": 1.05,
    "security_vulnerability": 1.05,
    "policy_regulation": 1.00,
    "opinion_commentary": 0.80,
    "case_study_pr": 0.60,
}

SIGNAL_BADGE_MAP = {
    "frontier_launch": "🚀 Frontier Launch",
    "open_source_release": "🔓 Open Weights",
    "research_paper": "📄 Research Paper",
    "sdk_api_update": "🛠️ Dev / SDK",
    "security_vulnerability": "🛡️ Security / Policy",
    "policy_regulation": "🛡️ Security / Policy",
    "case_study_pr": "🏢 Case Study",
    "opinion_commentary": "💭 Analysis / Opinion",
}


def classify_article_type(title, summary="", link="", source_type="", is_official=False):
  """Deterministically classifies an article into one of the 8 canonical intent types.
  Inspects URL slugs, headline, content, and publisher metadata.
  """
  t_low = (title or "").lower()
  s_low = (summary or "").lower()
  u_low = (link or "").lower()
  combined = f"{t_low} {s_low}"

  # 1. Vendor PR / Customer Case Study Check (Must be checked first to catch enterprise customer blogs)
  case_study_url_patterns = [
      "/customer-stories/", "/customer-story/", "/customers/", "/customer/",
      "/case-studies/", "/case-study/", "/stories/", "partners-with",
      "/index/customer", "/index/stories"
  ]
  case_study_keywords = [
      "case study", "customer story", "customer spotlight", "partner spotlight",
      "partners with", "partnering with", "powers ", "enterprise adoption",
      "customer success", "how ", "is building the agentic", "is building the",
      "powers legal work", "customer testimonial"
  ]
  if any(p in u_low for p in case_study_url_patterns):
    return "case_study_pr"
  if any(k in t_low for k in ["case study", "customer story", "customer spotlight", "partner spotlight", "partners with"]):
    return "case_study_pr"
  if re.search(r"how\s+[a-z0-9_\-]+\s+(uses|deploys|builds|scales)\b", t_low):
    return "case_study_pr"
  if "building the" in t_low and ("operating system for" in t_low or "platform for" in t_low):
    return "case_study_pr"

  # 2. Security Vulnerability / Exploit / CVE
  sec_keywords = [
      "cve-", "vulnerability", "vulnerabilities", "jailbreak", "prompt injection",
      "exploit", "backdoor", "red team", "red-team", "attack vector",
      "adversarial attack", "sandbox escape", "data leak", "malicious payload"
  ]
  if any(k in combined for k in sec_keywords):
    return "security_vulnerability"

  # 3. Policy & Regulation / Legal / Standards
  policy_keywords = [
      "regulation", "legislation", "lawsuit", "sues", "sued", "court", "copyright",
      "antitrust", "eu ai act", "executive order", "ftc", "doj", "senate", "congress",
      "ban", "compliance", "standards body", "treaty", "legal challenge", "regulators"
  ]
  if any(k in combined for k in policy_keywords):
    return "policy_regulation"

  # 4. Open-Source & Open-Weight Releases
  os_keywords = [
      "open weight", "open-weight", "open source", "open-source", "weights released",
      "weights available", "apache 2.0", "mit license", "github repo", "hugging face",
      "huggingface.co", "model weights", "checkpoint", "ollama", "vllm", "gguf",
      "finetuning", "fine-tuned", "open release"
  ]
  if any(k in combined for k in os_keywords):
    return "open_source_release"

  # 5. Developer SDK / API Updates
  sdk_keywords = [
      "api", "sdk", "endpoint", "pricing", "rate limit", "developer platform",
      "token pricing", "cli", "function calling", "tool use", "mcp server",
      "model context protocol", "dev kit", "playground", "developer tools",
      "python library", "node library", "rest api"
  ]
  if any(k in t_low for k in ["api", "sdk", "pricing", "developer", "mcp", "endpoint", "tool use"]):
    return "sdk_api_update"
  if any(k in combined for k in ["pricing drop", "price cut", "api release", "sdk update", "mcp protocol"]):
    return "sdk_api_update"

  # 6. Research Papers & Preprints (arXiv, BAIR, academic source_type)
  if "arxiv.org" in u_low or "bair.berkeley.edu" in u_low or source_type == "research":
    return "research_paper"
  if any(k in t_low for k in ["paper", "preprint", "benchmark", "dataset", "empirical study", "architecture"]):
    return "research_paper"

  # 7. Frontier Foundation Model Launches
  frontier_models = [
      "gpt-5", "gpt-4", "o1", "o3", "o4", "claude 3.7", "claude 4", "gemini 2",
      "gemini 3", "deepseek-v3", "deepseek-r1", "llama 4", "qwen 2.5", "mistral large",
      "grok 3", "frontier model", "foundation model", "flagship model", "reasoning model"
  ]
  if any(k in t_low for k in frontier_models):
    return "frontier_launch"
  if any(k in t_low for k in ["unveils new model", "releases new model", "next-generation model"]):
    return "frontier_launch"

  # 8. Opinion & Commentary
  if source_type in ("community", "practitioner") or "simonwillison.net" in u_low or "importai" in u_low:
    return "opinion_commentary"
  if any(k in t_low for k in ["opinion", "why i think", "essay", "speculation", "editorial"]):
    return "opinion_commentary"

  # Default fallback based on publisher tier
  if is_official:
    return "frontier_launch"
  return "opinion_commentary"


# -------------------------------------------------------------
# 2. CALIBRATED PULSE SCORING FORMULA
# -------------------------------------------------------------
def calculate_story_scores(article, corroboration_count=1):
  """Calculates deterministic 0-100 sub-scores, calibrated overall pulse score,
  article intent classification, and signal badge.
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

  signal_badge = SIGNAL_BADGE_MAP.get(article_type, "⚡ AI Intelligence")

  # 1. Importance (Impact, novelty, scale)
  importance = 60
  if any(w in full_content for w in ["frontier", "breakthrough", "major", "first time", "release", "benchmark"]):
    importance += 15
  if any(w in full_content for w in ["gpt-5", "claude 3.7", "claude 4", "gemini 3", "llama 4", "o3", "new model"]):
    importance += 20
  if any(w in full_content for w in ["safety treaty", "disarmament", "regulation", "law", "executive order", "nist"]):
    importance += 15
  if is_official:
    importance += 10

  # Refined Safety & Policy Protected Baseline:
  # Apply protected importance floor (72) strictly when article_type is security_vulnerability or policy_regulation,
  # or when corroborated by 2+ independent sources.
  is_safety_or_policy = any(w in full_content for w in [
      "safety", "alignment", "policy", "governance", "regulation", "law",
      "executive order", "nist", "eval", "red team", "security", "treaty",
      "pre-deployment", "frontier safety"
  ])
  if is_safety_or_policy:
    importance += 15
    if article_type in ("security_vulnerability", "policy_regulation") or corroboration_count >= 2:
      importance = max(importance, 72)

  importance = min(100, max(0, importance))

  # 2. Audience Relevance (Developer, Practical Tools, Enterprise)
  audience_relevance = 65
  if any(w in full_content for w in ["developer", "coding", "api", "agent", "tool", "workflow", "mcp", "open source"]):
    audience_relevance += 20
  if any(w in full_content for w in ["free", "available now", "how to", "benchmark"]):
    audience_relevance += 15
  audience_relevance = min(100, max(0, audience_relevance))

  # 3. Freshness (Exponential decay from published date, neutral 50 if missing)
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

  # 4. Coverage & Corroboration Signal (Grounded in verified multi-publisher coverage)
  if corroboration_count >= 4:
    coverage_signal = 95
  elif corroboration_count == 3:
    coverage_signal = 85
  elif corroboration_count == 2:
    coverage_signal = 75
  else:
    coverage_signal = 50

  # 5. Source Quality & Authority Score
  if is_official or trust_tier == 1:
    source_quality = 100
  elif trust_tier == 2:
    source_quality = 85
  elif trust_tier == 3:
    source_quality = 80
  else:
    source_quality = 65

  # Base composite score formula:
  # 0.30 * Importance + 0.25 * Audience_Relevance + 0.20 * Freshness + 0.15 * Coverage_Corroboration + 0.10 * Source_Tier_Quality
  base_score = (
      0.30 * importance +
      0.25 * audience_relevance +
      0.20 * freshness +
      0.15 * coverage_signal +
      0.10 * source_quality
  )

  # Apply Intent Multiplier
  multiplier = ARTICLE_TYPE_MULTIPLIERS.get(article_type, 1.0)
  raw_score = base_score * multiplier

  # Special Intent Cap:
  # Cap maximum final score of any single-source "case_study_pr" item at 64.0
  # so it never enters top_developments unless corroborated by 3+ independent Tier-1/Tier-2 publications.
  if article_type == "case_study_pr" and corroboration_count < 3:
    final_score = min(raw_score, 64.0)
  else:
    final_score = min(100.0, max(0.0, raw_score))

  pulse_score = round(final_score, 1)

  # Calibrate confidence_label based on evidence provenance and source reliability
  summary_len = len(summary.strip())
  if (is_official and summary_len >= 50) or (trust_tier in (1, 2) and corroboration_count >= 2):
    confidence_label = "high"
  elif (trust_tier in (1, 2) or source_type == "research" or trust_tier == 3) and summary_len >= 30:
    confidence_label = "medium"
  else:
    confidence_label = "low"

  return {
      "pulse_score": pulse_score,
      "overall_score": pulse_score,  # Backward compatibility alias
      "importance_score": importance,
      "relevance_score": audience_relevance,
      "freshness_score": freshness,
      "coverage_score": coverage_signal,
      "source_quality_score": source_quality,
      "confidence_score": source_quality,  # Backward compatibility alias
      "popularity_score": coverage_signal,  # Backward compatibility alias
      "confidence_label": confidence_label,
      "article_type": article_type,
      "signal_badge": signal_badge,
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
