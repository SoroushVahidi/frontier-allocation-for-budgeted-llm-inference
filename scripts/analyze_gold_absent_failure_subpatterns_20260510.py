import csv
import json
import os
import re
from collections import Counter, defaultdict

def normalize_numeric(val):
    if val is None:
        return None
    try:
        s = re.sub(r'[^0-9.\-]', '', str(val))
        if not s:
            return None
        f = float(s)
        if f.is_integer():
            return int(f)
        return f
    except ValueError:
        return None

def infer_question_type(question):
    if not question:
        return "unknown"
    q = question.lower()
    if any(x in q for x in ["$", "cost", "price", "earned", "spent", "dollars", "cents", "paid"]):
        return "money/cost/revenue"
    if any(x in q for x in ["per hour", "per day", "speed", "miles per", "km/h", "rate", "each hour"]):
        return "rate/speed/work"
    if any(x in q for x in ["ratio", "proportion", "percentage", "%", "fraction", "half", "third", "quarter"]):
        return "ratio/proportion/percentage"
    if any(x in q for x in ["inches", "feet", "meters", "kilograms", "pounds", "conversion", "units", "cm", "km"]):
        return "unit conversion"
    if any(x in q for x in ["how many ways", "combinations", "arrangements", "choose"]):
        return "counting/combinatorics"
    if any(x in q for x in ["years from now", "ago", "days", "weeks", "months", "hours", "minutes", "seconds", "calendar"]):
        return "temporal/calendar"
    if any(x in q for x in ["remaining", "left", "unsold", "gave away", "remaining", "balance"]):
        return "inventory/remaining quantity"
    if any(x in q for x in ["area", "volume", "perimeter", "length", "width", "height", "geometry"]):
        return "geometry/measurement"
    if any(x in q for x in ["x +", "x -", "equation", "solve for x"]):
        return "algebra/equation setup"
    return "multi-step arithmetic"

def infer_error_type(case, gold_num, pred_num):
    notes = str(case.get('notes', '')).lower()
    diag = str(case.get('short_diagnosis', '')).lower()
    question = str(case.get('problem_text', '')).lower()
    
    if pred_num == 1 or pred_num == 0:
        if gold_num is not None and abs(float(gold_num)) > 1:
            return "structured extraction failure / fallback"

    if "stopped prematurely" in notes or "incomplete" in notes or "partial" in notes:
        return "premature intermediate answer"
    
    if gold_num is not None and pred_num is not None:
        nums_in_q = re.findall(r'\d+', question)
        if str(pred_num) in nums_in_q:
            return "premature intermediate answer (copied from problem)"
        
        if gold_num != 0 and pred_num != 0:
            ratio = float(pred_num) / float(gold_num)
            if abs(ratio - round(ratio)) < 1e-5 and round(ratio) > 1:
                return "counting/grouping off-by-factor (multiple)"
            inv_ratio = float(gold_num) / float(pred_num)
            if abs(inv_ratio - round(inv_ratio)) < 1e-5 and round(inv_ratio) > 1:
                return "counting/grouping off-by-factor (factor)"
            if abs(float(pred_num) + float(gold_num)) < 1e-5:
                return "wrong operation sign"

    if "mis-aligned objective" in notes or "wrong target" in notes:
        return "over-decomposition / lost global objective"
    if "extraction" in diag or "surfacing" in diag:
        return "parse/surfacing issue"
    if "arithmetic" in notes or "computation" in notes:
        return "arithmetic/reasoning-quality failure"
    
    return "unknown"

