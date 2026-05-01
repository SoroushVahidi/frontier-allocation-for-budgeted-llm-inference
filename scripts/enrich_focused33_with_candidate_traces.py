#!/usr/bin/env python3
"""Enrich focused loss-casebook rows with per-candidate traces from upstream run artifacts."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.answer_grouped_outcome_verifier import CandidateAnswer  # noqa: E402
from experiments.output_layer_repair import canonicalize_answer  # noqa: E402
from experiments.selector_candidate_extraction import (  # noqa: E402
    _extract_trace,
    build_candidates_from_metadata,
)
from scripts.selector_reconstruction import reconstruct_groups  # noqa: E402


def _norm_plain(s: Any) -> str:
    return str(s or "").strip().lower()


def canon_for_dataset(raw: Any, dataset: str) -> str:
    txt = str(raw or "").strip()
    if not txt:
        return ""
    c = canonicalize_answer(txt, dataset=dataset)
    return _norm_plain(c) if c else _norm_plain(txt)


def canonical_group_set(items: Iterable[str], dataset: str) -> set[str]:
    out: set[str] = set()
    for x in items:
        s = canon_for_dataset(x, dataset)
        if s:
            out.add(s)
        elif _norm_plain(x) == "__unknown__":
            out.add("__unknown__")
    return out


def canonical_node_answer_set(nodes: list[dict[str, Any]], dataset: str) -> set[str]:
    return canonical_group_set((str(n.get("final_answer") or "") for n in nodes), dataset)


def normalize_source_path(repo_root: Path, source_dir: str) -> Path:
    """Resolve MMFS/home path or relative path against repo."""
    txt = str(source_dir or "").strip()
    candidates = []
    candidate_path = Path(txt)
    mmfs_home = Path("/mmfs1/home/sv96/adaptive-reasoning-budget-allocation")
    if txt.startswith(str(mmfs_home)):
        suffix = txt[len(str(mmfs_home)) :].lstrip("/\\")
        candidates.append(repo_root / suffix)
    candidates.append(candidate_path.resolve() if candidate_path.is_absolute() else repo_root / txt.replace("/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/", "").lstrip("/"))
    candidates.append(candidate_path.resolve() if candidate_path.is_absolute() else repo_root / candidate_path)

    seen: set[Path] = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            if c.exists():
                return c
    first = candidates[0] if candidates else repo_root
    return Path(first)


def filter_focused_loss_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for r in rows:
        if str(r.get("trace_available", "")).strip() != "1":
            continue
        if str(r.get("gold_present_in_candidate_groups", "")).strip() != "1":
            continue
        if str(r.get("oracle_selector_would_fix", "")).strip() != "1":
            continue
        out.append(dict(r))
    return out


def _match_per_example_record(
    line_obj: dict[str, Any],
    *,
    dataset: str,
    example_id: str,
    seed: int,
    budget: int,
    method: str,
) -> bool:
    if line_obj.get("dataset") != dataset or line_obj.get("example_id") != example_id:
        return False
    if int(line_obj.get("seed", -999)) != seed or int(line_obj.get("budget", -999)) != budget:
        return False
    return _norm_plain(line_obj.get("method")) == _norm_plain(method)


def iter_jsonl_records(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj
            except json.JSONDecodeError:
                continue


def load_per_example_match(
    per_example_path: Path,
    *,
    dataset: str,
    example_id: str,
    seed: int,
    budget: int,
    method: str,
) -> tuple[dict[str, Any] | None, str]:
    for obj in iter_jsonl_records(per_example_path):
        if _match_per_example_record(obj, dataset=dataset, example_id=example_id, seed=seed, budget=budget, method=method):
            return obj, "exact"
    return None, "missing"


def load_final_branch_states_match(
    fbs_path: Path,
    *,
    example_id: str,
    seed: int,
    budget: int,
    method: str,
) -> tuple[dict[str, Any] | None, str]:
    for obj in iter_jsonl_records(fbs_path):
        if obj.get("example_id") != example_id:
            continue
        if int(obj.get("seed", -999)) != seed or int(obj.get("budget", -999)) != budget:
            continue
        if _norm_plain(obj.get("method")) != _norm_plain(method):
            continue
        return obj, "exact"
    return None, "missing"


def resolve_raw_record(source_dir: Path, row: dict[str, str]) -> tuple[dict[str, Any] | None, Path | None, str, list[str]]:
    """Return raw JSON object, filesystem path matched, confidence, notes."""
    notes: list[str] = []
    dataset = str(row["dataset"]).strip()
    example_id = str(row["example_id"]).strip()
    seed = int(row["seed"])
    budget = int(row["budget"])
    method = str(row["our_method_name"]).strip()

    pep = source_dir / "per_example_records.jsonl"
    if pep.exists():
        rec, how = load_per_example_match(pep, dataset=dataset, example_id=example_id, seed=seed, budget=budget, method=method)
        if rec is not None:
            return rec, pep, how, notes
        try:
            notes.append(f"no exact match in {pep.relative_to(REPO_ROOT)}")
        except ValueError:
            notes.append(f"no exact match in {pep}")

    fbsp = source_dir / "final_branch_states.jsonl"
    if fbsp.exists():
        rec, how = load_final_branch_states_match(fbsp, example_id=example_id, seed=seed, budget=budget, method=method)
        if rec is not None:
            return rec, fbsp, how, notes
        try:
            notes.append(f"no exact match in {fbsp.relative_to(REPO_ROOT)}")
        except ValueError:
            notes.append(f"no exact match in {fbsp}")

    notes.append(f"no per_example_records.jsonl or final_branch_states.jsonl under {source_dir}")
    return None, None, "missing", notes


def synthetic_row_for_groups(raw_record: dict[str, Any], *, mode: str) -> dict[str, Any]:
    if mode == "per_example":
        return raw_record
    return {"result_metadata": {"final_branch_states": raw_record.get("final_branch_states") or []}}


def gather_branch_list(metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    source_keys = [
        "selector_candidate_pool",
        "final_branch_states",
        "branch_states",
        "final_nodes",
        "candidate_answers",
        "answer_groups",
    ]
    for key in source_keys:
        rows = metadata.get(key, [])
        if isinstance(rows, list) and rows:
            br = [x for x in rows if isinstance(x, dict)]
            if br:
                return br, key
    return [], None


def branches_and_metadata(raw_record: dict[str, Any], mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return flat branch dicts plus metadata dict for build_candidates fallback."""
    if mode == "per_example":
        md = raw_record.get("result_metadata") or {}
        br, _src = gather_branch_list(md if isinstance(md, dict) else {})
        return br, md if isinstance(md, dict) else {}
    pools = raw_record.get("final_branch_states") or []
    if isinstance(pools, list):
        br = [x for x in pools if isinstance(x, dict)]
    else:
        br = []
    return br, {"final_branch_states": br}


