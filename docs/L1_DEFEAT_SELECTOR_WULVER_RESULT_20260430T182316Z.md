# L1 Defeat Selector Wulver Result 20260430T182316Z

- artifact root: `outputs/l1_defeat_selector_wulver_20260430T182316Z`
- paired examples: 5

## Observed Selector Outcomes (fast selector stage)

- `current_dr_v2_selector`: accuracy `0.4`
- `support_family_selector`: accuracy `0.8` (fixes=`2`, breaks=`0`, net=`+2`)
- `cohere_outcome_verifier_selector`: accuracy `0.4`
- `oracle_selector` (evaluation-only): accuracy `0.8`

## Interpretation

- On this small positive-headroom artifact, `support_family_selector` matched the oracle and improved over current DR-v2.
- This is promising, but sample size is too small for selector promotion.
- `oracle_selector` is evaluation-only and must not be used in deployable selection decisions.

## Cohere Verifier Status

- `outputs/l1_defeat_selector_wulver_20260430T182316Z/cohere_verifier/selector_summary.csv` is empty/zeroed (`0.0` rows across selectors).
- This Cohere verifier stage is not claim-bearing for promotion decisions.
- Cohere verifier pipeline should be debugged before any performance claim.

## Next Step

- Run larger validation for `support_family_selector` on explicitly positive-headroom artifacts.
- When oracle does not beat DR-v2/L1, prioritize discovery/coverage repair instead of selector tuning.
