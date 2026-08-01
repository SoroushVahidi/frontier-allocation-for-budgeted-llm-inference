"""Offline post-hoc dual-candidate (fs<=1 / fs0 / fs1-only) comparison on the
completed Cohere seed-83 live validation (tmux session
cohere_pooled4_fs_le1_validation_20260709T024735Z).

Reads only the already-generated
outputs/api_validation_live/cohere_pooled4_fs_le1_notie_20260709T024735Z/
raw_records/per_example_records.jsonl. Zero new API calls.

Reuses the frozen `decision_pooled4_fs_le1_notie(row, max_fs=...)` function from
experiments.freeze_pooled4_fs_le1_notie_candidate for both the original
`pooled4_fs_le1_notie_fta_v2_candidate` (max_fs=1, the definition that live run was
pre-registered against) and the conservative `pooled4_fs0_notie_risk_controlled_candidate`
(max_fs=0) discovered in the 2026-07-09 overnight pass. fs==1-only is the exact
set-difference (fires at max_fs=1, does not fire at max_fs=0) -- no selector logic is
reimplemented or changed.

Gold is used only for offline win/loss/tie labeling; the firing conditions
themselves never read gold (unchanged from the frozen module).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from experiments.build_failure_feature_table import build_feature_rows_from_specs
from experiments.evaluate_api_validation_repair_candidate import build_pooled4_fs_le1_validation_specs
from experiments.explore_offline_selector_rules import RuleSpec
from experiments.failure_analysis_common import write_csv, write_json, write_text
from experiments.freeze_pooled4_fs_le1_notie_candidate import (
    CANDIDATE_NAME as FSLE1_NAME,
    decision_pooled4_fs_le1_notie,
    pooled4_vote_counts,
)
from experiments.stress_test_exploratory_rules import evaluate_rule_full, paired_bootstrap_ci

DEFAULT_RECORDS = Path(
    "outputs/api_validation_live/cohere_pooled4_fs_le1_notie_20260709T024735Z/"
    "raw_records/per_example_records.jsonl"
)
FS0_NAME = "pooled4_fs0_notie_risk_controlled_candidate"
FS1_NAME = "pooled4_fs1_only_diagnostic"
FTA_NAME = "baseline_canonical_fta"
POOLED4_STANDALONE = "baseline_pooled4_normalized_plurality_tiebreak"
EXTERNAL3_STANDALONE = "baseline_external3_strict_majority_normalized"


def decision_fs0(row: dict[str, Any]) -> str | None:
    return decision_pooled4_fs_le1_notie(row, max_fs=0)


def decision_fs1_only(row: dict[str, Any]) -> str | None:
    """fires under fs<=1 (max_fs=1) but not under fs0 (max_fs=0) -- frontier_support==1 exactly."""
    d1 = decision_pooled4_fs_le1_notie(row, max_fs=1)
    if d1 is None:
        return None
    if decision_pooled4_fs_le1_notie(row, max_fs=0) is not None:
        return None
    return d1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--records-path", default=str(DEFAULT_RECORDS))
    p.add_argument("--output-dir", default=None)
    p.add_argument("--bootstrap-resamples", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=1234)
    return p.parse_args()


def _timestamp_dir() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs/failure_analysis") / f"cohere_seed83_dual_candidate_posthoc_{ts}"


def margin_and_votes(row: dict[str, Any]) -> tuple[int | None, dict[str, int]]:
    votes = pooled4_vote_counts(row)
    if not votes:
        return None, {}
    counts = sorted(votes.values(), reverse=True)
    top = counts[0]
    second = counts[1] if len(counts) > 1 else 0
    return top - second, votes


def action_case_row(row: dict[str, Any], decision_fn: Callable[[dict[str, Any]], str | None]) -> dict[str, Any]:
    proposal = decision_fn(row)
    fta = row.get("fta_selected_answer_canonical")
    gold = row.get("gold_answer_canonical")
    fta_correct = bool(row.get("fta_correct"))
    selected = proposal if proposal not in (None, "") else fta
    selected_correct = bool(
        selected not in (None, "") and gold not in (None, "") and str(selected) == str(gold)
    )
    if not fta_correct and selected_correct:
        outcome = "win"
    elif fta_correct and not selected_correct:
        outcome = "loss"
    else:
        outcome = "tie"
    margin, votes = margin_and_votes(row)
    return {
        "row_id": row.get("row_id"),
        "example_id": row.get("example_id"),
        "gold_answer": gold,
        "fta_answer": fta,
        "pooled4_answer": proposal,
        "frontier_answer": row.get("frontier_answer_canonical"),
        "l1_answer": row.get("l1_answer_canonical"),
        "s1_answer": row.get("s1_answer_canonical"),
        "tale_answer": row.get("tale_answer_canonical"),
        "frontier_support": row.get("frontier_support"),
        "candidate_pool_answer_group_count": row.get("candidate_pool_answer_group_count"),
        "pooled4_vote_counts": json.dumps(votes, sort_keys=True),
        "pooled4_vote_margin": margin,
        "fta_correct": fta_correct,
        "outcome": outcome,
    }


def fs_distribution(rows: list[dict[str, Any]], decision_fn: Callable[[dict[str, Any]], str | None]) -> dict[str, Any]:
    triggered = [r for r in rows if decision_fn(r) is not None]
    fs_counts = Counter(str(r.get("frontier_support")) for r in triggered)
    margins: list[int] = []
    for r in triggered:
        m, _ = margin_and_votes(r)
        if m is not None:
            margins.append(m)
    margin_counts = Counter(margins)
    return {
        "n_triggered": len(triggered),
        "frontier_support_distribution": dict(fs_counts),
        "pooled4_vote_margin_distribution": {str(k): v for k, v in sorted(margin_counts.items())},
    }


def classify(ev: dict[str, Any], boot_vs_fta: dict[str, Any] | None) -> str:
    net = ev["net_wins"]
    losses = ev["losses_vs_canonical_fta"]
    ci_excludes_zero = boot_vs_fta is not None and boot_vs_fta.get("includes_zero") is False
    if net > 0 and losses == 0 and ci_excludes_zero:
        return "validated candidate"
    if net > 0 and losses <= 2:
        return "promising, needs another validation"
    if net <= 0:
        return "rejected"
    return "inconclusive"


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else _timestamp_dir()
    if output_dir.exists():
        raise FileExistsError(f"refusing to write into an existing directory: {output_dir}")
    output_dir.mkdir(parents=True)

    records_path = Path(args.records_path)
    if not records_path.exists():
        raise FileNotFoundError(records_path)

    specs_in = [
        {
            "source_id": "cohere_seed83_dual_candidate_posthoc",
            "path": str(records_path),
            "rationale": "fs<=1 / fs0 / fs1-only post-hoc comparison, no new API calls",
        }
    ]
    feature_rows, build_summary = build_feature_rows_from_specs(specs_in)
    if len(feature_rows) != 300:
        raise RuntimeError(f"expected 300 examples from seed-83 run, found {len(feature_rows)}")

    base_specs = {s.name: s for s in build_pooled4_fs_le1_validation_specs()}
    fs0_spec = RuleSpec(
        FS0_NAME, "exploratory_frozen_not_promoted",
        "Conservative fs0 sub-variant (max_fs=0) of pooled4_fs_le1_notie_fta_v2_candidate.",
        decision_fs0,
    )
    fs1_spec = RuleSpec(
        FS1_NAME, "diagnostic_only",
        "fs==1-only slice: fires under fs<=1 but not under fs0 (strict set-difference).",
        decision_fs1_only,
    )

    method_order = [
        FTA_NAME, FSLE1_NAME, FS0_NAME, FS1_NAME, POOLED4_STANDALONE, EXTERNAL3_STANDALONE,
        "frontier_only", "l1_only", "s1_only", "tale_only",
    ]
    all_specs = {}
    for name in method_order:
        if name in (FS0_NAME, FS1_NAME):
            continue
        all_specs[name] = base_specs[name]
    all_specs[FS0_NAME] = fs0_spec
    all_specs[FS1_NAME] = fs1_spec

    evs = {name: evaluate_rule_full(feature_rows, spec) for name, spec in all_specs.items()}
    fta_ev = evs[FTA_NAME]
    pooled4_ev = evs[POOLED4_STANDALONE]
    external3_ev = evs[EXTERNAL3_STANDALONE]

    # --- SEED83_METHOD_COMPARISON.csv: all 10 methods/candidates, accuracy-first ---
    method_rows = []
    for name in method_order:
        ev = evs[name]
        method_rows.append(
            {
                "candidate": name,
                "family": all_specs[name].family,
                "accuracy": ev["accuracy"],
                "correct_count": ev["correct_count"],
                "row_count": ev["row_count"],
                "wins_vs_fta": ev["wins_vs_canonical_fta"],
                "losses_vs_fta": ev["losses_vs_canonical_fta"],
                "ties_vs_fta": ev["ties_vs_canonical_fta"],
                "net_vs_fta": ev["net_wins"],
                "trigger_count": ev["overrides_triggered"],
                "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
            }
        )
    write_csv(output_dir / "SEED83_METHOD_COMPARISON.csv", method_rows, list(method_rows[0].keys()))

    # --- SEED83_CANDIDATE_COMPARISON.csv: the six decision-rule candidates ---
    candidate_names = [FTA_NAME, FSLE1_NAME, FS0_NAME, FS1_NAME, POOLED4_STANDALONE, EXTERNAL3_STANDALONE]
    candidate_rows = []
    boot_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _boot(name_a: str, name_b: str) -> dict[str, Any]:
        key = (name_a, name_b)
        if key not in boot_cache:
            boot_cache[key] = paired_bootstrap_ci(
                evs[name_a]["per_row"], evs[name_b]["per_row"],
                n_resamples=args.bootstrap_resamples, seed=args.bootstrap_seed, stratify_by_source=True,
            )
        return boot_cache[key]

    for name in candidate_names:
        ev = evs[name]
        boot_fta = _boot(name, FTA_NAME) if name != FTA_NAME else None
        boot_p4 = _boot(name, POOLED4_STANDALONE) if name not in (FTA_NAME, POOLED4_STANDALONE) else None
        boot_ext3 = _boot(name, EXTERNAL3_STANDALONE) if name not in (FTA_NAME, EXTERNAL3_STANDALONE) else None
        candidate_rows.append(
            {
                "candidate": name,
                "accuracy": ev["accuracy"],
                "correct_count": ev["correct_count"],
                "row_count": ev["row_count"],
                "trigger_count": ev["overrides_triggered"],
                "wins_vs_fta": ev["wins_vs_canonical_fta"],
                "losses_vs_fta": ev["losses_vs_canonical_fta"],
                "ties_vs_fta": ev["ties_vs_canonical_fta"],
                "net_vs_fta": ev["net_wins"],
                "regression_rate_among_fta_correct": ev["regression_rate_among_fta_correct"],
                "bootstrap_ci_vs_fta_low": boot_fta["ci_low"] if boot_fta else None,
                "bootstrap_ci_vs_fta_high": boot_fta["ci_high"] if boot_fta else None,
                "bootstrap_ci_vs_fta_includes_zero": boot_fta["includes_zero"] if boot_fta else None,
                "delta_acc_vs_pooled4_standalone": boot_p4["observed_delta_accuracy"] if boot_p4 else None,
                "delta_acc_vs_external3_standalone": boot_ext3["observed_delta_accuracy"] if boot_ext3 else None,
            }
        )
    write_csv(output_dir / "SEED83_CANDIDATE_COMPARISON.csv", candidate_rows, list(candidate_rows[0].keys()))

    # --- SEED83_BOOTSTRAP_CI.csv ---
    boot_rows = []
    for name in [FSLE1_NAME, FS0_NAME, FS1_NAME, POOLED4_STANDALONE, EXTERNAL3_STANDALONE]:
        boot_rows.append({"comparison_name": f"{name}_vs_canonical_fta", **_boot(name, FTA_NAME)})
    for name in [FSLE1_NAME, FS0_NAME, FS1_NAME]:
        boot_rows.append({"comparison_name": f"{name}_vs_pooled4_standalone", **_boot(name, POOLED4_STANDALONE)})
        boot_rows.append({"comparison_name": f"{name}_vs_external3_standalone", **_boot(name, EXTERNAL3_STANDALONE)})
    boot_fields = sorted({k for r in boot_rows for k in r}, key=lambda k: (k != "comparison_name", k))
    write_csv(output_dir / "SEED83_BOOTSTRAP_CI.csv", boot_rows, boot_fields)

    # --- Action-case CSVs ---
    fsle1_fn = lambda row: decision_pooled4_fs_le1_notie(row, max_fs=1)  # noqa: E731
    fsle1_cases = [action_case_row(r, fsle1_fn) for r in feature_rows if fsle1_fn(r) is not None]
    fs0_cases = [action_case_row(r, decision_fs0) for r in feature_rows if decision_fs0(r) is not None]
    fs1_cases = [action_case_row(r, decision_fs1_only) for r in feature_rows if decision_fs1_only(r) is not None]
    case_fields = list(action_case_row(feature_rows[0], fsle1_fn).keys())
    write_csv(output_dir / "SEED83_FSLE1_ACTION_CASES.csv", fsle1_cases, case_fields)
    write_csv(output_dir / "SEED83_FS0_ACTION_CASES.csv", fs0_cases, case_fields)
    write_csv(output_dir / "SEED83_FS1_DIAGNOSTIC_CASES.csv", fs1_cases, case_fields)

    dist_fsle1 = fs_distribution(feature_rows, fsle1_fn)
    dist_fs0 = fs_distribution(feature_rows, decision_fs0)
    dist_fs1 = fs_distribution(feature_rows, decision_fs1_only)

    # --- Loss casebook (only if losses exist anywhere) ---
    any_losses = any(c["outcome"] == "loss" for cases in (fsle1_cases, fs0_cases, fs1_cases) for c in cases)
    if any_losses:
        lines = ["# Seed-83 Dual-Candidate Loss Casebook", ""]
        for label, cases in (("fs<=1 (original)", fsle1_cases), ("fs0 (conservative)", fs0_cases), ("fs1-only (diagnostic)", fs1_cases)):
            losses = [c for c in cases if c["outcome"] == "loss"]
            lines.append(f"## {label}: {len(losses)} losses")
            if not losses:
                lines.append("(none)")
            for c in losses:
                lines.append(
                    f"- {c['example_id']}: fta={c['fta_answer']} pooled4={c['pooled4_answer']} "
                    f"gold={c['gold_answer']} fs={c['frontier_support']} margin={c['pooled4_vote_margin']} "
                    f"votes={c['pooled4_vote_counts']}"
                )
            lines.append("")
        write_text(output_dir / "SEED83_LOSS_CASEBOOK.md", "\n".join(lines) + "\n")

    # --- Decision classification ---
    fsle1_class = classify(evs[FSLE1_NAME], _boot(FSLE1_NAME, FTA_NAME))
    fs0_class = classify(evs[FS0_NAME], _boot(FS0_NAME, FTA_NAME))
    fs1_net = evs[FS1_NAME]["net_wins"]
    if fs1_net > 0 and dist_fs1["n_triggered"] >= 5:
        fs1_class = "diagnostic high-gain subgroup (needs its own risk guard/validation)"
    elif fs1_net <= 0:
        fs1_class = "rejected on this data"
    else:
        fs1_class = "inconclusive (too few triggers)"

    decision_lines = [
        "# Seed-83 Validation Decision", "",
        f"generated_utc: {datetime.now(timezone.utc).isoformat()}", "",
        "## Original fs<=1 (`pooled4_fs_le1_notie_fta_v2_candidate`)",
        f"- classification: **{fsle1_class}**",
        f"- n_triggered={evs[FSLE1_NAME]['overrides_triggered']}, wins={evs[FSLE1_NAME]['wins_vs_canonical_fta']}, "
        f"losses={evs[FSLE1_NAME]['losses_vs_canonical_fta']}, net={evs[FSLE1_NAME]['net_wins']}",
        f"- bootstrap CI vs FTA: [{_boot(FSLE1_NAME, FTA_NAME)['ci_low']}, {_boot(FSLE1_NAME, FTA_NAME)['ci_high']}], "
        f"includes_zero={_boot(FSLE1_NAME, FTA_NAME)['includes_zero']}",
        "- Note: this was the *prospectively pre-registered* candidate for this live run "
        "(see outputs/failure_analysis/pooled4_fs_le1_candidate_freeze_20260709T015058Z/); "
        "this is its first genuinely fresh-data result.",
        "",
        "## Conservative fs0 (`pooled4_fs0_notie_risk_controlled_candidate`)",
        f"- classification: **{fs0_class}**",
        f"- n_triggered={evs[FS0_NAME]['overrides_triggered']}, wins={evs[FS0_NAME]['wins_vs_canonical_fta']}, "
        f"losses={evs[FS0_NAME]['losses_vs_canonical_fta']}, net={evs[FS0_NAME]['net_wins']}",
        f"- bootstrap CI vs FTA: [{_boot(FS0_NAME, FTA_NAME)['ci_low']}, {_boot(FS0_NAME, FTA_NAME)['ci_high']}], "
        f"includes_zero={_boot(FS0_NAME, FTA_NAME)['includes_zero']}",
        "- Note: fs0 and fs1 were evaluated *post-hoc* on this run's already-generated records -- "
        "they were not the pre-registered candidate for this specific live run.",
        "",
        "## fs==1-only diagnostic slice",
        f"- classification: **{fs1_class}**",
        f"- n_triggered={evs[FS1_NAME]['overrides_triggered']}, wins={evs[FS1_NAME]['wins_vs_canonical_fta']}, "
        f"losses={evs[FS1_NAME]['losses_vs_canonical_fta']}, net={evs[FS1_NAME]['net_wins']}",
        f"- frontier_support distribution: {dist_fs1['frontier_support_distribution']}",
        f"- Pooled-4 vote-margin distribution: {dist_fs1['pooled4_vote_margin_distribution']}",
        "",
        "## What should not be claimed",
        "- Neither fs0 nor fs1 has been prospectively pre-registered/frozen for a fresh live run of its own; "
        "this is a post-hoc replay on already-purchased data.",
        "- No candidate is promoted or has selector logic changed by this analysis.",
        "- No manuscript claim is updated by this analysis.",
    ]
    write_text(output_dir / "SEED83_VALIDATION_DECISION.md", "\n".join(decision_lines) + "\n")

    # --- Top-level summary ---
    summary_lines = [
        "# Seed-83 Dual-Candidate Post-Hoc Comparison Summary", "",
        f"generated_utc: {datetime.now(timezone.utc).isoformat()}",
        f"source records: `{records_path}` (300 examples, already generated; zero new API calls)",
        "", "## Candidate comparison (vs canonical FTA)", "",
    ]
    for name in candidate_names:
        ev = evs[name]
        summary_lines.append(
            f"- **{name}**: acc={ev['accuracy']:.4f} ({ev['correct_count']}/{ev['row_count']}), "
            f"triggers={ev['overrides_triggered']}, W/L/T={ev['wins_vs_canonical_fta']}/"
            f"{ev['losses_vs_canonical_fta']}/{ev['ties_vs_canonical_fta']}, net={ev['net_wins']}, "
            f"regression_rate={ev['regression_rate_among_fta_correct']}"
        )
    summary_lines += [
        "", "## Single-method baselines", "",
    ]
    for name in ["frontier_only", "l1_only", "s1_only", "tale_only"]:
        ev = evs[name]
        summary_lines.append(f"- **{name}**: acc={ev['accuracy']:.4f} ({ev['correct_count']}/{ev['row_count']})")
    summary_lines += [
        "", "## fs<=1 / fs0 / fs1 diagnostics", "",
        f"- fs<=1 frontier_support distribution: {dist_fsle1['frontier_support_distribution']}",
        f"- fs<=1 Pooled-4 vote-margin distribution: {dist_fsle1['pooled4_vote_margin_distribution']}",
        f"- fs0 frontier_support distribution: {dist_fs0['frontier_support_distribution']}",
        f"- fs0 Pooled-4 vote-margin distribution: {dist_fs0['pooled4_vote_margin_distribution']}",
        f"- fs1-only frontier_support distribution: {dist_fs1['frontier_support_distribution']}",
        f"- fs1-only Pooled-4 vote-margin distribution: {dist_fs1['pooled4_vote_margin_distribution']}",
        "", "## Decisions", "",
        f"- fs<=1: **{fsle1_class}**",
        f"- fs0: **{fs0_class}**",
        f"- fs1-only: **{fs1_class}**",
        "", "See SEED83_VALIDATION_DECISION.md for full rationale.", "",
        "## Confirmations",
        "- No new API calls (reads only already-generated per_example_records.jsonl).",
        "- No selector logic changed -- fs<=1 and fs0 both call the frozen "
        "`decision_pooled4_fs_le1_notie` function unmodified, parameterized only by `max_fs`.",
        "- No candidate promoted; FTA FIX-2+FIX-4 remains canonical.",
        "- No manuscript claim updated.",
        "- No commits/pushes performed.",
    ]
    write_text(output_dir / "SEED83_DUAL_CANDIDATE_POSTHOC_SUMMARY.md", "\n".join(summary_lines) + "\n")

    write_json(
        output_dir / "SEED83_BUILD_SUMMARY.json",
        {"build_summary": build_summary, "records_path": str(records_path)},
    )

    result = {
        "output_dir": str(output_dir),
        "fsle1": {"n": evs[FSLE1_NAME]["overrides_triggered"], "net": evs[FSLE1_NAME]["net_wins"], "losses": evs[FSLE1_NAME]["losses_vs_canonical_fta"], "classification": fsle1_class},
        "fs0": {"n": evs[FS0_NAME]["overrides_triggered"], "net": evs[FS0_NAME]["net_wins"], "losses": evs[FS0_NAME]["losses_vs_canonical_fta"], "classification": fs0_class},
        "fs1": {"n": evs[FS1_NAME]["overrides_triggered"], "net": evs[FS1_NAME]["net_wins"], "losses": evs[FS1_NAME]["losses_vs_canonical_fta"], "classification": fs1_class},
    }
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
