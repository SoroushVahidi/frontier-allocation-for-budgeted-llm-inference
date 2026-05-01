#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

KEYWORDS = ["candidate", "candidates", "candidate_nodes", "candidate_trace", "final_branch", "branch_states", "answer_groups", "traces"]
TRACE_FIELDS = ["trace_text", "step_text", "reasoning_trace", "reasoning_steps", "steps", "derivation", "solution_trace", "trace", "rationale", "full_text"]
ANS_FIELDS = ["final_answer", "answer", "normalized_answer", "selected_answer", "predicted_answer", "final"]


def iter_jsonl(p: Path):
    for ln in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if ln.strip():
            x = json.loads(ln)
            if isinstance(x, dict):
                yield x


def safe_str(s: str) -> dict[str, Any]:
    return {"type": "str", "length": len(s), "preview": s[:80]}


def sanitize(v: Any, k: str = "") -> Any:
    kl = k.lower()
    if any(x in kl for x in ["gold_answer", "oracle_selector", "token", "api_key", "secret", "credential"]):
        if isinstance(v, str):
            return {"type": "str", "length": len(v), "preview": "[REDACTED]"}
        return {"type": type(v).__name__}
    if isinstance(v, str):
        return safe_str(v)
    if isinstance(v, dict):
        return {kk: sanitize(vv, kk) for kk, vv in list(v.items())[:40]}
    if isinstance(v, list):
        return {"type": "list", "length": len(v), "first": sanitize(v[0]) if v else None}
    return {"type": type(v).__name__, "value": v if isinstance(v, (bool, int, float)) else None}


def find_candidate_paths(obj: Any, path: str = ""):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            lk = k.lower()
            if any(tok in lk for tok in KEYWORDS):
                if isinstance(v, list):
                    found.append((p, len(v), v[0] if v and isinstance(v[0], dict) else None))
            found.extend(find_candidate_paths(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            found.extend(find_candidate_paths(v, f"{path}[{i}]"))
    return found


def candidate_shape(c: dict[str, Any] | None):
    if not isinstance(c, dict):
        return None
    trace_field = next((f for f in TRACE_FIELDS if f in c and ((isinstance(c[f], str) and c[f].strip()) or (isinstance(c[f], list) and c[f]))), None)
    ans_field = next((f for f in ANS_FIELDS if f in c), None)
    norm_field = "normalized_answer" if "normalized_answer" in c else None
    trace_meta = None
    if trace_field:
        tv = c.get(trace_field)
        trace_meta = {"type": type(tv).__name__, "length": len(tv) if isinstance(tv, (str, list)) else None}
    return {"keys": sorted(c.keys()), "final_answer_like_field": ans_field, "normalized_answer_like_field": norm_field, "trace_like_field": trace_field, "trace_meta": trace_meta}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--max-records', type=int, default=3)
    ap.add_argument('--output-dir', required=True)
    a = ap.parse_args()
    out = Path(a.output_dir); out.mkdir(parents=True, exist_ok=False)

    rows = list(iter_jsonl(Path(a.input)))[:a.max_records]
    recs = []
    summary = {"input": a.input, "max_records": a.max_records, "records": []}
    for i, r in enumerate(rows):
        vi = r.get('verifier_input') if isinstance(r.get('verifier_input'), dict) else {}
        ev = r.get('evaluation_only') if isinstance(r.get('evaluation_only'), dict) else {}
        cand_paths = find_candidate_paths(r)
        rec_summary = {
            "record_index": i,
            "top_level_keys": sorted(r.keys()),
            "verifier_input_keys": sorted(vi.keys()),
            "evaluation_only_keys": sorted(ev.keys()),
            "top_level_candidate_nodes_exists": 'candidate_nodes' in r,
            "top_level_candidate_nodes_len": len(r.get('candidate_nodes')) if isinstance(r.get('candidate_nodes'), list) else None,
            "top_level_candidates_len": len(r.get('candidates')) if isinstance(r.get('candidates'), list) else None,
            "vi_candidates_for_verifier_len": len(vi.get('candidates_for_verifier')) if isinstance(vi.get('candidates_for_verifier'), list) else None,
            "vi_candidates_len": len(vi.get('candidates')) if isinstance(vi.get('candidates'), list) else None,
            "vi_candidate_nodes_len": len(vi.get('candidate_nodes')) if isinstance(vi.get('candidate_nodes'), list) else None,
            "raw_record_exists": isinstance(r.get('raw_record'), dict),
            "raw_record_result_metadata_exists": isinstance((r.get('raw_record') or {}).get('result_metadata'), dict) if isinstance(r.get('raw_record'), dict) else False,
            "candidate_like_paths": [{"path": p, "list_len": n, "first_candidate_shape": candidate_shape(fc)} for p, n, fc in cand_paths],
            "recommended_extraction_path": cand_paths[0][0] if cand_paths else "none_found",
        }
        summary['records'].append(rec_summary)
        recs.append(sanitize(r))

    (out/'schema_debug_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (out/'schema_debug_records_sanitized.jsonl').write_text('\n'.join(json.dumps(x) for x in recs)+'\n', encoding='utf-8')
    lines=["# Schema Debug Report", f"- Input: `{a.input}`", ""]
    for rec in summary['records']:
        lines.append(f"## Record {rec['record_index']}")
        lines.append(f"- top-level keys: {', '.join(rec['top_level_keys'])}")
        lines.append(f"- verifier_input keys: {', '.join(rec['verifier_input_keys'])}")
        lines.append(f"- evaluation_only keys: {', '.join(rec['evaluation_only_keys'])}")
        lines.append(f"- candidate_nodes len: {rec['top_level_candidate_nodes_len']}")
        lines.append(f"- vi.candidates_for_verifier len: {rec['vi_candidates_for_verifier_len']}")
        lines.append(f"- candidate-like paths: {len(rec['candidate_like_paths'])}")
        lines.append(f"- recommended extraction path: {rec['recommended_extraction_path']}")
        lines.append("")
    (out/'schema_debug_report.md').write_text('\n'.join(lines), encoding='utf-8')

if __name__=='__main__':
    main()
