# Current merged research baseline (post–PR #358 / #357)

## Clean workspace

- **Worktree:** `/home/soroush/research-next-wt`
- **Branch:** `research-next-frontier-iteration`
- **Tip:** includes squash merges **#358** then **#357** on `main` (`78252a0` → `f0bd308` ancestry under current HEAD).

## Merged PRs (what each added)

| PR | Squash subject | Role |
|----|----------------|------|
| **#358** | Add diverse-root frontier discovery strategy | Diverse-root frontier discovery (V1/guarded line), eval and held-out GSM8K comparison plumbing, extraction/parser hardening, generation budget controls—per squash message and present implementation/tests. |
| **#357** | Capped Cohere PAL vs external L1 pilot | Committed **paired pilot artifacts** under `outputs/cohere_paired_pal_vs_external_l1_fresh_20260505T222840Z/` plus **allowlist/materialization scripts** (`scripts/build_fresh_gsm8k_paired_allowlist.py`, `scripts/materialize_cohere_paired_pal_external_bundle.py`). |

## Documentation / artifacts skimmed for this note

- **Front door:** `README.md`, `START_HERE_CURRENT.md` (still emphasize `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak` without `_pal`; PAL-aware ID appears in pilot summaries).
- **UNIT-TRACK:** `docs/UNIT_TRACK_STATUS_20260505.md` — optional `…_unit_track` diagnostic; conservative, weak on A7 slice; park for stronger branch templates.
- **PR #357 curated report:** `outputs/cohere_paired_pal_vs_external_l1_fresh_20260505T222840Z/paired_report.md` + `paired_summary.json`.
- **PR #358 standalone narrative doc:** none found under `docs/` in this snapshot; rely on commit message + code/tests.

## Current best internal method (PAL-aware)

```text
direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
```

## Best current empirical signal

From the **capped paired PAL vs external_l1_max** pilot (**PR #357** bundle):

- **`external_l1_max`:** **36/43** exact (~83.7%)
- **PAL:** **40/43** exact (~93.0%)
- **PAL ahead by ~+9.3 percentage points** (reported gap −9.3 pp external − PAL)

Source: `outputs/cohere_paired_pal_vs_external_l1_fresh_20260505T222840Z/paired_summary.json` / `paired_report.md`.

## Claim boundary

**Small capped paired pilot** under explicit logical-call budgeting—not **paper-level proof** and not a license for broad superiority claims vs `external_l1_max`.

## Previous targeted PAL evidence (internal)

PAL fixed **21/28** targeted internal-loss cases after the **PAL integration fix** (internal loss-casebook milestone).

## Main remaining bottlenecks

1. Need **larger fresh paired PAL vs external_l1_max** validation.
2. Remaining PAL failures are mostly **code absent / safety rejection**.
3. Need **clean metric consistency** for PAL-aware discovery / Discovery3.
4. Need to **decide**: improve PAL prompt **vs** scale paired validation **first**.

## Recommended next research action

**No new algorithmic variant** until evidence scales: run a **larger paired PAL-vs-external validation only after** a **no-API preflight** that estimates **calls** and feasible **case count** under the chosen caps.
