# Rao-Kupper independent confirmation result note (new-paper track)

Date: 2026-04-14  
Run: `outputs/new_paper/raokupper_confirmation/20260414T223500Z`

## Scope
Final bounded confirmation pass for proxy BT vs Rao-Kupper under matched settings, using a **fresh seed set** and no heavy/API-backed evaluation.

## Matched setup used
- Dataset: `openai/gsm8k` pilot subset
- Seeds: `81,82,83,84` (independent from prior `71-74`)
- Subset size: `18`
- Ranking episodes: `130`
- Budget: `10`
- Compared methods:
  - `adaptive_bt_pairwise` (proxy BT baseline)
  - `adaptive_bt_pairwise_tie_aware_raokupper` (primary tie supervision set to `none`, per latest matched-audit best)
  - `adaptive_bt_pairwise_tie_aware_davidson` (reference)
  - `oracle_reference`

## Main outcome
This independent confirmation **did not support promotion** of Rao-Kupper to default:
- Proxy BT mean controller accuracy: `0.5417`
- Rao-Kupper (`none`) mean controller accuracy: `0.5139`
- Mean delta (Rao-Kupper - proxy): `-0.0278`
- Seed wins/losses/ties: `2/1/1` (mixed, with negative mean delta)

## Near-tie slice
- Primary Rao-Kupper (`none`) was effectively flat vs proxy BT on near-tie broad/extreme slices in this run.
- No repeat of a clear near-tie gain signal.

## Tie-supervision check within the same run
- `tie_or_uncertain` was the best Rao-Kupper mode this run (`+0.0278` vs proxy), while `none`/`strict_tie` were below proxy.
- This flips the previous matched-audit preference and indicates unresolved mode sensitivity under bounded variance.

## Decision answers
- Did Rao-Kupper win again in an independent matched run? **No (mixed/not confirmed for primary mode).**
- Is gain now strong enough to trust above plain proxy BT? **No.**
- Should proxy BT remain default? **Yes.**
- Should Rao-Kupper be promoted to recommended lightweight default now? **No.**
- Should Rao-Kupper remain experimental-leading branch? **Yes.**

## Repo guidance updates made
- Updated `docs/BRANCH_SCORER_STATUS.md` with an explicit conservative switch policy:
  - default remains proxy BT unless repeated independent matched wins hold,
  - near-tie non-regression required,
  - fresh-seed reproduction required before default switch.
- Added a convenience confirmation entry point:
  - `scripts/run_new_paper_raokupper_confirmation.py`
  - wraps matched resolution audit with bounded confirmation defaults.
