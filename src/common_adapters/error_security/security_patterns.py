"""
Reusable security and redaction helpers for production agents.
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Sanitize and detect suspicious user input before prompt construction."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions:",
        r"system\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
    ]

    def __init__(self):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]

    def is_suspicious(self, text: Optional[str]) -> tuple[bool, Optional[str]]:
        """Return whether input appears suspicious and the matching pattern if any."""
        if not text:
            return False, None
        for pattern in self.patterns:
            if pattern.search(text):
                logger.warning(
                    "[Security] Suspicious input detected pattern=%s chars=%s preview=%s",
                    pattern.pattern,
                    len(text),
                    safe_prompt_for_log(text, limit=600),
                )
                return True, pattern.pattern
        return False, None

    def sanitize(self, text: Optional[str]) -> str:
        """Apply low-risk sanitization to reduce prompt injection primitives."""
        if not text:
            return ""

        cleaned = text
        cleaned = re.sub(r"[-]{3,}", "", cleaned)
        cleaned = re.sub(r"[=]{3,}", "", cleaned)
        cleaned = cleaned.replace("{{", "{ {").replace("}}", "} }")
        if cleaned != text:
            logger.info(
                "[Security] Input sanitized chars_before=%s chars_after=%s before=%s after=%s",
                len(text),
                len(cleaned),
                safe_prompt_for_log(text, limit=600),
                safe_prompt_for_log(cleaned, limit=600),
            )
        return cleaned.strip()


class PIIDetector:
    """Detect and mask common PII and sensitive token-like strings."""

    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    }

    SENSITIVE_VALUE_PATTERNS = [
        (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
        (re.compile(r"(?i)\b(access[_\- ]?token|api[_\- ]?key|secret|password)\b\s*[:=]\s*['\"]?([^\s,'\"]+)"), r"\1=[REDACTED]"),
    ]

    def detect(self, text: Optional[str]) -> dict[str, list[str]]:
        """Detect PII in text."""
        if not text:
            return {}
        found: dict[str, list[str]] = {}
        for pii_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                found[pii_type] = matches
        if found:
            logger.warning(
                "[Security] PII detected types=%s counts=%s",
                list(found.keys()),
                {k: len(v) for k, v in found.items()},
            )
        return found

    def mask(self, text: Optional[str]) -> str:
        """Mask PII and sensitive values in text."""
        if not text:
            return ""

        masked = text
        for pii_type, pattern in self.PATTERNS.items():
            if pii_type == "email":
                masked = re.sub(pattern, "[EMAIL REDACTED]", masked)
            elif pii_type == "phone":
                masked = re.sub(pattern, "[PHONE REDACTED]", masked)
            elif pii_type == "ssn":
                masked = re.sub(pattern, "[SSN REDACTED]", masked)
            elif pii_type == "credit_card":
                masked = re.sub(pattern, "[CARD REDACTED]", masked)
            elif pii_type == "ip_address":
                masked = re.sub(pattern, "[IP REDACTED]", masked)

        for pattern, replacement in self.SENSITIVE_VALUE_PATTERNS:
            masked = pattern.sub(replacement, masked)

        if masked != text:
            logger.info(
                "[Security] Sensitive values masked chars_before=%s chars_after=%s",
                len(text),
                len(masked),
            )
        return masked


def redact_sensitive_dict(value: Any) -> Any:
    """Recursively redact token/secret-like fields and mask string leaves."""
    pii = PIIDetector()

    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            key_str = str(key).lower()
            if any(k in key_str for k in ("token", "secret", "password", "authorization", "cookie", "api_key")):
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_sensitive_dict(item)
        return out

    if isinstance(value, list):
        return [redact_sensitive_dict(v) for v in value]

    if isinstance(value, str):
        return pii.mask(value)

    return value


def safe_prompt_for_log(text: Optional[str], *, limit: Optional[int] = None) -> str:
    """Return log-safe prompt text with masking and optional truncation."""
    pii = PIIDetector()
    masked = pii.mask(text or "")
    if limit and limit > 0 and len(masked) > limit:
        return masked[:limit] + f"... [truncated {len(masked) - limit} chars]"
    return masked