def branch_to_node(branch: dict[str, Any], *, question: str, idx: int, source_hint: str | None, selected_answer: str) -> dict[str, Any]:
    cid = str(branch.get("branch_id") or branch.get("candidate_id") or branch.get("id") or f"branch_{idx}")
    final_ans = str(
        branch.get("predicted_answer") or branch.get("final_answer") or branch.get("answer") or branch.get("extracted_answer") or ""
    ).strip()
    sf = str(
        branch.get("strategy_family")
        or branch.get("source_family")
        or branch.get("source")
        or branch.get("source_id")
        or source_hint
        or cid
    )
    trace_txt = _extract_trace(branch).strip()
    try:
        score = float(branch.get("score", 0.5))
        score = min(max(score, 0.0), 1.0)
    except Exception:
        score = 0.5
    bd = branch.get("branch_depth")
    try:
        depth = int(float(bd)) if bd is not None else 0
    except Exception:
        depth = 0
    iso = branch.get("is_original_selected") if branch.get("is_original_selected") is not None else branch.get("selected")
    sel_flag = iso in (True, 1, "1", "true")
    if not sel_flag:
        if final_ans and _norm_plain(final_ans) == _norm_plain(selected_answer):
            sel_flag = branch.get("is_terminal") in (True, 1, "1")
    node: dict[str, Any] = {
        "candidate_id": cid,
        "source_family": sf,
        "final_answer": final_ans,
        "normalized_answer": _norm_plain(final_ans),
        "trace_text": trace_txt,
        "trace_available": bool(trace_txt),
        "score": score,
        "branch_depth": depth,
        "is_original_selected": int(sel_flag),
    }
    node["hint_for_verifier_only"] = "Do not infer gold correctness from prompts; evaluator supplies labels separately."
    return node


