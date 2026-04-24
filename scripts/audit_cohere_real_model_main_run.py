#!/usr/bin/env python3
"""Artifact-only Cohere real-model main-run audit."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = REPO_ROOT / "outputs"
DOCS = REPO_ROOT / "docs"
SLURM_LOGS = REPO_ROOT / "logs" / "slurm"

PROVIDER = "cohere"
MODEL = "command-r-plus-08-2024"
MAIN_STAMP = "20260424T_COHERE_REAL_MAIN"
EXPECTED_DATASETS = ["openai/gsm8k", "HuggingFaceH4/MATH-500", "HuggingFaceH4/aime_2024"]
EXPECTED_BUDGETS = [4, 6, 8]
EXPECTED_SEEDS = [11, 23]
EXPECTED_METHODS = ["strict_f3", "strict_gate1_cap_k6", "strict_f2", "external_l1_max", "self_consistency_3"]
EXPECTED_SUBSET_SIZE = 20


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _to_int(value: Optional[str], default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Optional[str]) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _group_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return mean(valid)


def _dataset_slug(dataset: str) -> str:
    return dataset.replace("/", "_")


def _doc_main_findings_empty(path: Path) -> bool:
    if not path.exists():
        return True
    text = path.read_text(encoding="utf-8", errors="replace")
    needle = "Main bounded findings"
    idx = text.find(needle)
    if idx < 0:
        return True
    tail = text[idx + len(needle) :].splitlines()
    content_lines = []
    for line in tail:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            break
        content_lines.append(s)
    if not content_lines:
        return True
    joined = " ".join(content_lines).lower()
    return joined in {"tbd", "none"} or "not available" in joined


@dataclass
class ExampleRow:
    provider: str
    model: str
    dataset: str
    seed: str
    budget: str
    example_id: str
    method: str
    is_correct: int
    absent_from_tree: int
    output_layer_mismatch: int
    actions_used: Optional[float]
    expansions: Optional[float]


def discover_sources() -> Dict[str, List[Path]]:
    canonical_dirs = sorted(
        p for p in OUTPUTS.glob(f"canonical_real_model_validation_*{MAIN_STAMP}*") if p.is_dir()
    )
    real_model_dirs = sorted(
        p for p in OUTPUTS.glob("real_model_ours_vs_external_validation_*COHERE_REAL_MAIN*") if p.is_dir()
    )
    doc_files = sorted(
        list(DOCS.glob("*COHERE*REAL_MODEL*.md")) + list(DOCS.glob("*REAL_MODEL*COHERE*.md"))
    )
    slurm_logs = sorted(SLURM_LOGS.glob("*cohere*real*main*.*"))
    return {
        "canonical_dirs": canonical_dirs,
        "real_model_dirs": real_model_dirs,
        "doc_files": doc_files,
        "slurm_logs": slurm_logs,
    }


def load_retry_errors(real_model_dirs: Iterable[Path]) -> Dict[Tuple[str, str, str, str], int]:
    counts: Dict[Tuple[str, str, str, str], int] = defaultdict(int)
    for run_dir in real_model_dirs:
        retry_csv = run_dir / "cohere" / "retry_error_log.csv"
        if not retry_csv.exists():
            continue
        with retry_csv.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = (
                    row.get("dataset", ""),
                    str(row.get("budget", "")),
                    str(row.get("seed", "")),
                    row.get("method", ""),
                )
                counts[key] += 1
    return counts


def load_examples(canonical_dirs: Iterable[Path], real_model_dirs: Iterable[Path]) -> List[ExampleRow]:
    paths: List[Path] = []
    for run_dir in canonical_dirs:
        p = run_dir / "per_example_rows.csv"
        if p.exists():
            paths.append(p)
    for run_dir in real_model_dirs:
        p = run_dir / "cohere" / "per_example_rows.csv"
        if p.exists():
            paths.append(p)

    rows: List[ExampleRow] = []
    seen = set()
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("provider", "").lower() != PROVIDER:
                    continue
                key = (
                    row.get("provider", ""),
                    row.get("model", ""),
                    row.get("dataset", ""),
                    str(row.get("seed", "")),
                    str(row.get("budget", "")),
                    row.get("example_id", ""),
                    row.get("method", ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    ExampleRow(
                        provider=row.get("provider", ""),
                        model=row.get("model", ""),
                        dataset=row.get("dataset", ""),
                        seed=str(row.get("seed", "")),
                        budget=str(row.get("budget", "")),
                        example_id=row.get("example_id", ""),
                        method=row.get("method", ""),
                        is_correct=_to_int(row.get("is_correct")),
                        absent_from_tree=_to_int(row.get("absent_from_tree")),
                        output_layer_mismatch=_to_int(row.get("output_layer_mismatch")),
                        actions_used=_to_float(row.get("actions_used")),
                        expansions=_to_float(row.get("expansions")),
                    )
                )
    return rows


def build_missing_or_incomplete_rows(
    canonical_dirs: List[Path], retry_counts: Dict[Tuple[str, str, str, str], int]
) -> List[Dict[str, object]]:
    by_name = {d.name: d for d in canonical_dirs}
    out: List[Dict[str, object]] = []
    expected_row_count = EXPECTED_SUBSET_SIZE * len(EXPECTED_METHODS)
    severe_retry_threshold = max(3, int(expected_row_count * 0.1))

    for dataset in EXPECTED_DATASETS:
        dslug = _dataset_slug(dataset)
        for seed in EXPECTED_SEEDS:
            for budget in EXPECTED_BUDGETS:
                dirname = f"canonical_real_model_validation_{MAIN_STAMP}_{PROVIDER}_{seed}_{budget}_{dslug}"
                dpath = by_name.get(dirname)
                issues: List[str] = []
                n_rows = 0
                n_methods = 0
                retry_error_count = 0
                manifest_present = False
                doc_empty = True

                if dpath is None:
                    issues.append("missing_output_directory")
                else:
                    manifest_present = (dpath / "manifest.json").exists()
                    if not manifest_present:
                        issues.append("missing_manifest")
                    per_example = dpath / "per_example_rows.csv"
                    if not per_example.exists():
                        issues.append("missing_per_example_rows")
                    else:
                        with per_example.open(newline="", encoding="utf-8") as handle:
                            rows = list(csv.DictReader(handle))
                        n_rows = len(rows)
                        n_methods = len({r.get("method", "") for r in rows})
                        if n_rows < expected_row_count:
                            issues.append(f"insufficient_scored_examples:{n_rows}<{expected_row_count}")
                        if n_methods < len(EXPECTED_METHODS):
                            issues.append(f"insufficient_methods:{n_methods}<{len(EXPECTED_METHODS)}")
                        missing_methods = [m for m in EXPECTED_METHODS if m not in {r.get("method", "") for r in rows}]
                        if missing_methods:
                            issues.append(f"missing_methods:{'|'.join(missing_methods)}")

                for method in EXPECTED_METHODS:
                    retry_error_count += retry_counts.get((dataset, str(budget), str(seed), method), 0)
                if retry_error_count >= severe_retry_threshold:
                    issues.append(f"severe_retry_error_log:{retry_error_count}>={severe_retry_threshold}")

                doc_path = DOCS / f"CANONICAL_REAL_MODEL_VALIDATION_{MAIN_STAMP}_{PROVIDER}_{seed}_{budget}_{dslug}.md"
                doc_empty = _doc_main_findings_empty(doc_path)
                if doc_empty:
                    issues.append("doc_main_bounded_findings_empty_or_missing")

                out.append(
                    {
                        "provider": PROVIDER,
                        "model": MODEL,
                        "dataset": dataset,
                        "seed": seed,
                        "budget": budget,
                        "subset_size_expected": EXPECTED_SUBSET_SIZE,
                        "methods_expected": "|".join(EXPECTED_METHODS),
                        "expected_output_dir": f"outputs/{dirname}",
                        "manifest_present": int(manifest_present),
                        "n_scored_examples": n_rows,
                        "n_methods_found": n_methods,
                        "retry_error_count": retry_error_count,
                        "doc_main_bounded_findings_empty": int(doc_empty),
                        "is_missing_or_incomplete": int(bool(issues)),
                        "issues": "|".join(issues) if issues else "ok",
                    }
                )
    return out


def write_summary_by_dataset_budget_method(
    out_path: Path,
    examples: List[ExampleRow],
    retry_counts: Dict[Tuple[str, str, str, str], int],
) -> None:
    groups: Dict[Tuple[str, str, str, str, str, str], List[ExampleRow]] = defaultdict(list)
    for row in examples:
        groups[(row.provider, row.model, row.dataset, row.budget, row.seed, row.method)].append(row)

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "provider",
            "model",
            "dataset",
            "budget",
            "seed",
            "subset_size_expected",
            "method",
            "n_evaluated_examples",
            "accuracy",
            "absent_from_tree_rate",
            "output_layer_mismatch_rate",
            "retry_error_count",
            "mean_actions",
            "mean_expansions",
            "mean_latency_seconds",
            "mean_prompt_tokens",
            "mean_completion_tokens",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(groups.keys()):
            group_rows = groups[key]
            provider, model, dataset, budget, seed, method = key
            n = len(group_rows)
            writer.writerow(
                {
                    "provider": provider,
                    "model": model,
                    "dataset": dataset,
                    "budget": budget,
                    "seed": seed,
                    "subset_size_expected": EXPECTED_SUBSET_SIZE,
                    "method": method,
                    "n_evaluated_examples": n,
                    "accuracy": sum(r.is_correct for r in group_rows) / n if n else 0.0,
                    "absent_from_tree_rate": sum(r.absent_from_tree for r in group_rows) / n if n else 0.0,
                    "output_layer_mismatch_rate": sum(r.output_layer_mismatch for r in group_rows) / n if n else 0.0,
                    "retry_error_count": retry_counts.get((dataset, budget, seed, method), 0),
                    "mean_actions": _group_mean(r.actions_used for r in group_rows),
                    "mean_expansions": _group_mean(r.expansions for r in group_rows),
                    "mean_latency_seconds": None,
                    "mean_prompt_tokens": None,
                    "mean_completion_tokens": None,
                }
            )


def write_summary_by_method(out_path: Path, examples: List[ExampleRow]) -> None:
    groups: Dict[Tuple[str, str, str], List[ExampleRow]] = defaultdict(list)
    for row in examples:
        groups[(row.provider, row.model, row.method)].append(row)

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "provider",
            "model",
            "method",
            "subset_size_expected",
            "n_evaluated_examples",
            "datasets_covered",
            "budgets_covered",
            "seeds_covered",
            "accuracy",
            "absent_from_tree_rate",
            "output_layer_mismatch_rate",
            "mean_actions",
            "mean_expansions",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(groups.keys()):
            provider, model, method = key
            group_rows = groups[key]
            n = len(group_rows)
            writer.writerow(
                {
                    "provider": provider,
                    "model": model,
                    "method": method,
                    "subset_size_expected": EXPECTED_SUBSET_SIZE,
                    "n_evaluated_examples": n,
                    "datasets_covered": "|".join(sorted({r.dataset for r in group_rows})),
                    "budgets_covered": "|".join(sorted({r.budget for r in group_rows}, key=lambda b: int(b))),
                    "seeds_covered": "|".join(sorted({r.seed for r in group_rows}, key=lambda s: int(s))),
                    "accuracy": sum(r.is_correct for r in group_rows) / n if n else 0.0,
                    "absent_from_tree_rate": sum(r.absent_from_tree for r in group_rows) / n if n else 0.0,
                    "output_layer_mismatch_rate": sum(r.output_layer_mismatch for r in group_rows) / n if n else 0.0,
                    "mean_actions": _group_mean(r.actions_used for r in group_rows),
                    "mean_expansions": _group_mean(r.expansions for r in group_rows),
                }
            )


def build_claim_safety(examples: List[ExampleRow]) -> Dict[str, object]:
    method_rows: Dict[str, List[ExampleRow]] = defaultdict(list)
    per_cell: Dict[Tuple[str, str, str], Dict[str, List[ExampleRow]]] = defaultdict(lambda: defaultdict(list))

    for row in examples:
        method_rows[row.method].append(row)
        per_cell[(row.dataset, row.seed, row.budget)][row.method].append(row)

    def acc(rows: List[ExampleRow]) -> Optional[float]:
        if not rows:
            return None
        return sum(r.is_correct for r in rows) / len(rows)

    strict_f3_acc = acc(method_rows["strict_f3"])
    gate_acc = acc(method_rows["strict_gate1_cap_k6"])
    ext_l1_acc = acc(method_rows["external_l1_max"])

    frontier_methods = {"strict_f3", "strict_gate1_cap_k6", "strict_f2"}
    frontier_rows = [r for m in frontier_methods for r in method_rows.get(m, [])]
    frontier_acc = acc(frontier_rows)

    strict_vs_gate_support = strict_f3_acc is not None and gate_acc is not None and strict_f3_acc > gate_acc
    frontier_dominates_external = frontier_acc is not None and ext_l1_acc is not None and frontier_acc > ext_l1_acc

    if frontier_dominates_external:
        disposition = "headline-safe"
    elif strict_vs_gate_support and not frontier_dominates_external:
        disposition = "appendix-only"
    else:
        disposition = "not-usable-for-dominance-claims"

    return {
        "questions": {
            "A_strict_f3_dominates_strict_gate1_cap_k6": {
                "answer": "yes" if strict_vs_gate_support else "no",
                "strict_f3_accuracy": strict_f3_acc,
                "strict_gate1_cap_k6_accuracy": gate_acc,
            },
            "B_frontier_allocation_dominates_external_l1_max": {
                "answer": "yes" if frontier_dominates_external else "no",
                "frontier_accuracy": frontier_acc,
                "external_l1_max_accuracy": ext_l1_acc,
            },
            "C_frontier_competitive_not_dominant": {
                "answer": "yes" if (strict_vs_gate_support and not frontier_dominates_external) else "no"
            },
            "D_recommended_disposition": {"answer": disposition},
        },
        "n_total_evaluated_rows": len(examples),
    }


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_status(out_path: Path, claim: Dict[str, object], sources: Dict[str, List[Path]], gaps: List[Dict[str, object]]) -> None:
    q = claim["questions"]
    n_gaps = sum(int(r["is_missing_or_incomplete"]) for r in gaps)
    text = f"""# Cohere real-model main-run audit status

