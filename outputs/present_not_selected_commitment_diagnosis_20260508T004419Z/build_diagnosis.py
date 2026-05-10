#!/usr/bin/env python3
"""Offline PNS / commitment diagnosis from existing artifacts only."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
COLLECT = ROOT / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z"
BANK_DIR = ROOT / "outputs/latest_pal_external_loss_bank_20260508T004000Z"

CASE_COLS = [
    "case_id",
    "source_artifacts",
    "problem_text",
    "gold_answer",
    "current_selected_answer",
    "pal_prediction",
    "pal_stdout_answer",
    "overlay_answer",
    "frontier_tiebreak_answer",
    "answer_group_supports",
    "gold_in_tree_or_pool",
    "primary_commitment_mechanism",
    "failure_tag",
    "track_b_status",
    "why_current_failed",
    "candidate_validator_signal_available",
    "proposed_validator_rule",
    "would_rule_fix_case",
    "risk_of_breaking_correct_cases",
    "notes",
]


def read_csv_dict(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_json(s: str):
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def pal_stdout_from_summary(summary_str: str) -> str:
    d = safe_json(summary_str)
    if not d:
        return ""
    for key in ("pal_seed_execution",):
        block = d.get(key) or {}
        er = block.get("pal_execution_result") or {}
        if er.get("pal_stdout"):
            return str(er.get("pal_stdout", "")).strip()
    er = d.get("pal_execution_result") or {}
    return str(er.get("pal_stdout", "")).strip()


def overlay_prev(overlay_str: str) -> str:
    d = safe_json(overlay_str)
    if not d:
        return ""
    return str(d.get("pal_overlay_previous_answer", "")).strip()


def mechanism_bucket(raw: str, ambiguous: str) -> str:
    if not raw:
        if "gold_in_tree_flag_but_not_in_normalized_selector_pool" in (ambiguous or ""):
            return "gold_in_tree_but_not_in_selector_pool_normalized"
        return "other_or_unknown"
    return raw


def main():
    union_rows = read_csv_dict(BANK_DIR / "latest_pal_external_loss_union_by_case.csv")
    bank_rows = read_csv_dict(BANK_DIR / "latest_pal_external_loss_bank.csv")
    replay_rows = {r["case_id"]: r for r in read_csv_dict(COLLECT / "present_not_selected_replay_table.csv")}
    cluster = {r["case_id"]: r for r in read_csv_dict(COLLECT / "failure_cluster_summary.csv")}
    track_by_case = {r["case_id"]: r for r in read_csv_dict(COLLECT / "track_b_gate_offline_replay_targets.csv")}
    union_by = {r["case_id"]: r for r in union_rows}

    pns_ids = set()
    for r in union_rows:
        flags = r.get("gold_absent_or_present_not_selected") or ""
        if "present_not_selected" in flags:
            pns_ids.add(r["case_id"])
    for r in bank_rows:
        if r.get("present_not_selected") == "yes":
            pns_ids.add(r["case_id"])

    exec_ids = {
        r["case_id"]
        for r in bank_rows
        if "executable_pal_present_but_not_committed=yes" in (r.get("notes") or "")
    }

    inspect_ids = sorted(pns_ids | exec_ids)
    bank_by_case = {}
    for r in bank_rows:
        bank_by_case.setdefault(r["case_id"], []).append(r)

    diagnosis_rows = []
    mech_counter = Counter()

    for cid in inspect_ids:
        rp = replay_rows.get(cid, {})
        cl = cluster.get(cid, {})
        tr = track_by_case.get(cid, {})
        ub = union_by.get(cid, {})
        banks = bank_by_case.get(cid, [])

        src = ub.get("source_artifacts") or ";".join(sorted({b.get("source_artifact", "") for b in banks}))

        raw_mech = (rp.get("primary_commitment_mechanism") or "").strip()
        ambiguous = rp.get("ambiguous_gold_presence") or ""
        mech = mechanism_bucket(raw_mech, ambiguous)
        if mech != "other_or_unknown":
            mech_counter[mech] += 1
        else:
            mech_counter["other_or_unknown"] += 1

        summary_json = rp.get("pal_execution_summary_json") or ""
        overlay_json = rp.get("pal_overlay_json") or ""
        stdout_ans = pal_stdout_from_summary(summary_json)
        overlay_ans = overlay_prev(overlay_json) or rp.get("pal_overlay_previous", "")

        tb_stat = "not_applicable"
        if tr:
            otag = tr.get("outcome_tag", "")
            if otag == "fixed_by_override":
                tb_stat = "fixed"
            elif otag == "unchanged_still_wrong":
                tb_stat = "abstained" if (tr.get("gate_abstain_reason") or "").strip() else "still_wrong"

        gold = rp.get("gold_normalized") or ub.get("gold_answer") or ""
        if banks:
            gold = gold or banks[0].get("gold_answer", "")
        problem = rp.get("question") or ub.get("problem_text") or (banks[0].get("problem_text") if banks else "")

        current_sel = rp.get("pal_surfaced_normalized") or (banks[0].get("pal_prediction") if banks else "")
        pal_pred = (banks[0].get("pal_prediction") if banks else "") or rp.get("pal_final_answer_raw", "")
        supports = rp.get("answer_group_support_counts_json", "")
        ftb = rp.get("frontier_tiebreak_selected_group", "")
        git = cl.get("gold_in_tree", "") or f"tree={rp.get('gold_in_tree_flag','')};pool={rp.get('gold_in_selector_pool','')}"

        why = []
        if raw_mech:
            why.append(raw_mech)
        if stdout_ans and current_sel and stdout_ans.replace(".0", "").strip() != str(current_sel).replace(".0", "").strip():
            why.append("PAL_stdout_differs_from_surfaced_answer")
        if ambiguous:
            why.append(f"ambiguous:{ambiguous[:80]}")

        signal = "unknown"
        if rp:
            if stdout_ans and current_sel and stdout_ans != current_sel:
                signal = "yes"
            elif overlay_ans and current_sel and overlay_ans != current_sel:
                signal = "yes"
            elif rp.get("frontier_tiebreak_triggered") == "True":
                signal = "yes"
            elif supports:
                signal = "yes"
        elif banks and banks[0].get("present_not_selected") == "yes":
            signal = "yes"

        # proposed rule mapping
        rule = ""
        fix = "unknown"
        risk = "unknown"
        if mech == "overlay_previous_equals_gold_but_surface_used_bad_pal_stdout":
            rule = "Rule_B_overlay_surface_repair_when_overlay_disagrees_with_stdout_and_histogram_supports_overlay_peer"
            fix = "yes" if tb_stat == "fixed" else "likely_yes_with_Track_B_style_gate"
            risk = "medium"
        elif mech == "frontier_tiebreak_selected_peer_not_gold_while_gold_in_pool":
            rule = "Rule_C_tiebreak_prefer_histogram_peer_with_executable_DR_leaf_when_PAL_stdout_conflicts"
            fix = "likely_partial"
            risk = "medium"
        elif mech == "gold_in_tree_but_not_in_selector_pool_normalized":
            rule = "Rule_D_normalize_pool_keys_repair_or_abstain_when_no_normalized_gold_bucket"
            fix = "no_without_normalizer"
            risk = "low"
        elif mech == "histogram_skew_duplicate_paths_favor_wrong_answer":
            rule = "Rule_E_downweight_duplicate_branch_hashes_or_caps_per_answer_group"
            fix = "partial_needs_implementation"
            risk = "high"
        elif mech == "gold_in_pool_but_missing_from_answer_group_histogram":
            rule = "Rule_F_fill_answer_group_histogram_from_selector_pool_before_commit"
            fix = "partial"
            risk = "medium"
        elif cid == "openai_gsm8k_851":
            rule = "needs_replay_table_or_trace"
            fix = "unknown"
            risk = "unknown"
        else:
            rule = "unspecified"
            fix = "unknown"

        sup_disp = supports
        if len(supports) > 300:
            sup_disp = supports[:300] + "…"

        notes_parts = []
        if cid not in replay_rows:
            notes_parts.append("no_row_in_present_not_selected_replay_table")
        if exec_ids & {cid}:
            notes_parts.append("flagged_executable_pal_not_committed_in_bank_notes")
        notes_parts.append(f"track_b_gate:{tr.get('gate_reason','')}" if tr else "no_track_b_target_row")

        diagnosis_rows.append(
            {
                "case_id": cid,
                "source_artifacts": src,
                "problem_text": problem[:500] + ("…" if len(problem) > 500 else ""),
                "gold_answer": gold,
                "current_selected_answer": current_sel,
                "pal_prediction": pal_pred,
                "pal_stdout_answer": stdout_ans,
                "overlay_answer": overlay_ans,
                "frontier_tiebreak_answer": ftb,
                "answer_group_supports": sup_disp,
                "gold_in_tree_or_pool": git,
                "primary_commitment_mechanism": mech,
                "failure_tag": cl.get("failure_tag", "") or rp.get("failure_tag", ""),
                "track_b_status": tb_stat,
                "why_current_failed": ";".join(why) if why else "see_failure_tag",
                "candidate_validator_signal_available": signal,
                "proposed_validator_rule": rule,
                "would_rule_fix_case": fix,
                "risk_of_breaking_correct_cases": risk,
                "notes": ";".join(notes_parts),
            }
        )

    with (OUT / "present_not_selected_commitment_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CASE_COLS)
        w.writeheader()
        for row in sorted(diagnosis_rows, key=lambda x: x["case_id"]):
            w.writerow(row)

    tb_fixed = sum(1 for r in diagnosis_rows if r["track_b_status"] == "fixed")
    tb_still_wrong = sum(
        1 for r in diagnosis_rows if r["track_b_status"] in ("abstained", "still_wrong")
    )
    likely_fix = sum(
        1
        for r in diagnosis_rows
        if r["primary_commitment_mechanism"]
        in (
            "overlay_previous_equals_gold_but_surface_used_bad_pal_stdout",
            "frontier_tiebreak_selected_peer_not_gold_while_gold_in_pool",
        )
    )
    unknown_trace = sum(
        1
        for r in diagnosis_rows
        if r["primary_commitment_mechanism"]
        in (
            "gold_in_tree_but_not_in_selector_pool_normalized",
            "histogram_skew_duplicate_paths_favor_wrong_answer",
            "gold_in_pool_but_missing_from_answer_group_histogram",
            "other_or_unknown",
        )
    )

    pal_stdout_mismatch_observable = sum(
        1 for r in diagnosis_rows if "PAL_stdout_differs_from_surfaced_answer" in r["why_current_failed"]
    )

    # mechanism_counts.json
    mc = {
        "total_pns_cases_inspected": len(pns_ids),
        "total_cases_in_diagnosis_table": len(inspect_ids),
        "executable_pal_present_but_not_committed": len(exec_ids),
        "track_b_fixed": tb_fixed,
        "track_b_still_wrong": tb_still_wrong,
        "mechanisms": dict(mech_counter),
        "likely_fixable_by_policy_v1": likely_fix,
        "unknown_or_needs_trace": unknown_trace,
        "pal_stdout_surfaced_mismatch_observable": pal_stdout_mismatch_observable,
        "notes": {
            "replay_PNS_cohort_rows": 23,
            "extra_union_PNS_without_replay": [i for i in sorted(pns_ids) if i not in replay_rows],
            "track_b_note": "still_wrong bucket counts offline outcomes where Track B did not apply fixed_by_override (mostly abstained with gate_abstain_reason).",
            "counterfactual_guardrail_reference": "present_not_selected_replay_report.md section E (both_correct cohort 183 rows)",
        },
    }
    (OUT / "mechanism_counts.json").write_text(json.dumps(mc, indent=2), encoding="utf-8")

    # markdown files — keep concise; user reads files for detail
    pol = """# Proposed commitment policy v1 (offline; gold used only in eval)\n\n## Preconditions\n- All signals below are **gold-free at runtime** except offline scoring.\n- Apply only when PAL executed (`pal_exec_ok`) and parsed stdout exists.\n\n## Rule A — Executable consistency flag\n- Compute `executable_consistent` when normalized `pal_json_answer` matches normalized executable `stdout` (or single print output).\n- If the committed/surfaced PAL answer disagrees with `stdout`, mark **surface_exec_mismatch**.\n\n## Rule B — Overlay vs surface repair (Track B provenance)\n- If `pal_overlay_previous_answer` is defined and differs from `pal_surfaced_normalized`, and overlay value appears as a peer in answer-group / branch metadata, prefer **re-surfacing overlay** when tie-break fired or when **surface_exec_mismatch** (see `override_overlay_prior_matches_tiebreak_conflicts_with_pal_stdout`).\n- **Guards:** require histogram peer support ≥1 OR prior tie-break; abstain if ambiguous multi-peer tie (`gate_abstain_reason` patterns in `track_b_gate_offline_replay_targets.csv`).\n\n## Rule C — Frontier tie-break peer vs pool gold\n- When `frontier_tiebreak_triggered` and selected peer ≠ DR final leaf but an alternate leaf matches DR / pool, re-check branch scores; prefer peer aligned with executable DR if scores within epsilon.\n\n## Rule D — Selector normalization / abstain\n- When gold is flagged in tree but **not** in normalized selector pool (`gold_in_tree_but_not_in_selector_pool_normalized`), **abstain override** unless pool normalizer fixes bucket; do not promote PAL stdout blindly.\n\n## Rule E — Histogram collapse guard\n- When support histogram omits a pool candidate (`gold_in_pool_but_missing_from_answer_group_histogram`) or duplicate inflates a wrong group (`histogram_skew_duplicate_paths_favor_wrong_answer`), require **pool→histogram promotion pass** or cap duplicate branch weights before max-support commit.\n\n## Rule F — Global abstain\n- If executable consistency fails, parse ambiguity, or uniform multi-group tie with stdout off-manifold, abstain (mirror Track B abstain buckets).\n"""
    (OUT / "proposed_commitment_policy_v1.md").write_text(pol, encoding="utf-8")

    plan = """# Commitment policy offline replay plan (next implementation step)\n\n## Positive targets (PNS / commitment failures)\n- **Full PNS replay inventory (23):** listed in `present_not_selected_replay_report.md` §A.\n- **Track B proved fixes:** `openai_gsm8k_1087`, `openai_gsm8k_1279`, `openai_gsm8k_1290` (see `track_b_gate_offline_replay_targets.csv`).\n- **Still-wrong / abstained under offline gate (20 rows):** all `outcome_tag=unchanged_still_wrong` in `track_b_gate_offline_replay_targets.csv`.\n- **Extra union case without replay row:** `openai_gsm8k_851` (needs trace export).\n\n## Regression guardrails (already-correct cohorts)\n- **Both PAL and best-external correct:** 183 rows on band 1072–1318 (`present_not_selected_replay_report.md` §E).\n- **PAL-only wins:** 5 rows — high priority no-regress.\n- Reuse counters in `counterfactual_policy_summary.csv`; `prefer_strong_pal_executable` showed lowest both-correct regressions (1) in §E table.\n\n## Implementation files / scripts to inspect\n- **`experiments/output_layer_repair.py`** — `decide_track_b_overlay_commitment_gate`.\n- **`experiments/controllers.py`** — integration around line ~8236 (`enable_track_b_overlay_commitment_gate`).\n- **`scripts/replay_track_b_commitment_gate.py`** — offline replay harness.\n- **`tests/test_track_b_overlay_commitment_gate.py`**.\n- Offline audits: `scripts/track_a_discovery_diagnostics.py`, `scripts/pal_code_static_audit.py`.\n- Validation runner: `scripts/run_cohere_real_model_cost_normalized_validation.py`.\n\n## Suggested method id\n- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1`\n\n## Estimated impact (offline; not executed here)\n| Rule | PNS rows likely touched | Cannot fix alone (from §D2 report) | Track B overlap | Regression note |\n|------|-------------------------|-------------------------------------|-----------------|-----------------|\n| B overlay/surface | 16 (`primary_commitment_mechanism` count) | Histogram-only losses (e.g. 1083, 1085) | 3 proved fixes | Medium — mirror §E regressions for max-support style |\n| C tie-break peer | 3 | Ambiguous multi-peer ties | partial | Medium |\n| D normalize/abstain | 2 + ambiguous rows | Requires schema fix | abstain-safe | Low |\n| E histogram repair | 2 | Needs dedup policy | none | High — duplicate inflation |\n\n## Next step\n1. Implement Rule A+B behind feature flag on method id above. 2. Replay 23 PNS + 183 guardrail IDs offline. 3. Expand to union case 851 with exported replay row.\n"""
    (OUT / "commitment_policy_replay_plan.md").write_text(plan, encoding="utf-8")

    print("Wrote", OUT)


if __name__ == "__main__":
    main()
