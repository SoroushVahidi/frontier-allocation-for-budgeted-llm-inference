# Claim revision note (matched-50)

## Why “beats all external baselines” is unsafe
- PAL/PoT fair reaches **40/50** vs production_equiv **36/50** on the same cases.
- Best six-way external oracle is **43/50**, strictly above production_equiv.

## Safer claims
- Production-equiv **beats** L1/SC4/S1/TALE-EP and **ties SC6** (**36** each) but **trails PAL/PoT** by **4** on this slice.
- Production-equiv is **competitive** among budgeted narrative methods; **PAL/PoT is the strongest single external** baseline here.
- **Best external oracle** is an **upper bound** over heterogeneous single-method runs, not one deployable policy.

## Evidence needed for a stronger claim
- Repeated, validated failure families where PAL wins and production-equiv loses, with ablations showing fix lifts **without** hurting PAL-regression cases.
- Larger slices / robustness (not done here).

## Main table
- **Yes**: promote PAL/PoT (and SC6) to the **main comparison table** alongside core4 for transparency.
