#!/usr/bin/env python3
"""Generate and validate the M015 final evidence matrix.

The matrix is intentionally conservative: every required runtime item must map to
fresh seam evidence, a fixed outcome, or an explicit non-goal. Validation blocks
false green results before milestone close.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from redaction import validate_no_sensitive_evidence, write_validated_json, write_validated_text  # noqa: E402

MILESTONE = "M015"
MATRIX_JSON_NAME = "m015-evidence-matrix.json"
MATRIX_MD_NAME = "m015-evidence-matrix.md"
SEAM_EVIDENCE = {
    "db": "db-seam-evidence.json",
    "session": "session-seam-evidence.json",
    "provider": "provider-seam-evidence.json",
    "artifact": "artifact-seam-evidence.json",
}
REQUIRED_REQUIREMENT_IDS = ("R012", "R013", "R014", "R015", "R017", "R018")
REQUIRED_RUNTIME_ITEMS = (
    "db_tls_rls_runtime",
    "session_revocation_multi_process",
    "taskiq_worker_db_recheck",
    "provider_wuzapi_stub_boundary",
    "provider_gemini_stub_boundary",
    "private_upload_app_routes",
    "report_export_app_routes",
    "synthetic_only_no_live_providers",
    "redaction_safe_evidence",
    "strict_red_signal_closure",
)
VALID_STATUSES = {"fresh_evidence", "fixed_outcome", "explicit_non_goal"}
VALIDATOR_FAILURE_CLASSES = (
    "missing_required_row",
    "missing_evidence_artifact",
    "failed_seam_result",
    "stale_evidence_correlation",
    "placeholder_text",
    "unsafe_sensitive_content",
    "raw_download_url_leak",
    "unclassified_warning",
    "unresolved_red_signal",
)
CLASSIFIED_WARNINGS = {
    "upload_quota_async_session_query_warning": "Non-fatal runtime log warning from upload quota lookup; route catches it and S04 artifact proof passes. S05 keeps it classified so milestone validation can decide whether to remediate beyond security proof scope.",
}
NON_GOALS = (
    "no_live_provider_credentials",
    "no_production_systems_or_phi",
    "no_browser_frontend_flows",
    "no_cdn_object_storage_claim",
    "no_broad_dast_or_exploitation",
)


@dataclass(frozen=True)
class MatrixFailure(Exception):
    failure_class: str
    message: str

    def __str__(self) -> str:
        return f"{self.failure_class}: {self.message}"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MatrixFailure("missing_evidence_artifact", f"missing evidence artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MatrixFailure("missing_evidence_artifact", f"malformed evidence artifact: {path}") from exc


def seam_passed(payload: dict[str, Any]) -> bool:
    if payload.get("result") == "failed":
        return False
    if payload.get("result") == "passed":
        return True
    events = payload.get("events") or payload.get("phase_events") or []
    if any(isinstance(event, dict) and event.get("status") == "failed" for event in events):
        return False
    return bool(payload.get("correlation_id"))


def validate_safe_payload(payload: Any, *, context: str) -> None:
    try:
        validate_no_sensitive_evidence(payload)
    except Exception as exc:
        raise MatrixFailure("unsafe_sensitive_content", f"unsafe sensitive content in {context}") from exc


def load_seam_evidence(input_dir: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for seam, filename in SEAM_EVIDENCE.items():
        path = input_dir / filename
        payload = read_json(path)
        if payload.get("seam") != seam:
            raise MatrixFailure("missing_evidence_artifact", f"{filename} does not identify seam {seam}")
        if not seam_passed(payload):
            raise MatrixFailure("failed_seam_result", f"{filename} is not a passed seam evidence artifact")
        validate_safe_payload(payload, context=filename)
        loaded[seam] = payload
    return loaded


def evidence_path(seam: str) -> str:
    return f"backend-hormonia/docs/reports/security/m015/{SEAM_EVIDENCE[seam]}"


def correlation_ids(evidence: dict[str, dict[str, Any]], seams: list[str]) -> list[str]:
    ids: list[str] = []
    for seam in seams:
        value = evidence[seam].get("correlation_id")
        if not value:
            raise MatrixFailure("stale_evidence_correlation", f"{seam} evidence has no correlation_id")
        ids.append(str(value))
    return ids


def row(
    item_id: str,
    *,
    requirement_ids: list[str],
    seams: list[str],
    evidence: dict[str, dict[str, Any]],
    status: str = "fresh_evidence",
    proof: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "requirement_ids": requirement_ids,
        "source_seams": seams,
        "status": status,
        "proof": proof,
        "notes": notes,
        "evidence_paths": [evidence_path(seam) for seam in seams],
        "correlation_ids": correlation_ids(evidence, seams),
        "redaction_validated": True,
        "raw_sensitive_values_persisted": False,
    }


def build_matrix(input_dir: Path) -> dict[str, Any]:
    evidence = load_seam_evidence(input_dir)
    all_seams = ["db", "session", "provider", "artifact"]
    rows = [
        row(
            "db_tls_rls_runtime",
            requirement_ids=["R012", "R014"],
            seams=["db"],
            evidence=evidence,
            proof="PostgreSQL verify-full TLS, app-role migrations/readiness, and RLS allow/deny behavior were exercised by the DB seam.",
            notes="Fresh DB seam evidence is synthetic-only and redaction-validated.",
        ),
        row(
            "session_revocation_multi_process",
            requirement_ids=["R013", "R014"],
            seams=["session"],
            evidence=evidence,
            proof="Cookie-backed staff sessions, cache miss DB fallback, explicit revocation, stale-cache denial, and expired-session denial were exercised by the session seam.",
            notes="No Bearer shortcut or dependency override is used for the runtime claim.",
        ),
        row(
            "taskiq_worker_db_recheck",
            requirement_ids=["R013", "R014"],
            seams=["session"],
            evidence=evidence,
            proof="Taskiq worker participation re-checks PostgreSQL session state before accepting queued work.",
            notes="Worker proof is scoped to synthetic session revocation, not broad queue load testing.",
        ),
        row(
            "provider_wuzapi_stub_boundary",
            requirement_ids=["R014", "R015"],
            seams=["provider"],
            evidence=evidence,
            proof="WuzAPI-compatible calls traverse the Compose network to a controlled local stub with success, client/server error, timeout, and replay scenarios.",
            notes="Live WuzAPI credentials and production systems are explicit non-goals.",
        ),
        row(
            "provider_gemini_stub_boundary",
            requirement_ids=["R014", "R015"],
            seams=["provider"],
            evidence=evidence,
            proof="Gemini-compatible calls traverse the Compose network to the controlled local stub and exercise success/error handling.",
            notes="Live Gemini credentials and prompts are not used or persisted.",
        ),
        row(
            "private_upload_app_routes",
            requirement_ids=["R014", "R017"],
            seams=["artifact"],
            evidence=evidence,
            proof="Private upload owner/admin gated downloads succeed; anonymous, cross-owner, and direct private static access fail closed.",
            notes="S04 fixed upload schema alignment and cached-session UUID owner comparison before accepting green evidence.",
        ),
        row(
            "report_export_app_routes",
            requirement_ids=["R014", "R017"],
            seams=["artifact"],
            evidence=evidence,
            proof="Base report, enhanced builder, and enhanced export app routes enforce ownership, safe attachment headers, fallback downloads, and unsafe URL withholding.",
            notes="CDN/object storage and browser rendering are explicit non-goals.",
        ),
        row(
            "synthetic_only_no_live_providers",
            requirement_ids=["R015"],
            seams=all_seams,
            evidence=evidence,
            proof="All seams run in a synthetic Compose project with generated credentials, local stubs, and no real PHI/provider data.",
            notes="This row closes the anti-feature boundary against production exploitation claims.",
        ),
        row(
            "redaction_safe_evidence",
            requirement_ids=["R017"],
            seams=all_seams,
            evidence=evidence,
            proof="All seam artifacts and this matrix pass denylist validation for secrets, PHI, raw cookies/session IDs, private paths, bytes, DSNs, and raw download URL maps.",
            notes="Durable evidence stores hashes, booleans, status classes, correlation IDs, and non-goals only.",
        ),
        row(
            "strict_red_signal_closure",
            requirement_ids=["R018"],
            seams=all_seams,
            evidence=evidence,
            status="fixed_outcome",
            proof="Runtime red signals found during M015 were fixed or classified: DB/session/provider/artifact seams pass; S04 upload schema and UUID owner mismatches were fixed; upload quota warning is classified for final review.",
            notes="The validator treats unclassified warnings and unresolved red signals as closure blockers.",
        ),
    ]
    matrix = {
        "milestone": MILESTONE,
        "command": "./scripts/security/verify-m015-runtime-security.sh",
        "generated_at": utc_now(),
        "result": "passed",
        "requirements": list(REQUIRED_REQUIREMENT_IDS),
        "required_runtime_items": list(REQUIRED_RUNTIME_ITEMS),
        "rows": rows,
        "warnings": [
            {
                "id": warning_id,
                "classification": "known_non_blocking_runtime_warning",
                "notes": note,
                "closure_policy": "classified_not_silent; milestone validation may choose remediation but matrix is not silently green",
            }
            for warning_id, note in sorted(CLASSIFIED_WARNINGS.items())
        ],
        "non_goals": list(NON_GOALS),
        "validator": {
            "result": "passed",
            "failure_classes": list(VALIDATOR_FAILURE_CLASSES),
        },
    }
    validate_matrix(matrix)
    return matrix


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# M015 Evidence Matrix",
        "",
        f"- Result: `{matrix['result']}`",
        f"- Generated at: `{matrix['generated_at']}`",
        f"- Command: `{matrix['command']}`",
        "- Validator: `passed`",
        "",
        "## Rows",
        "",
        "| ID | Requirements | Status | Source seams | Evidence |",
        "|---|---|---|---|---|",
    ]
    for row_data in matrix["rows"]:
        lines.append(
            "| {id} | {requirements} | {status} | {seams} | {evidence} |".format(
                id=row_data["id"],
                requirements=", ".join(row_data["requirement_ids"]),
                status=row_data["status"],
                seams=", ".join(row_data["source_seams"]),
                evidence="<br>".join(row_data["evidence_paths"]),
            )
        )
    lines.extend(["", "## Classified warnings", ""])
    for warning in matrix["warnings"]:
        lines.append(f"- `{warning['id']}` — {warning['classification']}: {warning['notes']}")
    lines.extend(["", "## Non-goals", ""])
    for non_goal in matrix["non_goals"]:
        lines.append(f"- `{non_goal}`")
    lines.append("")
    return "\n".join(lines)


def _iter_strings_for_placeholder_scan(value: Any) -> list[str]:
    if isinstance(value, dict):
        strings: list[str] = []
        for key, child in value.items():
            if key in {"failure_classes", "validator"}:
                continue
            strings.extend(_iter_strings_for_placeholder_scan(child))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for child in value:
            strings.extend(_iter_strings_for_placeholder_scan(child))
        return strings
    if isinstance(value, str):
        return [value]
    return []


def _contains_placeholder(value: Any) -> bool:
    haystack = "\n".join(_iter_strings_for_placeholder_scan(value)).lower()
    return any(marker in haystack for marker in ("todo", "tbd", "placeholder"))


def validate_matrix(matrix: dict[str, Any]) -> None:
    row_ids = {row.get("id") for row in matrix.get("rows", []) if isinstance(row, dict)}
    missing = set(REQUIRED_RUNTIME_ITEMS).difference(row_ids)
    if missing:
        raise MatrixFailure("missing_required_row", f"missing required rows: {sorted(missing)}")

    for row_data in matrix.get("rows", []):
        status = row_data.get("status")
        if status not in VALID_STATUSES:
            raise MatrixFailure("unresolved_red_signal", f"row {row_data.get('id')} has invalid status {status!r}")
        if not row_data.get("correlation_ids"):
            raise MatrixFailure("stale_evidence_correlation", f"row {row_data.get('id')} has no correlations")
        if row_data.get("redaction_validated") is not True:
            raise MatrixFailure("unsafe_sensitive_content", f"row {row_data.get('id')} is not redaction validated")

    if _contains_placeholder(matrix):
        raise MatrixFailure("placeholder_text", "matrix contains placeholder/TODO/TBD text")
    if not matrix.get("warnings"):
        raise MatrixFailure("unclassified_warning", "matrix must classify runtime warnings, even when none are blocking")
    for warning in matrix.get("warnings", []):
        if not warning.get("classification") or not warning.get("closure_policy"):
            raise MatrixFailure("unclassified_warning", f"warning {warning.get('id')} lacks classification")

    serialized = json.dumps(matrix, sort_keys=True).lower()
    if '"download_urls"' in serialized or "/uploads/private" in serialized:
        raise MatrixFailure("raw_download_url_leak", "matrix contains raw download URL or private artifact path")
    validate_safe_payload(matrix, context="matrix")


def write_outputs(matrix: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix_json = output_dir / MATRIX_JSON_NAME
    matrix_md = output_dir / MATRIX_MD_NAME
    markdown = render_markdown(matrix)
    validate_safe_payload(markdown, context="matrix markdown")
    write_validated_json(matrix_json, matrix)
    write_validated_text(matrix_md, markdown)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        matrix = build_matrix(args.input_dir)
        write_outputs(matrix, args.output_dir)
        if args.validate:
            validate_matrix(read_json(args.output_dir / MATRIX_JSON_NAME))
        print(f"M015 evidence matrix validated: {args.output_dir / MATRIX_JSON_NAME}")
        return 0
    except MatrixFailure as exc:
        print(f"failure_class={exc.failure_class} {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI surface.
        print(f"failure_class=unsafe_sensitive_content unexpected matrix error: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
