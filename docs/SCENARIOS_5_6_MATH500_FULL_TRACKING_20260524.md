# Scenarios 5 and 6: MATH-500 Full Tracking (2026-05-24)

## Dataset and Contract
- Dataset identifier: `HuggingFaceH4/MATH-500`
- Target examples: 300 per provider (seed 71, budget 6).
- Methods: frontier, L1, S1, TALE (fixed four-source pool).
- Shared exact-case and allowlist files prepared and validated (`mismatch_count=0`, API-free validation).

## Active Job Safety
- Existing Cerebras GSM8K validation process detected and left untouched.
- No attach/kill/restart/interrupt actions were performed on existing jobs.

## Launch Decisions
### Scenario 5: Mistral × MATH-500
- Launch status: **launched**
- tmux session: `mistral_math500_s5_20260524T014937Z`
- output root: `outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z`
- log: `outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z.log`
- estimated logical API call upper bound: `6000`
- immediate progress rows: `22`
- immediate method counts: `{'direct_reserve_semantic_frontier_v2': 22}`

### Scenario 6: Cerebras × MATH-500
- Launch status: **queued/blocked**
- reason: Existing long-running Cerebras GSM8K validation process is active; launching a second Cerebras API run is queued to avoid account-level contention/stall risk.
- planned tmux session (when unblocked): `cerebras_math500_s6_20260524T014938Z`
- planned output root: `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260524T014938Z`
- planned log: `outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260524T014938Z.log`
- estimated logical API call upper bound: `6000`

## Immediate Error Check
- Mistral: no immediate auth/dataset/model startup error in first progress lines.
- Cerebras: not launched in this pass due active-run safety gate.

## Failure Tracking Plan and Outputs
Prepared output targets include full failure case sets, taxonomy summaries, case-level selector outputs, representative failure markdown logs, and algorithm-improvement hypothesis notes for each provider.

## Monitoring Next
Run this non-invasive monitor command later:
```bash
cd /home/soroush/frontier-allocation-for-budgeted-llm-inference
tmux ls || true
ps -eo pid,ppid,etime,stat,pcpu,pmem,cmd | grep -E "mistral_math500_s5|cerebras_frozen_agreement_only_2of3_validation_20260523|run_cohere_real_model_cost_normalized_validation|python3" | grep -v grep || true
python3 - <<'PY'
import pathlib, json, collections
p=pathlib.Path('outputs/scenarios_5_6_math500_full_tracking_20260524/mistral_math500_full_20260524T014937Z/cohere_real_model_cost_normalized_validation_20260524T014937Z/per_example_records.jsonl')
c=collections.Counter()
n=0
if p.exists():
  for line in p.read_text().splitlines():
    if line.strip():
      o=json.loads(line); n+=1; c[o.get("method")]+=1
print({"rows":n,"method_counts":dict(c)})
PY
```

## Confirmation
- No Cohere jobs launched.
- No policy logic changes or promotion decisions made.
