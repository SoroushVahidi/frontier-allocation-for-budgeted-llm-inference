#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
REQUIRED=["strict_f3","direct_reserve_semantic_frontier_v2","direct_reserve_semantic_frontier_v2_outcome_verifier_answer_group_selector_v1","l1_length_control_rl","tale_token_budget_aware_reasoning","s1_simple_test_time_scaling"]
SECRET=re.compile(r"(api[_-]?key|token|secret)",re.I)

def loadj(path):return json.loads(path.read_text())

def audit(outdir:Path):
    probs=[]
    registry=loadj(outdir/'method_registry_snapshot.json')['all']
    if sorted(registry)!=sorted(REQUIRED):probs.append('method_registry_mismatch')
    for m in REQUIRED:
        p=outdir/'per_method_outputs'/f'{m}.jsonl'
        if not p.exists(): probs.append(f'missing_output_{m}')
    manifest=loadj(outdir/'manifest.json')
    blob=json.dumps(manifest)
    if SECRET.search(blob): probs.append('secret_pattern_in_manifest')
    return {'ok':not probs,'problems':probs}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('outdir')
    a=ap.parse_args();r=audit(Path(a.outdir));print(json.dumps(r,indent=2)); raise SystemExit(0 if r['ok'] else 1)
