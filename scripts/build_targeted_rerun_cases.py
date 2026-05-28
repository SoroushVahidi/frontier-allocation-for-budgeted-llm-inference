"""Build targeted failure-case and regression-check sets for rerun.

Uses only existing completed Cohere and Mistral artifacts.
No API calls. No Cerebras touch. No frozen policy modification.
All outputs: outputs/targeted_failure_case_rerun_prep_and_mistral_probe_20260523/
"""

import csv
import json
import random
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "outputs" / "targeted_failure_case_rerun_prep_and_mistral_probe_20260523"
OUT.mkdir(parents=True, exist_ok=True)

COHERE_TABLE = (
    REPO / "outputs"
    / "cohere_mistral_failure_pattern_hypotheses_20260523"
    / "cohere_failure_pattern_table.csv"
)
MISTRAL_TABLE = (
    REPO / "outputs"
    / "cohere_mistral_failure_pattern_hypotheses_20260523"
    / "mistral_failure_pattern_table.csv"
)
COHERE_JSONL = (
    REPO / "outputs"
    / "canonical_final300_cohere_contract_matched_live_20260523T181948Z"
    / "cohere_real_model_cost_normalized_validation_20260523T181948Z"
    / "per_example_records.jsonl"
)
MISTRAL_JSONL = (
    REPO / "outputs"
    / "mistral_frozen_agreement_only_2of3_validation_20260523T145416Z"
    / "cohere_real_model_cost_normalized_validation_20260523T145416Z"
    / "per_example_records.jsonl"
)


def load_table(path: Path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return rows


def i(row, key):
    try:
        return int(row.get(key, 0))
    except (ValueError, TypeError):
        return 0


def load_questions(jsonl_path: Path):
    """Return {example_id: question_text} from raw JSONL."""
    q = {}
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            eid = rec["example_id"]
            if eid not in q:
                q[eid] = rec.get("question", "")
    return q


def make_base_row(row, questions, provider, case_sets, reason):
    eid = row["example_id"]
    return {
        "provider": provider,
        "example_id": eid,
        "case_sets": "|".join(sorted(case_sets)),
        "question": questions.get(eid, "")[:300],
        "gold": row.get("gold", ""),
        "frontier_ans": row.get("f_a", ""),
        "l1_ans": row.get("l1_a", ""),
        "s1_ans": row.get("s1_a", ""),
        "tale_ans": row.get("ta_a", ""),
        "frontier_ok": i(row, "f_ok"),
        "l1_ok": i(row, "l1_ok"),
        "s1_ok": i(row, "s1_ok"),
        "tale_ok": i(row, "ta_ok"),
        "agr_ans": row.get("agr_a", ""),
        "agr_ok": i(row, "agr_ok"),
        "pool_ans": row.get("pool_a", ""),
        "pool_ok": i(row, "pool_ok"),
        "oracle_ok": i(row, "oracle_ok"),
        "majority_pattern": row.get("majority_pattern", ""),
        "lt_agree": i(row, "lt_agree"),
        "lt_wrong": i(row, "lt_wrong"),
        "lt_wrong_s1_correct": i(row, "lt_wrong_s1_correct"),
        "s1_isolated": i(row, "s1_isolated"),
        "all_wrong": i(row, "all_wrong"),
        "pool_fail_class": row.get("pool_fail_class", ""),
        "agr_fail_class": row.get("agr_fail_class", ""),
        "reason_selected": reason,
        "rerun_recommended": "yes",
    }


def write_csv(path: Path, rows, fieldnames=None):
    if not rows:
        path.write_text("")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path.name} ({len(rows)} rows)")


def write_jsonl(path: Path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"  wrote {path.name} ({len(rows)} rows)")


