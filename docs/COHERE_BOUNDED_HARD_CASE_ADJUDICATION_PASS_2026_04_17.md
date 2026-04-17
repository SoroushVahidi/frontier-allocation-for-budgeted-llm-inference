# Cohere bounded hard-case adjudication pass (2026-04-17)

## A) Short implementation plan

1. Perform explicit Cohere capability check (env vars, SDK/library availability, repo integration references, live API probe).
2. Use one bounded Cohere use case only: strong-model adjudication for hardest ambiguous pairwise branch comparisons (near-tie/adjacent/high-uncertainty).
3. Integrate Cohere output in one concrete way: relabel only high-confidence adjudicated hard pairs, with explicit provenance.
4. Run one matched baseline-vs-improved learner comparison under fixed scaffold (`pairwise` default, `v2` features).

## B) Capability check result

Cohere access is available in this environment for bounded execution.

Checks run:
- `COHERE_API_KEY` presence in environment: present.
- Cohere Python SDK import: initially missing, then installed (`cohere==5.15.0`).
- Repo integration references: none pre-existing (new bounded integration added in this pass).
- Live API probe: succeeded (`command-r-plus-08-2024` returned `OK.`).

Capability-check artifact:
- `outputs/cohere_hard_case_adjudication/cohere_capability_check_20260417.json`

## C) Bounded Cohere use case chosen

Chosen single use case (preferred A):
- **hard-case pair adjudication / relabeling** on a bounded subset.

Selection policy (bounded):
- prioritize pairwise rows with high hard-score driven by:
  - near-tie margin,
  - adjacent-rank structure,
  - higher uncertainty.
- adjudicate only top `N` selected hard pairs (bounded run used `N=18`).

Cohere model used:
- `command-r-plus-08-2024`.

## D) Integration design (single concrete integration)

One integration only:
- replace pairwise label on selected hard rows **only when Cohere confidence >= threshold** and winner is non-tie.

Provenance fields added to improved target rows:
- `label_source: "cohere_adjudicated_hard"`
- `cohere_adjudicated`, `cohere_replaced`, `cohere_model`, `cohere_confidence`
- `replaced_approx_label`
- `supervision_reliability_weight`

New bounded artifact families:
- raw adjudications/provenance:
  - `outputs/cohere_hard_case_adjudication/cohere_hard_adjudication_v3_20260417/`
- target regimes for matched comparison:
  - `outputs/branch_label_bruteforce_targets/cohere_hard_adjudication_v3_20260417/regime_all_pairs/`
  - `outputs/branch_label_bruteforce_targets/cohere_hard_adjudication_v3_20260417/regime_cohere_hard_adjudicated/`

## E) Matched comparison run

Matched run artifact:
- `outputs/branch_label_bruteforce_learning/cohere_hard_adjudication_matched_v3_20260417/`

Compared:
1. baseline: `all_pairs`
2. improved: `cohere_hard_adjudicated`

Settings:
- seeds: `11,29,47`
- feature set: `v2`
- same learning scaffold, only target regime changed.

## F) Result summary (machine-readable and concise)

Machine-readable delta summary:
- `outputs/branch_label_bruteforce_learning/cohere_hard_adjudication_matched_v3_20260417/cohere_delta_summary.json`

Bounded result in this run:
- Cohere-selected hard pairs: `18`
- Cohere-replaced pairs: `10`
- Pairwise accuracy (mean): `0.6313 -> 0.4582` (degraded)
- Top-1 (mean): `0.6389 -> 0.5556` (degraded)
- Near-tie (mean): `0.1667 -> 0.1667` (flat)
- Adjacent-rank (mean): `0.6171 -> 0.4945` (degraded)

Conservative conclusion:
- Cohere capability was available and fully exercised in a bounded provenance-aware pass.
- This specific bounded relabeling policy **did not improve** the hard-case bottleneck; it degraded overall and adjacent-rank behavior while leaving near-tie unchanged.
- Next likely step (still bounded) is to tighten adjudication acceptance policy (e.g., stricter confidence + consistency checks against existing signals) before allowing label replacement.

## Commands executed

```bash
python -m pip install -q cohere==5.15.0

python - <<'PY'
import os, json
import cohere
co=cohere.ClientV2(api_key=os.environ['COHERE_API_KEY'])
r=co.chat(model='command-r-plus-08-2024', messages=[{'role':'user','content':'Return exactly OK'}], max_tokens=5, temperature=0)
print(r)
PY

python scripts/cohere_adjudicate_hard_pairs.py \
  --labels-dir outputs/branch_label_bruteforce/dq_base_approx_20260417 \
  --run-id cohere_hard_adjudication_v3_20260417 \
  --model command-r-plus-08-2024 \
  --max-pairs 18 \
  --near-tie-margin 0.03 \
  --replace-confidence-min 0.6 \
  --max-retries 8 \
  --retry-sleep-sec 4.0

python scripts/run_target_fidelity_regime_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/cohere_hard_adjudication_v3_20260417 \
  --run-id cohere_hard_adjudication_matched_v3_20260417 \
  --seeds 11,29,47 \
  --near-tie-margin 0.03 \
  --feature-set v2
```
