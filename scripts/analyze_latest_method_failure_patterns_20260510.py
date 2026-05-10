import csv
import json
import os
from collections import Counter, defaultdict

def analyze_patterns():
    full_failures_path = "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv"
    diagnostic_cases_path = "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl"
    
    # 1. Load FULL failures list
    full_failures = []
    if os.path.exists(full_failures_path):
        with open(full_failures_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            full_failures = list(reader)
    
    print(f"Total FULL failure records: {len(full_failures)}")
    
    unique_ids = {row['case_id'] for row in full_failures}
    print(f"Unique FULL case IDs: {len(unique_ids)}")
    
    # 2. Analyze failure families from the CSV
    family_counts = Counter(row['failure_family'] for row in full_failures)
    print("\nFailure Family Counts (from CSV):")
    for fam, count in family_counts.most_common():
        print(f"  {fam}: {count}")
    
    # 3. Load deep diagnostic metadata
    diagnostic_cases = []
    if os.path.exists(diagnostic_cases_path):
        with open(diagnostic_cases_path, "r", encoding="utf-8") as f:
            for line in f:
                diagnostic_cases.append(json.loads(line))
    
    print(f"\nDeep diagnostic cases loaded: {len(diagnostic_cases)}")
    
    # 4. Analyze gold presence and correctness availability
    gold_present_count = 0
    correct_alternate_available_count = 0
    pal_correct_but_not_selected = 0
    dr_correct_but_not_selected = 0
    frontier_correct_but_not_selected = 0
    
    for case in diagnostic_cases:
        if case.get('gold_present_in_candidate_pool') == 'yes':
            gold_present_count += 1
        if case.get('correct_alternate_available') == 'yes':
            correct_alternate_available_count += 1
            
        gold = str(case.get('gold_answer')).strip()
        pal_ans = str(case.get('pal_answer')).strip()
        dr_ans = str(case.get('direct_reserve_answer')).strip()
        frontier_ans = str(case.get('frontier_answer')).strip()
        selected = str(case.get('selected_answer')).strip()
        
        if pal_ans == gold and selected != gold:
            pal_correct_but_not_selected += 1
        if dr_ans == gold and selected != gold:
            dr_correct_but_not_selected += 1
        if frontier_ans == gold and selected != gold:
            frontier_correct_but_not_selected += 1

    print(f"\nGold Presence Analysis (N={len(diagnostic_cases)}):")
    print(f"  Gold present in candidate pool: {gold_present_count}")
    print(f"  Correct alternate available: {correct_alternate_available_count}")
    print(f"  PAL correct but not selected: {pal_correct_but_not_selected}")
    print(f"  DR correct but not selected: {dr_correct_but_not_selected}")
    print(f"  Frontier correct but not selected: {frontier_correct_but_not_selected}")

    # 5. Analyze selected source
    source_counts = Counter(case.get('selected_source') for case in diagnostic_cases)
    print("\nSelected Answer Source (Deep Diagnostics):")
    for src, count in source_counts.most_common():
        print(f"  {src}: {count}")

    # 6. Analyze structural commit reasons
    reason_counts = Counter(case.get('structural_commit_reason') for case in diagnostic_cases)
    print("\nStructural Commit Reasons:")
    for reason, count in reason_counts.most_common():
        print(f"  {reason}: {count}")

if __name__ == "__main__":
    analyze_patterns()
