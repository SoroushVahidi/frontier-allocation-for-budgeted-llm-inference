#!/usr/bin/env python3
"""Generate markdown report from TALE MODE B import verification JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate TALE MODE B import report")
    p.add_argument("--verification-json", required=True)
    p.add_argument("--output-md", required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    verification_path = Path(args.verification_json)
    if verification_path.exists():
        payload = json.loads(verification_path.read_text(encoding="utf-8"))
    else:
        payload: dict[str, Any] = {
            "status": "invalid",
            "issues": ["missing_verification_json"],
            "errors": [],
            "expected": {},
            "observed": {},
        }

    status = str(payload.get("status", "invalid"))
    issues = payload.get("issues", []) if isinstance(payload.get("issues", []), list) else []
    errors = payload.get("errors", []) if isinstance(payload.get("errors", []), list) else []
    expected = payload.get("expected", {}) if isinstance(payload.get("expected", {}), dict) else {}
    observed = payload.get("observed", {}) if isinstance(payload.get("observed", {}), dict) else {}

    lines = [
        "# TALE MODE B official import report",
        "",
        f"- status: `{status}`",
        f"- requested_results_path: `{payload.get('requested_results_path', '')}`",
        f"- resolved_package_dir: `{payload.get('resolved_package_dir', '')}`",
        "",
        "## Expected comparison contract",
        f"- dataset: `{expected.get('dataset', '')}`",
        f"- split: `{expected.get('split', '')}`",
        f"- expected budgets: `{expected.get('budgets', [])}`",
        "",
        "## Observed import payload",
        f"- num_rows: `{observed.get('num_rows', 0)}`",
        f"- observed budgets: `{observed.get('observed_budgets', [])}`",
        f"- observed variant tuples: `{observed.get('observed_variant_triples', [])}`",
        "",
        "## Verification outcome",
    ]

    if status == "valid":
        lines.extend(
            [
                "- Import accepted.",
                "- Schema + metadata completeness + provenance checks passed.",
                "- TALE variant identity is explicit and not mixed (TALE vs TALE-PT separation preserved).",
                "- Imported rows are suitable for repository comparison tables.",
            ]
        )
    else:
        lines.append("- Import rejected.")

    lines.append("")
    lines.append("## Issues")
    lines.extend([f"- {issue}" for issue in issues] or ["- none"])

    lines.append("")
    lines.append("## Errors")
    lines.extend([f"- {error}" for error in errors] or ["- none"])

    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": args.output_md}, indent=2))


if __name__ == "__main__":
    main()
