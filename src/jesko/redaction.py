from __future__ import annotations
import re

PATTERNS = [
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]"),
    (r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]"),
    (r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]"),
    (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b", "[REDACTED JWT]"),
    (r"\b(?:ghp|github_pat|sk|xoxb|AKIA)[A-Za-z0-9_-]{12,}\b", "[REDACTED KEY]"),
]

def redact(text: str, limit: int = 1000) -> str:
    value = text or ""
    for pattern, replacement in PATTERNS:
        value = re.sub(pattern, replacement, value)
    return value[:limit]
