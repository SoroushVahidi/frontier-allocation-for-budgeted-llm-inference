import os
import json
import csv
import re
from pathlib import Path

# Configuration
REPO_ROOT = os.path.expanduser("~/frontier-allocation-for-budgeted-llm-inference")
ARCHIVE_ROOT = os.path.expanduser("~/frontier-allocation-old-folders-archive-20260510")
SKIP_DIRS = {
    ".cache", ".conda", ".local", ".npm", ".cursor", ".vscode", ".git", 
    "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "node_modules"
}

METHOD_PATTERNS = [
    r"external_[a-zA-Z0-9_]+",
    r"baseline_[a-zA-Z0-9_]+",
    r"l1_[a-zA-Z0-9_]+",
    r"tale_[a-zA-Z0-9_]+",
    r"s1_[a-zA-Z0-9_]+",
    r"zhai_[a-zA-Z0-9_]+",
    r"cpo_[a-zA-Z0-9_]+",
    r"self_consistency_[a-zA-Z0-9_]*",
    r"tree_of_thought_[a-zA-Z0-9_]*",
    r"tot_[a-zA-Z0-9_]*",
    r"verifier_[a-zA-Z0-9_]*",
    r"program_of_thought_[a-zA-Z0-9_]*",
    r"pal_[a-zA-Z0-9_]*",
    r"direct_hybrid_[a-zA-Z0-9_]*",
    r"direct_l1_anchor_[a-zA-Z0-9_]*",
    r"production_equiv_[a-zA-Z0-9_]*",
    r"direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak[a-zA-Z0-9_]*"
]

def extract_methods(text):
    methods = set()
    for pattern in METHOD_PATTERNS:
        matches = re.findall(pattern, text)
        methods.update(matches)
    return methods

def classify_method(method_id):
    mid = method_id.lower()
    if mid.startswith("external_"):
        return "external baseline"
    if any(x in mid for x in ["zhai", "tale", "s1", "l1_exact", "l1_max"]):
        return "external baseline"
    if "pal" in mid:
        return "internal method (PAL)"
    if any(x in mid for x in ["direct_hybrid", "direct_l1_anchor", "production_equiv", "diverse_root"]):
        return "internal method"
    if any(x in mid for x in ["strict_f3", "strict_gate1_cap_k6", "strict_f2"]):
        return "historical/internal superseded method"
    return "unknown / needs manual review"

def audit_inventory():
    inventory = {}
    
    def scan_dir(root_path, source_label):
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith((".py", ".md", ".json", ".csv", ".jsonl", ".txt")):
                    path = os.path.join(root, f)
                    try:
                        with open(path, 'r', errors='ignore') as f_obj:
                            content = f_obj.read()
                            methods = extract_methods(content)
                            for m in methods:
                                if m not in inventory:
                                    inventory[m] = {
                                        "method_id": m,
                                        "category": classify_method(m),
                                        "appears_in": set(),
                                        "sources": set(),
                                        "has_code": False,
                                        "has_test": False,
                                        "has_output": False,
                                        "has_manifest": False
                                    }
                                inventory[m]["appears_in"].add(os.path.relpath(path, root_path))
                                inventory[m]["sources"].add(source_label)
                                
                                # Check for specific markers
                                if "experiments/" in path and f.endswith(".py"):
                                    inventory[m]["has_code"] = True
                                if "tests/" in path and f.endswith(".py"):
                                    inventory[m]["has_test"] = True
                                if "outputs/" in path:
                                    inventory[m]["has_output"] = True
                                if f == "manifest.json":
                                    inventory[m]["has_manifest"] = True
                    except:
                        pass

    print(f"Scanning canonical repo: {REPO_ROOT}")
    scan_dir(REPO_ROOT, "repo")
    
    print(f"Scanning archive: {ARCHIVE_ROOT}")
    scan_dir(ARCHIVE_ROOT, "archive")

    # Convert sets to lists for JSON serialization
    for m in inventory:
        inventory[m]["appears_in"] = sorted(list(inventory[m]["appears_in"]))
        inventory[m]["sources"] = sorted(list(inventory[m]["sources"]))

    output_path = os.path.join(REPO_ROOT, "docs/project_handoff_20260510/external_baseline_inventory_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(inventory, f, indent=2)
    
    print(f"Audit complete. Found {len(inventory)} unique methods.")
    return inventory

if __name__ == "__main__":
    audit_inventory()
