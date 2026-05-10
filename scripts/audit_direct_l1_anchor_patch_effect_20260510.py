import csv
import json
import os
import re
from collections import Counter, defaultdict

def normalize_numeric(val):
    if val is None:
        return None
    try:
        s = re.sub(r'[^0-9.\\-]', '', str(val))
        if not s:
            return None
        f = float(s)
        if f.is_integer():
            return int(f)
        return f
    except ValueError:
        return None

def normalize_answer_group_key(val):
    num = normalize_numeric(val)
    if num is None:
        return "__unknown__"
    return str(num)

def audit_patch_effect():
    analysis_csv = "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
    diagnostic_jsonl = "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl"
    
    per_example_sources = [
        "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/cohere_real_model_cost_normalized_validation_20260507T161935Z/per_example_records.jsonl",
        "outputs/cohere_track_b_ab_pilot_30case_20260507T204409Z/cohere_real_model_cost_normalized_validation_live_run_20260507T204409Z/per_example_records.jsonl",
        "outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/cohere_real_model_cost_normalized_validation_20260506T194114Z/per_example_records.jsonl"
    ]

    casebooks = [
        "outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/relaxed_pal_vs_prod_casebook_new.csv"
    ]

    cases_by_id = {}
    if os.path.exists(analysis_csv):
        with open(analysis_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row['case_id']
                cases_by_id[cid] = row
                cases_by_id[cid]['hybrid_seed_answer'] = None
                cases_by_id[cid]['external_l1_exact'] = None
                if row.get('external_contrast') == "L1 correct, ours wrong":
                    cases_by_id[cid]['external_l1_exact'] = '1'

    # Load from casebooks
    for cb in casebooks:
        if not os.path.exists(cb):
            continue
        with open(cb, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row.get('case_id')
                if cid in cases_by_id:
                    pa = row.get('pal_answer')
                    if pa:
                        cases_by_id[cid]['hybrid_seed_answer'] = pa
                    if row.get('pal_correct') == '1':
                        cases_by_id[cid]['external_l1_exact'] = '1'

    # Load hybrid seed answers from per_example_records.jsonl
    for src in per_example_sources:
        if not os.path.exists(src):
            continue
        with open(src, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    cid = data.get('example_id')
                    if cid in cases_by_id:
                        rm = data.get('result_metadata', {})
                        hsa = rm.get('direct_hybrid_seed_answer')
                        if hsa:
                            cases_by_id[cid]['hybrid_seed_answer'] = hsa
                        if 'exact_match' in data:
                            cases_by_id[cid]['external_l1_exact'] = str(data['exact_match'])
                except:
                    continue

    # Load from diagnostic cases
    if os.path.exists(diagnostic_jsonl):
        with open(diagnostic_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                cid = data.get('case_id')
                if cid in cases_by_id:
                    # In diagnostic cases, we might have pal_answer which is L1-like
                    if not cases_by_id[cid]['hybrid_seed_answer']:
                        cases_by_id[cid]['hybrid_seed_answer'] = data.get('pal_answer')

    audit_results = []
    summary = {
        "total_cases": len(cases_by_id),
        "cases_with_anchor": 0,
        "diversity_increased": 0,
        "gold_recovered": 0,
        "remains_gold_absent": 0,
        "anchor_differs_from_wrong": 0,
        "anchor_matches_l1_max": 0,
        "by_question_type": defaultdict(lambda: Counter()),
        "by_error_type": defaultdict(lambda: Counter())
    }

    for cid, case in cases_by_id.items():
        q_type = case.get('question_type', 'unknown')
        e_type = case.get('error_type', 'unknown')
        gold_num = normalize_numeric(case.get('gold'))
        pred_num = normalize_numeric(case.get('predicted'))
        anchor_raw = case.get('hybrid_seed_answer')
        anchor_num = normalize_numeric(anchor_raw)
        
        l1_exact = case.get('external_l1_exact')
        
        has_anchor = anchor_num is not None
        if has_anchor:
            summary["cases_with_anchor"] += 1
        
        # Diversity before: num_candidate_groups (from analysis csv)
        try:
            div_before = int(case.get('num_candidate_groups', 0))
        except:
            div_before = 0
            
        # Diversity after: if anchor forms new group
        anchor_group = normalize_answer_group_key(anchor_raw) if anchor_raw else None
        
        # We don't have the full candidate pool groups here, but we know if it was low diversity (1 group)
        # If div_before is 0 or 1, and we add an anchor that differs from pred_num, it increases.
        
        div_after = div_before
        new_group = False
        if has_anchor:
            # Simple proxy: if anchor != predicted, it's likely a new group (or increases diversity)
            if normalize_answer_group_key(anchor_raw) != normalize_answer_group_key(case.get('predicted')):
                div_after = div_before + 1
                new_group = True
                summary["diversity_increased"] += 1
                summary["anchor_differs_from_wrong"] += 1

        recovered = False
        if has_anchor and gold_num is not None and anchor_num == gold_num:
            recovered = True
            summary["gold_recovered"] += 1
        
        if not recovered:
            summary["remains_gold_absent"] += 1

        if has_anchor and l1_exact == '1':
            summary["anchor_matches_l1_max"] += 1

        audit_results.append({
            "case_id": cid,
            "question_type": q_type,
            "error_type": e_type,
            "gold": gold_num,
            "original_predicted": pred_num,
            "anchor_answer": anchor_num,
            "has_anchor": int(has_anchor),
            "diversity_before": div_before,
            "diversity_after": div_after,
            "diversity_increased": int(new_group),
            "gold_recovered": int(recovered),
            "anchor_matches_l1_max": int(has_anchor and l1_exact == '1'),
            "external_l1_exact": l1_exact
        })
        
        # Update nested summary
        s_key = "recovered" if recovered else "remains_absent"
        summary["by_question_type"][q_type][s_key] += 1
        summary["by_error_type"][e_type][s_key] += 1

    output_csv = "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv"
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        if audit_results:
            writer = csv.DictWriter(f, fieldnames=audit_results[0].keys())
            writer.writeheader()
            writer.writerows(audit_results)

    output_json = "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_summary_20260510.json"
    # Convert defaultdict/Counter to dict for JSON
    summary_json = dict(summary)
    summary_json["by_question_type"] = {k: dict(v) for k, v in summary["by_question_type"].items()}
    summary_json["by_error_type"] = {k: dict(v) for k, v in summary["by_error_type"].items()}
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    print(f"Audit complete. CSV: {output_csv}, JSON: {output_json}")

if __name__ == "__main__":
    audit_patch_effect()
