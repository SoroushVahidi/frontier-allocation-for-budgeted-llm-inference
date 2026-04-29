#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

REQ_DOCS=[
    'docs/CANONICAL_PROJECT_STATE_AND_NEXT_STEPS_20260429.md',
    'docs/METHOD_REGISTRY_CANONICAL_20260429.md',
    'docs/RESULTS_INDEX_CANONICAL_20260429.md',
    'docs/SCRIPT_REGISTRY_CANONICAL_20260429.md',
    'docs/PAPER_SOURCE_OF_TRUTH.md',
]


def parse_method_rows(path: Path):
    rows=[]
    for ln in path.read_text(encoding='utf-8').splitlines():
        if not ln.startswith('|') or 'method ID' in ln or ln.startswith('|---'):
            continue
        cols=[c.strip() for c in ln.strip('|').split('|')]
        if len(cols)<12: continue
        rows.append(cols)
    return rows


def main()->int:
    errs=[]
    for d in REQ_DOCS:
        if not (ROOT/d).exists(): errs.append(f'missing required doc: {d}')

    reg=ROOT/'docs/METHOD_REGISTRY_CANONICAL_20260429.md'
    runner=(ROOT/'scripts/run_cohere_real_model_cost_normalized_validation.py').read_text(encoding='utf-8')
    methods_map=set(re.findall(r'"([a-z0-9_]+)": \{"runtime":', runner))
    rows=parse_method_rows(reg)
    recommended=(ROOT/'docs/CANONICAL_PROJECT_STATE_AND_NEXT_STEPS_20260429.md').read_text(encoding='utf-8').lower()

    for r in rows:
        method,live,diag=r[0],r[2].lower(),r[3].lower()
        if method=='direct_reserve_semantic_frontier_v2_thresholded_ordered' and live.startswith('yes'):
            errs.append('thresholded_ordered cannot be live-runnable in canonical registry')
        if live.startswith('yes') and method not in methods_map and 'cobbe-style' not in method.lower() and 'bt/tie-aware' not in method.lower() and 'prm' not in method.lower():
            errs.append(f'live-runnable method missing from runner METHODS map: {method}')

    default_methods=re.search(r'DEFAULT_METHODS = "([^"]+)"', runner)
    if default_methods:
        defs=set(default_methods.group(1).split(','))
        if 'direct_reserve_semantic_frontier_v2_thresholded_ordered' in defs:
            errs.append('diagnostic-only thresholded_ordered appears in DEFAULT_METHODS')

    if 'outcome_verifier_rerank_v1' not in recommended:
        errs.append('next recommended selector path does not mention outcome_verifier_rerank_v1')

    if errs:
        print('repository status consistency: FAIL')
        for e in errs: print('-',e)
        return 1
    print('repository status consistency: PASS')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
