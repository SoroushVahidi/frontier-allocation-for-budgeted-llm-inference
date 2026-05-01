#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.analyze_offline_selector_variants import load_cases
from scripts.run_selector_tournament import run as run_tournament

TARGET_PRIORITIES = [
    "outputs/selector_tournament_compact_export_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE",
    "outputs/cohere_real_model_cost_normalized_validation_20260430T_SELECTOR_TOURNAMENT_50CASE_COHERE",
    "outputs/cohere_real_model_cost_normalized_validation_20260430T_TRACE_COMPLETE_30CASE_COHERE",
]
DR = "direct_reserve_semantic_frontier_v2"
L1 = "external_l1_max"


@dataclass
class ArtifactCheck:
    artifact_dir: Path
    records_path: Path | None
    usable: bool
    priority_rank: int
    reasons: list[str]
    stats: dict[str, int]


def _resolve_records_path(path: Path) -> Path | None:
    if path.is_file() and path.name == "per_example_records.jsonl":
        return path
    p = path / "per_example_records.jsonl"
    return p if p.exists() else None


def _safe_norm(x: Any) -> str:
    return str(x or "").strip().lower()


def validate_artifact(path: Path) -> ArtifactCheck:
    rec = _resolve_records_path(path)
    reasons: list[str] = []
    rows: list[dict[str, Any]] = []
    if rec is None:
        return ArtifactCheck(path, None, False, 10_000, ["missing per_example_records.jsonl"], {})
    try:
        rows = [json.loads(l) for l in rec.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception as exc:
        return ArtifactCheck(path, rec, False, 10_000, [f"invalid jsonl: {exc}"], {})
    if not rows:
        reasons.append("empty records file")

    dr_rows = [r for r in rows if r.get("method") == DR]
    l1_rows = [r for r in rows if r.get("method") == L1]
    if not dr_rows:
        reasons.append("no DR-v2 rows")
    if not l1_rows:
        reasons.append("no external_l1_max rows")

    gold_rows = [
        r for r in rows
        if _safe_norm(r.get("gold_answer_canonical") or r.get("gold_answer") or r.get("expected_answer"))
    ]
    if not gold_rows:
        reasons.append("no gold answers")

    dr_selected_rows = [
        r for r in dr_rows
        if _safe_norm(r.get("final_answer_canonical") or r.get("final_answer_raw") or r.get("selected_answer_canonical") or r.get("selected_answer_raw"))
    ]
    if not dr_selected_rows:
        reasons.append("no current selected answer on DR-v2 rows")

    candidate_nonempty = 0
    for r in dr_rows:
        md = r.get("result_metadata") or {}
        pool = md.get("selector_candidate_pool") or md.get("final_branch_states") or r.get("final_nodes") or []
        pool = [x for x in pool if isinstance(x, dict)]
        if pool:
            candidate_nonempty += 1
    if candidate_nonempty == 0:
        reasons.append("no candidate groups")

    usable_pairs = load_cases(rows)
    if len(usable_pairs) == 0:
        reasons.append("zero usable paired examples")

    stat = {
        "rows": len(rows),
        "dr_rows": len(dr_rows),
        "l1_rows": len(l1_rows),
        "gold_rows": len(gold_rows),
        "dr_selected_rows": len(dr_selected_rows),
        "candidate_nonempty_dr_rows": candidate_nonempty,
        "usable_pairs": len(usable_pairs),
    }
    pri = TARGET_PRIORITIES.index(str(path)) if str(path) in TARGET_PRIORITIES else 1000
    return ArtifactCheck(path, rec, len(reasons) == 0, pri, reasons, stat)


def discover_candidates(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit)]
    cands = [Path(p) for p in TARGET_PRIORITIES]
    for pat in ["selector_tournament_compact_export_*", "*SELECTOR_TOURNAMENT*", "*TRACE_COMPLETE*", "cohere_real_model_cost_normalized_validation_*"]:
        cands.extend([p for p in Path("outputs").glob(pat) if p.is_dir()])
    uniq = sorted(set(cands), key=lambda p: (0 if str(p) in TARGET_PRIORITIES else 1, -p.stat().st_mtime if p.exists() else float("-inf")))
    return uniq


def print_diagnostics(checks: list[ArtifactCheck]) -> None:
    print("# Artifact diagnosis")
    for i, c in enumerate(checks, 1):
        status = "USABLE" if c.usable else "REJECT"
        print(f"{i}. [{status}] {c.artifact_dir}")
        if c.records_path is not None:
            print(f"   records: {c.records_path}")
        if c.stats:
            print("   stats: " + ", ".join(f"{k}={v}" for k, v in c.stats.items()))
        if c.reasons:
            print("   reasons: " + "; ".join(c.reasons))


def pick_artifact(checks: list[ArtifactCheck]) -> ArtifactCheck:
    usable = [c for c in checks if c.usable]
    if not usable:
        raise RuntimeError("No usable selector artifact found. Run with --list-artifacts to inspect rejection reasons.")
    usable.sort(key=lambda c: (c.priority_rank, -c.stats.get("usable_pairs", 0), -c.stats.get("candidate_nonempty_dr_rows", 0), str(c.artifact_dir)))
    return usable[0]


