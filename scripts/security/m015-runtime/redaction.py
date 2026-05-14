#!/usr/bin/env python3
"""Redaction guardrails for M015 runtime security evidence.

The DB seam writes durable artifacts under docs/reports/security/m015.  Those
artifacts must be useful for later agents without carrying DSNs, credentials,
private keys, local host paths, PHI, or live-provider payloads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


class RedactionError(RuntimeError):
    """Raised when evidence contains a denylisted sensitive value."""

    def __init__(self, findings: Iterable[str]) -> None:
        self.findings = tuple(dict.fromkeys(findings))
        super().__init__("redaction_denylist_hit: " + ", ".join(self.findings))


# Patterns are intentionally conservative for durable evidence.  Sanitization is
# allowed for transient subprocess/log output, but persisted evidence must fail
# closed if any of these survive into the final JSON or Markdown summary.
DENYLIST_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "credentialed_url",
        re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@"),
    ),
    (
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    ),
    (
        "certificate_block",
        re.compile(r"-----BEGIN CERTIFICATE-----", re.IGNORECASE),
    ),
    (
        "authorization_header",
        re.compile(r"(?i)\bauthorization\s*:\s*(bearer|basic)\s+[^\s,;]+"),
    ),
    (
        "cookie_header",
        re.compile(r"(?i)\b(set-cookie|cookie)\s*:\s*[^\n\r]+"),
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b[A-Z0-9_]*(PASSWORD|TOKEN|SECRET|PRIVATE[_-]?KEY|API[_-]?KEY)[A-Z0-9_]*\s*[:=]\s*[^\s,}]+"
        ),
    ),
    (
        "firebase_service_account_material",
        re.compile(r"(?i)\b(firebase_admin|service_account|private_key_id|client_x509_cert_url)\b"),
    ),
    ("cpf_like_value", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    (
        "real_email_like_value",
        re.compile(
            r"(?i)\b[A-Z0-9._%+-]+@(?!example\.invalid\b|localhost\b)[A-Z0-9.-]+\.[A-Z]{2,}\b"
        ),
    ),
    (
        "br_phone_like_value",
        re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9\d{4}[-\s]?\d{4}(?!\d)"),
    ),
    ("raw_windows_mount_path", re.compile(r"/mnt/c/[^\s,;\])}]+")),
    ("runtime_cert_path", re.compile(r"/m015-certs/[^\s,;\])}]+")),
    (
        "raw_sql_stderr",
        re.compile(
            r"(?is)\b(?:stderr|stdout|sql|statement|query)\s*[:=][^\n\r]*"
            r"(?:select\s+.+?\s+from|insert\s+into|update\s+.+?\s+set|delete\s+from|alter\s+table|create\s+table|drop\s+table)\b"
        ),
    ),
    (
        "raw_patient_or_provider_payload",
        re.compile(
            r"(?i)[\"']?\b(patient[_ -]?name|patient[_ -]?value|provider[_ -]?payload|raw[_ -]?payload|cpf|phone|email)\b[\"']?\s*[:=]"
        ),
    ),
)


_SANITIZERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@"),
        "<scheme>://<redacted>@",
    ),
    (
        re.compile(r"(?is)-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----"),
        "<redacted-private-key>",
    ),
    (
        re.compile(r"(?is)-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----"),
        "<redacted-certificate>",
    ),
    (re.compile(r"(?i)(authorization\s*:\s*)(bearer|basic)\s+[^\s,;]+"), r"\1<redacted>"),
    (re.compile(r"(?i)((?:set-cookie|cookie)\s*:\s*)[^\n\r]+"), r"\1<redacted>"),
    (
        re.compile(
            r"(?i)(\b[A-Z0-9_]*(?:PASSWORD|TOKEN|SECRET|PRIVATE[_-]?KEY|API[_-]?KEY)[A-Z0-9_]*\s*[:=]\s*)[^\s,}]+"
        ),
        r"\1<redacted>",
    ),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "<redacted-cpf>"),
    (
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@(?!example\.invalid\b|localhost\b)[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "<redacted-email>",
    ),
    (
        re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9\d{4}[-\s]?\d{4}(?!\d)"),
        "<redacted-phone>",
    ),
    (
        re.compile(
            r"(?is)(\b(?:stderr|stdout|sql|statement|query)\s*[:=]\s*)"
            r"(?:select\s+.+?\s+from|insert\s+into|update\s+.+?\s+set|delete\s+from|alter\s+table|create\s+table|drop\s+table)"
            r".*?(?=(?:\n|\r|$|\]))"
        ),
        r"\1<redacted-sql-statement>",
    ),
    (
        re.compile(
            r"(?i)([\"']?\b(?:patient[_ -]?name|patient[_ -]?value|provider[_ -]?payload|raw[_ -]?payload|cpf|phone|email)\b[\"']?\s*[:=]\s*)[^\n\r,}]+"
        ),
        r"\1<redacted>",
    ),
    (re.compile(r"/mnt/c/[^\s,;\])}]+"), "<redacted-host-path>"),
    (re.compile(r"/m015-certs/[^\s,;\])}]+"), "<redacted-cert-path>"),
)


def sanitize_text(value: Any, *, max_chars: int | None = None) -> str:
    """Return a log-safe string with known sensitive shapes replaced."""

    text = str(value)
    for pattern, replacement in _SANITIZERS:
        text = pattern.sub(replacement, text)
    if max_chars is not None and len(text) > max_chars:
        return text[-max_chars:]
    return text


def _flatten_for_scan(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)


def redaction_findings(value: Any) -> list[str]:
    """Return denylist finding names present in value."""

    text = _flatten_for_scan(value)
    return [name for name, pattern in DENYLIST_PATTERNS if pattern.search(text)]


def validate_no_sensitive_evidence(value: Any) -> None:
    """Fail closed if value contains any durable-evidence denylist hit."""

    findings = redaction_findings(value)
    if findings:
        raise RedactionError(findings)


def write_validated_json(path: str | Path, payload: Any) -> None:
    """Validate and atomically write a JSON evidence artifact."""

    validate_no_sensitive_evidence(payload)
    output = json.dumps(payload, indent=2, sort_keys=True, default=str, ensure_ascii=False) + "\n"
    validate_no_sensitive_evidence(output)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(output, encoding="utf-8")
    tmp.replace(target)


def write_validated_text(path: str | Path, text: str) -> None:
    """Validate and atomically write a Markdown/text evidence artifact."""

    validate_no_sensitive_evidence(text)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)
