"""Offline dry-run for target-staged PAL retry pilot: materialize prompts, no API."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from experiments.target_staged_pal_pilot_manifest import (
    EXPECTED_PRIMARY_CASE_IDS,
    validate_deployable_pilot_manifest,
)
from experiments.target_staged_pal_prompt import (
    VARIANT_B,
    materialize_user_prompt,
    prompt_includes_required_sections_instruction,
    variant_b_leakage_violations,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_primary_case_problem_texts() -> dict[str, str]:
    csv_path = (
        REPO_ROOT
        / "outputs/gold_absent_external_success_schema_mining_20260507"
        / "schema_mining_cases.csv"
    )
    out: dict[str, str] = {}
    with csv_path.open(encoding="utf-8", newline="") as fp:
        for row in csv.DictReader(fp):
            cid = str(row.get("case_id") or "")
            if cid in EXPECTED_PRIMARY_CASE_IDS:
                out[cid] = str(row.get("problem_text") or "").strip()
    missing = set(EXPECTED_PRIMARY_CASE_IDS) - set(out)
    if missing:
        raise ValueError(f"missing problem_text in schema_mining_cases.csv for: {sorted(missing)}")
    return out


def _load_problem_text_by_case_id() -> dict[str, str]:
    return load_primary_case_problem_texts()


def run_dry_run(*, manifest_path: Path, out_dir: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path.resolve())

    if manifest.get("api_execution_enabled") is not False:
        raise ValueError("dry-run requires api_execution_enabled: false")
    if manifest.get("primary_case_count") != 11:
        raise ValueError("dry-run requires primary_case_count == 11")
    if manifest.get("hard_logical_call_cap") != 120:
        raise ValueError("dry-run requires hard_logical_call_cap == 120")

    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 11:
        raise ValueError("manifest must list exactly 11 cases")

    validate_deployable_pilot_manifest(manifest)

    questions = _load_problem_text_by_case_id()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    all_headers_ok = True
    all_metadata_ok = True
    all_leak_ok = True

    for case in cases:
        cid = str(case["source_case_id"])
        tv = str(case["template_variant"])
        schemas = str(case.get("required_schemas") or "")
        fails = str(case.get("pal_failure_modes") or "")
        q = questions[cid]
        prompt = materialize_user_prompt(tv, question=q)

        headers_ok = prompt_includes_required_sections_instruction(prompt)
        all_headers_ok = all_headers_ok and headers_ok

        meta_ok = (
            cid not in prompt
            and schemas not in prompt
            and fails not in prompt
            and "required_schemas" not in prompt
            and "pal_failure_modes" not in prompt
            and "source_case_id" not in prompt
        )
        all_metadata_ok = all_metadata_ok and meta_ok

        leak: list[str] = []
        if tv == VARIANT_B:
            leak = variant_b_leakage_violations(prompt)
            all_leak_ok = all_leak_ok and (len(leak) == 0)

        rows.append(
            {
                "source_case_id": cid,
                "template_variant": tv,
                "prompt_chars": len(prompt),
                "section_instruction_headers_ok": headers_ok,
                "metadata_absent_from_prompt_ok": meta_ok,
                "variant_b_leakage_patterns": leak,
                "materialized_user_prompt": prompt,
            }
        )

    if not all_headers_ok:
        raise ValueError("one or more prompts missing required section instruction headers")
    if not all_metadata_ok:
        raise ValueError("metadata leakage detected in one or more prompts")
    if not all_leak_ok:
        raise ValueError("variant B leakage patterns detected")

    summary = {
        "manifest_path": str(manifest_path.resolve()),
        "out_dir": str(out_dir.resolve()),
        "api_execution_enabled": manifest.get("api_execution_enabled"),
        "primary_case_count": manifest.get("primary_case_count"),
        "per_case_budget": manifest.get("per_case_budget"),
        "soft_logical_call_cap": manifest.get("soft_logical_call_cap"),
        "hard_logical_call_cap": manifest.get("hard_logical_call_cap"),
        "prompts_materialized": len(rows),
        "all_section_instruction_headers_ok": all_headers_ok,
        "metadata_not_in_prompts_ok": all_metadata_ok,
        "variant_b_leakage_checks_passed": all_leak_ok,
        "no_external_api_called": True,
        "dry_run_module": "experiments.target_staged_pal_pilot_dry_run",
    }

    jsonl_path = out_dir / "materialized_prompts.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    (out_dir / "dry_run_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    preview_lines = [
        "# Target-staged PAL dry-run — prompt preview",
        "",
        f"_Manifest:_ `{summary['manifest_path']}`",
        "",
        "## Prompt 1",
        "",
        "```text",
        rows[0]["materialized_user_prompt"][:12000],
        "",
        "```",
        "",
    ]
    if len(rows) > 1:
        preview_lines.extend(
            [
                "## Prompt 2 (excerpt)",
                "",
                "```text",
                rows[1]["materialized_user_prompt"][:3500],
                "\n... [truncated]",
                "```",
                "",
            ]
        )
    (out_dir / "prompt_preview.md").write_text("\n".join(preview_lines), encoding="utf-8")

    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "manifests" / "target_staged_pal_retry_primary_11_20260507.json",
    )
    ap.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for dry-run artifacts",
    )
    args = ap.parse_args()
    s = run_dry_run(manifest_path=args.manifest, out_dir=args.out)
    print(f"Wrote dry-run artifacts to {s['out_dir']}")


if __name__ == "__main__":
    main()
