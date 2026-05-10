import os
import json
import csv
import hashlib
import re
from pathlib import Path

# Configuration
REPO_ROOT = os.path.expanduser("~/frontier-allocation-for-budgeted-llm-inference")
ARCHIVE_ROOT = os.path.expanduser("~/frontier-allocation-old-folders-archive-20260510")
SKIP_DIRS = {
    ".cache", ".conda", ".local", ".npm", ".cursor", ".vscode", ".git", 
    "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"
}

PATTERNS = [
    "full_latest_method_failures",
    "target_audit_diagnostic_cases",
    "latest_method_failure",
    "gold_absent",
    "failure_casebook",
    "failure_audit",
    "diagnostic_cases",
    "external_only",
    "present_not_selected",
    "frontier_collapse",
    "direct_l1_anchor_patch_effect",
    "recovery_cases",
    "still_failed_cases",
    "regression_cases",
    "openai_gsm8k_59",
    "openai_gsm8k_1177",
    "openai_gsm8k_118",
    "openai_gsm8k_800",
    "openai_gsm8k_1180",
    "openai_gsm8k_30",
    "openai_gsm8k_24",
    "openai_gsm8k_17",
    "openai_gsm8k_42",
    "project_handoff_20260510",
    "exhaustive_failure_audit"
]

CORE_ARTIFACTS = [
    "docs/project_handoff_20260510/exhaustive_failure_audit/full_latest_method_failures.csv",
    "docs/project_handoff_20260510/target_audit_diagnostic_cases.jsonl",
    "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv",
    "docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_summary_20260510.json",
    "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_20260510.csv",
    "docs/project_handoff_20260510/exhaustive_failure_audit/direct_l1_anchor_patch_effect_summary_20260510.json",
    "docs/LATEST_METHOD_FULLY_TRACKED_FAILURE_CASES_20260510.md",
    "docs/LATEST_METHOD_FAILURE_PATTERN_MINING_20260510.md",
    "docs/GOLD_ABSENT_FAILURE_SUBPATTERN_ANALYSIS_20260510.md",
    "docs/DIRECT_L1_ANCHOR_PATCH_EFFECT_AUDIT_20260510.md"
]

def get_file_hash(path):
    hasher = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def count_cases(path):
    count = 0
    case_ids = set()
    try:
        if path.endswith('.csv'):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    count += 1
                    for key in ['case_id', 'example_id', 'id']:
                        if key in row:
                            case_ids.add(row[key])
                            break
        elif path.endswith('.jsonl'):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        count += 1
                        data = json.loads(line)
                        for key in ['case_id', 'example_id', 'id']:
                            if key in data:
                                case_ids.add(data[key])
                                break
        elif path.endswith('.json'):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    count = len(data)
                    for item in data:
                        if isinstance(item, dict):
                            for key in ['case_id', 'example_id', 'id']:
                                if key in item:
                                    case_ids.add(item[key])
                                    break
                elif isinstance(data, dict):
                    # Check if it's a summary or a list of cases
                    if 'cases' in data and isinstance(data['cases'], list):
                        count = len(data['cases'])
                        for item in data['cases']:
                            for key in ['case_id', 'example_id', 'id']:
                                if key in item:
                                    case_ids.add(item[key])
                                    break
                    else:
                        count = 1
    except:
        pass
    return count, case_ids

def audit():
    repo_files = {}
    print("Scanning repo...")
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            path = os.path.join(root, f)
            rel_path = os.path.relpath(path, REPO_ROOT)
            
            # Check if relevant
            is_relevant = any(p in f or p in rel_path for p in PATTERNS)
            if not is_relevant:
                try:
                    with open(path, 'r', errors='ignore') as f_obj:
                        content = f_obj.read(1000) # Peek
                        if any(p in content for p in PATTERNS):
                            is_relevant = True
                except:
                    pass
            
            if is_relevant:
                h = get_file_hash(path)
                repo_files[h] = rel_path
                repo_files[rel_path] = h

    print("Scanning archive and other folders...")
    outside_results = []
    search_paths = [ARCHIVE_ROOT, os.path.expanduser("~/Downloads"), os.path.expanduser("~/Documents"), os.path.expanduser("~/Desktop")]
    
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        print(f"Scanning {search_path}...")
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                path = os.path.join(root, f)
                
                is_relevant = any(p in f for p in PATTERNS)
                if not is_relevant:
                    try:
                        with open(path, 'r', errors='ignore') as f_obj:
                            content = f_obj.read(1000)
                            if any(p in content for p in PATTERNS):
                                is_relevant = True
                    except:
                        pass
                
                if is_relevant:
                    h = get_file_hash(path)
                    size = os.path.getsize(path)
                    mtime = os.path.getmtime(path)
                    
                    status = "unique failure material missing from repo"
                    match_path = ""
                    if h in repo_files:
                        status = "already in repo exact match"
                        match_path = repo_files[h]
                    elif f in repo_files:
                        # Same name, different hash
                        repo_path = os.path.join(REPO_ROOT, f) # Simplification
                        # Actually find the file with same name in repo
                        for k, v in repo_files.items():
                            if isinstance(v, str) and v.endswith(f):
                                repo_path = os.path.join(REPO_ROOT, v)
                                break
                        
                        if os.path.exists(repo_path):
                            repo_mtime = os.path.getmtime(repo_path)
                            if mtime > repo_mtime:
                                status = "duplicate newer version"
                            else:
                                status = "duplicate older version"
                            match_path = os.path.relpath(repo_path, REPO_ROOT)

                    outside_results.append({
                        "path": path,
                        "match_path": match_path,
                        "status": status,
                        "size": size,
                        "mtime": mtime,
                        "hash": h
                    })

    # Core artifact verification
    print("Verifying core artifacts...")
    core_verification = []
    all_repo_case_ids = set()
    for art in CORE_ARTIFACTS:
        path = os.path.join(REPO_ROOT, art)
        exists = os.path.exists(path)
        count = 0
        case_ids = set()
        size = 0
        if exists:
            size = os.path.getsize(path)
            count, case_ids = count_cases(path)
            all_repo_case_ids.update(case_ids)
        
        core_verification.append({
            "path": art,
            "exists": exists,
            "size": size,
            "count": count,
            "unique_case_ids": len(case_ids)
        })

    # Output results
    results = {
        "core_verification": core_verification,
        "outside_results": outside_results,
        "all_repo_case_ids_count": len(all_repo_case_ids)
    }
    
    output_path = os.path.join(REPO_ROOT, "docs/project_handoff_20260510/exhaustive_failure_audit/failure_case_transfer_audit_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Audit complete. Results written to {output_path}")

if __name__ == "__main__":
    audit()
