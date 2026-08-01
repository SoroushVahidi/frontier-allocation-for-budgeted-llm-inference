"""Post-hoc evaluation and reporting for a completed Cohere full validation run.

Never makes API calls. Writes manuscript-ready summaries under the run
directory. W&B supplemental logging is best-effort and never raises.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.build_failure_feature_table import build_feature_rows_from_specs
from experiments.evaluate_api_validation_repair_candidate import build_candidate_specs, evaluate_all
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import load_jsonl, write_csv, write_json, write_text
from experiments.replay_azure_inspired_rules_on_cohere import decision_ext3_when_swfb
from experiments.stress_test_exploratory_rules import evaluate_rule_full, paired_bootstrap_ci
from experiments.wandb_logging import supplemental_log_safe

REPO_ROOT = Path(__file__).resolve().parents[1]
REPAIR_NAME = "repair_primary_plus_unanimity_fallback"
FTA_NAME = "baseline_canonical_fta"
EXT3_NAME = "baseline_external3_majority"
POOLED4_NAME = "baseline_pooled4_majority_reconstructed"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True, help="Full validation output directory.")
    p.add_argument("--source-id", default="cohere_disjoint_seed53_full")
    p.add_argument("--bootstrap-resamples", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=1234)
    p.add_argument("--skip-wandb", action="store_true")
    return p.parse_args()


def _classify_repair_candidate(
    *,
    repair_ev: dict[str, Any],
    fta_ev: dict[str, Any],
    repair_boot: dict[str, Any] | None,
    ext3_ev: dict[str, Any],
    pooled4_ev: dict[str, Any],
    audit_clean: bool,
) -> tuple[str, str]:
    net = repair_ev["net_wins"]
    losses = repair_ev["losses_vs_canonical_fta"]
    regress_rate = repair_ev.get("regression_rate_among_fta_correct") or 0.0
    ci_excludes_zero = repair_boot is not None and repair_boot.get("includes_zero") is False
    worse_than_ext3 = repair_ev["accuracy"] < ext3_ev["accuracy"] and net <= 0
    worse_than_pooled = repair_ev["accuracy"] < pooled4_ev["accuracy"] and net <= 0

    if not audit_clean:
        return "inconclusive", "decision-legality audit not clean"
    if net > 0 and losses <= 2 and regress_rate <= 0.005 and ci_excludes_zero:
        if worse_than_ext3 and worse_than_pooled:
            return "promising but needs another validation", "positive vs FTA but weaker than External-3/Pooled-4"
        return "validated candidate for promotion", "positive net wins, low regressions, CI excludes zero"
    if net > 0 and regress_rate <= 0.01:
        return "promising but needs another validation", "positive net but CI includes zero or borderline regressions"
    if net <= 0 and losses > 5:
        return "rejected due to regression/fragility", f"net={net}, losses={losses}"
    return "inconclusive", f"net_wins={net}, losses={losses}, regress_rate={regress_rate}"


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    run_out = run_dir / "run_out"
    records_path = run_out / "per_example_records.jsonl"
    if not records_path.exists():
        raise FileNotFoundError(f"missing {records_path}")

    eval_dir = run_dir / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = run_dir / "raw_records"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest_raw = raw_dir / "per_example_records.jsonl"
    if not dest_raw.exists():
        shutil.copy2(records_path, dest_raw)

    eval_results = eval_dir / "validation_results.csv"
    if not eval_results.exists():
        subprocess.run(
            [
                sys.executable,
                "-m",
                "experiments.evaluate_api_validation_repair_candidate",
                "--input",
                str(records_path),
                "--source-id",
                args.source_id,
                "--output-dir",
                str(eval_dir),
                "--bootstrap-resamples",
                str(args.bootstrap_resamples),
                "--bootstrap-seed",
                str(args.bootstrap_seed),
            ],
            cwd=REPO_ROOT,
            check=True,
        )

    specs_in = [{"source_id": args.source_id, "path": str(records_path), "rationale": "full validation"}]
    feature_rows, build_summary = build_feature_rows_from_specs(specs_in)
    candidate_specs = build_candidate_specs()
    result = evaluate_all(
        feature_rows,
        candidate_specs,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    evaluations = result["evaluations"]
    repair_ev = evaluations[REPAIR_NAME]
    fta_ev = evaluations[FTA_NAME]
    ext3_ev = evaluations[EXT3_NAME]
    pooled4_ev = evaluations[POOLED4_NAME]

    swfb_ev = evaluate_rule_full(
        feature_rows,
        RuleSpec("azure_ext3_when_swfb", "azure_inspired_diagnostic", "", decision_ext3_when_swfb),
    )

    boot_by_name = {r["comparison_name"]: r for r in result["bootstrap_rows"]}
    repair_boot = boot_by_name.get(f"{REPAIR_NAME}_vs_canonical_fta")
    extra_boot = []
    for baseline_name, label in ((EXT3_NAME, "external3"), (POOLED4_NAME, "pooled4")):
        base_ev = evaluations[baseline_name]
        extra_boot.append(
            {
                "comparison_name": f"{REPAIR_NAME}_vs_{label}",
                **paired_bootstrap_ci(
                    repair_ev["per_row"],
                    base_ev["per_row"],
                    n_resamples=args.bootstrap_resamples,
                    seed=args.bootstrap_seed,
                    stratify_by_source=True,
                ),
            }
        )

    audit_rows = result["audit_rows"]
    audit_clean = all(r.get("is_runtime_legal") for r in audit_rows)
    classification, classification_reason = _classify_repair_candidate(
        repair_ev=repair_ev,
        fta_ev=fta_ev,
        repair_boot=repair_boot,
        ext3_ev=ext3_ev,
        pooled4_ev=pooled4_ev,
        audit_clean=audit_clean,
    )

    raw_rows = load_jsonl(records_path)
    api_failures = sum(1 for r in raw_rows if r.get("status") == "failed")
    parse_failures = sum(int(r.get("parse_extraction_failure", 0) or 0) for r in raw_rows)

    run_meta_path = run_out / "run_metadata.json"
    run_meta = json.loads(run_meta_path.read_text(encoding="utf-8")) if run_meta_path.exists() else {}
    usage = (run_meta.get("live_delegate_run") or {}).get("usage") or {}

    comparison_rows = []
    for name, ev in evaluations.items():
        comparison_rows.append(
            {
                "candidate": name,
                "family": ev["family"],
                "accuracy": ev["accuracy"],
                "correct_count": ev["correct_count"],
                "row_count": ev["row_count"],
                "wins_vs_canonical_fta": ev["wins_vs_canonical_fta"],
                "losses_vs_canonical_fta": ev["losses_vs_canonical_fta"],
                "ties_vs_canonical_fta": ev["ties_vs_canonical_fta"],
                "net_wins": ev["net_wins"],
                "regression_rate_among_fta_correct": ev.get("regression_rate_among_fta_correct"),
                "overrides_triggered": ev.get("overrides_triggered"),
                "overrides_changed_answer": ev.get("overrides_changed_answer"),
            }
        )
    comparison_rows.append(
        {
            "candidate": "azure_ext3_when_swfb",
            "family": "azure_inspired_diagnostic",
            "accuracy": swfb_ev["accuracy"],
            "correct_count": swfb_ev["correct_count"],
            "row_count": swfb_ev["row_count"],
            "wins_vs_canonical_fta": swfb_ev["wins_vs_canonical_fta"],
            "losses_vs_canonical_fta": swfb_ev["losses_vs_canonical_fta"],
            "ties_vs_canonical_fta": swfb_ev["ties_vs_canonical_fta"],
            "net_wins": swfb_ev["net_wins"],
            "regression_rate_among_fta_correct": swfb_ev.get("regression_rate_among_fta_correct"),
            "overrides_triggered": swfb_ev.get("overrides_triggered"),
            "overrides_changed_answer": swfb_ev.get("overrides_changed_answer"),
        }
    )
    write_csv(run_dir / "FULL_COHERE_RULE_COMPARISON.csv", comparison_rows, list(comparison_rows[0].keys()))

    all_boot = list(result["bootstrap_rows"]) + extra_boot
    write_csv(
        run_dir / "FULL_COHERE_BOOTSTRAP_CI.csv",
        all_boot,
        list(all_boot[0].keys()) if all_boot else ["comparison_name"],
    )

    usage_summary = {
        "examples_planned": run_meta.get("examples_planned"),
        "method_call_rows": usage.get("method_call_rows"),
        "scored": usage.get("scored"),
        "failed": usage.get("failed"),
        "api_failures": api_failures,
        "parse_failures": parse_failures,
        "total_input_tokens": usage.get("total_input_tokens"),
        "total_output_tokens": usage.get("total_output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "total_latency_seconds": usage.get("total_latency_seconds"),
        "total_logical_api_calls": usage.get("total_logical_api_calls"),
        "elapsed_seconds_runner": run_meta.get("elapsed_seconds"),
        "elapsed_seconds_delegate": (run_meta.get("live_delegate_run") or {}).get("elapsed_seconds"),
    }
    write_json(run_dir / "FULL_COHERE_USAGE_SUMMARY.json", usage_summary)

    eval_summary = {
        "classification": classification,
        "classification_reason": classification_reason,
        "canonical_fta": {
            "accuracy": fta_ev["accuracy"],
            "correct_count": fta_ev["correct_count"],
            "row_count": fta_ev["row_count"],
        },
        "repair_primary_plus_unanimity_fallback": {
            "accuracy": repair_ev["accuracy"],
            "correct_count": repair_ev["correct_count"],
            "row_count": repair_ev["row_count"],
            "wins_vs_canonical_fta": repair_ev["wins_vs_canonical_fta"],
            "losses_vs_canonical_fta": repair_ev["losses_vs_canonical_fta"],
            "ties_vs_canonical_fta": repair_ev["ties_vs_canonical_fta"],
            "net_wins": repair_ev["net_wins"],
            "regression_rate_among_fta_correct": repair_ev.get("regression_rate_among_fta_correct"),
            "overrides_triggered": repair_ev.get("overrides_triggered"),
            "overrides_changed_answer": repair_ev.get("overrides_changed_answer"),
            "bootstrap_vs_fta": repair_boot,
            "bootstrap_vs_external3": next((b for b in extra_boot if "external3" in b["comparison_name"]), None),
            "bootstrap_vs_pooled4": next((b for b in extra_boot if "pooled4" in b["comparison_name"]), None),
        },
        "baseline_external3": {"accuracy": ext3_ev["accuracy"], "correct_count": ext3_ev["correct_count"]},
        "baseline_pooled4": {"accuracy": pooled4_ev["accuracy"], "correct_count": pooled4_ev["correct_count"]},
        "diagnostic_azure_ext3_when_swfb": {
            "accuracy": swfb_ev["accuracy"],
            "net_wins_vs_fta": swfb_ev["net_wins"],
            "role": "diagnostic_only",
        },
        "decision_legality_audit_clean": audit_clean,
        "failure_class_counts": build_summary.get("failure_class_counts"),
        "gate_counts": build_summary.get("gate_counts"),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "FULL_COHERE_EVALUATION_SUMMARY.json", eval_summary)

    failure_lines = [
        "# Full Cohere Failure Analysis",
        "",
        f"- API failures (status=failed): **{api_failures}**",
        f"- Parse extraction failures: **{parse_failures}**",
        f"- Failure class counts: {json.dumps(build_summary.get('failure_class_counts', {}))}",
        f"- Gate counts: {json.dumps(build_summary.get('gate_counts', {}))}",
        "",
        f"Repair overrides triggered: {repair_ev.get('overrides_triggered')}",
        f"Repair answer-changing overrides: {repair_ev.get('overrides_changed_answer')}",
    ]
    write_text(run_dir / "FULL_COHERE_FAILURE_ANALYSIS.md", "\n".join(failure_lines).rstrip() + "\n")

    wandb_status: dict[str, Any] = {"skipped": args.skip_wandb}
    if not args.skip_wandb:
        wandb_status = supplemental_log_safe(
            run_name=f"cohere_full_seed53_{run_dir.name.split('_')[-1]}_posthoc",
            metrics={
                "fta_accuracy": fta_ev["accuracy"],
                "repair_accuracy": repair_ev["accuracy"],
                "repair_net_wins": repair_ev["net_wins"],
                "repair_losses": repair_ev["losses_vs_canonical_fta"],
                "total_tokens": usage.get("total_tokens") or 0,
                "method_call_rows": usage.get("method_call_rows") or 0,
            },
            extra_config={
                "run_dir": str(run_dir),
                "classification": classification,
                "provider": "cohere",
                "seed": 53,
            },
            tags=("cohere_full", "seed53", "posthoc"),
        )
    wandb_report = [
        "# Full Cohere W&B Report",
        "",
        f"- In-run W&B: see `full_validation.log` for `[wandb]` lines",
        f"- Supplemental post-hoc: {json.dumps(wandb_status, indent=2)}",
    ]
    write_text(run_dir / "FULL_COHERE_WANDB_REPORT.md", "\n".join(wandb_report).rstrip() + "\n")

    manuscript_lines = [
        "# Full Cohere Readiness for Manuscript",
        "",
        f"**Classification:** {classification}",
        f"**Reason:** {classification_reason}",
        "",
        "This run does **not** automatically update manuscript claims. FTA remains canonical.",
        f"Repair candidate status: exploratory unless separately reviewed.",
        "",
        f"- FTA: {fta_ev['correct_count']}/{fta_ev['row_count']} = {fta_ev['accuracy']:.4f}",
        f"- Repair: {repair_ev['correct_count']}/{repair_ev['row_count']} = {repair_ev['accuracy']:.4f}",
        f"- Net wins vs FTA: {repair_ev['net_wins']}",
        f"- Regression rate among FTA-correct: {repair_ev.get('regression_rate_among_fta_correct')}",
    ]
    write_text(run_dir / "FULL_COHERE_READINESS_FOR_MANUSCRIPT.md", "\n".join(manuscript_lines).rstrip() + "\n")

    final = [
        "# Final Full Cohere Validation Summary",
        "",
        f"- run_dir: `{run_dir}`",
        f"- examples: {fta_ev['row_count']}",
        f"- method-example rows: {usage.get('method_call_rows', 'unknown')}",
        f"- API failures: {api_failures}",
        f"- parse failures: {parse_failures}",
        f"- logical API calls: {usage.get('total_logical_api_calls', 'unknown')}",
        f"- total tokens: {usage.get('total_tokens', 'unknown')}",
        f"- wall-clock (runner): {run_meta.get('elapsed_seconds', 'unknown')}s",
        f"- canonical FTA: {fta_ev['accuracy']:.4f} ({fta_ev['correct_count']}/{fta_ev['row_count']})",
        f"- repair: {repair_ev['accuracy']:.4f} ({repair_ev['correct_count']}/{repair_ev['row_count']})",
        f"- net wins vs FTA: {repair_ev['net_wins']} (W={repair_ev['wins_vs_canonical_fta']} L={repair_ev['losses_vs_canonical_fta']} T={repair_ev['ties_vs_canonical_fta']})",
        f"- External-3: {ext3_ev['accuracy']:.4f}",
        f"- Pooled-4: {pooled4_ev['accuracy']:.4f}",
        f"- classification: **{classification}**",
        f"- W&B supplemental: {wandb_status.get('run_url') or wandb_status.get('note', 'see FULL_COHERE_WANDB_REPORT.md')}",
        "",
        "No selector logic changed. No code promotion. No commits.",
    ]
    write_text(run_dir / "FINAL_FULL_COHERE_VALIDATION_SUMMARY.md", "\n".join(final).rstrip() + "\n")

    manifest_path = run_dir / "LIVE_RUN_MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["posthoc_completed_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["classification"] = classification
        manifest["status"] = "completed"
        manifest["generation_completed_utc"] = run_meta.get("timestamp_utc")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        write_json(manifest_path, {
            "run_id": run_dir.name,
            "classification": classification,
            "status": "completed",
            "posthoc_completed_utc": datetime.now(timezone.utc).isoformat(),
        })

    print(json.dumps({"classification": classification, "fta_accuracy": fta_ev["accuracy"], "repair_accuracy": repair_ev["accuracy"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