def build_candidate_nodes(
    *,
    raw_record: dict[str, Any],
    mode: str,
    question: str,
    current_answer: str,
) -> tuple[list[dict[str, Any]], int, str | None]:
    branches, md = branches_and_metadata(raw_record, mode)
    source_hint = branches[0].get("strategy_family") if branches else None
    seen: set[tuple[str, str]] = set()
    nodes: list[dict[str, Any]] = []
    if branches:
        for i, br in enumerate(branches):
            n = branch_to_node(br, question=question, idx=i, source_hint=str(source_hint) if source_hint else None, selected_answer=current_answer)
            k = (n["candidate_id"], n["final_answer"])
            if k in seen:
                continue
            seen.add(k)
            nodes.append(n)
        return nodes, len(branches), gather_branch_list(md if mode == "per_example" else {"final_branch_states": branches})[1]

    cands, used_keys = build_candidates_from_metadata(question, md)
    for i, cand in enumerate(cands):
        d = candidate_answer_to_public_dict(cand, idx=i, selected_answer=current_answer)
        nodes.append(d)
    return nodes, len(cands), (used_keys[0] if used_keys else None)


def candidate_answer_to_public_dict(c: CandidateAnswer, *, idx: int, selected_answer: str) -> dict[str, Any]:
    trace_txt = str(c.trace or "").strip()
    sel = _norm_plain(c.final_answer) == _norm_plain(selected_answer)
    return {
        "candidate_id": c.candidate_id,
        "source_family": str(c.source_id or ""),
        "final_answer": c.final_answer,
        "normalized_answer": str(c.normalized_answer or ""),
        "trace_text": trace_txt,
        "trace_available": bool(trace_txt),
        "score": float(c.source_prior),
        "branch_depth": int(round(min(max(float(c.cost_norm), 0.0), 1.0) * 10)),
        "is_original_selected": int(sel),
        "hint_for_verifier_only": "Do not infer gold correctness from prompts; evaluator supplies labels separately.",
    }


def casebook_candidate_strings(casebook_row: dict[str, str]) -> list[str]:
    raw = str(casebook_row.get("all_candidate_answer_groups") or "").strip()
    if not raw:
        return []
    try:
        arr = json.loads(raw)
        return [str(x) for x in arr] if isinstance(arr, list) else []
    except json.JSONDecodeError:
        return []


