#!/usr/bin/env python3
"""No-API plan: PAL vs production_equiv multi-batch casebook collection pool and exclusions."""

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

MATCHED_50 = REPO / "outputs/main_table_core4_baselines_50case_checkpoint_20260508T174557Z/selected_50case_core4_baseline_cases.csv"
NONOVERLAP_30 = REPO / "outputs/nonoverlap_our_method_discovery3_live_20260508T185859Z/selected_nonoverlap_cases.csv"
PRIOR_PAL_CASEBOOK = REPO / "outputs/pal_vs_production_equiv_casebook_live_20260508T223635Z/selected_casebook_cases.csv"
CASEBOOK_SOURCE = REPO / "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/all_casebook.csv"
CASEBOOK_FALLBACK = REPO / "outputs/stage3_tale_s1_pilot_readiness_20260508T032919Z/stage3_pilot_cases.csv"

MAX_ACTUAL_CALLS = 900
SCREEN_BATCH = 50
FOLLOWUP_CAP = 25
TARGET_PAL_ONLY = 30
TARGET_DISAGREEMENT = 50
MAX_SCREENED = 300
EST_FIRST_BATCH = SCREEN_BATCH + FOLLOWUP_CAP * 4  # 150 upper bound


def _read_ids_csv(path: Path, id_key: str = "case_id") -> set[str]:
    if not path.is_file():
        return set()
    out: set[str] = set()
    for row in csv.DictReader(path.open(encoding="utf-8")):
        cid = str(row.get(id_key) or row.get("example_id") or "").strip()
        if cid:
            out.add(cid)
    return out


