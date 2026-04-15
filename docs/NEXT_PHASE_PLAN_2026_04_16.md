# Next phase plan (2026-04-16)

## Purpose

This note is the updated next-phase plan after the latest stop-vs-act bounded passes.

It supersedes older “next lightweight steps” notes for the current stop-vs-act phase, while keeping them for provenance.

---

## Current phase objective

The current phase objective is:

**improve the local ACT-vs-STOP comparator so that STOP better reflects the downstream opportunity cost of preserving compute.**

This is now more precise than the older formulation “improve target stability.”

Target stability still matters, but the sharper current issue is the meaning of STOP under bounded future allocation.

---

## Main current diagnosis

The project has already tried several sensible fixes:
- uncertainty/threshold refinements,
- label-band refinements,
- one-step counterfactual target,
- small-horizon ACT-vs-STOP target,
- repeated averaging / target stabilization,
- matched-RNG comparator,
- one-step policy-coupled STOP reallocation,
- slightly longer-horizon policy-coupled STOP reallocation.

The consistent lesson is:
- better local estimates are not enough if the comparator is still not aligned,
- and even slightly longer-horizon policy-coupled STOP remained mixed in bounded checks.

So the current best diagnosis is:

**the remaining high-value problem is a bounded, reallocation-aware, policy-coupled STOP baseline that better represents future use of preserved compute.**

---

## Immediate next experimental direction

### Highest-priority next step (updated after latest bounded pass)
Transition from lightweight local target tweaking to a **higher-fidelity offline label-generation plan**:

- keep current default stop-vs-act as anchor,
- define the oracle/distillation label schema and heavy-run manifest,
- run only tiny scaffold/dry-run generation now,
- defer true heavy oracle label generation to compute-rich runs.

### Why this is next
Because current evidence now suggests:
- one-step and slightly longer-horizon policy-coupled STOP tweaks did not produce robust replacement-level gains,
- bounded local comparator engineering appears near diminishing returns,
- the likely remaining lever is stronger supervision quality from deeper oracle-style paired ACT/STOP values.

---

## What a good next target should mean

A stronger STOP baseline should approximate:

- **ACT**: spend one unit of compute on the current branch now, then continue under the normal bounded downstream policy,
- **STOP**: do not spend that unit here now; preserve it and let the downstream allocator reuse it naturally over a small bounded future horizon.

The important part is that STOP should represent:
- released resource,
- downstream policy reuse,
- same remaining-budget context,
- and as much matched future context as practical.

---

## Promotion rule for this phase

Do **not** promote a new mode unless bounded evidence shows:
- improved mean margin versus the heuristic baseline,
- improved win/loss counts versus the current default,
- and at least comparable or better local comparator stability.

If these are not met:
- keep the current default,
- preserve the new mode as provenance,
- and continue treating the line as promising but mixed.

---

## Explicit non-goals right now

Do **not** prioritize:
- heavier controller models,
- broad dataset scaling,
- broad benchmark expansion,
- another threshold-only tweak,
- a major controller redesign,
- or a search for more existing external labeled data as the main immediate fix.

---

## Secondary priorities

After the schema/scaffold bridge is in place, secondary priorities are:
- execute heavy offline oracle label generation on a controlled grid,
- train distilled stop-vs-act models against oracle action-gap labels,
- evaluate whether oracle-distilled supervision can beat the current default and heuristic baseline more reliably than local-target tweaks.

Operational assets for the first pilot are now expected to include:
- `docs/ORACLE_LABEL_PILOT_PROTOCOL_V1.md` (execution protocol),
- `docs/ORACLE_LABEL_PILOT_STATE_SELECTION_PROTOCOL_V1.md` (state extraction/selection protocol),
- `configs/stop_vs_act_oracle_label_pilot_v1.json` (pilot settings + quality gates),
- `configs/stop_vs_act_oracle_pilot_state_selection_v1.json` (state-selection config),
- `scripts/build_oracle_label_pilot_state_manifest.py` (deterministic stratified state manifest builder),
- `scripts/validate_oracle_label_pilot_outputs.py` (dry-run config validation + post-run quality report).

---

## Bottom line

The next phase is not about inventing a different controller family.

It is about making the STOP side of the local stop-vs-act comparison more faithful to:

**what the downstream allocator would actually do with preserved compute.**
