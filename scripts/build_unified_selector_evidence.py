#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BANNED_KEYS = {"gold_answer", "oracle_selector_answer", "oracle_selector_would_fix", "evaluation_only"}


def iter_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            x = json.loads(line)
            if isinstance(x, dict):
                yield x


def parse_input(s: str) -> tuple[Path, str]:
    if ":" in s:
        p, label = s.split(":", 1)
    else:
        p = s
        label = Path(s).parent.name
    return Path(p), label


def scrub_verifier_input(v: dict[str, Any], no_gold: bool) -> dict[str, Any]:
    out = json.loads(json.dumps(v if isinstance(v, dict) else {}))
    if no_gold:
        for k in list(out.keys()):
            if k in BANNED_KEYS:
                del out[k]
    return out


def contains_banned(obj: Any) -> bool:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in BANNED_KEYS:
                return True
            if contains_banned(v):
                return True
    elif isinstance(obj, list):
        return any(contains_banned(v) for v in obj)
    elif isinstance(obj, str):
        s = obj.lower()
        return any(k in s for k in BANNED_KEYS)
    return False


def _candidate_trace_text(c: dict[str, Any]) -> str:
    trace = c.get("trace_text") or c.get("step_text") or c.get("reasoning_trace")
    if trace:
        return str(trace)
    steps = c.get("steps")
    if isinstance(steps, list):
        return "\n".join(str(x) for x in steps if x is not None)
    if isinstance(steps, str):
        return steps
    return ""


def extract_candidate_nodes(r: dict[str, Any]) -> list[dict[str, Any]]:
    vi = r.get("verifier_input") if isinstance(r.get("verifier_input"), dict) else {}
    metadata = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
    raw_record = r.get("raw_record") if isinstance(r.get("raw_record"), dict) else {}
    paths = [
        r.get("candidate_nodes"),
        r.get("candidates"),
        vi.get("candidates_for_verifier"),
        vi.get("candidates"),
        vi.get("candidate_nodes"),
        metadata.get("candidate_nodes"),
        raw_record.get("candidate_nodes"),
        (raw_record.get("result_metadata") or {}).get("candidate_nodes") if isinstance(raw_record.get("result_metadata"), dict) else None,
        vi.get("answer_candidates"),
        r.get("final_branch_states"),
        r.get("answer_groups"),
        (r.get("evaluation_only") or {}).get("candidate_nodes") if isinstance(r.get("evaluation_only"), dict) else None,
    ]
    for v in paths:
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            return v
    return []


