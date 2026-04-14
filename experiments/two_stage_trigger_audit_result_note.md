# Two-stage trigger audit result note (new-paper, 2026-04-14)

This pass stays entirely on the **new-paper track** and is a compact keep-or-drop diagnostic.
No heavy training, no API-backed eval, no binary artifacts.

## Why this run
After the lightweight stability audit, baseline proxy BT remained safest, while two-stage gains looked fragile.
This run asks a narrower question:

> when stage-2 fires, does it help enough to justify keeping the branch?

## Setup (bounded)
- Output root: `outputs/new_paper/two_stage_trigger_audit/20260414T195047Z_rerun/`
- Seeds: `61,62,63,64`
- Budget: `10`
- Ranking episodes per seed: `180`
- Eval subset per seed: `24`
- Fixed tie-model family: **decision stump on compact features** trained on `tie_or_uncertain==1` train pairs
- Threshold grid only (no new model family):
  - `near_tie_margin ∈ {0.04, 0.06, 0.08}`
  - `min_tie_confidence ∈ {0.00, 0.10, 0.20}`

## What was measured
For each seed/config:
- trigger coverage (how often stage-2 fires)
- triggered-regime composition (low budget, high verify, stalled, tie-like, tiny base-gap)
- triggered effect split (improve vs hurt vs unchanged)
- pair delta vs baseline
- controller delta vs baseline

## Direct answers

### 1) How often is the two-stage tie-breaker triggered?
Very infrequently in this compact sweep.
- Mean trigger-rate range over configs: **0.000 to 0.031** of test pairs.

### 2) In triggered cases, does it help more often than hurt?
No robustly.
- For practical firing configs, help/hurt is generally below 1.
- Example (`m0p06_c0p00`): improve rate `0.221`, hurt rate `0.295`.

### 3) Is there a narrow safer trigger region?
Only a **degenerate** one:
- `m0p08_c0p20` had the highest mean controller delta (`+0.0208`) but trigger-rate was ~`0.001`.
- That means it is mostly equivalent to baseline (near-never firing), not a strong selective benefit.

### 4) Is positive mean effect likely selective benefit or noise?
Likely **unstable/noisy or near-no-op behavior**.
The apparent best config gains come from extremely low activation, not clear help>hurt selective utility.

### 5) Keep/drop decision
Conservative recommendation:
- **Baseline default:** keep `adaptive_bt_pairwise`.
- **Two-stage branch:** keep as **diagnostic-only** for now.
- Do not prioritize more tuning unless a bounded repeat shows:
  - non-trivial trigger coverage,
  - help/hurt clearly > 1,
  - and repeatable positive controller delta.

## Practical conclusion
This audit reduced uncertainty mainly by showing what *not* to trust:
- broad two-stage triggering hurts/mixes,
- tight gating avoids damage mostly by rarely firing,
- no convincing selective-safe operating region was found yet.