def choose_best_deployable(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    deploy = [r for r in rows if r["selector"] != "oracle_selector"]
    if not deploy:
        return None
    deploy.sort(key=lambda r: (-float(r.get(key, 0.0)), -float(r.get("accuracy", 0.0)), float(r.get("breaks", 0)), r["selector"]))
    return deploy[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--list-artifacts", action="store_true")
    ap.add_argument("--diagnose-artifacts", action="store_true")
    args = ap.parse_args()

    checks = [validate_artifact(p) for p in discover_candidates(args.artifact_dir)]
    checks.sort(key=lambda c: (0 if c.usable else 1, c.priority_rank, -c.stats.get("usable_pairs", 0), str(c.artifact_dir)))

    if args.list_artifacts or args.diagnose_artifacts:
        print_diagnostics(checks)
        return

    selected = pick_artifact(checks)
    print_diagnostics(checks)
    print(f"\nUsing artifact: {selected.artifact_dir}")
    rows = [json.loads(line) for line in selected.records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit > 0:
        rows = rows[: args.limit]

    summary_rows, casebook_rows, _ = run_tournament(rows)
    by_name = {r["selector"]: dict(r) for r in summary_rows}
    rename = {
        "support_only_with_guard_v1": "risk_gated_support_override",
        "conservative_outcome_verifier_override_v2": "conservative_override",
        "source_aware_direct_reserve_prior": "source_family_diversity",
        "hybrid_support_confidence_consistency": "support_plus_family",
    }
    for old, new in rename.items():
        if old in by_name:
            row = by_name.pop(old)
            row["selector"] = new
            by_name[new] = row

    keep = ["current_dr_v2", "support_only", "source_family_diversity", "support_plus_family", "risk_gated_support_override", "conservative_override", "oracle_selector"]
    final_rows = [by_name[k] for k in keep if k in by_name]
    if not final_rows:
        raise RuntimeError("No selector rows produced; aborting.")

    all_zero = all(float(r.get("accuracy", 0.0)) == 0.0 for r in final_rows)
    all_no_changes = all(int(r.get("fixes", 0)) == 0 and int(r.get("breaks", 0)) == 0 and int(r.get("overrides", 0)) == 0 for r in final_rows)
    warn_all_zero = all_zero and all_no_changes

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir) if args.output_dir else Path("outputs") / f"fast_selector_selection_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "selector_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(final_rows[0].keys()))
        w.writeheader(); w.writerows(final_rows)
    with (out_dir / "selector_override_casebook.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(casebook_rows[0].keys()) if casebook_rows else ["selector"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(casebook_rows)

    best_acc = choose_best_deployable(final_rows, "accuracy")
    best_net = choose_best_deployable(final_rows, "net_fixes_minus_breaks")
    safe = [r for r in final_rows if r["selector"] != "oracle_selector" and r["breaks"] == 0 and r["delta_vs_current_dr_v2"] > 0]
    safest = sorted(safe, key=lambda r: (-r["delta_vs_current_dr_v2"], -r["accuracy"]))[0] if safe else None
    beats_l1 = any((r["selector"] != "oracle_selector" and r["delta_vs_external_l1_max"] > 0) for r in final_rows)

    summary = {
        "artifact_used": str(selected.artifact_dir),
        "records_path": str(selected.records_path),
        "artifact_diagnostics": {"reasons": selected.reasons, "stats": selected.stats},
        "paired_examples_evaluated": selected.stats.get("usable_pairs", 0),
        "selector_rows": final_rows,
        "best_deployable_by_accuracy": best_acc,
        "best_deployable_by_net": best_net,
        "safest_positive_gain_selector": safest,
        "any_deployable_beats_external_l1_max": beats_l1,
        "all_zero_metrics_warning": warn_all_zero,
    }
    (out_dir / "selector_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    recommendation = "move to cached outcome-verifier scoring" if (best_acc is None or best_acc["delta_vs_external_l1_max"] <= 0) else "selector promotion can be considered"
    rep = ["# Fast Selector Selection Report", "", f"- Artifact used: `{selected.artifact_dir}`", f"- Paired examples evaluated: {selected.stats.get('usable_pairs',0)}", f"- Best deployable selector by accuracy: `{best_acc['selector'] if best_acc else 'none'}`", f"- Best deployable selector by net fixes-minus-breaks: `{best_net['selector'] if best_net else 'none'}`", f"- Safest positive-gain selector: `{safest['selector'] if safest else 'none'}`", f"- Any deployable selector beats external_l1_max: {'yes' if beats_l1 else 'no'}", f"- Recommendation: {recommendation}."]
    if warn_all_zero:
        rep.append("- WARNING: all selectors have zero accuracy and no changes; verify artifact suitability before interpreting results.")
    (out_dir / "selector_selection_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print(out_dir)


if __name__ == "__main__":
    main()