def verifier_safe_candidates(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip evaluation-only cues; verifier sees problem + traces + final answers only."""
    out = []
    for n in nodes:
        out.append(
            {
                "candidate_id": n.get("candidate_id"),
                "source_family": n.get("source_family"),
                "final_answer": n.get("final_answer"),
                "normalized_answer": n.get("normalized_answer"),
                "trace_text": n.get("trace_text"),
                "branch_depth": n.get("branch_depth"),
                "score": n.get("score"),
            }
        )
    return out


def enriched_record_for_casebook_row(repo_root: Path, row: dict[str, str]) -> dict[str, Any]:
    ds = str(row.get("dataset") or "")
    src = normalize_source_path(repo_root, row["source_artifact"])
    raw, raw_path, conf, lookup_notes = resolve_raw_record(src, row)
    q = str(row.get("problem_statement") or "").strip()
    current = str(row.get("selected_answer_group") or row.get("our_final_answer") or "").strip()

    summary_line: dict[str, Any] = {
        "case_id": row.get("case_id"),
        "dataset": row.get("dataset"),
        "example_id": row.get("example_id"),
        "seed": int(row["seed"]),
        "budget": int(row["budget"]),
        "our_method_name": row.get("our_method_name"),
        "current_answer": str(row.get("our_final_answer") or ""),
        "selected_answer_group": str(row.get("selected_answer_group") or ""),
        "gold_answer_evaluation_only": str(row.get("gold_answer") or ""),
        "problem_statement": q,
        "source_artifact": str(row["source_artifact"]).strip(),
        "source_dir_resolved": str(src),
        "raw_record_path": str(raw_path) if raw_path else "",
        "raw_record_found": bool(raw),
        "raw_record_match_confidence": conf if raw else "missing",
        "lookup_notes": lookup_notes,
        "candidate_count_from_casebook": int(row.get("candidate_count", 0) or 0),
    }

    if not raw:
        summary_line.update(
            {
                "candidate_count_from_raw_metadata": 0,
                "metadata_source_pool": None,
                "candidate_nodes": [],
                "answer_groups_canonical_from_nodes": sorted(canonical_node_answer_set([], ds)),
                "answer_groups_canonical_from_casebook": sorted(canonical_group_set(casebook_candidate_strings(row), ds)),
                "answer_groups_agree_casebook_vs_nodes": False,
                "gold_present_in_candidate_nodes_canonical_evaluation": False,
                "gold_answer_in_casebook_aggregate_canonical_evaluation": False,
                "evaluation_only": {"gold_answer": str(row.get("gold_answer") or ""), "_note": "offline evaluation labels only"},
                "verifier_input": {"problem_statement": q, "candidates_for_verifier": []},
                "enrichment_notes": ["raw record missing upstream"] + lookup_notes,
            }
        )
        return summary_line

    rec_mode = "per_example" if raw_path is not None and raw_path.name == "per_example_records.jsonl" else "subset"

    synth = synthetic_row_for_groups(raw, mode=rec_mode)

    nodes, raw_branch_count, pool_key = build_candidate_nodes(
        raw_record=raw,
        mode=rec_mode,
        question=q,
        current_answer=str(row.get("selected_answer_group") or row.get("our_final_answer") or ""),
    )

    from_nodes_canon = canonical_node_answer_set(nodes, ds)
    casebook_canon = canonical_group_set(casebook_candidate_strings(row), ds)
    gold_norm_canon = canon_for_dataset(row.get("gold_answer"), ds)
    curr_norm_canon = canon_for_dataset(row.get("our_final_answer"), ds)
    gold_in_aggregate_canonical_evaluation = gold_norm_canon in casebook_canon if gold_norm_canon else False
    agree = (
        not (from_nodes_canon.symmetric_difference(casebook_canon))
        if from_nodes_canon and casebook_canon
        else (not casebook_canon and not from_nodes_canon)
    )

    grp_rows = reconstruct_groups(synth)

    enrichment_notes = list(lookup_notes)
    if pool_key:
        enrichment_notes.append(f"pooled_candidates_from_metadata_key={pool_key}")
    if raw_branch_count != len(nodes):
        enrichment_notes.append(f"dedupe_raw_branches:{raw_branch_count}->{len(nodes)}")

    enriched: dict[str, Any] = {
        **summary_line,
        "candidate_count_from_raw_metadata": raw_branch_count,
        "metadata_source_pool": pool_key,
        "candidate_nodes": nodes,
        "answer_groups_canonical_from_nodes": sorted(from_nodes_canon),
        "answer_groups_reconstructed_row": grp_rows,
        "answer_groups_canonical_from_casebook": sorted(casebook_canon),
        "gold_present_in_candidate_nodes_canonical_evaluation": gold_norm_canon in from_nodes_canon if gold_norm_canon else False,
        "gold_answer_in_casebook_aggregate_canonical_evaluation": gold_in_aggregate_canonical_evaluation,
        "current_answer_present_in_nodes": curr_norm_canon in from_nodes_canon if curr_norm_canon else False,
        "answer_groups_agree_casebook_vs_nodes": agree,
        "evaluation_only": {
            "gold_answer": str(row.get("gold_answer") or ""),
            "oracle_selector_answer": str(row.get("oracle_selector_answer") or ""),
            "_note": "Gold/oracle strings are offline evaluation-only; omit from verifier prompts.",
        },
        "verifier_input": {"problem_statement": q, "candidates_for_verifier": verifier_safe_candidates(nodes)},
        "enrichment_notes": enrichment_notes,
    }
    return enriched


def load_trace_csv(casebook_dir: Path) -> list[dict[str, str]]:
    p = casebook_dir / "loss_casebook_trace_complete.csv"
    if not p.exists():
        raise SystemExit(f"Missing casebook CSV: {p}")
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run_enrichment(casebook_dir: Path, output_dir: Path, repo_root: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_all = load_trace_csv(casebook_dir)
    focused = filter_focused_loss_rows(rows_all)
    if len(focused) != 33:
        raise SystemExit(f"Expected 33 focused rows, got {len(focused)}")

    enriched_list: list[dict[str, Any]] = []
    for row in focused:
        enriched_list.append(enriched_record_for_casebook_row(repo_root, row))

    found_count = sum(1 for x in enriched_list if x["raw_record_found"])

    cand_with_nodes = sum(1 for x in enriched_list if x["candidate_nodes"])
    cand_with_some_trace = sum(1 for x in enriched_list if any(n.get("trace_available") for n in x["candidate_nodes"]))
    cand_all_traces = sum(
        1 for x in enriched_list if x["candidate_nodes"] and all(n.get("trace_available") for n in x["candidate_nodes"])
    )
    total_nodes = sum(len(x["candidate_nodes"]) for x in enriched_list)
    total_traced_nodes = sum(1 for x in enriched_list for n in x["candidate_nodes"] if n.get("trace_available"))
    gold_hit_extracted_nodes = sum(1 for x in enriched_list if x.get("gold_present_in_candidate_nodes_canonical_evaluation"))
    gold_hit_casebook_aggregate = sum(1 for x in enriched_list if x.get("gold_answer_in_casebook_aggregate_canonical_evaluation"))

    def disagree_row(rec: dict[str, Any], csv_row: dict[str, str]) -> bool:
        dset = str(csv_row.get("dataset") or "")
        cb = canonical_group_set(casebook_candidate_strings(csv_row), dset)
        gn = canonical_node_answer_set(rec.get("candidate_nodes") or [], dset)
        if not cb and not gn:
            return False
        return cb.symmetric_difference(gn) != set()

    group_disagree = sum(1 for r, cw in zip(enriched_list, focused) if disagree_row(r, cw))

    missing_paths_report = sorted(
        {str(Path(x["source_artifact"])) for x in enriched_list if not x["raw_record_found"]},
        key=lambda s: s,
    )

    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "casebook_dir": str(casebook_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "focused_input_rows": len(focused),
        "raw_records_found": found_count,
        "cases_with_candidate_nodes_positive": cand_with_nodes,
        "cases_with_at_least_one_candidate_trace": cand_with_some_trace,
        "cases_with_all_candidate_traces": cand_all_traces,
        "total_candidate_nodes_extracted": total_nodes,
        "total_candidate_nodes_with_trace_text": total_traced_nodes,
        "cases_gold_canonical_in_extracted_node_finals": gold_hit_extracted_nodes,
        "cases_gold_canonical_in_casebook_candidates_aggregate": gold_hit_casebook_aggregate,
        "cases_casebook_answer_groups_disagree_with_nodes": group_disagree,
        "missing_source_paths_when_raw_record_missing": missing_paths_report,
        "fraction_nodes_with_trace": round(total_traced_nodes / total_nodes, 4) if total_nodes else 0.0,
    }

    jl = output_dir / "focused33_trace_enriched.jsonl"
    with jl.open("w", encoding="utf-8") as fout:
        for row in enriched_list:
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")

    skip_csv_complex = frozenset(
        {"candidate_nodes", "verifier_input", "answer_groups_reconstructed_row", "evaluation_only"}
    )
    csv_cols = sorted({k for row in enriched_list for k in row.keys()} - skip_csv_complex)
    csv_flat: list[dict[str, Any]] = []
    for row in enriched_list:
        flat = {k: row[k] for k in csv_cols if k in row}
        flat["candidate_nodes_json"] = json.dumps(row.get("candidate_nodes") or [])
        flat["verifier_candidates_json"] = json.dumps(row.get("verifier_input") or {}).replace("\n", " ")
        flat["evaluation_only_json"] = json.dumps(row.get("evaluation_only") or {})
        csv_flat.append(flat)
    ocp = output_dir / "focused33_trace_enriched.csv"
    with ocp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in csv_flat for k in r}))
        w.writeheader()
        w.writerows(csv_flat)

    sum_path = output_dir / "focused33_trace_enrichment_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Focused-33 trace enrichment summary\n",
        f"- Generated (UTC): `{summary['generated_at_utc']}`\n",
        f"- Focused rows: **{summary['focused_input_rows']}**\n",
        f"- Raw records found: **{summary['raw_records_found']} / {summary['focused_input_rows']}**\n",
        f"- Cases with candidates: **{summary['cases_with_candidate_nodes_positive']}**\n",
        f"- Cases with ≥1 traced candidate: **{summary['cases_with_at_least_one_candidate_trace']}**\n",
        f"- Cases with every candidate traced: **{summary['cases_with_all_candidate_traces']}**\n",
        f"- Candidate nodes extracted: **{summary['total_candidate_nodes_extracted']}** ({summary['fraction_nodes_with_trace']} with trace text)\n",
        f"- Gold in casebook aggregates (canonical, expected 33): **{summary['cases_gold_canonical_in_casebook_candidates_aggregate']}**\n",
        f"- Gold in extracted node finals (canonical, strict subset): **{summary['cases_gold_canonical_in_extracted_node_finals']}**\n",
        f"- Casebook-vs-node answer group mismatch: **{summary['cases_casebook_answer_groups_disagree_with_nodes']}**\n",
    ]
    if missing_paths_report:
        md_lines.append("\nMissing upstream dirs / records:\n")
        md_lines.extend(f"- `{p}`\n" for p in missing_paths_report)
    (output_dir / "focused33_trace_enrichment_report.md").write_text("".join(md_lines), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--loss-casebook-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--repo-root", default=str(REPO_ROOT))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_enrichment(Path(args.loss_casebook_dir), Path(args.output_dir), Path(args.repo_root))


if __name__ == "__main__":
    main()