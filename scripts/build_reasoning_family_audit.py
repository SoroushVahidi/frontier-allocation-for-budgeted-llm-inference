#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class BranchObs:
    branch_id: str
    parent_branch_id: str
    depth: int
    method: str
    dataset: str
    example_id: str
    seed: int
    budget: int
    question: str
    reasoning: str
    pred_answer: str
    strategy_family: str
    source_file: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Audit semantic reasoning families from existing trace artifacts.")
    p.add_argument("--timestamp", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    p.add_argument("--output-root", default="outputs")
    return p.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            if fieldnames:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
            return
        w = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def safe_int(v: Any, d: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return d


def norm_answer(x: Any) -> str:
    s = str(x or "").strip().lower()
    s = s.replace("\\boxed{", "").replace("}", "")
    s = re.sub(r"[^0-9a-z\.\-+/% ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def op_type(text: str, q: str) -> str:
    t = (text + " " + q).lower()
    if any(k in t for k in ["percent", "%", "ratio", "fraction", "proportion"]):
        return "ratio/percent"
    if any(k in t for k in ["equation", "solve for", "let x", "variable"]):
        return "algebraic"
    if any(k in t for k in ["how many", "count", "arrange", "combination", "permutation"]):
        return "counting"
    if any(k in t for k in ["per ", "rate", "speed", "hour", "minute", "km", "mile", "kg", "meter"]):
        return "units/rate"
    if any(k in t for k in ["greater", "less", "compare", "difference between"]):
        return "comparison"
    if any(k in t for k in ["plan", "strategy", "first", "then", "next"]):
        return "planning"
    if any(k in t for k in ["atom", "cell", "force", "physics", "chemistry", "biology"]):
        return "science QA"
    if re.search(r"\d\s*[+\-*/]\s*\d", t):
        return "arithmetic"
    return "unknown"


def key_verbs(text: str) -> str:
    verbs = ["add", "subtract", "multiply", "divide", "compute", "calculate", "set", "solve", "count", "convert", "compare"]
    toks = set(re.findall(r"[a-z]+", text.lower()))
    return ",".join(sorted(v for v in verbs if v in toks))


def first_steps(text: str, n: int = 2) -> str:
    parts = [p.strip().lower() for p in re.split(r"[\n\.]+", text or "") if p.strip()]
    return " | ".join(parts[:n])


def jaccard(a: str, b: str) -> float:
    sa = set(re.findall(r"[a-z0-9]+", a.lower()))
    sb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def cluster_signature(b: BranchObs) -> dict[str, Any]:
    txt = b.reasoning or ""
    nums = sorted(set(re.findall(r"-?\d+(?:\.\d+)?", txt)))[:8]
    fs = first_steps(txt)
    return {
        "op_type": op_type(txt, b.question),
        "norm_answer": norm_answer(b.pred_answer),
        "nums": nums,
        "verbs": key_verbs(txt),
        "first_steps": fs,
        "strategy_family": (b.strategy_family or "").strip().lower(),
    }


def similar(s1: dict[str, Any], s2: dict[str, Any]) -> bool:
    if s1["strategy_family"] and s1["strategy_family"] == s2["strategy_family"]:
        return True
    if s1["op_type"] == s2["op_type"] and s1["norm_answer"] and s1["norm_answer"] == s2["norm_answer"]:
        return True
    if s1["op_type"] == s2["op_type"] and jaccard(s1["first_steps"], s2["first_steps"]) >= 0.55:
        return True
    if len(set(s1["nums"]) & set(s2["nums"])) >= 2 and jaccard(s1["verbs"], s2["verbs"]) >= 0.4:
        return True
    return False


def main() -> None:
    args = parse_args()
    out_dir = REPO_ROOT / args.output_root / f"reasoning_family_audit_{args.timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    trace_files = []
    patterns = [
        "outputs/cohere_trace_complete_loss_subset_*/final_branch_states.jsonl",
        "outputs/cohere_absent_from_tree_loss_diagnostics_*/final_branch_states.jsonl",
        "outputs/cohere_direct_reserve_validation_*/final_branch_states.jsonl",
        "outputs/*/final_branch_states.jsonl",
    ]
    for pat in patterns:
        trace_files.extend(sorted(REPO_ROOT.glob(pat)))
    trace_files = sorted(set(trace_files))

    case_meta: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    # pull labels from known diagnostics
    for p in sorted(REPO_ROOT.glob("outputs/cohere_trace_complete_loss_subset_*/loss_subset_trace_diagnostics.csv")):
        for r in read_csv(p):
            k = (str(r.get("example_id", "")), safe_int(r.get("seed", -1), -1), safe_int(r.get("budget", -1), -1), str(r.get("method", "")))
            case_meta[k] = {
                "failure_bucket": str(r.get("failure_bucket", "")),
                "correct_region_present": str(r.get("correct_region_present", "")),
            }

    assignments = []
    per_case = []
    coverage_rows = []
    redundancy_rows = []
    immediate_rows = []

    total_cases = 0
    usable_cases = 0

    for tf in trace_files:
        for rec in read_jsonl(tf):
            total_cases += 1
            branches = rec.get("final_branch_states") or []
            if not branches:
                continue
            usable_cases += 1
            example_id = str(rec.get("example_id", ""))
            seed = safe_int(rec.get("seed", -1), -1)
            budget = safe_int(rec.get("budget", -1), -1)
            method = str(rec.get("method", ""))
            dataset = "unknown"
            if example_id.startswith("openai_gsm8k"):
                dataset = "openai/gsm8k"
            root_branches = [b for b in branches if safe_int(b.get("branch_depth", 0), 0) <= 1]
            if not root_branches:
                root_branches = branches

            fam_sigs = []
            fam_members: dict[int, list[BranchObs]] = defaultdict(list)
            for b in root_branches:
                obs = BranchObs(
                    branch_id=str(b.get("branch_id", "")),
                    parent_branch_id=str(b.get("parent_branch_id", "")),
                    depth=safe_int(b.get("branch_depth", 0), 0),
                    method=method,
                    dataset=dataset,
                    example_id=example_id,
                    seed=seed,
                    budget=budget,
                    question="",
                    reasoning="\n".join([str(x) for x in (b.get("steps") or [])]),
                    pred_answer=str(b.get("predicted_answer", "")),
                    strategy_family=str(b.get("strategy_family", "")),
                    source_file=str(tf.relative_to(REPO_ROOT)),
                )
                sig = cluster_signature(obs)
                assigned = None
                for i, fs in enumerate(fam_sigs):
                    if similar(sig, fs):
                        assigned = i
                        break
                if assigned is None:
                    fam_sigs.append(sig)
                    assigned = len(fam_sigs) - 1
                fam_members[assigned].append(obs)

            family_count = max(1, len(fam_members))
            root_branch_count = len(root_branches)
            sizes = [len(v) for v in fam_members.values()]
            max_size = max(sizes) if sizes else 0
            p = [s / max(1, sum(sizes)) for s in sizes if s > 0]
            entropy = -sum(pi * math.log(pi + 1e-12, 2) for pi in p)
            all_depths = [m.depth for fam in fam_members.values() for m in fam]
            depth_min = min(all_depths) if all_depths else 0
            depth_mean = sum(all_depths) / max(1, len(all_depths))
            fam_ge2 = sum(1 for fam in fam_members.values() if max(m.depth for m in fam) >= 2)
            fam_ge3 = sum(1 for fam in fam_members.values() if max(m.depth for m in fam) >= 3)

            mkey = (example_id, seed, budget, method)
            meta = case_meta.get(mkey, {})
            fail_bucket = meta.get("failure_bucket", "unknown")
            corr_present = str(meta.get("correct_region_present", "")).lower() in {"1", "true", "yes"}

            similar_all = family_count == 1
            per_case.append({
                "example_id": example_id,
                "seed": seed,
                "budget": budget,
                "method": method,
                "dataset": dataset,
                "root_branch_count": root_branch_count,
                "semantic_family_count": family_count,
                "family_redundancy_ratio": round(root_branch_count / max(1, family_count), 4),
                "max_family_size": max_size,
                "family_entropy": round(entropy, 4),
                "family_depth_min": depth_min,
                "family_depth_mean": round(depth_mean, 4),
                "families_depth_ge2": fam_ge2,
                "families_depth_ge3": fam_ge3,
                "gold_or_correct_region_signal_any_family": int(corr_present),
                "correct_region_family_depth_ge2": int(corr_present and fam_ge2 > 0),
                "correct_region_family_depth_ge3": int(corr_present and fam_ge3 > 0),
                "all_expanded_families_semantically_similar": int(similar_all),
                "failure_bucket": fail_bucket,
                "trace_source": str(tf.relative_to(REPO_ROOT)),
            })

            for fid, members in fam_members.items():
                for m in members:
                    sig = cluster_signature(m)
                    assignments.append({
                        "example_id": example_id, "seed": seed, "budget": budget, "method": method,
                        "branch_id": m.branch_id, "family_id": f"fam_{fid}", "branch_depth": m.depth,
                        "op_type": sig["op_type"], "norm_answer": sig["norm_answer"],
                        "numeric_quantities": "|".join(sig["nums"]), "key_verbs": sig["verbs"],
                        "first_steps": sig["first_steps"], "strategy_family": sig["strategy_family"],
                        "source_file": m.source_file,
                    })

    # aggregate summaries
    by_method = defaultdict(list)
    by_fail = defaultdict(list)
    for r in per_case:
        by_method[r["method"]].append(r)
        by_fail[r["failure_bucket"]].append(r)
        if r["failure_bucket"] == "immediate_miss":
            immediate_rows.append(r)

    for m, rows in sorted(by_method.items()):
        coverage_rows.append({
            "method": m,
            "cases": len(rows),
            "avg_families_depth_ge2": round(sum(x["families_depth_ge2"] for x in rows) / len(rows), 4),
            "avg_families_depth_ge3": round(sum(x["families_depth_ge3"] for x in rows) / len(rows), 4),
            "avg_family_depth_mean": round(sum(x["family_depth_mean"] for x in rows) / len(rows), 4),
        })

    for f, rows in sorted(by_fail.items()):
        redundancy_rows.append({
            "failure_bucket": f,
            "cases": len(rows),
            "avg_root_branch_count": round(sum(x["root_branch_count"] for x in rows) / len(rows), 4),
            "avg_semantic_family_count": round(sum(x["semantic_family_count"] for x in rows) / len(rows), 4),
            "avg_redundancy_ratio": round(sum(x["family_redundancy_ratio"] for x in rows) / len(rows), 4),
            "pct_all_similar": round(sum(x["all_expanded_families_semantically_similar"] for x in rows) / len(rows), 4),
        })

    implication = [
        "# Candidate controller implications",
        "",
        f"- Cases analyzed: {total_cases}",
        f"- Cases with usable branch traces: {usable_cases}",
        f"- Avg root_branch_count: {round(sum(r['root_branch_count'] for r in per_case)/max(1,len(per_case)),4)}",
        f"- Avg semantic_family_count: {round(sum(r['semantic_family_count'] for r in per_case)/max(1,len(per_case)),4)}",
        f"- Avg redundancy ratio: {round(sum(r['family_redundancy_ratio'] for r in per_case)/max(1,len(per_case)),4)}",
        "",
        "## Initial diagnostic reading",
        "- If redundancy ratio is consistently >1 with low family entropy in immediate_miss rows, minimum depth-over-root likely overcounts redundant branches.",
        "- If correct-region flags are present but depth-ge2/ge3 remains low, semantic minimum maturation is likely needed.",
        "- If family diversity is high yet misses persist, adaptive post-maturation scoring likely needs calibration.",
    ]
    (out_dir / "candidate_controller_implications.md").write_text("\n".join(implication) + "\n", encoding="utf-8")

    write_jsonl(out_dir / "family_assignments.jsonl", assignments)
    write_csv(out_dir / "per_case_family_summary.csv", per_case)
    write_csv(out_dir / "family_depth_coverage_summary.csv", coverage_rows)
    write_csv(out_dir / "redundancy_vs_failure_summary.csv", redundancy_rows)
    write_csv(out_dir / "immediate_miss_family_audit.csv", immediate_rows)
    manifest = {
        "timestamp": args.timestamp,
        "output_dir": str(out_dir.relative_to(REPO_ROOT)),
        "cases_analyzed": total_cases,
        "cases_with_usable_branch_traces": usable_cases,
        "source_trace_files": [str(p.relative_to(REPO_ROOT)) for p in trace_files],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
