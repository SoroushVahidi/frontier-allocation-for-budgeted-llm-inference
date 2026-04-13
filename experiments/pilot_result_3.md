# Pilot Result 3: Immediate min-expand safeguard for adaptive controller

## Objective

Implement the smallest fix recommended by `pilot_diagnosis_1.md`: break the deterministic `verify -> prune` loop by requiring a minimum number of expansions per branch before verify/prune can dominate.

## Code changes (minimal)

- Added `min_expansions_before_prune` to `AdaptiveController`.
- Added forced-expand logic per branch until that floor is reached.
- Preserved old controller behavior via `min_expansions_before_prune: 0`.
- Added a new controller variant: `adaptive_min_expand`.
- Added config support in `configs/pilot_gsm8k.yaml`.
- Added `forced_expand` to adaptive action trace rows for transparency.

## Exact commands used

```bash
python -m pip install datasets -q
python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml
python scripts/evaluate_pilot_gsm8k.py outputs/pilot/20260412T231805Z
python - <<'PY'
import json,collections
from pathlib import Path
run_dir=Path('outputs/pilot/20260412T231805Z')
rows=[json.loads(l) for l in (run_dir/'adaptive_diagnostics.jsonl').read_text().splitlines() if l.strip()]
out={}
for m in sorted({r['method'] for r in rows}):
    subset=[r for r in rows if r['method']==m]
    ac=collections.Counter(); first=collections.Counter(); forced=0; zero=0; anyexp=0
    for r in subset:
        tr=r['action_trace']
        c=collections.Counter(a['action'] for a in tr)
        ac.update(c)
        first[tr[0]['action'] if tr else 'none']+=1
        forced += sum(1 for a in tr if a.get('forced_expand'))
        if c.get('expand',0)==0: zero +=1
        else: anyexp +=1
    tot=sum(ac.values())
    out[m]={
      'action_counts':dict(ac),
      'action_fractions':{k:v/tot for k,v in sorted(ac.items())},
      'forced_expand_count':forced,
      'examples_with_any_expand':anyexp,
      'examples_zero_expand':zero,
      'first_action_counts':dict(first),
    }
(run_dir/'adaptive_comparison_stats.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
PY
```

## Run artifacts

- Run directory: `outputs/pilot/20260412T231805Z`
- Summary: `outputs/pilot/20260412T231805Z/summary.json`
- Adaptive action stats: `outputs/pilot/20260412T231805Z/adaptive_comparison_stats.json`

## Data/provider/model/budgets

From `manifest.json`:

- Data: `huggingface:gsm8k` (`test` split), pilot size `12`.
- Backend mode: `openai_api`.
- Provider/model: `openai` / `gpt-4.1-mini`.
- Temperature: `0.2`.
- Max output tokens: `220`.
- Budget: `max_actions_per_problem = 8`.

Note: `api_key_present` is `false` in this environment; requests still executed via configured `OPENAI_BASE_URL` proxy path.

## Metrics table (all 5 methods)

| Method | Accuracy | Avg actions | Avg expansions | Avg verifications | Avg surviving branches | Budget exhaustion rate |
|---|---:|---:|---:|---:|---:|---:|
| Greedy single-path | 1.0000 | 3.3333 | 3.3333 | 0.0000 | 1.0000 | 0.0000 |
| Best-of-N | 0.8333 | 8.0000 | 6.5000 | 1.5000 | 2.2163 | 1.0000 |
| Fixed-width beam | 1.0000 | 6.4167 | 6.4167 | 0.0000 | 2.0000 | 0.2500 |
| Adaptive (old) `adaptive_expand_verify_prune` | 0.0000 | 1.0000 | 0.0000 | 1.0000 | 0.5000 | 0.0000 |
| Adaptive (new) `adaptive_min_expand` | 0.5833 | 7.9167 | 6.4167 | 1.5000 | 2.6292 | 0.4167 |

## Action statistics: old vs new adaptive

### Old adaptive (`adaptive_expand_verify_prune`)
- Action counts: `expand=0`, `verify=12`, `prune=12`
- Fractions: `expand=0.0000`, `verify=0.5000`, `prune=0.5000`
- Examples with any expand: `0 / 12`
- Examples with zero expand: `12 / 12`
- First action counts: `verify=12`

### New adaptive (`adaptive_min_expand`)
- Action counts: `expand=77`, `verify=18`, `prune=1`
- Fractions: `expand=0.8021`, `verify=0.1875`, `prune=0.0104`
- Forced expands (due to safeguard): `43`
- Examples with any expand: `12 / 12`
- Examples with zero expand: `0 / 12`
- First action counts: `expand=12`

## Did this fix the zero-expand failure?

**Yes.** The zero-expand collapse is fixed for the safeguarded variant in this pilot (`0/12` zero-expand examples vs `12/12` for old adaptive).

## Does safeguarded adaptive now expand branches?

**Yes.** It performs substantial expansion (`avg_expansions=6.4167`, `77` total expands).

## Did performance improve?

**Yes vs old adaptive, but still not competitive with strongest baselines in this run.**

- Old adaptive accuracy: `0.0000`
- New safeguarded adaptive accuracy: `0.5833`
- Best baseline accuracy in this pilot: `1.0000` (greedy and beam)

So the engineering bug is addressed (controller explores), but empirical quality remains below top baselines.

## Honest interpretation

- The safeguard successfully turns a degenerate policy into a minimally functional exploring controller.
- This supports the diagnosis that the immediate failure was control-flow collapse, not merely “hard examples.”
- However, this is still a tiny sample (`n=12`), so effect sizes are noisy.
- The safeguarded controller likely still needs score/threshold/verifier calibration; this is not evidence that adaptive control is already superior.
