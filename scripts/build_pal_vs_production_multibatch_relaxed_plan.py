#!/usr/bin/env python3
"""No-API plan: Relaxed PAL vs production_equiv multi-batch casebook collection."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Previous results
PREV_LIVE_DIR = REPO / "outputs/pal_vs_production_multibatch_casebook_live_20260508T234831Z"
PREV_CASEBOOK = PREV_LIVE_DIR / "cumulative_pal_vs_prod_casebook.csv"
PREV_SUMMARY = PREV_LIVE_DIR / "cumulative_casebook_summary.json"

# Exclusions to relax
MATCHED_50 = REPO / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv"
NONOVERLAP_30 = REPO / "outputs/nonoverlap_our_method_discovery3_live_20260508T185859Z/selected_nonoverlap_cases.csv"
PRIOR_PAL_CB_30 = REPO / "outputs/pal_vs_production_equiv_casebook_live_20260508T223635Z/selected_casebook_cases.csv"

# Pools
POOL_1 = REPO / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_casebook.csv"
POOL_2 = REPO / "outputs/final_paired_pal_external_preflight_20260505/fresh_candidate_cases.csv"

MAX_NEW_ACTUAL_CALLS = 900
SCREEN_BATCH = 50
FOLLOWUP_CAP = 25
TARGET_CUM_PAL_ONLY = 30
TARGET_CUM_DISAGREEMENT = 50
TARGET_CUM_USEFUL = 50
MAX_NEW_SCREENED = 300

def _read_ids(path: Path, id_key: str = "case_id") -> set[str]:
    if not path.is_file():
        return set()
    ids = set()
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get(id_key) or row.get("example_id") or "").strip()
            if cid:
                ids.add(cid)
    return ids

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=Path, default=None)
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"pal_vs_production_multibatch_relaxed_plan_{ts}")
    out.mkdir(parents=True, exist_ok=True)

    # 1. Load previous state
    prev_ids = _read_ids(PREV_CASEBOOK)
    with PREV_SUMMARY.open(encoding="utf-8") as f:
        prev_summ = json.load(f)

    # 2. Load exclusion sets
    matched_ids = _read_ids(MATCHED_50, "example_id") | _read_ids(MATCHED_50, "case_id")
    nonoverlap_ids = _read_ids(NONOVERLAP_30)
    prior_pal_ids = _read_ids(PRIOR_PAL_CB_30)

    # 3. Build candidate pool from POOL_1 and POOL_2
    pool_cases: dict[str, dict[str, str]] = {}

    def add_to_pool(path: Path, id_k: str, q_k: str, a_k: str):
        if not path.is_file():
            return
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cid = (row.get(id_k) or "").strip()
                q = (row.get(q_k) or "").strip()
                a = (row.get(a_k) or "").strip()
                if cid and q and a and cid not in prev_ids:
                    if cid not in pool_cases:
                        pool_cases[cid] = {"case_id": cid, "problem_text": q, "gold_answer": a, "source": str(path)}

    add_to_pool(POOL_1, "case_id", "question", "gold_answer")
    add_to_pool(POOL_2, "example_id", "question", "answer")

    # 4. Classify and inventory
    inv_pool = []
    overlap_inv = []
    
    fresh_count = 0
    matched_count = 0
    nonoverlap_count = 0
    prior_pal_count = 0

    ordered_ids = sorted(pool_cases.keys(), key=lambda x: (int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else 0, x))

    for cid in ordered_ids:
        case = pool_cases[cid]
        overlaps = []
        if cid in matched_ids: overlaps.append("matched50")
        if cid in nonoverlap_ids: overlaps.append("prior_nonoverlap30")
        if cid in prior_pal_ids: overlaps.append("prior_pal_vs_prod30")
        
        if not overlaps:
            overlap_src = "fresh"
            fresh_count += 1
        elif len(overlaps) > 1:
            overlap_src = "multiple_overlap"
        else:
            overlap_src = overlaps[0]
            if overlap_src == "matched50": matched_count += 1
            elif overlap_src == "prior_nonoverlap30": nonoverlap_count += 1
            elif overlap_src == "prior_pal_vs_prod30": prior_pal_count += 1

        inv_pool.append({
            **case,
            "overlap_source": overlap_src,
            "eligible": "yes"
        })
        overlap_inv.append({
            "case_id": cid,
            "overlap_source": overlap_src,
            "matched50": "yes" if cid in matched_ids else "no",
            "prior_nonoverlap30": "yes" if cid in nonoverlap_ids else "no",
            "prior_pal_vs_prod30": "yes" if cid in prior_pal_ids else "no"
        })

    # 5. Write files
    with (out / "relaxed_candidate_pool_inventory.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "problem_text", "gold_answer", "source", "overlap_source", "eligible"])
        w.writeheader()
        w.writerows(inv_pool)

    with (out / "relaxed_exclusion_and_overlap_inventory.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "overlap_source", "matched50", "prior_nonoverlap30", "prior_pal_vs_prod30"])
        w.writeheader()
        w.writerows(overlap_inv)

    # 6. Plan batches
    plan_rows = []
    n_batches = (len(inv_pool) + SCREEN_BATCH - 1) // SCREEN_BATCH
    for b in range(1, n_batches + 1):
        start = (b - 1) * SCREEN_BATCH
        count = min(SCREEN_BATCH, len(inv_pool) - start)
        plan_rows.append({
            "batch_id": b,
            "planned_pal_screen_count": count,
            "planned_production_followup_cap": FOLLOWUP_CAP,
            "est_calls": count + FOLLOWUP_CAP * 4
        })
    
    with (out / "relaxed_multibatch_collection_plan.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["batch_id", "planned_pal_screen_count", "planned_production_followup_cap", "est_calls"])
        w.writeheader()
        w.writerows(plan_rows)

    # 7. Manifest
    manifest = {
        "previous_live_dir": str(PREV_LIVE_DIR),
        "previous_screened_cases": prev_summ["screened_cases"],
        "previous_followup_cases": prev_summ["followup_cases"],
        "previous_pal_only_count": prev_summ["pal_only_count"],
        "previous_disagreement_count": prev_summ["disagreement_count"],
        "previous_useful_selector_case_count": prev_summ["useful_selector_case_count"],
        "relaxed_candidate_pool_size": len(inv_pool),
        "fresh_candidate_count": fresh_count,
        "matched50_overlap_allowed_count": matched_count,
        "prior_nonoverlap30_overlap_allowed_count": nonoverlap_count,
        "prior_pal_vs_prod30_overlap_allowed_count": prior_pal_count,
        "planned_screen_batch_size": SCREEN_BATCH,
        "planned_followup_batch_size_max": FOLLOWUP_CAP,
        "target_cumulative_pal_only_count": TARGET_CUM_PAL_ONLY,
        "target_cumulative_disagreement_count": TARGET_CUM_DISAGREEMENT,
        "target_cumulative_useful_selector_case_count": TARGET_CUM_USEFUL,
        "max_new_screened_cases": MAX_NEW_SCREENED,
        "max_new_actual_calls": MAX_NEW_ACTUAL_CALLS,
        "estimated_calls_first_batch": SCREEN_BATCH + FOLLOWUP_CAP * 4,
        "all_candidates_have_problem_text": all(bool(c["problem_text"]) for c in inv_pool),
        "all_candidates_have_gold": all(bool(c["gold_answer"]) for c in inv_pool),
        "ready_for_live_loop": len(inv_pool) >= 30
    }
    with (out / "relaxed_plan_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # 8. Report
    report = f"""# Relaxed PAL vs production_equiv multi-batch casebook plan

- **Previous live dir:** `{PREV_LIVE_DIR.name}`
- **Previous useful cases:** pal_only={manifest['previous_pal_only_count']}, disagreement={manifest['previous_disagreement_count']}, useful={manifest['previous_useful_selector_case_count']}
- **Relaxed pool size:** {manifest['relaxed_candidate_pool_size']} (fresh={fresh_count}, matched50={matched_count}, others={nonoverlap_count + prior_pal_count})
- **Targets:** cumulative pal_only>={TARGET_CUM_PAL_ONLY}, disagreement>={TARGET_CUM_DISAGREEMENT}
- **Caps:** new screened<={MAX_NEW_SCREENED}, new calls<={MAX_NEW_ACTUAL_CALLS}
- **Ready:** {manifest['ready_for_live_loop']}
"""
    (out / "relaxed_plan_report.md").write_text(report, encoding="utf-8")

    print(out)
    return 0

if __name__ == "__main__":
    sys.exit(main())