- A (`strict_f3` dominates `strict_gate1_cap_k6`): **{q["A_strict_f3_dominates_strict_gate1_cap_k6"]["answer"]}**
- B (frontier-allocation dominates `external_l1_max`): **{q["B_frontier_allocation_dominates_external_l1_max"]["answer"]}**
- C (frontier-allocation is competitive but not dominant): **{q["C_frontier_competitive_not_dominant"]["answer"]}**
- D (manuscript disposition): **{q["D_recommended_disposition"]["answer"]}**

## Artifact coverage

- Cohere canonical validation directories: {len(sources["canonical_dirs"])}
- Cohere aggregate real-model directories: {len(sources["real_model_dirs"])}
- Cohere real-model docs inspected: {len(sources["doc_files"])}
- Cohere Slurm logs inspected: {len(sources["slurm_logs"])}
- Missing/incomplete contract slices: {n_gaps}

This audit is artifact-only and does not issue new API calls.
"""
    out_path.write_text(text, encoding="utf-8")


def write_doc(
    out_path: Path,
    timestamp: str,
    sources: Dict[str, List[Path]],
    claim: Dict[str, object],
    gaps: List[Dict[str, object]],
) -> None:
    q = claim["questions"]
    rel = lambda p: str(p.relative_to(REPO_ROOT))
    src_lines = []
    for key in ("canonical_dirs", "real_model_dirs", "doc_files", "slurm_logs"):
        for path in sources[key]:
            src_lines.append(f"- `{rel(path)}`")
    missing_rows = [r for r in gaps if int(r["is_missing_or_incomplete"]) == 1]
    if missing_rows:
        gap_lines = [
            f"- `{r['dataset']}` seed `{r['seed']}` budget `{r['budget']}`: {r['issues']}" for r in missing_rows
        ]
    else:
        gap_lines = ["- None. All contract slices appear complete under current checks."]

    text = f"""# Cohere real-model main-run audit ({timestamp})

