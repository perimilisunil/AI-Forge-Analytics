"""
src/governance/analyzer.py
───────────────────────────
PII Detection Engine using spaCy Named Entity Recognition.
Scans prompt text for sensitive data patterns:
  - Personal names (PERSON)
  - Organisations (ORG)
  - Locations (GPE, LOC)
  - Credit card / phone / email patterns (regex)
  - API keys, passwords (pattern matching)
  - Custom sensitive keywords (configurable)

Returns a risk score 0–100 and a list of detected entity types.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

# spaCy import — graceful fallback if model not downloaded
try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
    logger.info("spaCy en_core_web_sm loaded successfully")
except OSError:
    _SPACY_AVAILABLE = False
    _NLP = None
    logger.warning(
        "spaCy model 'en_core_web_sm' not found. "
        "Run: python -m spacy download en_core_web_sm\n"
        "Falling back to regex-only PII detection."
    )


# ─── Sensitive keyword list ───────────────────────────────
SENSITIVE_KEYWORDS = {
    # Credentials
    "password", "passwd", "secret", "api_key", "apikey",
    "token", "bearer", "private_key", "access_key", "secret_key",
    # Finance
    "credit card", "card number", "cvv", "bank account",
    "routing number", "ssn", "social security",
    # Medical
    "diagnosis", "prescription", "patient id", "medical record",
    # Legal / IP
    "confidential", "proprietary", "attorney-client", "nda",
    "trade secret", "merger", "acquisition", "insider",
    # Internal project codes (example — extend per org)
    "project phoenix", "operation", "internal only",
}

# ─── Regex patterns ──────────────────────────────────────
REGEX_PATTERNS = {
    "email":       re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_us":    re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ssn":         re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "api_key":     re.compile(r"\b(?:sk|pk|ghp|xox[baprs])-[A-Za-z0-9_\-]{10,}\b"),
    "ip_address":  re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "url_with_cred": re.compile(r"https?://[^@\s]+:[^@\s]+@[^\s]+"),
}

# ─── Scoring weights ─────────────────────────────────────
SCORE_WEIGHTS = {
    "ner_PERSON":      15,
    "ner_ORG":         10,
    "ner_GPE":          5,
    "ner_LOC":          5,
    "ner_MONEY":       20,
    "regex_email":     25,
    "regex_phone_us":  20,
    "regex_credit_card": 40,
    "regex_ssn":       45,
    "regex_api_key":   50,
    "regex_ip_address":  5,
    "regex_url_with_cred": 45,
    "keyword_match":   20,
}


@dataclass
class PIIAnalysisResult:
    """Result object returned by analyze_prompt()."""
    prompt_id:      str
    risk_score:     float          # 0–100
    risk_level:     str            # Low / Medium / High / Critical
    risk_flag:      int            # 0 or 1 (flagged if score > 25)
    entities_found: list[str]      = field(default_factory=list)
    pii_types:      list[str]      = field(default_factory=list)
    redacted_text:  Optional[str]  = None


def _score_to_level(score: float) -> str:
    if score >= 75: return "Critical"
    if score >= 50: return "High"
    if score >= 25: return "Medium"
    return "Low"


def analyze_prompt(prompt_id: str, text: str) -> PIIAnalysisResult:
    """
    Analyse a single prompt for PII and sensitive content.

    Args:
        prompt_id: Unique identifier for the prompt
        text:      Raw prompt text

    Returns:
        PIIAnalysisResult with score, level, flag, and entity list
    """
    if not text or not isinstance(text, str):
        return PIIAnalysisResult(
            prompt_id=prompt_id, risk_score=0,
            risk_level="Low", risk_flag=0
        )

    score       = 0.0
    pii_types   = []
    text_lower  = text.lower()

    # ── 1. spaCy NER ─────────────────────────────────────
    if _SPACY_AVAILABLE and _NLP is not None:
        doc = _NLP(text[:5000])  # Limit to 5K chars for performance
        ner_types_seen = set()
        for ent in doc.ents:
            key = f"ner_{ent.label_}"
            if key in SCORE_WEIGHTS and key not in ner_types_seen:
                score += SCORE_WEIGHTS[key]
                pii_types.append(f"NER:{ent.label_}")
                ner_types_seen.add(key)

    # ── 2. Regex patterns ────────────────────────────────
    for pattern_name, pattern in REGEX_PATTERNS.items():
        if pattern.search(text):
            weight_key = f"regex_{pattern_name}"
            score += SCORE_WEIGHTS.get(weight_key, 10)
            pii_types.append(f"REGEX:{pattern_name.upper()}")

    # ── 3. Sensitive keyword matching ───────────────────
    keywords_matched = []
    for kw in SENSITIVE_KEYWORDS:
        if kw in text_lower:
            keywords_matched.append(kw)
    if keywords_matched:
        # Cap keyword contribution to avoid over-scoring
        keyword_score = min(SCORE_WEIGHTS["keyword_match"] * len(keywords_matched), 40)
        score += keyword_score
        pii_types.append(f"KEYWORD:{','.join(keywords_matched[:3])}")

    # Cap at 100
    score = min(round(score, 1), 100.0)
    level = _score_to_level(score)
    flag  = 1 if score >= 25 else 0

    return PIIAnalysisResult(
        prompt_id=prompt_id,
        risk_score=score,
        risk_level=level,
        risk_flag=flag,
        pii_types=pii_types,
    )


def batch_analyze(records: list[dict]) -> list[PIIAnalysisResult]:
    """
    Analyse a list of {'prompt_id': ..., 'prompt_text': ...} dicts.
    Returns list of PIIAnalysisResult in same order.
    """
    results = []
    for rec in records:
        r = analyze_prompt(rec.get("prompt_id", ""), rec.get("prompt_text", ""))
        results.append(r)
    return results
