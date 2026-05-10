# Discovery retry — budget-6 integration plan

Budget **6** is tight; avoid broad self-consistency. Use **one** targeted retry slot when structural
commitment does not apply (no present-not-selected fix) and the run is in the **gold-absent** regime.

## Interaction with `structural_commit_v1`

1. Structural commit runs **after** PAL channel merge (existing order). It repairs commitment/surfacing,
   not missing discovery.
2. If structural abstains **and** answer-group support shows a single weak leaf with no peer agreement,
   mark candidate for **discovery retry** (gold-free proxy: low support diversity + PAL-external mismatch
   in historical bank patterns — implementation TBD).
3. Never spend discovery retry **only** to duplicate structural’s channel; they are orthogonal.

## When to abstain

- Minimal text or unit ambiguity persists after restatement.
- Scaffold triggers disagree (e.g. both rate_table and timeline match); prefer abstain over double retry.

## When to spend extra call

- Exactly **one** scaffold fired with high confidence (mechanism tag or heuristic ≥ medium).
- External reference in offline bank suggests gold existed but tree lacked it (discovery hypothesis).

## When **not** to retry

- Present-not-selected pattern with gold in pool (Track B / structural jurisdiction).
- Known `reproduce_in_minimal_slice` rows without full GSM8K problem text in union.

---

## Schedule A — conservative fixed retry

- Slot 5 or 6 (last expand): if `discovery_eligible` flag set from offline bank features or live
  emptiness signal, run **one** scaffold matching derived family (from lightweight keyword router).
- Cost: **+0** to base if it replaces a generic diversity expand; **+1** if added (must drop a weak expand).

## Schedule B — adaptive last-slot

- Hold last slot until frontier summary is built.
- Trigger retry only if: normalized answer groups ≥2 with tie/near-tie **or** validator/PAL-exec failure
  on incumbent — AND scaffold trigger present.
- Cost: usually **0** net (swap), occasional **1** when frontier collapsed early.

**Recommendation for pilots:** start with **Schedule A** on a frozen list of ~37 gold-absent IDs;
measure harm on PNS + structural guardrails before Schedule B.