def normalize_record(r: dict[str, Any], src_label: str, src_path: Path, idx: int, no_gold: bool) -> dict[str, Any]:
    cands = extract_candidate_nodes(r)
    norm_cands = []
    traced = 0
    for i, c in enumerate(cands):
        if not isinstance(c, dict):
            continue
        n = {
            "candidate_id": c.get("candidate_id", f"cand_{i}"),
            "source_family": c.get("source_family") or c.get("source_id"),
            "final_answer": c.get("final_answer"),
            "normalized_answer": c.get("normalized_answer"),
            "trace_text": _candidate_trace_text(c),
            "step_text": c.get("step_text"),
            "reasoning_trace": c.get("reasoning_trace"),
            "reasoning_steps": c.get("reasoning_steps"),
            "steps": c.get("steps"),
            "derivation": c.get("derivation"),
            "solution_trace": c.get("solution_trace"),
            "branch_depth": c.get("branch_depth"),
            "cost_proxy": c.get("cost_proxy") or c.get("cost_norm"),
            "score": c.get("score"),
            "score_prior": c.get("score_prior") or c.get("prior"),
            "source_metadata": c.get("source_metadata"),
            "original_candidate": c,
        }
        oc = n.get("original_candidate") if isinstance(n.get("original_candidate"), dict) else {}
        has_trace = any([
            bool(str(n.get("trace_text") or "").strip()),
            bool(str(n.get("step_text") or "").strip()),
            bool(str(n.get("reasoning_trace") or "").strip()),
            bool(str(n.get("reasoning_steps") or "").strip()),
            bool(str(n.get("derivation") or "").strip()),
            bool(str(n.get("solution_trace") or "").strip()),
            bool(n.get("steps")),
            bool(str(oc.get("trace_text") or "").strip()),
            bool(str(oc.get("step_text") or "").strip()),
            bool(str(oc.get("reasoning_trace") or "").strip()),
            bool(oc.get("steps")),
        ])
        if has_trace:
            traced += 1
        n["trace_available"] = has_trace
        norm_cands.append(n)
    eval_only = dict(r.get("evaluation_only") or {})
    for k in ["gold_answer", "oracle_selector_answer", "oracle_selector_would_fix", "our_correct", "external_correct", "gold_answer_evaluation_only"]:
        if k in r and k not in eval_only:
            eval_only[k] = r.get(k)
    gold_agg = bool(r.get("gold_in_aggregate_answer_groups") or r.get("gold_answer_in_casebook_aggregate_canonical_evaluation"))
    gold_terminal = bool(r.get("gold_in_extracted_terminal_node_finals") or r.get("gold_present_in_candidate_nodes_canonical_evaluation"))
    sel_terminal = bool(r.get("selected_answer_in_extracted_terminal_node_finals") or r.get("current_answer_present_in_nodes"))
    has_any = traced > 0
    all_traced = bool(norm_cands) and traced == len(norm_cands)
    usable = bool(norm_cands) and has_any
    agg_only = gold_agg and (not gold_terminal) and (not sel_terminal)
    o = {
        "case_id": r.get("case_id", f"{src_label}:{idx}"),
        "dataset": r.get("dataset"),
        "example_id": r.get("example_id"),
        "seed": r.get("seed"),
        "budget": r.get("budget"),
        "our_method_name": r.get("our_method_name") or r.get("method"),
        "problem_statement": r.get("problem_statement") or r.get("question"),
        "candidate_nodes": norm_cands,
        "verifier_input": scrub_verifier_input({
            "problem_statement": (r.get("verifier_input") or {}).get("problem_statement") if isinstance(r.get("verifier_input"), dict) else None or r.get("problem_statement"),
            "candidates_for_verifier": [
                {k: c.get(k) for k in ("candidate_id", "source_family", "final_answer", "normalized_answer", "trace_text", "step_text", "steps", "score", "score_prior")}
                for c in norm_cands
            ],
        }, no_gold),
        "evaluation_only": eval_only,
        "current_answer": r.get("current_answer") or r.get("our_final_answer"),
        "selected_answer_group": r.get("selected_answer_group"),
        "provenance_source": src_label,
        "source_package": str(src_path.parent),
        "gold_in_aggregate_answer_groups": gold_agg,
        "gold_in_extracted_terminal_node_finals": gold_terminal,
        "selected_answer_in_extracted_terminal_node_finals": sel_terminal,
        "has_any_candidate_trace": has_any,
        "all_candidates_traced": all_traced,
        "usable_for_trace_aware_selector": usable,
        "aggregate_only_present_not_selected": agg_only,
        "_source_path": str(src_path),
    }
    if contains_banned(o["verifier_input"]):
        raise ValueError("verifier_input contains banned gold/oracle fields")
    text = json.dumps(o)
    if any(t in text.lower() for t in ["sk-", "cohere", "anthropic", "openai_api_key"]):
        raise ValueError("potential secret/api content detected")
    return o


