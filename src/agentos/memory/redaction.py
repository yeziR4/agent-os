"""Shared redaction helpers for memory-derived text."""

from __future__ import annotations

import re

from agentos.redact import redact_sensitive_text

#: This is the last-resort net for exactly what redact_sensitive_text's
#: general pipeline deliberately lets through: a credential-shaped value
#: shorter than _MIN_SECRET_VALUE_LEN (12 chars) — too short to be worth
#: blocking for general-purpose text, but not something a durable memory
#: write should keep in the clear either. The optional quote after the
#: keyword matches a JSON/YAML key's closing quote (``"password": "..."``),
#: mirroring redact.py's own _ASSIGNMENT_RE — without it, a short secret
#: in JSON-quoted-key form (the most common shape for tool output and API
#: payloads that end up in memory) matched neither this pattern nor the
#: general pipeline, and was persisted unredacted.
_KEYWORD_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)(['\"]?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
)


def _replace_keyword(match: re.Match[str]) -> str:
    val = match.group(3)
    stripped_val = val.strip("\"'")
    if "***" in stripped_val or "«redacted" in stripped_val or "[REDACTED]" in stripped_val:
        return match.group(0)
    return f"{match.group(1)}{match.group(2)}[REDACTED]"


def redact_memory_text(text: str) -> str:
    # force=True: AGENTOS_REDACT_SECRETS=0 is an *egress* escape hatch and must
    # not unmask what gets written to durable memory.
    redacted = redact_sensitive_text(text, force=True) or text
    return _KEYWORD_PATTERN.sub(_replace_keyword, redacted)