def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[start] {ts}")

    print("Loading tables...")
    cohere_rows = load_table(COHERE_TABLE)
    mistral_rows = load_table(MISTRAL_TABLE)
    print(f"  Cohere: {len(cohere_rows)} rows, Mistral: {len(mistral_rows)} rows")

    print("Loading question texts...")
    cohere_q = load_questions(COHERE_JSONL)
    mistral_q = load_questions(MISTRAL_JSONL)

    # ── Step 3: build failure and regression candidate sets ───────────────────

    # --- Mistral failure sets ---
    mistral_case_labels = {r["example_id"]: set() for r in mistral_rows}
    mistral_reasons = {r["example_id"]: [] for r in mistral_rows}

    for row in mistral_rows:
        eid = row["example_id"]
        s1_ok = i(row, "s1_ok")
        agr_ok = i(row, "agr_ok")
        pool_ok = i(row, "pool_ok")
        s1_isolated = i(row, "s1_isolated")
        lt_wrong_s1 = i(row, "lt_wrong_s1_correct")
        maj_pat = row.get("majority_pattern", "")
        pool_fail = row.get("pool_fail_class", "")
        agr_fail = row.get("agr_fail_class", "")
        f_ok = i(row, "f_ok")
        oracle_ok = i(row, "oracle_ok")
        all_wrong = i(row, "all_wrong")

        if agr_ok == 0 and s1_ok == 1:
            mistral_case_labels[eid].add("mistral_agreement_wrong_s1_correct")
            mistral_reasons[eid].append("agreement-only wrong, S1 correct")

        if pool_ok == 0 and s1_ok == 1:
            mistral_case_labels[eid].add("mistral_pooled4_wrong_s1_correct")
            mistral_reasons[eid].append("pooled-4 wrong, S1 correct")

        if s1_ok == 1 and s1_isolated == 1 and pool_ok == 0:
            mistral_case_labels[eid].add("mistral_best_source_isolated_correct_pooled_wrong")
            mistral_reasons[eid].append("S1 isolated+correct, pooled-4 wrong")

        if pool_fail == "E_no_majority_frontier_fallback_wrong" or agr_fail == "A_no_ext_majority_keep_wrong_frontier":
            mistral_case_labels[eid].add("mistral_no_majority_frontier_fallback_wrong")
            mistral_reasons[eid].append("no majority, wrong frontier fallback")

        if lt_wrong_s1 == 1:
            mistral_case_labels[eid].add("mistral_l1_tale_wrong_majority_s1_correct")
            mistral_reasons[eid].append("L1+TALE agree wrong while S1 correct")

    # --- Cohere failure sets ---
    cohere_case_labels = {r["example_id"]: set() for r in cohere_rows}
    cohere_reasons = {r["example_id"]: [] for r in cohere_rows}

    for row in cohere_rows:
        eid = row["example_id"]
        pool_ok = i(row, "pool_ok")
        agr_ok = i(row, "agr_ok")
        oracle_ok = i(row, "oracle_ok")
        all_wrong = i(row, "all_wrong")
        best_correct_pool_wrong = i(row, "best_correct_pool_wrong")
        pool_fail = row.get("pool_fail_class", "")
        maj_pat = row.get("majority_pattern", "")
        f_ok = i(row, "f_ok")

        if pool_ok == 0 and oracle_ok == 1:
            cohere_case_labels[eid].add("cohere_pooled4_wrong_oracle_correct")
            cohere_reasons[eid].append("pooled-4 wrong, oracle correct")

        if pool_fail == "E_no_majority_frontier_fallback_wrong" or maj_pat == "all_different":
            if pool_ok == 0:
                cohere_case_labels[eid].add("cohere_no_majority_frontier_fallback_wrong")
                cohere_reasons[eid].append("no majority / all-different, wrong frontier fallback")

        if agr_ok == 0 and pool_ok == 1:
            cohere_case_labels[eid].add("cohere_agreement_wrong_pooled4_correct")
            cohere_reasons[eid].append("agreement-only wrong, pooled-4 correct")

        if best_correct_pool_wrong == 1:
            cohere_case_labels[eid].add("cohere_best_source_isolated_correct_pooled_wrong")
            cohere_reasons[eid].append("best source correct but pooled-4 wrong")

        if all_wrong == 1:
            cohere_case_labels[eid].add("cohere_all_sources_wrong")
            cohere_reasons[eid].append("all four sources wrong (irreducible)")

    # ── Step 3: build output rows ─────────────────────────────────────────────
    mistral_fail_rows_map = {r["example_id"]: r for r in mistral_rows}
    cohere_fail_rows_map = {r["example_id"]: r for r in cohere_rows}

    all_failure_rows = []
    for eid, labels in mistral_case_labels.items():
        if not labels:
            continue
        row = mistral_fail_rows_map[eid]
        reason = "; ".join(mistral_reasons[eid])
        all_failure_rows.append(make_base_row(row, mistral_q, "mistral", labels, reason))

    for eid, labels in cohere_case_labels.items():
        if not labels:
            continue
        row = cohere_fail_rows_map[eid]
        reason = "; ".join(cohere_reasons[eid])
        all_failure_rows.append(make_base_row(row, cohere_q, "cohere", labels, reason))

    write_csv(OUT / "selected_failure_case_sets.csv", all_failure_rows)

    # ── Step 3: regression-check cases ───────────────────────────────────────
    random.seed(42)
    regression_rows = []

    # Mistral regression: S1 correct, mix of pool/agr correct+wrong
    mistral_s1_correct = [r for r in mistral_rows if i(r, "s1_ok") == 1]
    mistral_reg_s1 = random.sample(mistral_s1_correct, min(15, len(mistral_s1_correct)))
    for row in mistral_reg_s1:
        regression_rows.append(make_base_row(
            row, mistral_q, "mistral",
            {"mistral_regression_s1_correct"},
            "regression-check: S1 correct; test regime_selector routes to S1 without regressing"
        ))

    # Cohere regression: pooled-4 correct, include fragile cases
    cohere_pool_correct = [r for r in cohere_rows if i(r, "pool_ok") == 1]
    cohere_reg = random.sample(cohere_pool_correct, min(15, len(cohere_pool_correct)))
    for row in cohere_reg:
        regression_rows.append(make_base_row(
            row, cohere_q, "cohere",
            {"cohere_regression_pooled4_correct"},
            "regression-check: pooled-4 correct; verify new rules do not regress"
        ))

    for r in regression_rows:
        r["rerun_recommended"] = "yes_regression"

    write_csv(OUT / "selected_regression_check_cases.csv", regression_rows)

    # ── Step 4: choose targeted rerun subset ──────────────────────────────────
    # Mistral: priority failure sets + regression
    mistral_failure_targets = {
        "mistral_agreement_wrong_s1_correct",
        "mistral_pooled4_wrong_s1_correct",
        "mistral_no_majority_frontier_fallback_wrong",
        "mistral_best_source_isolated_correct_pooled_wrong",
        "mistral_l1_tale_wrong_majority_s1_correct",
    }
    mistral_rerun_eids = set()
    for row in all_failure_rows:
        if row["provider"] != "mistral":
            continue
        labels = set(row["case_sets"].split("|"))
        if labels & mistral_failure_targets:
            mistral_rerun_eids.add(row["example_id"])

    # add regression cases for Mistral
    mistral_reg_eids = set()
    for row in regression_rows:
        if row["provider"] == "mistral":
            mistral_reg_eids.add(row["example_id"])

    # cap total at 40 unique failure + 15 regression = max 55 (but keep separate)
    mistral_rerun_eids = set(list(mistral_rerun_eids)[:40])
    mistral_reg_eids = set(list(mistral_reg_eids)[:15])
    mistral_all_eids = mistral_rerun_eids | mistral_reg_eids

    # Cohere: candidate set only, not launched
    cohere_fail_targets = {
        "cohere_pooled4_wrong_oracle_correct",
        "cohere_no_majority_frontier_fallback_wrong",
        "cohere_agreement_wrong_pooled4_correct",
        "cohere_best_source_isolated_correct_pooled_wrong",
    }
    cohere_candidate_eids = set()
    for row in all_failure_rows:
        if row["provider"] != "cohere":
            continue
        labels = set(row["case_sets"].split("|"))
        if labels & cohere_fail_targets:
            cohere_candidate_eids.add(row["example_id"])
    cohere_candidate_eids = set(list(cohere_candidate_eids)[:30])

    print(f"\nMistral rerun: {len(mistral_rerun_eids)} failure + {len(mistral_reg_eids)} regression = {len(mistral_all_eids)} unique cases")
    print(f"Cohere candidate (not launched): {len(cohere_candidate_eids)} cases")

    # Build Mistral rerun JSONL (exact-cases format: {example_id, question?, split?})
    mistral_rerun_records = []
    for eid in sorted(mistral_all_eids):
        row = mistral_fail_rows_map.get(eid) or next((r for r in regression_rows if r["example_id"] == eid and r["provider"] == "mistral"), None)
        case_type = "failure" if eid in mistral_rerun_eids else "regression"
        mistral_rerun_records.append({
            "example_id": eid,
            "dataset": "openai/gsm8k",
            "seed": 71,
            "split": "train",
            "case_type": case_type,
        })
    write_jsonl(OUT / "mistral_targeted_rerun_cases.jsonl", mistral_rerun_records)

    cohere_candidate_records = []
    for eid in sorted(cohere_candidate_eids):
        cohere_candidate_records.append({
            "example_id": eid,
            "dataset": "openai/gsm8k",
            "seed": 71,
            "split": "train",
            "case_type": "failure",
        })
    write_jsonl(OUT / "cohere_paid_rerun_candidate_cases.jsonl", cohere_candidate_records)

    # Build manifest CSV
    manifest_rows = []
    for rec in mistral_rerun_records:
        eid = rec["example_id"]
        labels = []
        if eid in {r["example_id"] for r in all_failure_rows if r["provider"] == "mistral"}:
            fr = next(r for r in all_failure_rows if r["example_id"] == eid and r["provider"] == "mistral")
            labels = fr["case_sets"].split("|")
        else:
            labels = ["mistral_regression_s1_correct"]
        manifest_rows.append({
            "provider": "mistral",
            "example_id": eid,
            "case_type": rec["case_type"],
            "case_sets": "|".join(labels),
            "rerun_provider": "mistral",
        })
    for rec in cohere_candidate_records:
        eid = rec["example_id"]
        labels = []
        if eid in {r["example_id"] for r in all_failure_rows if r["provider"] == "cohere"}:
            cr = next(r for r in all_failure_rows if r["example_id"] == eid and r["provider"] == "cohere")
            labels = cr["case_sets"].split("|")
        manifest_rows.append({
            "provider": "cohere",
            "example_id": eid,
            "case_type": "failure_candidate_not_launched",
            "case_sets": "|".join(labels),
            "rerun_provider": "cohere_NOT_LAUNCHED",
        })
    write_csv(OUT / "targeted_rerun_case_manifest.csv", manifest_rows)

    # ── Summary JSON ──────────────────────────────────────────────────────────
    mistral_set_counts = {}
    for row in all_failure_rows:
        if row["provider"] != "mistral":
            continue
        for lbl in row["case_sets"].split("|"):
            mistral_set_counts[lbl] = mistral_set_counts.get(lbl, 0) + 1

    cohere_set_counts = {}
    for row in all_failure_rows:
        if row["provider"] != "cohere":
            continue
        for lbl in row["case_sets"].split("|"):
            cohere_set_counts[lbl] = cohere_set_counts.get(lbl, 0) + 1

    summary = {
        "created_at": ts,
        "mistral_failure_set_counts": mistral_set_counts,
        "mistral_failure_cases_selected_for_rerun": len(mistral_rerun_eids),
        "mistral_regression_cases_selected": len(mistral_reg_eids),
        "mistral_total_rerun_cases": len(mistral_all_eids),
        "cohere_failure_set_counts": cohere_set_counts,
        "cohere_candidate_cases": len(cohere_candidate_eids),
        "cohere_rerun_launched": False,
        "cohere_rerun_note": "Cohere paid rerun NOT launched. Candidate cases prepared for future authorization.",
    }
    (OUT / "targeted_case_selection_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"  wrote targeted_case_selection_summary.json")
    print(f"\nMistral set counts: {mistral_set_counts}")
    print(f"Cohere set counts: {cohere_set_counts}")

    ts_end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[done] {ts_end}")

    return {
        "mistral_all_eids": mistral_all_eids,
        "mistral_rerun_eids": mistral_rerun_eids,
        "mistral_reg_eids": mistral_reg_eids,
        "cohere_candidate_eids": cohere_candidate_eids,
        "mistral_set_counts": mistral_set_counts,
        "cohere_set_counts": cohere_set_counts,
    }


if __name__ == "__main__":
    main()
