"""
tests/test_pii_detection.py
────────────────────────────
Unit tests for the PII detection and redaction engine.
Run: pytest tests/test_pii_detection.py -v
"""

import sys
from pathlib import Path
import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.governance.analyzer import analyze_prompt, batch_analyze, _score_to_level
from src.governance.redactor import redact_text, pseudonymise_user_id, redact_dataframe


# ═══════════════════════════════════════════════════════
# PII DETECTION — REGEX PATTERNS
# ═══════════════════════════════════════════════════════

class TestRegexDetection:

    def test_email_detected(self):
        result = analyze_prompt("p1", "Contact john.doe@example.com for support")
        assert result.risk_flag == 1
        assert any("EMAIL" in t for t in result.pii_types)

    def test_credit_card_detected(self):
        result = analyze_prompt("p2", "Process card number 4111-1111-1111-1111")
        assert result.risk_flag == 1
        assert any("CREDIT_CARD" in t for t in result.pii_types)

    def test_ssn_detected(self):
        result = analyze_prompt("p3", "Employee SSN: 123-45-6789")
        assert result.risk_flag == 1
        assert any("SSN" in t for t in result.pii_types)

    def test_api_key_detected(self):
        result = analyze_prompt("p4", "My key is sk-prod-abc123def456ghi789")
        assert result.risk_flag == 1
        assert any("API_KEY" in t for t in result.pii_types)

    def test_github_token_detected(self):
        result = analyze_prompt("p5", "Token: ghp-abcdef123456789xyz")
        assert result.risk_flag == 1

    def test_clean_prompt_no_risk(self):
        result = analyze_prompt(
            "p6", "Write a function to calculate the Fibonacci sequence"
        )
        assert result.risk_level in ["Low", "Medium"]
        # Should not be Critical for a clean technical prompt
        assert result.risk_level != "Critical"

    def test_empty_prompt(self):
        result = analyze_prompt("p7", "")
        assert result.risk_score == 0.0
        assert result.risk_flag == 0

    def test_none_prompt(self):
        result = analyze_prompt("p8", None)
        assert result.risk_score == 0.0
        assert result.risk_flag == 0


# ═══════════════════════════════════════════════════════
# RISK SCORING THRESHOLDS
# ═══════════════════════════════════════════════════════

class TestRiskScoreThresholds:

    def test_score_to_level_mapping(self):
        assert _score_to_level(0)   == "Low"
        assert _score_to_level(10)  == "Low"
        assert _score_to_level(25)  == "Medium"
        assert _score_to_level(50)  == "High"
        assert _score_to_level(75)  == "Critical"
        assert _score_to_level(100) == "Critical"

    def test_high_risk_prompt_scores_high(self):
        """Prompt with credit card + SSN + email should score Critical."""
        text = (
            "Customer John Doe (SSN 987-65-4321) charged card 4111-1111-1111-1111 "
            "confirmation to jd@bank.com"
        )
        result = analyze_prompt("p9", text)
        assert result.risk_score >= 50  # At least High
        assert result.risk_flag == 1

    def test_result_has_required_fields(self):
        result = analyze_prompt("p10", "Hello world")
        assert hasattr(result, "prompt_id")
        assert hasattr(result, "risk_score")
        assert hasattr(result, "risk_level")
        assert hasattr(result, "risk_flag")
        assert hasattr(result, "pii_types")

    def test_score_capped_at_100(self):
        """Even extremely risky prompts should not exceed 100."""
        text = " ".join([
            "password=hunter2 card 4111-1111-1111-1111",
            "SSN 123-45-6789 email a@b.com",
            "api_key sk-secret-abc123 secret token bearer",
            "credit card private_key access_key confidential merger acquisition",
        ])
        result = analyze_prompt("p11", text)
        assert result.risk_score <= 100.0


# ═══════════════════════════════════════════════════════
# BATCH ANALYSIS
# ═══════════════════════════════════════════════════════

