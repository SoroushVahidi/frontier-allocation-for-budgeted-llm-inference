# Near-tie improvement result note (new-paper, 2026-04-14)

This pass stays on the **new-paper track** and is fully lightweight/text-only.
No heavy training, no API-backed evaluation, and no binary artifacts were used.

## Run roots
- Hard-pair extraction: `outputs/new_paper/near_tie_pairs/20260414T165052Z/`
- Improvement comparison: `outputs/new_paper/near_tie_improvement/20260414T165052Z/`

## Near-tie pair audit findings
- Total proxy BT pairs: `13,750`
- Hard/near-tie pairs extracted: `10,066` (`73.2%`)
- Dominant hard-pair signals:
  - `dominant_signal_collapse`: `8,511`
  - `small_bt_margin`: `801`
  - `tie_or_uncertain`: `4,648`
- Oracle-join (bounded, partial): `443` joined hard pairs with
  proxy-vs-oracle disagreement rate `0.698` on joined subset.

Interpretation:
- Near-tie/hard comparisons are common and strongly linked to signal collapse / disagreement.
- They appear mostly in higher remaining-budget regimes in this sampled setup (`6+` bucket dominates).

## Cheap targeted improvement tested
- Improvement path: **hard-pair oversampling** for BT training.
  - duplicate near-tie training pairs (oversample factor = 3), then retrain BT.
- This directly targets low-separation comparisons without introducing a heavy model.

## Before vs after
- Pairwise test accuracy (all test pairs): improved model > baseline
  (`0.7524` vs `0.7420` in trainer output).
- Near-tie test slice pairwise delta (improved - baseline): `+0.0074`.
- Controller-level overall delta (near-tie model - baseline BT): `-0.10` (worse).

## Decision
- Near-tie analysis is clearly useful and should continue.
- This specific cheap improvement helps the near-tie slice slightly but hurts overall controller accuracy.
- Do **not** adopt this oversampling variant as the practical default yet.

## Suggested next bounded step
- Keep the hard-pair pipeline and run **smaller/softer weighting schedules**
  (e.g., factor 1.25-1.75 equivalent by probabilistic resampling or confidence blending),
  with explicit guardrails against global-regime regression.
