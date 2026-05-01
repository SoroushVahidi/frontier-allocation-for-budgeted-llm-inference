# COBBE-STYLE OUTCOME VERIFIER FOCUSED33 INITIAL RESULT

## Run metadata
- commit: f3d9eeb
- input artifact path: `outputs/external_loss_casebook_broad_20260430T185500Z/loss_casebook_trace_complete.csv`
- output artifact path: `outputs/cobbe_style_outcome_verifier_focused33_20260430T233209Z`
- paid run executed: **No** (dry-run only)

## Input artifact recovery
The required CSV was initially missing in this checkout. It was regenerated in-place using:

```bash
python scripts/collect_external_loss_casebook.py \
  --target-losses 200 \
  --search-roots outputs archive logs \
  --output-dir outputs/external_loss_casebook_broad_20260430T185500Z \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run \
  --broad-search
```

Observed regeneration outcome in this checkout:
- `trace_complete_selected`: 19
- `selected_cases`: 19
- not 33.

So the historical 33-case focused subset could **not** be reproduced from local artifacts currently available in this checkout.

## Dry-run execution
Command used:

```bash
python scripts/run_cobbe_style_outcome_verifier_focused33.py \
  --loss-casebook-dir outputs/external_loss_casebook_broad_20260430T185500Z \
  --output-dir outputs/cobbe_style_outcome_verifier_focused33_20260430T233209Z \
  --provider cohere \
  --cohere-model command-r-plus \
  --dry-run
```

Dry-run checks:
- selected focused cases: **19** (expected 33 historically, not recovered here)
- `cohere_call_plan.json` written: **yes**
- expected calls before run: **0**
- paid API calls: **none** (dry-run)

## Trace availability audit (critical)
From `selector_focused33_casebook.csv` in this run output:
- cases with full candidate trace for all candidates: **0 / 19**
- cases with selected node trace available: **0 / 19**
- cases with no candidate trace (answer-only fallback): **19 / 19**

Interpretation:
- This run is **not claim-bearing Cobbe-style full-solution verification**.
- In this checkout’s regenerated artifact path, it degenerates to an answer-only diagnostic setting due to missing candidate trace text in extracted metadata.

## Focused-set metrics for this checkout run
| selector | cases | accuracy | fixed | remaining failures | overrides_from_current | override_precision | verifier/cohere calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_default_selector (historical baseline) | 33 | n/a | 0 | 33 | n/a | n/a | n/a |
| support_family_selector (historical baseline) | 33 | n/a | 2 | 31 | n/a | n/a | n/a |
| existing cohere_outcome_verifier_selector (historical baseline) | 33 | n/a | 1 | 32 | n/a | n/a | n/a |
| existing cohere_pairwise_verifier_selector (historical baseline) | 33 | n/a | 0 | 33 | n/a | n/a | n/a |
| oracle_selector (historical baseline) | 33 | n/a | 33 | 0 | n/a | n/a | n/a |
| new cobbe_style_outcome_verifier selector (this checkout run) | 19 | 0.000 | 0 | 19 | 0 | 0.000 | 0 |

Additional summary fields from this run:
- safety_set_size: 0
- safety breaks: 0
- net_fixes_minus_safety_breaks: 0

## Failure analysis taxonomy (>=5 inspected failures)
Given 0/19 fixes and empty candidate extraction in this run output, failures are dominated by artifact/candidate reconstruction limits:
1. missing full candidate trace: **present** (all inspected failures)
2. answer-only verifier limitation: **present** (all inspected failures)
3. current candidate reconstruction lost useful node metadata: **present** (all inspected failures; no extracted candidates)
4. group aggregation issue: **not primary** (no candidate groups available to score)
5. cache/JSON parsing fallback issue: **not primary** (no verifier calls emitted)

Consequence: the blocking issue in this checkout is upstream artifact completeness/recoverability, not yet comparative selector quality.

## Missing dependency note for reproducing historical focused-33
To reproduce the historical 33-case slice exactly, this checkout appears to need the original broad casebook artifact bundle referenced in docs:
- `/mmfs1/home/sv96/adaptive-reasoning-budget-allocation/outputs/external_loss_casebook_broad_20260430T185500Z`

Without that upstream environment/artifacts, local regeneration currently yields 19 trace-complete selected losses rather than 33.
