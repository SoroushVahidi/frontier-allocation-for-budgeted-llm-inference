#!/usr/bin/env python3
"""Prepare a no-API preflight for a future 15-case Direct L1 strong seed live diagnostic."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.frontier_matrix_core import build_frontier_strategies
from scripts import run_cohere_real_model_cost_normalized_validation as runner

DEFAULT_EXACT_CASES_JSONL = (
    REPO_ROOT / "docs/project_handoff_20260510/exact_case_replay/direct_l1_strong_seed_15case_exact_cases_20260511.jsonl"
)
DEFAULT_OUTPUT_PREFIX = "direct_l1_strong_seed_15case_preflight_"
DEFAULT_BUDGET = 4
DEFAULT_TREATMENT_METHOD = (
    "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_l1_strong_seed_v1"
)
DEFAULT_BASELINE_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_direct_hybrid"
DEFAULT_DIV_ANCHOR_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_diverse_anchor"
DEFAULT_VALIDATE_OUTPUT_ROOT = Path("/tmp")
DEFAULT_VALIDATE_TIMESTAMP = "20260511"
DEFAULT_FUTURE_LIVE_OUTPUT_ROOT = Path("outputs")

# Canonical 15-case slice currently tracked in-repo.
EXPECTED_CASE_IDS = (
    "openai_gsm8k_168",
    "openai_gsm8k_180",
    "openai_gsm8k_190",
    "openai_gsm8k_197",
    "openai_gsm8k_213",
    "openai_gsm8k_264",
    "openai_gsm8k_347",
    "openai_gsm8k_367",
    "openai_gsm8k_376",
    "openai_gsm8k_391",
    "openai_gsm8k_297",
    "openai_gsm8k_204",
    "openai_gsm8k_228",
    "openai_gsm8k_233",
    "openai_gsm8k_354",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_method_list(include_diverse_anchor: bool) -> list[str]:
    methods = [DEFAULT_BASELINE_METHOD, DEFAULT_TREATMENT_METHOD]
    if include_diverse_anchor:
        methods.append(DEFAULT_DIV_ANCHOR_METHOD)
    return methods


def _build_validate_only_command(
    *,
    exact_cases_jsonl: Path,
    methods: list[str],
    budget: int,
    output_root: Path,
    timestamp: str,
) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
        "--validate-exact-cases-only",
        "--provider",
        "cohere",
        "--datasets",
        "openai/gsm8k",
        "--budgets",
        str(int(budget)),
        "--methods",
        ",".join(methods),
        "--exact-cases-jsonl",
        str(exact_cases_jsonl),
        "--expected-exact-case-count",
        "15",
        "--output-root",
        str(output_root),
        "--timestamp",
        timestamp,
    ]


def _build_future_live_command(
    *,
    exact_cases_jsonl: Path,
    methods: list[str],
    budget: int,
    output_root: Path,
    timestamp: str,
) -> list[str]:
    return [
        sys.executable,
        str(REPO_ROOT / "scripts/run_cohere_real_model_cost_normalized_validation.py"),
        "--provider",
        "cohere",
        "--datasets",
        "openai/gsm8k",
        "--budgets",
        str(int(budget)),
        "--methods",
        ",".join(methods),
        "--exact-cases-jsonl",
        str(exact_cases_jsonl),
        "--output-root",
        str(output_root),
        "--timestamp",
        timestamp,
    ]


def _call_cap_estimate(*, case_count: int, method_count: int, budget: int) -> int:
    case_count_i = max(1, int(case_count))
    method_count_i = max(1, int(method_count))
    budget_i = max(1, int(budget))
    safety_margin = max(10, case_count_i)
    return case_count_i * method_count_i * budget_i + safety_margin


def _load_exact_cases(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing exact-case JSONL: {path}")
    rows = runner.load_exact_case_rows(str(path))
    if len(rows) != 15:
        raise ValueError(f"Expected 15 exact cases, found {len(rows)} in {path}")
    if len({str(r.get('example_id')) for r in rows}) != len(rows):
        raise ValueError(f"Expected unique exact-case IDs in {path}")
    for row in rows:
        if not _stringify(row.get("question")):
            raise ValueError(f"Missing question for {row.get('example_id')}")
        if not _stringify(row.get("gold_answer_canonical")):
            raise ValueError(f"Missing canonical gold for {row.get('example_id')}")
    return rows


def _validate_expected_ids(
    rows: list[dict[str, Any]],
    *,
    expected_case_ids: tuple[str, ...],
    allow_different_ids: bool,
) -> dict[str, Any]:
    actual_ids = [str(r.get("example_id")) for r in rows]
    expected_ids = list(expected_case_ids)
    actual_set = set(actual_ids)
    expected_set = set(expected_ids)
    missing = [case_id for case_id in expected_ids if case_id not in actual_set]
    extra = [case_id for case_id in actual_ids if case_id not in expected_set]
    matches = actual_ids == expected_ids
    if not allow_different_ids and not matches:
        raise ValueError(
            "Exact-case IDs do not match expected list. "
            f"missing={missing} extra={extra} allow_different_ids={allow_different_ids}"
        )
    return {
        "expected_case_ids": expected_ids,
        "actual_case_ids": actual_ids,
        "exact_case_count": len(actual_ids),
        "unique_case_id_count": len(actual_set),
        "case_id_order_matches_expected": matches,
        "missing_case_ids": missing,
        "extra_case_ids": extra,
        "allow_different_ids": bool(allow_different_ids),
    }


def _resolve_method_rows(methods: list[str], *, budget: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = __import__("random").Random(11)
    runner_specs = build_frontier_strategies(
        lambda: None,
        budget,
        [1],
        rng,
        use_openai_api=False,
        include_broad_diversity_aggregation_methods=True,
        include_external_l1_baseline=True,
        include_external_s1_baseline=True,
        include_external_tale_baseline=True,
    )
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for method in methods:
        runtime = runner.METHODS.get(method, {}).get("runtime", "")
        registered = method in runner.METHODS
        runtime_present = bool(runtime and runtime in runner_specs)
        row = {
            "method_id": method,
            "runtime_id": runtime,
            "registered_in_METHODS": registered,
            "runtime_present_in_runner_specs": runtime_present,
        }
        rows.append(row)
        if not registered or not runtime_present:
            mismatches.append(row)
    if mismatches:
        raise ValueError(f"Unresolved method registry entries: {mismatches}")
    return rows, {"methods": methods, "budget": int(budget), "method_count": len(methods)}


def _command_to_shell_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _run_validate_only(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "validate-only command failed\n"
            f"cmd: {_command_to_shell_text(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    report_root = Path(command[command.index("--output-root") + 1]) / f"cohere_real_model_cost_normalized_validation_{command[command.index('--timestamp') + 1]}"
    report_path = report_root / "exact_case_validation_report.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"Missing validate-only report: {report_path}")
    report = _read_json(report_path)
    report["_report_path"] = str(report_path)
    report["_stdout"] = result.stdout.strip()
    return report


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Direct L1 Strong Seed 15-Case Live Preflight",
        "",
        "## Goal",
        "",
        "Prepare a reviewer-safe no-API preflight for a future 15-case live diagnostic of the opt-in Direct L1 strong seed method.",
        "",
        "## Exact Cases",
        "",
        f"- count: `{summary['exact_case_count']}`",
        f"- unique_ids: `{summary['unique_case_id_count']}`",
        f"- ids: `{', '.join(summary['actual_case_ids'])}`",
        "",
        "## Methods",
        "",
    ]
    for row in summary["method_resolution_rows"]:
        lines.append(
            f"- `{row['method_id']}` -> runtime `{row['runtime_id']}` | registered={row['registered_in_METHODS']} | runnable_without_api={row['runtime_present_in_runner_specs']}"
        )
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "### Validate-only command run in this preflight",
            "",
            "```bash",
            summary["validate_only_command"],
            "```",
            "",
            "### Future live command not run here",
            "",
            "```bash",
            summary["future_live_command"],
            "```",
            "",
            "## Call Cap",
            "",
            f"- estimated_future_call_cap: `{summary['estimated_future_call_cap']}`",
            f"- formula: `{summary['call_cap_formula']}`",
            "",
            "## Outputs",
            "",
            f"- future_live_output_dir: `{summary['future_live_output_dir']}`",
            f"- validate_only_report_path: `{summary.get('validate_only_report_path', '')}`",
            "",
            "## Metrics To Inspect",
            "",
        ]
    )
    for metric in summary["metrics_to_inspect"]:
        lines.append(f"- {metric}")
    lines.extend(
        [
            "",
            "## Promising Result",
            "",
        ]
    )
    for criterion in summary["promising_result_criteria"]:
        lines.append(f"- {criterion}")
    lines.extend(
        [
            "",
            "## Stop Criteria",
            "",
        ]
    )
    for criterion in summary["stop_regression_criteria"]:
        lines.append(f"- {criterion}")
    lines.extend(
        [
            "",
            "## Claim Boundaries",
            "",
        ]
    )
    for boundary in summary["claim_boundaries"]:
        lines.append(f"- {boundary}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--exact-cases-jsonl",
        default=str(DEFAULT_EXACT_CASES_JSONL),
        help="Tracked exact-case JSONL for the 15-case diagnostic slice.",
    )
    p.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help="Budget for the future live diagnostic comparison.",
    )
    p.add_argument(
        "--treatment-method",
        default=DEFAULT_TREATMENT_METHOD,
        help="Opt-in Direct L1 strong seed runtime method ID.",
    )
    p.add_argument(
        "--baseline-method",
        default=DEFAULT_BASELINE_METHOD,
        help="Comparator runtime method ID.",
    )
    p.add_argument(
        "--include-diverse-anchor",
        action="store_true",
        help="Also include the diverse-anchor comparator in the method list.",
    )
    p.add_argument(
        "--allow-different-ids",
        action="store_true",
        help="Allow the exact-case JSONL IDs to differ from the tracked canonical list.",
    )
    p.add_argument(
        "--output-dir",
        default="",
        help="Optional output directory. Defaults to outputs/direct_l1_strong_seed_15case_preflight_<timestamp>/.",
    )
    p.add_argument(
        "--validate-output-root",
        default=str(DEFAULT_VALIDATE_OUTPUT_ROOT),
        help="Root directory for the no-API validate-only runner command.",
    )
    p.add_argument(
        "--timestamp",
        default=_utc_stamp(),
        help="UTC timestamp suffix for the default output directory and validate-only command.",
    )
    p.add_argument(
        "--dry-run",
        "--validate-only",
        action="store_true",
        dest="dry_run",
        help="Validate and print the plan without writing outputs.",
    )
    return p.parse_args(argv)


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)

    exact_cases_jsonl = Path(args.exact_cases_jsonl).expanduser()
    validate_output_root = Path(args.validate_output_root).expanduser()
    methods = _build_method_list(include_diverse_anchor=bool(args.include_diverse_anchor))

    rows = _load_exact_cases(exact_cases_jsonl)
    case_validation = _validate_expected_ids(
        rows,
        expected_case_ids=EXPECTED_CASE_IDS,
        allow_different_ids=bool(args.allow_different_ids),
    )
    method_rows, method_summary = _resolve_method_rows(methods, budget=int(args.budget))

    validate_only_command = _build_validate_only_command(
        exact_cases_jsonl=exact_cases_jsonl,
        methods=methods,
        budget=int(args.budget),
        output_root=validate_output_root,
        timestamp=str(args.timestamp),
    )
    future_live_output_dir = DEFAULT_FUTURE_LIVE_OUTPUT_ROOT / f"cohere_real_model_cost_normalized_validation_{args.timestamp}"
    future_live_command = _build_future_live_command(
        exact_cases_jsonl=exact_cases_jsonl,
        methods=methods,
        budget=int(args.budget),
        output_root=DEFAULT_FUTURE_LIVE_OUTPUT_ROOT,
        timestamp=str(args.timestamp),
    )

    validate_report: dict[str, Any] = {}
    if not bool(args.dry_run):
        validate_report = _run_validate_only(validate_only_command)

    call_cap = _call_cap_estimate(
        case_count=case_validation["exact_case_count"],
        method_count=len(methods),
        budget=int(args.budget),
    )

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        **case_validation,
        "method_resolution_rows": method_rows,
        "method_ids": methods,
        "baseline_method": args.baseline_method,
        "treatment_method": args.treatment_method,
        "include_diverse_anchor": bool(args.include_diverse_anchor),
        "validate_only_command": _command_to_shell_text(validate_only_command),
        "future_live_command": _command_to_shell_text(future_live_command),
        "future_live_command_path": "future_live_command.sh",
        "future_live_output_dir": str(future_live_output_dir),
        "estimated_future_call_cap": call_cap,
        "call_cap_formula": "estimated = case_count * method_count * budget + max(10, case_count)",
        "metrics_to_inspect": [
            "Exact accuracy by method on the 15-case slice.",
            "Per-case improved / worsened / unchanged labels versus the baseline.",
            "Gold-in-pool if the live runner exposes it in metadata.",
            "Candidate answer group count / entropy if available.",
            "Direct L1 strong seed metadata if available.",
            "Token and call counts by method.",
        ],
        "promising_result_criteria": [
            "Treatment solves more cases than the baseline on the 15-case slice.",
            "No more than a small number of regressions relative to baseline.",
            "Gold-in-pool improves or stays stable on the treatment slice.",
            "The direct-L1 strong seed metadata is consistent with a direct answer plus self-check pattern.",
        ],
        "stop_regression_criteria": [
            "Treatment ties or worsens the baseline while adding more regressions than it fixes.",
            "Gold-in-pool does not improve on the slice.",
            "The treatment collapses to the same wrong supported consensus as the baseline.",
        ],
        "claim_boundaries": [
            "No external-baseline claim.",
            "No broad method promotion.",
            "15-case diagnostic only.",
            "Paid run requires explicit later approval.",
            "No runtime default change.",
        ],
        "validate_only_report_path": validate_report.get("_report_path", ""),
        "validate_only_result": validate_report,
    }

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else REPO_ROOT / "outputs" / f"{DEFAULT_OUTPUT_PREFIX}{args.timestamp}"
    if not bool(args.dry_run):
        output_dir.mkdir(parents=True, exist_ok=True)
        _json_dump(output_dir / "summary.json", summary)
        (output_dir / "direct_l1_strong_seed_15case_live_preflight_report.md").write_text(
            _render_report(summary),
            encoding="utf-8",
        )
        (output_dir / "future_live_command.sh").write_text(
            "#!/usr/bin/env bash\n"
            "# NOT RUN IN THIS PR.\n"
            "# Future live diagnostic command for the opt-in Direct L1 strong seed slice.\n"
            f"{summary['future_live_command']}\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> int:
    try:
        run()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
