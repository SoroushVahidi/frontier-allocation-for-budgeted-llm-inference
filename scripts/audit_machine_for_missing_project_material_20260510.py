import os
import hashlib
import json
import csv
import time
from pathlib import Path

# Configuration
REPO_ROOT = os.path.expanduser("~/frontier-allocation-for-budgeted-llm-inference")
SEARCH_PATHS = [
    os.path.expanduser("~"),
    os.path.expanduser("~/frontier-allocation-old-folders-archive-20260510"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
]
SKIP_DIRS = {
    ".cache", ".conda", ".local", ".npm", ".cursor", ".vscode", ".git", 
    "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules",
    "Library", "Applications", "Pictures", "Music", "Movies", "Public"
}
KEY_TERMS = [
    "direct_l1_anchor", "direct_hybrid", "production_equiv_v1", "frontier_tiebreak",
    "k1_frontier4", "PAL", "output_layer_repair", "commitment_gate",
    "external_l1_max", "external_l1_exact", "external_s1_budget_forcing",
    "external_tale_prompt_budgeting", "external_zhai_cpo_mode_a", "self_consistency",
    "verifier_guided", "TreeOfThought", "ProgramOfThought", "full_latest_method_failures",
    "target_audit_diagnostic_cases", "gold_absent", "failure_audit", "failure_casebook",
    "openai_gsm8k_", "project_handoff_20260510", "ranked_methods", "manifest.json", "summary.json"
]

def get_hash(path):
    try:
        if os.path.getsize(path) > 100 * 1024 * 1024: # Skip files > 100MB for hashing
            return "TOO_LARGE"
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def index_repo():
    repo_files = {}
    for root, dirs, files in os.walk(REPO_ROOT):
        if ".git" in dirs:
            dirs.remove(".git")
        for f in files:
            path = os.path.join(root, f)
            rel_path = os.path.relpath(path, REPO_ROOT)
            h = get_hash(path)
            if h:
                repo_files[h] = rel_path
                # Also index by name for similarity
                repo_files[f"name:{f}"] = rel_path
    return repo_files

def audit():
    repo_index = index_repo()
    results = []
    
    for search_root in SEARCH_PATHS:
        if not os.path.exists(search_root):
            continue
        print(f"Scanning {search_root}...")
        for root, dirs, files in os.walk(search_root):
            # Prune noisy directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            
            if root.startswith(REPO_ROOT):
                continue
                
            for f in files:
                path = os.path.join(root, f)
                if os.path.islink(path):
                    continue
                    
                h = get_hash(path)
                classification = "unrelated/noise"
                reason = ""
                
                if h in repo_index:
                    classification = "already in repo exact match"
                    reason = f"Matches {repo_index[h]}"
                elif f"name:{f}" in repo_index:
                    classification = "likely duplicate"
                    reason = f"Same name as {repo_index[f'name:{f}']}, different content"
                    # Check mtime
                    try:
                        repo_path = os.path.join(REPO_ROOT, repo_index[f"name:{f}"])
                        if os.path.getmtime(path) > os.path.getmtime(repo_path):
                            classification = "likely duplicate newer version"
                        else:
                            classification = "likely duplicate older version"
                    except:
                        pass
                else:
                    # Search for key terms in name or content
                    is_important = False
                    for term in KEY_TERMS:
                        if term.lower() in f.lower():
                            is_important = True
                            reason = f"Found term '{term}' in filename"
                            break
                    
                    if not is_important and h != "TOO_LARGE":
                        try:
                            # Sample first 4KB for terms
                            with open(path, 'r', errors='ignore') as f_obj:
                                content = f_obj.read(4096)
                                for term in KEY_TERMS:
                                    if term in content:
                                        is_important = True
                                        reason = f"Found term '{term}' in content"
                                        break
                        except:
                            pass
                    
                    if is_important:
                        classification = "unique important material missing from repo"
                        
                # Safety checks
                if any(x in f.lower() for x in [".env", "secret", "token", "credential", "key", "id_rsa"]):
                    classification = "unsafe/secret/do-not-commit"
                    reason = "Potential secret found in filename"

                if classification != "unrelated/noise":
                    results.append({
                        "path": path,
                        "classification": classification,
                        "reason": reason,
                        "size": os.path.getsize(path),
                        "mtime": time.ctime(os.path.getmtime(path)),
                        "hash": h
                    })

    # Output results
    output_json = os.path.join(REPO_ROOT, "docs/project_handoff_20260510/whole_machine_audit_results.json")
    output_csv = os.path.join(REPO_ROOT, "docs/project_handoff_20260510/whole_machine_audit_results.csv")
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    
    with open(output_json, "w") as f:
        json.dump(results, f, indent=2)
        
    if results:
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            
    print(f"Audit complete. Found {len(results)} candidate files.")
    return results

if __name__ == "__main__":
    audit()
