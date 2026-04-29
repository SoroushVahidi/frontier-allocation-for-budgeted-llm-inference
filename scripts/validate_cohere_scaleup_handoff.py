#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SBATCH = ROOT / 'batch/run_cohere_direct_reserve_v2_vs_external_l1_scaleup_20260428T221840Z.sbatch'
RUNNER = ROOT / 'scripts/run_cohere_real_model_cost_normalized_validation.py'
POST = ROOT / 'scripts/postprocess_cohere_scaleup_outputs.py'
RESULT_DOC = ROOT / 'docs/COHERE_DIRECT_RESERVE_V2_VS_EXTERNAL_L1_SCALEUP_RESULTS_20260428T221908Z.md'
HANDOFF_DOC = ROOT / 'docs/WULVER_HANDOFF_COHERE_DIRECT_RESERVE_V2_SCALEUP_20260428T221840Z.md'

errors: list[str] = []

def need(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)

for p in [SBATCH, RUNNER, POST, RESULT_DOC, HANDOFF_DOC]:
    need(p.exists(), f'missing required file: {p.relative_to(ROOT)}')

if SBATCH.exists():
    txt = SBATCH.read_text(encoding='utf-8')
    for script in [
        'scripts/run_cohere_real_model_cost_normalized_validation.py',
        'scripts/build_real_model_cost_validation_outputs.py',
        'scripts/postprocess_cohere_scaleup_outputs.py',
    ]:
        need(script in txt, f'sbatch missing referenced script: {script}')
    out = re.search(r"#SBATCH --output=(.+)", txt)
    err = re.search(r"#SBATCH --error=(.+)", txt)
    need(out is not None and err is not None, 'sbatch missing stdout/stderr directives')

for d in [ROOT / 'outputs', ROOT / 'outputs/slurm_logs']:
    d.mkdir(parents=True, exist_ok=True)
    need(d.exists(), f'cannot create directory: {d.relative_to(ROOT)}')

if RUNNER.exists():
    rt = RUNNER.read_text(encoding='utf-8')
    need('"direct_reserve_semantic_frontier_v1": {"runtime": "direct_reserve_frontier_gate_v1"' in rt,
         'missing alias: direct_reserve_semantic_frontier_v1 -> direct_reserve_frontier_gate_v1')
    need('"direct_reserve_semantic_frontier_v2": {"runtime": "direct_reserve_frontier_gate_v2"' in rt,
         'missing alias: direct_reserve_semantic_frontier_v2 -> direct_reserve_frontier_gate_v2')

for doc in [RESULT_DOC, HANDOFF_DOC]:
    if not doc.exists():
        continue
    t = doc.read_text(encoding='utf-8').lower()
    need('submitted' not in t or 'not' in t or 'manual' in t,
         f'doc appears to claim submission/completion: {doc.name}')

if RESULT_DOC.exists():
    t = RESULT_DOC.read_text(encoding='utf-8').lower()
    need('pending' in t or 'not executed' in t or 'manual' in t,
         'result scaffold should indicate pending/manual submission status')

if errors:
    print('VALIDATION FAILED')
    for e in errors:
        print(f'- {e}')
    sys.exit(1)
print('VALIDATION OK: Cohere scale-up Wulver handoff package looks consistent.')