## Artifact sources inspected
{chr(10).join(src_lines)}

## Contract checked
- Provider/model: `{PROVIDER}/{MODEL}`
- Datasets: `{EXPECTED_DATASETS}`
- Budgets: `{EXPECTED_BUDGETS}`
- Seeds: `{EXPECTED_SEEDS}`
- Subset size: `{EXPECTED_SUBSET_SIZE}`
- Methods: `{EXPECTED_METHODS}`

## Claim-safety summary
- A (`strict_f3` > `strict_gate1_cap_k6`): **{q["A_strict_f3_dominates_strict_gate1_cap_k6"]["answer"]}**
- B (frontier-allocation > `external_l1_max`): **{q["B_frontier_allocation_dominates_external_l1_max"]["answer"]}**
- C (competitive not dominant): **{q["C_frontier_competitive_not_dominant"]["answer"]}**
- D (disposition): **{q["D_recommended_disposition"]["answer"]}**

## Missing or incomplete slices
{chr(10).join(gap_lines)}

## Safe manuscript guidance
Treat Cohere real-model evidence as appendix calibration unless and until dominance over `external_l1_max` is robust across full slices.
"""
    out_path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Cohere real-model main-run artifacts.")
    parser.add_argument("--timestamp", default=_now_utc_stamp())
    args = parser.parse_args()
    timestamp = args.timestamp

    out_dir = OUTPUTS / f"cohere_real_model_main_run_audit_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = discover_sources()
    retry_counts = load_retry_errors(sources["real_model_dirs"])
    examples = load_examples(sources["canonical_dirs"], sources["real_model_dirs"])
    if not examples:
        raise SystemExit("No Cohere real-model examples found.")

    write_summary_by_dataset_budget_method(
        out_dir / "cohere_summary_by_dataset_budget_method.csv", examples, retry_counts
    )
    write_summary_by_method(out_dir / "cohere_summary_by_method.csv", examples)
    gaps = build_missing_or_incomplete_rows(sources["canonical_dirs"], retry_counts)
    write_csv(out_dir / "missing_or_incomplete_slices.csv", gaps)

    claim = build_claim_safety(examples)
    (out_dir / "cohere_claim_safety_assessment.json").write_text(
        json.dumps(claim, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_status(out_dir / "STATUS.md", claim, sources, gaps)

    doc_path = DOCS / f"COHERE_REAL_MODEL_MAIN_RUN_AUDIT_{timestamp}.md"
    write_doc(doc_path, timestamp, sources, claim, gaps)
    print(json.dumps({"status": "ok", "out_dir": str(out_dir), "doc_path": str(doc_path)}, indent=2))


if __name__ == "__main__":
    main()
