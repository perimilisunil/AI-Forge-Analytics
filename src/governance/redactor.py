"""
src/governance/redactor.py
───────────────────────────
Privacy-First Anonymisation Layer.
Masks PII before data is stored or displayed.
Demonstrates a "Privacy-First Architecture" for enterprise compliance.
"""

import re
import hashlib
from loguru import logger

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
except OSError:
    _SPACY_AVAILABLE = False
    _NLP = None

from src.governance.analyzer import REGEX_PATTERNS


# ─── Redaction tokens ────────────────────────────────────
REDACTION_MAP = {
    "email":           "[EMAIL_REDACTED]",
    "phone_us":        "[PHONE_REDACTED]",
    "credit_card":     "[CARD_REDACTED]",
    "ssn":             "[SSN_REDACTED]",
    "api_key":         "[API_KEY_REDACTED]",
    "ip_address":      "[IP_REDACTED]",
    "url_with_cred":   "[URL_CRED_REDACTED]",
    "PERSON":          "[NAME_REDACTED]",
    "ORG":             "[ORG_REDACTED]",
    "GPE":             "[LOCATION_REDACTED]",
    "LOC":             "[LOCATION_REDACTED]",
}


def redact_text(text: str) -> str:
    """
    Replace all detected PII in text with safe placeholders.
    Order: spaCy NER first, then regex patterns.
    """
    if not text or not isinstance(text, str):
        return text

    redacted = text

    # ── 1. Regex redaction ───────────────────────────────
    for pattern_name, pattern in REGEX_PATTERNS.items():
        token = REDACTION_MAP.get(pattern_name, f"[{pattern_name.upper()}_REDACTED]")
        redacted = pattern.sub(token, redacted)

    # ── 2. spaCy NER redaction ───────────────────────────
    if _SPACY_AVAILABLE and _NLP is not None:
        doc = _NLP(redacted[:5000])
        # Process in reverse order to preserve character offsets
        for ent in sorted(doc.ents, key=lambda e: e.start_char, reverse=True):
            token = REDACTION_MAP.get(ent.label_, f"[{ent.label_}_REDACTED]")
            redacted = redacted[:ent.start_char] + token + redacted[ent.end_char:]

    return redacted


def pseudonymise_user_id(user_id: str, salt: str = "aiforge_salt_2024") -> str:
    """
    Replace a real user_id with a consistent pseudonym.
    Same input always produces same output (deterministic hash).
    Irreversible without the salt.
    """
    h = hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:12]
    return f"USR_{h.upper()}"


def redact_dataframe(df, text_col: str = "prompt_text",
                     user_col: str = None,
                     pseudonymise: bool = False) -> object:
    """
    Apply redaction to an entire DataFrame column in-place.

    Args:
        df:           pandas DataFrame
        text_col:     Column containing prompt text to redact
        user_col:     Optional column with user IDs to pseudonymise
        pseudonymise: If True, also hash user_col values

    Returns:
        Modified DataFrame (copy)
    """
    result = df.copy()

    if text_col in result.columns:
        logger.info(f"Redacting column '{text_col}' in {len(result)} rows")
        result[text_col] = result[text_col].apply(
            lambda t: redact_text(t) if isinstance(t, str) else t
        )

    if pseudonymise and user_col and user_col in result.columns:
        logger.info(f"Pseudonymising column '{user_col}'")
        result[user_col] = result[user_col].apply(pseudonymise_user_id)

    return result