def _load_book(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _row_ok(r: dict[str, str]) -> bool:
    cid = (r.get("case_id") or "").strip()
    q = (r.get("problem_text") or r.get("question") or "").strip()
    g = str(r.get("gold_answer") or r.get("answer") or "").strip()
    return bool(cid and q and g)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", type=Path, default=None)
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_dir or (REPO / "outputs" / f"pal_vs_production_multibatch_casebook_plan_{ts}")
    out.mkdir(parents=True, exist_ok=True)

    matched = _read_ids_csv(MATCHED_50, "example_id") | _read_ids_csv(MATCHED_50, "case_id")
    nonoverlap = _read_ids_csv(NONOVERLAP_30)
    prior_pal_cb = _read_ids_csv(PRIOR_PAL_CASEBOOK)

    book_path = CASEBOOK_SOURCE if CASEBOOK_SOURCE.is_file() else CASEBOOK_FALLBACK
    book = _load_book(book_path)
    # Normalize keys for fallback CSV
    norm_rows: list[dict[str, str]] = []
    for r in book:
        cid = (r.get("case_id") or r.get("example_id") or "").strip()
        q = (r.get("question") or r.get("problem_text") or "").strip()
        g = str(r.get("gold_answer") or r.get("answer") or "").strip()
        norm_rows.append({"case_id": cid, "question": q, "gold_answer": g, "_src": str(book_path)})

    exclusion_union = matched | nonoverlap | prior_pal_cb

    inv_pool: list[dict[str, str]] = []
    for r in norm_rows:
        cid = r["case_id"]
        if not cid:
            continue
        reason = ""
        if cid in matched:
            reason = "matched_50"
        elif cid in nonoverlap:
            reason = "prior_nonoverlap_30"
        elif cid in prior_pal_cb:
            reason = "prior_pal_vs_production_casebook_30"
        inv_pool.append(
            {
                "case_id": cid,
                "problem_text": r["question"].replace("\n", " ").replace("\r", " ").strip(),
                "gold_answer": r["gold_answer"].strip(),
                "source_artifact": r.get("_src", str(book_path)),
                "excluded_reason": reason,
                "eligible_for_multibatch_loop": "yes" if not reason else "no",
            }
        )

    with (out / "candidate_pool_inventory.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(inv_pool[0].keys()) if inv_pool else ["case_id"])
        w.writeheader()
        w.writerows(inv_pool)

    excl_rows: list[dict[str, str]] = []
    for cid in sorted(matched):
        excl_rows.append({"exclusion_source": "matched_50_core4", "case_id": cid})
    for cid in sorted(nonoverlap):
        excl_rows.append({"exclusion_source": "nonoverlap_our_method_discovery3_live_20260508T185859Z", "case_id": cid})
    for cid in sorted(prior_pal_cb):
        excl_rows.append({"exclusion_source": "pal_vs_production_equiv_casebook_live_20260508T223635Z", "case_id": cid})
    with (out / "exclusion_set_inventory.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["exclusion_source", "case_id"])
        w.writeheader()
        w.writerows(excl_rows)

    eligible = [r for r in inv_pool if r["eligible_for_multibatch_loop"] == "yes" and _row_ok(r)]
    # Dedupe by case_id (keep first)
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for r in eligible:
        if r["case_id"] in seen:
            continue
        seen.add(r["case_id"])
        deduped.append(r)
    deduped.sort(key=lambda x: (int(x["case_id"].split("_")[-1]) if x["case_id"].split("_")[-1].isdigit() else 0, x["case_id"]))

    n_batches = (len(deduped) + SCREEN_BATCH - 1) // SCREEN_BATCH if deduped else 0
    plan_rows = []
    for b in range(1, max(1, n_batches) + 1):
        start = (b - 1) * SCREEN_BATCH
        if start >= len(deduped):
            break
        plan_rows.append(
            {
                "batch_id": str(b),
                "planned_pal_screen_count": str(min(SCREEN_BATCH, len(deduped) - start)),
                "planned_production_followup_cap": str(FOLLOWUP_CAP),
                "estimated_logical_calls_upper_bound": str(min(SCREEN_BATCH, len(deduped) - start) + FOLLOWUP_CAP * 4),
                "notes": "PAL screen first; production_equiv follow-up on subset (<=25) with priority PAL-correct-clean.",
            }
        )
    with (out / "multibatch_collection_plan.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(plan_rows[0].keys()) if plan_rows else ["batch_id"])
        w.writeheader()
        w.writerows(plan_rows)

    all_text = all(bool(r.get("problem_text")) for r in deduped)
    all_gold = all(bool(r.get("gold_answer")) for r in deduped)
    no_dup = len({r["case_id"] for r in deduped}) == len(deduped)
    overlap_matched = sum(1 for r in deduped if r["case_id"] in matched)

    pool_size = len(deduped)
    ready = bool(
        pool_size >= 30
        and all_text
        and all_gold
        and no_dup
        and overlap_matched == 0
        and EST_FIRST_BATCH <= 200
    )
    if pool_size >= 50:
        ready = ready and True

    manifest = {
        "timestamp_utc": ts,
        "candidate_pool_size": pool_size,
        "excluded_matched50_count": len(matched),
        "excluded_prior_nonoverlap_count": len(nonoverlap),
        "excluded_prior_pal_casebook_count": len(prior_pal_cb),
        "planned_screen_batch_size": SCREEN_BATCH,
        "planned_followup_batch_size_max": FOLLOWUP_CAP,
        "target_pal_only_count": TARGET_PAL_ONLY,
        "target_disagreement_count": TARGET_DISAGREEMENT,
        "max_screened_cases": MAX_SCREENED,
        "max_actual_calls": MAX_ACTUAL_CALLS,
        "estimated_calls_first_batch": EST_FIRST_BATCH,
        "all_candidates_have_problem_text": bool(all_text and pool_size > 0),
        "all_candidates_have_gold": bool(all_gold and pool_size > 0),
        "no_duplicate_case_ids": no_dup,
        "overlap_with_matched50_in_eligible_pool": overlap_matched,
        "ready_for_live_loop": ready,
        "primary_case_pool_path": str(book_path.resolve()),
        "cohere_api_key_required": True,
    }
    (out / "multibatch_plan_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    report = "\n".join(
        [
            "# PAL vs production_equiv multi-batch casebook plan",
            "",
            f"- **Eligible candidate pool size:** {pool_size}",
            f"- **Excluded (matched-50):** {len(matched)} ids",
            f"- **Excluded (prior nonoverlap 30):** {len(nonoverlap)} ids",
            f"- **Excluded (prior PAL casebook 30):** {len(prior_pal_cb)} ids",
            f"- **Screen batch size:** {SCREEN_BATCH} PAL calls; **follow-up cap:** {FOLLOWUP_CAP} production runs (budget 4 calls each, upper bound).",
            f"- **First batch estimated logical calls (upper bound):** {EST_FIRST_BATCH} (<=200 preflight gate).",
            f"- **Global cap:** {MAX_ACTUAL_CALLS} logical Cohere calls; max screened {MAX_SCREENED}.",
            f"- **Stop targets:** pal_only>={TARGET_PAL_ONLY}, disagreement>={TARGET_DISAGREEMENT}, or caps.",
            f"- **ready_for_live_loop:** {ready}",
            "",
            "## Preflight before API",
            "",
            "- Set `COHERE_API_KEY`.",
            "- Run `scripts/run_pal_vs_production_multibatch_casebook_live.py --plan-dir <this_dir>`.",
        ]
    )
    (out / "multibatch_plan_report.md").write_text(report + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
