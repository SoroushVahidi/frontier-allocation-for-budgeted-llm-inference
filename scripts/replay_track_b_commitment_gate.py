#!/usr/bin/env python3
"""Offline replay for Track B overlay commitment gate (no API, no gold in decisions).

Reads archived GSM8K cohort artifacts, reconstructs compact gate inputs, calls
``decide_track_b_overlay_commitment_gate``, and scores outcomes **after** the
decision using gold labels only.

This script is **gate-only**: it does not simulate ``choose_repair_answer``,
``apply_controller_committed_surfacing_for_evaluation``, or
``apply_pal_residual_strong_integration_fix``. Live harness ``exact_match`` can
differ from counterfactual gate-vs-gold alignment for those reasons.

Outputs under:
  outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from experiments.frontier_max_support_tiebreak import normalize_answer_group_key
from experiments.output_layer_repair import decide_track_b_overlay_commitment_gate

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z"
PAL_METHOD = "direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal"

FIXTURE_ANCHORS = [
    "openai_gsm8k_1083",
    "openai_gsm8k_1085",
    "openai_gsm8k_1095",
    "openai_gsm8k_1124",
    "openai_gsm8k_1087",
    "openai_gsm8k_1279",
]


def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes"}


def _safe_json_dict(raw: str | None) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        out = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return out if isinstance(out, dict) else {}


def signals_from_replay_table_row(row: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    """Build gate inputs from ``present_not_selected_replay_table.csv`` row."""
    counts = _safe_json_dict(row.get("answer_group_support_counts_json"))
    missing = not counts
    tiebreak_meta = {
        "frontier_tiebreak_triggered": _parse_bool(row.get("frontier_tiebreak_triggered")),
        "frontier_tiebreak_selected_group": str(row.get("frontier_tiebreak_selected_group") or "").strip(),
        "frontier_tiebreak_previous_group": "",
        "frontier_tiebreak_reason": str(row.get("frontier_tiebreak_reason") or "").strip(),
    }
    px = _safe_json_dict(row.get("pal_execution_summary_json"))
    pal_flat = {
        "pal_candidate_answer": str(px.get("pal_candidate_answer") or "").strip(),
        "pal_json_answer": str(px.get("pal_json_answer") or "").strip(),
    }
    if not pal_flat["pal_candidate_answer"] and not pal_flat["pal_json_answer"]:
        missing = True
    ov = _safe_json_dict(row.get("pal_overlay_json"))
    prev_col = str(row.get("pal_overlay_previous") or "").strip()
    if prev_col and "pal_overlay_previous_answer" not in ov:
        ov = dict(ov)
        ov["pal_overlay_previous_answer"] = prev_col
    return counts, tiebreak_meta, pal_flat, ov, missing


def signals_from_pal_all_results(obj: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    """Build gate inputs from a PAL-method row in ``all_results.jsonl``."""
    rm = obj.get("result_metadata_full")
    if not isinstance(rm, dict):
        rm = {}
    counts = rm.get("answer_group_support_counts")
    if not isinstance(counts, dict):
        counts = {}
    missing = not counts
    tm_raw = obj.get("tiebreak_metadata") or {}
    if not isinstance(tm_raw, dict):
        tm_raw = {}
    tiebreak_meta = {
        "frontier_tiebreak_triggered": bool(tm_raw.get("frontier_tiebreak_triggered")),
        "frontier_tiebreak_selected_group": str(tm_raw.get("selected_group") or "").strip(),
        "frontier_tiebreak_previous_group": "",
        "frontier_tiebreak_reason": str(tm_raw.get("reason") or "").strip(),
    }
    pe = obj.get("pal_execution") or {}
    if not isinstance(pe, dict):
        pe = {}
    pal_flat = {
        "pal_candidate_answer": str(pe.get("pal_candidate_answer") or "").strip(),
        "pal_json_answer": str(pe.get("pal_json_answer") or "").strip(),
    }
    if not pal_flat["pal_candidate_answer"] and not pal_flat["pal_json_answer"]:
        missing = True
    pal_ov = rm.get("pal_overlay")
    overlay: dict[str, Any] = dict(pal_ov) if isinstance(pal_ov, dict) else {}
    # Mirror controller: compact overlay prior from committed pre-PAL final when absent.
    if not str(overlay.get("pal_overlay_previous_answer") or "").strip():
        pred = obj.get("predicted_answer")
        if pred is not None and str(pred).strip():
            overlay = dict(overlay)
            overlay["pal_overlay_previous_answer"] = str(pred).strip()
    return counts, tiebreak_meta, pal_flat, overlay, missing


def gold_norm(g: str | None) -> str:
    if g is None:
        return ""
    return normalize_answer_group_key(str(g).strip()) or ""


def counterfactual_matches_gold(gate: Mapping[str, Any], gold: str) -> bool | None:
    """Return whether override output aligns with gold (None if no override)."""
    if not gate.get("should_override"):
        return None
    gk = gold_norm(gold)
    if not gk:
        return False
    ra = gate.get("recommended_answer")
    if isinstance(ra, str) and ra.strip():
        return gold_norm(ra) == gk
    rgn = gate.get("recommended_normalized_group")
    if isinstance(rgn, str) and rgn.strip() and rgn != "__unknown__":
        return str(rgn).strip() == gk
    return False


def load_pal_rows_by_case(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("method") != PAL_METHOD:
                continue
            cid = str(obj.get("case_id") or obj.get("example_id") or "").strip()
            if cid:
                out[cid] = obj
    return out


def load_casebook_cohorts(path: Path) -> tuple[set[str], set[str]]:
    """Return (both_correct_ids, pal_only_correct_ids) in GSM8K band 1072–1318."""
    both: set[str] = set()
    pal_only: set[str] = set()

    def in_band(cid: str) -> bool:
        if not cid.startswith("openai_gsm8k_"):
            return False
        try:
            n = int(cid.rsplit("_", 1)[-1])
        except ValueError:
            return False
        return 1072 <= n <= 1318

    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row.get("case_id") or ""
            if not in_band(cid):
                continue
            pc, be = row.get("pal_correct"), row.get("best_external_correct")
            if pc == "1" and be == "1":
                both.add(cid)
            elif pc == "1" and be == "0":
                pal_only.add(cid)
    return both, pal_only


def run_replay(bundle_dir: Path) -> dict[str, Any]:
    replay_csv = bundle_dir / "present_not_selected_replay_table.csv"
    casebook = bundle_dir / "all_casebook.csv"
    all_results = bundle_dir / "all_results.jsonl"

    target_rows: dict[str, dict[str, str]] = {}
    with replay_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            target_rows[row["case_id"]] = row

    both_ids, pal_only_ids = load_casebook_cohorts(casebook)
    pal_by_case = load_pal_rows_by_case(all_results)

    def eval_case(
        case_id: str,
        cohort: str,
        gold: str,
        baseline_correct: bool | None,
        counts: dict[str, Any],
        tiebreak_meta: dict[str, Any],
        pal_flat: dict[str, Any],
        overlay: dict[str, Any],
        meta_missing: bool,
    ) -> dict[str, Any]:
        decision = decide_track_b_overlay_commitment_gate(
            combined_group_counts_base=dict(counts),
            tiebreak_meta=dict(tiebreak_meta),
            pal_execution_flat=dict(pal_flat),
            overlay_tiebreak_summary=dict(overlay) if overlay else None,
        )
        override = bool(decision.get("should_override"))
        cf_ok = counterfactual_matches_gold(decision, gold)
        row_out: dict[str, Any] = {
            "case_id": case_id,
            "cohort": cohort,
            "gold_normalized": gold_norm(gold),
            "baseline_correct": "" if baseline_correct is None else int(baseline_correct),
            "metadata_missing": int(meta_missing),
            "gate_should_override": int(override),
            "gate_reason": decision.get("reason"),
            "gate_abstain_reason": decision.get("abstain_reason"),
            "recommended_answer": decision.get("recommended_answer"),
            "recommended_normalized_group": decision.get("recommended_normalized_group"),
            "recommended_source": decision.get("recommended_source"),
            "counterfactual_matches_gold": "" if cf_ok is None else int(cf_ok),
        }
        # Outcome tags
        if baseline_correct is False:  # target failures
            if not override:
                row_out["outcome_tag"] = "unchanged_still_wrong"
            elif cf_ok:
                row_out["outcome_tag"] = "fixed_by_override"
            else:
                row_out["outcome_tag"] = "worsened_or_neutral_override"
        elif baseline_correct is True:
            if not override:
                row_out["outcome_tag"] = "unchanged_still_correct"
            elif cf_ok:
                row_out["outcome_tag"] = "override_keeps_correct"
            else:
                row_out["outcome_tag"] = "would_flip_correct_to_wrong"
        else:
            row_out["outcome_tag"] = "unknown_baseline"
        return row_out

    target_out: list[dict[str, Any]] = []
    for cid, row in target_rows.items():
        gold = str(row.get("gold_normalized") or row.get("gold_answer_raw") or "")
        counts, tm, pf, ov, miss = signals_from_replay_table_row(row)
        target_out.append(
            eval_case(cid, "target_present_not_selected", gold, False, counts, tm, pf, ov, miss)
        )

    guard_out: list[dict[str, Any]] = []
    guard_ids = sorted(both_ids | pal_only_ids)
    for cid in guard_ids:
        obj = pal_by_case.get(cid)
        if obj is None:
            guard_out.append(
                {
                    "case_id": cid,
                    "cohort": "guardrail_both_correct"
                    if cid in both_ids
                    else "guardrail_pal_only_correct",
                    "gold_normalized": "",
                    "baseline_correct": "",
                    "metadata_missing": 1,
                    "gate_should_override": "",
                    "gate_reason": "missing_pal_row_in_all_results",
                    "gate_abstain_reason": "",
                    "recommended_answer": "",
                    "recommended_normalized_group": "",
                    "recommended_source": "",
                    "counterfactual_matches_gold": "",
                    "outcome_tag": "missing_row",
                }
            )
            continue
        gold = str(obj.get("normalized_gold_answer") or obj.get("gold_answer") or "")
        baseline_ok = bool(int(obj.get("exact_match") or 0) == 1)
        cohort = "guardrail_both_correct" if cid in both_ids else "guardrail_pal_only_correct"
        counts, tm, pf, ov, miss = signals_from_pal_all_results(obj)
        guard_out.append(eval_case(cid, cohort, gold, baseline_ok, counts, tm, pf, ov, miss))

    # Metrics
    def summarize(rows: list[dict[str, Any]], *, cohort_filter: str | None = None) -> dict[str, Any]:
        rr = [x for x in rows if cohort_filter is None or x.get("cohort") == cohort_filter]
        evaluated = len(rr)
        overrides = sum(1 for x in rr if str(x.get("gate_should_override")) == "1")
        abstains = evaluated - overrides
        meta_miss = sum(1 for x in rr if str(x.get("metadata_missing")) == "1")
        reasons = Counter(str(x.get("gate_reason")) for x in rr if x.get("gate_reason"))
        abst_reasons = Counter(str(x.get("gate_abstain_reason")) for x in rr if x.get("gate_abstain_reason"))
        fixed = sum(1 for x in rr if x.get("outcome_tag") == "fixed_by_override")
        worsened = sum(1 for x in rr if x.get("outcome_tag") == "worsened_or_neutral_override")
        unchanged_wrong = sum(1 for x in rr if x.get("outcome_tag") == "unchanged_still_wrong")
        flip_bad = sum(1 for x in rr if x.get("outcome_tag") == "would_flip_correct_to_wrong")
        return {
            "rows": evaluated,
            "gate_override_count": overrides,
            "abstain_count": abstains,
            "metadata_missing_count": meta_miss,
            "fixed_by_override": fixed,
            "worsened_or_failed_override": worsened,
            "unchanged_still_wrong": unchanged_wrong,
            "would_flip_correct_to_wrong": flip_bad,
            "reasons_top": dict(reasons.most_common(25)),
            "abstain_reasons_top": dict(abst_reasons.most_common(25)),
        }

    summary = {
        "bundle": str(bundle_dir),
        "gate_function": "decide_track_b_overlay_commitment_gate",
        "pal_method": PAL_METHOD,
        "targets": summarize(target_out, cohort_filter="target_present_not_selected"),
        "targets_fixed_case_ids": sorted(
            x["case_id"] for x in target_out if x.get("outcome_tag") == "fixed_by_override"
        ),
        "targets_worsened_case_ids": sorted(
            x["case_id"] for x in target_out if x.get("outcome_tag") == "worsened_or_neutral_override"
        ),
        "guardrails_all": summarize(guard_out),
        "guardrails_both_correct": summarize(guard_out, cohort_filter="guardrail_both_correct"),
        "guardrails_pal_only": summarize(guard_out, cohort_filter="guardrail_pal_only_correct"),
        "guardrail_metadata_missing_case_ids": sorted(
            x["case_id"] for x in guard_out if str(x.get("metadata_missing")) == "1"
        ),
        "fixture_anchor_subset": [
            x for x in target_out if x.get("case_id") in FIXTURE_ANCHORS
        ],
    }
    return {
        "summary": summary,
        "target_rows": target_out,
        "guardrail_rows": guard_out,
    }


def write_outputs(bundle_dir: Path, data: dict[str, Any]) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    summary = data["summary"]

    with (bundle_dir / "track_b_gate_offline_replay_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    fieldnames = [
        "case_id",
        "cohort",
        "gold_normalized",
        "baseline_correct",
        "metadata_missing",
        "gate_should_override",
        "gate_reason",
        "gate_abstain_reason",
        "recommended_answer",
        "recommended_normalized_group",
        "recommended_source",
        "counterfactual_matches_gold",
        "outcome_tag",
    ]
    for name, rows in [
        ("track_b_gate_offline_replay_targets.csv", data["target_rows"]),
        ("track_b_gate_offline_replay_guardrails.csv", data["guardrail_rows"]),
    ]:
        with (bundle_dir / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow(row)

    # Markdown report
    t = summary["targets"]
    g_b = summary["guardrails_both_correct"]
    g_p = summary["guardrails_pal_only"]
    md_lines = [
        "# Track B overlay commitment gate — offline replay report",
        "",
        f"**Bundle:** `{bundle_dir}`",
        "",
        "This report is generated by `scripts/replay_track_b_commitment_gate.py`. "
        "Decisions use only archived metadata (no gold at decision time). "
        "Gold labels are used **after** the gate runs for scoring only.",
        "",
        "**Note:** Replay scores gate recommendations vs gold only — not full harness evaluator semantics "
        "(repair layer, controller surfacing, PAL residual integration).",
        "",
        "## Summary — target cohort (23 present-not-selected)",
        "",
        f"- Rows evaluated: **{t['rows']}**",
        f"- Gate override: **{t['gate_override_count']}**",
        f"- Abstain / no override: **{t['abstain_count']}**",
        f"- Metadata flagged incomplete: **{t['metadata_missing_count']}**",
        f"- Cases scored as fixed by override (gold-aligned): **{t['fixed_by_override']}**",
        f"- Overrides not aligned with gold: **{t['worsened_or_failed_override']}**",
        f"- Still wrong with no override: **{t['unchanged_still_wrong']}**",
        "",
        "### Gate outcome reasons (targets)",
        "",
        "```",
        json.dumps(t["reasons_top"], indent=2),
        "```",
        "",
        "### Abstain reasons (targets)",
        "",
        "```",
        json.dumps(t["abstain_reasons_top"], indent=2),
        "```",
        "",
        "## Summary — guardrail cohort (both PAL and best-external correct)",
        "",
        f"- Rows evaluated: **{g_b['rows']}**",
        f"- Overrides: **{g_b['gate_override_count']}**",
        f"- **Would flip correct → wrong:** **{g_b['would_flip_correct_to_wrong']}**",
        f"- Metadata missing: **{g_b['metadata_missing_count']}**",
        "",
        "## Summary — guardrail cohort (PAL-only correct vs externals)",
        "",
        f"- Rows evaluated: **{g_p['rows']}**",
        f"- Overrides: **{g_p['gate_override_count']}**",
        f"- **Would flip correct → wrong:** **{g_p['would_flip_correct_to_wrong']}**",
        "",
        "## Fixture anchors (six JSON fixtures — subset of targets)",
        "",
        "| case_id | override | reason | outcome |",
        "|---------|----------|--------|---------|",
    ]
    for row in summary["fixture_anchor_subset"]:
        md_lines.append(
            f"| {row.get('case_id')} | {row.get('gate_should_override')} | "
            f"{row.get('gate_reason')} | {row.get('outcome_tag')} |"
        )
    md_lines += [
        "",
        "### Target override detail",
        "",
        f"- **Gold-aligned fixes:** `{summary['targets_fixed_case_ids']}`",
        f"- **Overrides not matching gold (offline score):** `{summary['targets_worsened_case_ids']}`",
        "",
        "### Guardrail metadata gaps",
        "",
        f"- Rows with incomplete histogram / PAL fields (replay-only flag): `{summary['guardrail_metadata_missing_case_ids']}`",
        "",
        "## Design contract checklist (informal)",
        "",
        "- Section L offline criteria require reporting fixes among 23, guardrail flips, and an agreed regression budget. "
        "This run reports counts; **numerical flip budget is not fixed in the bundle** — compare flips to policy.",
        "- No API calls; suitable as a prerequisite to a **small capped Cohere pilot** only after stakeholders accept flip risk.",
        "",
    ]
    with (bundle_dir / "track_b_gate_offline_replay_report.md").open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--bundle-dir",
        type=Path,
        default=REPO_ROOT / BUNDLE,
        help="Directory containing replay CSV + all_results.jsonl + all_casebook.csv",
    )
    ap.add_argument(
        "--structural-commit-v1",
        action="store_true",
        help="Run structural commitment v1 replay (separate output directory).",
    )
    ap.add_argument(
        "--structural-commit-v1-output",
        type=Path,
        default=None,
        help="Override output directory for --structural-commit-v1 (default: outputs/structural_commit_v1_replay_<utc>).",
    )
    args = ap.parse_args()
    bundle = args.bundle_dir.resolve()
    if args.structural_commit_v1:
        import importlib.util

        mod_path = Path(__file__).resolve().parent / "replay_structural_commit_v1.py"
        spec = importlib.util.spec_from_file_location("replay_structural_commit_v1", mod_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load replay_structural_commit_v1.py")
        sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sc)
        out = args.structural_commit_v1_output
        if out is None:
            from datetime import datetime, timezone

            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            out = REPO_ROOT / "outputs" / f"structural_commit_v1_replay_{ts}"
        data = sc.run_replay(bundle_dir=bundle, diagnosis_csv=sc.DEFAULT_DIAGNOSIS.resolve())
        sc.write_out(out.resolve(), data)
        print(f"Structural commit v1 replay wrote {out.resolve()}")
        return
    data = run_replay(bundle)
    write_outputs(bundle, data)
    print(f"Wrote replay artifacts under {bundle}")


if __name__ == "__main__":
    main()