def dedup_key(r: dict[str, Any], cols: list[str]) -> tuple:
    vals = tuple(r.get(c) for c in cols)
    if any(v is None for v in vals):
        return (r.get("dataset"), r.get("example_id"), r.get("source_package"), r.get("case_id"))
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--dedup-key", default="dataset,example_id,seed,budget,our_method_name")
    ap.add_argument("--prefer-source-label", action="append", default=[])
    ap.add_argument("--no-gold-in-verifier-input", action="store_true", default=True)
    a = ap.parse_args()

    prefer = []
    for x in a.prefer_source_label:
        prefer.extend([z.strip() for z in x.split(",") if z.strip()])
    prefer_rank = {k: i for i, k in enumerate(prefer)}
    dedup_cols = [x.strip() for x in a.dedup_key.split(",") if x.strip()]

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=False)

    all_rows = []
    source_order = {}
    for sidx, inp in enumerate(a.input):
        p, label = parse_input(inp)
        source_order[str(p)] = sidx
        for ridx, r in enumerate(iter_jsonl(p)):
            all_rows.append(normalize_record(r, label, p, ridx, a.no_gold_in_verifier_input))

    buckets = defaultdict(list)
    for r in all_rows:
        buckets[dedup_key(r, dedup_cols)].append(r)

    kept, excluded, dedup_rows = [], [], []
    for k, rows in buckets.items():
        ranked = sorted(rows, key=lambda r: (
            -len(r.get("candidate_nodes") or []),
            -sum(1 for c in (r.get("candidate_nodes") or []) if c.get("trace_available")),
            -(1 if r.get("gold_in_extracted_terminal_node_finals") else 0),
            prefer_rank.get(r.get("provenance_source"), 10_000),
            source_order.get(r.get("_source_path"), 10_000),
        ))
        winner = ranked[0]
        kept.append(winner)
        for lose in ranked[1:]:
            ex = dict(lose)
            ex["duplicate_of_case_id"] = winner.get("case_id")
            excluded.append(ex)
            dedup_rows.append({"dedup_key": str(k), "kept_case_id": winner.get("case_id"), "excluded_case_id": lose.get("case_id"), "kept_source": winner.get("provenance_source"), "excluded_source": lose.get("provenance_source")})

    def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(rows)
        cand = sum(len(r.get("candidate_nodes") or []) for r in rows)
        traced = sum(sum(1 for c in (r.get("candidate_nodes") or []) if c.get("trace_available")) for r in rows)
        corr = sum(1 for r in rows if r.get("evaluation_only", {}).get("our_correct") is True)
        wrong = sum(1 for r in rows if r.get("evaluation_only", {}).get("our_correct") is False)
        return {
            "records": n,
            "candidate_nodes": cand,
            "traced_candidate_nodes": traced,
            "cases_with_candidate_nodes": sum(1 for r in rows if (r.get("candidate_nodes") or [])),
            "cases_with_at_least_one_candidate_trace": sum(1 for r in rows if r.get("has_any_candidate_trace")),
            "cases_with_all_candidates_traced": sum(1 for r in rows if r.get("all_candidates_traced")),
            "gold_present_in_aggregate_answer_buckets": sum(1 for r in rows if r.get("gold_in_aggregate_answer_groups")),
            "gold_present_in_extracted_terminal_node_finals": sum(1 for r in rows if r.get("gold_in_extracted_terminal_node_finals")),
            "selected_answer_present_in_extracted_terminal_node_finals": sum(1 for r in rows if r.get("selected_answer_in_extracted_terminal_node_finals")),
            "aggregate_only_present_not_selected_cases": sum(1 for r in rows if r.get("aggregate_only_present_not_selected")),
            "usable_for_trace_aware_selector": sum(1 for r in rows if r.get("usable_for_trace_aware_selector")),
            "current_incumbent_correct_count": corr,
            "current_incumbent_wrong_count": wrong,
            "oracle_ceiling_over_unique_records": (sum(1 for r in rows if r.get("evaluation_only", {}).get("oracle_selector_would_fix")) / n) if n else None,
        }

    overall = metrics(kept)
    overall_out = {
        "total_input_records": len(all_rows),
        "total_unique_records": len(kept),
        "total_duplicates_excluded": len(excluded),
        **overall,
    }
    by_prov = {}
    for p in sorted({r.get("provenance_source") for r in all_rows}):
        in_rows = [r for r in all_rows if r.get("provenance_source") == p]
        k_rows = [r for r in kept if r.get("provenance_source") == p]
        m = metrics(k_rows)
        by_prov[p] = {
            "input_records": len(in_rows), "unique_records_kept": len(k_rows), "duplicates_excluded": len(in_rows)-len(k_rows),
            "candidate_nodes": m["candidate_nodes"], "traced_candidate_nodes": m["traced_candidate_nodes"],
            "gold_present_in_aggregate_answer_buckets": m["gold_present_in_aggregate_answer_buckets"],
            "gold_present_in_extracted_terminal_node_finals": m["gold_present_in_extracted_terminal_node_finals"],
            "usable_for_trace_aware_selector": m["usable_for_trace_aware_selector"],
        }

    unified_path = out / "unified_candidate_trace_enriched.jsonl"
    unified_path.write_text("\n".join(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}) for r in kept) + "\n", encoding="utf-8")
    (out / "excluded_or_duplicate_cases.jsonl").write_text("\n".join(json.dumps({k: v for k, v in r.items() if not k.startswith('_')}) for r in excluded) + ("\n" if excluded else ""), encoding="utf-8")

    summary = {"overall": overall_out, "by_provenance_source": by_prov}
    (out / "unified_selector_evidence_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out / "unified_selector_evidence_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["scope", "metric", "value"])
        for k, v in overall_out.items(): w.writerow(["overall", k, v])
        for p, d in by_prov.items():
            for k, v in d.items(): w.writerow([p, k, v])
    with (out / "deduplication_report.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dedup_key", "kept_case_id", "excluded_case_id", "kept_source", "excluded_source"])
        w.writeheader(); w.writerows(dedup_rows)

    report = ["# Unified Selector Evidence Report", "", f"- Total input records: {len(all_rows)}", f"- Total unique records: {len(kept)}", f"- Total duplicates excluded: {len(excluded)}", ""]
    (out / "unified_selector_evidence_report.md").write_text("\n".join(report), encoding="utf-8")

    manifest = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "inputs": a.input,
        "output_dir": str(out),
        "dedup_key": dedup_cols,
        "prefer_source_label": prefer,
        "no_gold_in_verifier_input": a.no_gold_in_verifier_input,
        "git_commit": subprocess.getoutput("git rev-parse HEAD"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