def load_extra_data(cases_by_id):
    sources = [
        "outputs/cohere_collect_pal_failure_cases_vs_3_external_20260507T161935Z/cohere_real_model_cost_normalized_validation_20260507T161935Z/per_example_records.jsonl",
        "outputs/cohere_paired_pal_retry_vs_external_l1_300case_poolfix_20260506/pal_results.csv",
        "outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z/pal_results.csv",
        "outputs/external_only_loss_collection_pal_vs_l1_round2_20260506T130225Z/pal_results.csv",
        "outputs/external_only_loss_collection_pal_vs_l1_round3_20260506T151731Z/pal_results.csv"
    ]
    
    for src in sources:
        if not os.path.exists(src):
            continue
        if src.endswith(".jsonl"):
            with open(src, "r", encoding="utf-8") as f:
                for line in f:
                    data = json.loads(line)
                    cid = data.get('example_id')
                    if cid in cases_by_id:
                        cases_by_id[cid]['problem_text'] = data.get('question', cases_by_id[cid].get('problem_text'))
                        cases_by_id[cid]['gold_answer'] = data.get('gold_answer_canonical', cases_by_id[cid].get('gold_answer'))
        elif src.endswith(".csv"):
            with open(src, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cid = row.get('example_id')
                    if cid in cases_by_id:
                        cases_by_id[cid]['problem_text'] = row.get('question', cases_by_id[cid].get('problem_text'))
                        cases_by_id[cid]['gold_answer'] = row.get('gold_answer', cases_by_id[cid].get('gold_answer'))
                        if 'exact_match' in row:
                            cases_by_id[cid]['external_l1_exact'] = row.get('exact_match')

def analyze_subpatterns():
    full_failures_path = "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
    diagnostic_cases_path = "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl"
    wrong_casebook_path = "outputs/failure_audit_l1_vs_k1_frontier_tiebreak_10case_20260505T004535Z/wrong_casebook.csv"
    
    cases_by_id = {}
    
    if os.path.exists(full_failures_path):
        with open(full_failures_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row['case_id']
                cases_by_id[cid] = row

    if os.path.exists(diagnostic_cases_path):
        with open(diagnostic_cases_path, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                cid = data['case_id']
                if cid in cases_by_id:
                    cases_by_id[cid].update(data)
                else:
                    cases_by_id[cid] = data

    if os.path.exists(wrong_casebook_path):
        with open(wrong_casebook_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row['example_id']
                if cid in cases_by_id:
                    cases_by_id[cid]['problem_text'] = row.get('question', cases_by_id[cid].get('problem_text'))
                    cases_by_id[cid]['gold_answer'] = row.get('gold_canonical', cases_by_id[cid].get('gold_answer'))
                    cases_by_id[cid]['selected_answer'] = row.get('k1_selected_canonical', cases_by_id[cid].get('selected_answer'))
                    cases_by_id[cid]['notes'] = row.get('classification_note', cases_by_id[cid].get('notes'))
                    cases_by_id[cid]['gold_present_in_candidate_pool'] = 'no' if row.get('k1_gold_in_tree') == '0' else 'yes'
                    cases_by_id[cid]['external_l1_exact'] = row.get('external_l1_exact')

    load_extra_data(cases_by_id)

    gold_absent_cases = [c for c in cases_by_id.values() if c.get('gold_present_in_candidate_pool') != 'yes' and c.get('evidence_completeness') == 'FULL']
    print(f"Total unique gold-absent cases analyzed: {len(gold_absent_cases)}")

    analysis_results = []
    summary = {
        "question_types": Counter(),
        "error_types": Counter(),
        "distance_buckets": Counter(),
        "candidate_diversity": Counter(),
        "external_l1_contrast": Counter()
    }

    for case in gold_absent_cases:
        cid = case.get('case_id') or case.get('example_id')
        question = case.get('problem_text', '')
        gold_raw = case.get('gold_answer', '')
        if '####' in str(gold_raw):
            gold_str = str(gold_raw).split('####')[-1].strip()
        else:
            gold_str = str(gold_raw).strip()
        
        gold_num = normalize_numeric(gold_str)
        pred_num = normalize_numeric(case.get('selected_answer'))
        
        q_type = infer_question_type(question)
        e_type = infer_error_type(case, gold_num, pred_num)
        
        abs_err = None
        rel_err = None
        dist_bucket = "unknown"
        if gold_num is not None and pred_num is not None:
            try:
                abs_err = abs(float(pred_num) - float(gold_num))
                rel_err = abs_err / max(1.0, abs(float(gold_num)))
                if abs_err == 0:
                    dist_bucket = "exact (unexpected)"
                elif rel_err < 0.1:
                    dist_bucket = "near (<10%)"
                elif rel_err < 0.5:
                    dist_bucket = "medium (10-50%)"
                else:
                    dist_bucket = "far (>50%)"
                
                if gold_num != 0 and pred_num != 0:
                    if abs(float(pred_num) / float(gold_num) - round(float(pred_num) / float(gold_num))) < 1e-5:
                        dist_bucket += " (multiple)"
                    elif abs(float(gold_num) / float(pred_num) - round(float(gold_num) / float(pred_num))) < 1e-5:
                        dist_bucket += " (factor)"
            except:
                pass

        cands = case.get('candidate_answers', [])
        if isinstance(cands, str):
            try:
                cands = eval(cands)
            except:
                cands = [cands]
        
        num_groups = len(set(str(c).strip() for c in cands))
        div_bucket = "low (1 group)" if num_groups <= 1 else "medium (2-3 groups)" if num_groups <= 3 else "high (4+ groups)"
        
        l1_correct = case.get('external_l1_exact')
        contrast = "unknown"
        if l1_correct == '1':
            contrast = "L1 correct, ours wrong"
        elif l1_correct == '0':
            contrast = "Both wrong"

        summary["question_types"][q_type] += 1
        summary["error_types"][e_type] += 1
        summary["distance_buckets"][dist_bucket] += 1
        summary["candidate_diversity"][div_bucket] += 1
        summary["external_l1_contrast"][contrast] += 1

        analysis_results.append({
            "case_id": cid,
            "question_type": q_type,
            "error_type": e_type,
            "gold": gold_num,
            "predicted": pred_num,
            "abs_error": abs_err,
            "rel_error": rel_err,
            "distance_bucket": dist_bucket,
            "num_candidate_groups": num_groups,
            "diversity_bucket": div_bucket,
            "external_contrast": contrast,
            "notes": case.get('notes', '')
        })

    output_csv = "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv"
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=analysis_results[0].keys())
        writer.writeheader()
        writer.writerows(analysis_results)

    output_json = "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_summary_20260510.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({
            "total_gold_absent": len(gold_absent_cases),
            "summary": {k: dict(v) for k, v in summary.items()}
        }, f, indent=2)

    print(f"Analysis complete. CSV: {output_csv}, JSON: {output_json}")

if __name__ == "__main__":
    analyze_subpatterns()