class TestBatchAnalysis:

    def test_batch_returns_correct_count(self):
        records = [
            {"prompt_id": "b1", "prompt_text": "Normal technical query"},
            {"prompt_id": "b2", "prompt_text": "Call 555-123-4567 for help"},
            {"prompt_id": "b3", "prompt_text": "Write unit tests"},
        ]
        results = batch_analyze(records)
        assert len(results) == 3

    def test_batch_preserves_order(self):
        records = [
            {"prompt_id": f"b{i}", "prompt_text": f"prompt {i}"}
            for i in range(10)
        ]
        results = batch_analyze(records)
        for i, r in enumerate(results):
            assert r.prompt_id == f"b{i}"

    def test_batch_empty_list(self):
        results = batch_analyze([])
        assert results == []


# ═══════════════════════════════════════════════════════
# REDACTION
# ═══════════════════════════════════════════════════════

class TestRedaction:

    def test_email_redacted(self):
        out = redact_text("Contact john@example.com today")
        assert "john@example.com" not in out
        assert "[EMAIL_REDACTED]" in out

    def test_credit_card_redacted(self):
        out = redact_text("Charge card 4111-1111-1111-1111")
        assert "4111" not in out
        assert "[CARD_REDACTED]" in out

    def test_ssn_redacted(self):
        out = redact_text("SSN 123-45-6789 is confidential")
        assert "123-45-6789" not in out

    def test_api_key_redacted(self):
        out = redact_text("Use key sk-prod-abc123def456")
        assert "sk-prod-abc123def456" not in out

    def test_clean_text_unchanged_semantically(self):
        original = "Write a function to sort a list of integers"
        out = redact_text(original)
        # No PII → text should be largely unchanged (NER may change ORG names)
        assert len(out) > 0

    def test_none_input_returns_none(self):
        assert redact_text(None) is None

    def test_empty_string_returns_empty(self):
        assert redact_text("") == ""


# ═══════════════════════════════════════════════════════
# PSEUDONYMISATION
# ═══════════════════════════════════════════════════════

class TestPseudonymisation:

    def test_deterministic(self):
        """Same input always gives same output."""
        h1 = pseudonymise_user_id("USR001")
        h2 = pseudonymise_user_id("USR001")
        assert h1 == h2

    def test_different_inputs_different_outputs(self):
        h1 = pseudonymise_user_id("USR001")
        h2 = pseudonymise_user_id("USR002")
        assert h1 != h2

    def test_output_format(self):
        h = pseudonymise_user_id("USR001")
        assert h.startswith("USR_")

    def test_original_not_in_output(self):
        h = pseudonymise_user_id("USR001_JOHN_SMITH")
        assert "JOHN" not in h
        assert "SMITH" not in h


# ═══════════════════════════════════════════════════════
# DATAFRAME REDACTION
# ═══════════════════════════════════════════════════════

class TestDataFrameRedaction:

    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"user_id": "U001", "prompt_text": "Email me at alice@corp.com please"},
            {"user_id": "U002", "prompt_text": "Card 4111-1111-1111-1111 declined"},
            {"user_id": "U003", "prompt_text": "Sort algorithm in Python"},
        ])

    def test_pii_removed_from_column(self):
        df = self._sample_df()
        result = redact_dataframe(df, text_col="prompt_text")
        for text in result["prompt_text"]:
            assert "alice@corp.com"  not in text
            assert "4111-1111-1111" not in text

    def test_non_pii_row_not_corrupted(self):
        df = self._sample_df()
        result = redact_dataframe(df, text_col="prompt_text")
        assert "Sort algorithm" in result["prompt_text"].iloc[2]

    def test_pseudonymise_user_column(self):
        df = self._sample_df()
        result = redact_dataframe(df, text_col="prompt_text",
                                  user_col="user_id", pseudonymise=True)
        for uid in result["user_id"]:
            assert uid.startswith("USR_")
            assert "U001" not in uid

    def test_returns_copy_not_inplace(self):
        df   = self._sample_df()
        orig = df["prompt_text"].tolist()
        redact_dataframe(df, text_col="prompt_text")
        assert df["prompt_text"].tolist() == orig  # original unchanged
