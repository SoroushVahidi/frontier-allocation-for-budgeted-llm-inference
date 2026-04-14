# Rao-Kupper contradiction-resolution audit result note (new-paper track)

Date: 2026-04-14  
Run: `outputs/new_paper/raokupper_resolution_audit/20260414T212146Z`

## Why the contradiction happened
The apparent conflict between:
- "proxy BT safest default" (earlier notes), and
- "global Rao-Kupper strongest" (latest bounded hybrid-gating run)

is plausibly explained by **setup drift + bounded-run variance** rather than a single robust truth shift.

Key mismatches observed across prior artifacts:
- single-run tie-aware comparison used different settings (`seed=73`, subset/ranking defaults not matching later runs)
- tie-aware stability note reported 71-74 with smaller subset/ranking than its script defaults (script defaults include seed 75, subset 20, ranking 150)
- hybrid-gating run used matched 71-74 / subset 18 / ranking 130 and showed stronger Rao-Kupper

So this pass enforced one matched setup for all methods.

## Matched setup used here (cheap + bounded)
- Seeds: `71,72,73,74`
- Dataset: `openai/gsm8k` pilot subset
- Subset size: `18`
- Ranking episodes: `130`
- Budget: `10`
- Same controller/eval regime for all compared methods
- Compared methods:
  - `adaptive_bt_pairwise` (proxy BT)
  - `adaptive_bt_pairwise_tie_aware_raokupper`
  - `adaptive_bt_pairwise_tie_aware_davidson`
  - `oracle_reference`

## Main matched result
From `stability_summary.csv`:
- proxy BT mean controller accuracy: **0.4167**
- Rao-Kupper (tie_or_uncertain) mean controller accuracy: **0.5417**
- Rao-Kupper vs proxy: **wins/losses/ties = 3/0/1**, mean delta **+0.1250**

So in this tightly matched bounded run, Rao-Kupper again beats proxy BT.

## Tie-supervision calibration check (Rao-Kupper only)
Tested only:
- `none`
- `strict_tie`
- `tie_or_uncertain`

Aggregate result in this run:
- `none`: mean controller acc **0.5556**, delta vs proxy **+0.1389**
- `strict_tie`: identical to `none` here (expected with effectively no exact ties)
- `tie_or_uncertain`: mean controller acc **0.5417**, delta vs proxy **+0.1250**

Best mode in this bounded run: **`none`** (very close to `strict_tie`; both above `tie_or_uncertain`).

## Overall-up vs near-tie issue
In this run, near-tie slices were not uniformly worse; they were mostly positive for Rao-Kupper:
- mean delta in `near_tie:extreme`: **+0.1584**
- mean delta in `near_tie:medium`: **+0.0522**
- but high-confidence/global slices were near-flat or slightly negative

Interpretation: gains appear regime-dependent and calibration-like, not a guaranteed universal improvement.

## Direct answers requested
- Was recent strong Rao-Kupper real or likely noise? **Likely real in this matched bounded setting, but still bounded and seed-sensitive.**
- In matched multi-seed setting, does Rao-Kupper beat proxy BT? **Yes (3/0/1 vs proxy).**
- Which tie-supervision mode worked best? **`none` (≈`strict_tie`), then `tie_or_uncertain`.**
- Why might overall improve without hardest near-tie fix? **Regime-dependent calibration effects; not all slices move together.**
- Should proxy BT remain default? **Conservative answer: keep proxy BT as default until another independent matched rerun confirms promotion criteria.**
- Should Rao-Kupper be promoted to default now? **Not yet; keep as the main experimental branch with stronger evidence than before.**

## Conservative conclusion
This resolves the contradiction toward: "Rao-Kupper may be stronger than previously thought under matched settings," but evidence is still bounded. Treat Rao-Kupper as the top lightweight experimental branch, while deferring default promotion pending one more independent matched stability confirmation.
