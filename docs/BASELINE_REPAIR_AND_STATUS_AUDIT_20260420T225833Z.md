# Baseline repair and status audit (2026-04-20T22:58:33Z)

This document is the **paper-facing baseline audit** for this repository phase. It aligns human-readable docs, generated completeness artifacts, and the machine-readable status matrix under a **single normalized taxonomy**. It prefers **honest downgrade** over implied full reproduction.

## Machine-readable outputs

- `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json`
- `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.csv`

Regenerate (UTC timestamp in dirname comes from the script clock):

```bash
python scripts/build_baseline_repair_and_status_audit.py
```

## Normalized taxonomy (v1)

### Field: `status`

One of:

- `runnable_direct` — in-repo controller/eval path runs without importing an external paper stack; comparable claims still require control-equivalence care.
- `runnable_adjacent` — reserved for adjacent stacks that are runnable as a whole outside strict import-only protocols (rare here).
- `adapter_based` — **MODE A** style paths: inference-only or prompt-budget adapters on this repo’s substrate (`s1`, `TALE`, `L1`).
- `import_validated` — strict CSV/metadata import + validator scripts; **not** a full upstream training/inference reproduction in this repo.
- `discuss_only` — citation/framing/ingredient only; no reproducible in-repo comparator path.
- `blocked` — provenance or policy blockers prevent honest “usable baseline” claims.
- `broken_needs_repair` — wiring exists but is non-functional (none flagged in this pass).

### Field: `control_equivalence`

- `direct` — same decision class as the paper’s primary control story (rare; do not claim without evidence).
- `near_direct` — **matched-substrate** budget neighbor (MODE A adapters for `s1` / `TALE` / `L1`).
- `adjacent` — reviewer-relevant but **not** control-space-equivalent (routing, imported tree search metrics, MODE B imports, internal `verifier_guided_search` vs external PRM papers).
- `ingredient_only` — informs method design; not a runnable empirical comparator stack (legacy note; Let’s Verify Step by Step is now strengthened to an adjacent partial-runnable lane in later passes).

### Other normalized flags (matrix)

- `paper_safe_now` — `yes` if conservative doc wording matches repo capability.
- `repo_command_available` — `yes` if a documented script/entrypoint exists for the claimed path.
- `artifact_backed_now` — `yes` if configs/docs/scripts and/or a pinned comparison bundle row exist (see matrix `notes`).
- `official_resource_verified` — `yes` only if upstream official artifacts for the **cited paper** are audited as authoritative in-repo (generally **no** here).

## Consolidated status matrix (high-priority and internal)

| baseline_id | status | control_equivalence | paper_safe_now | repo_command_available | artifact_backed_now | official_resource_verified |
|---|---|---|---|---|---|---|
| s1_mode_a | adapter_based | near_direct | yes | yes | yes | no |
| s1_mode_b | import_validated | adjacent | yes | yes | yes | no |
| tale_mode_a | adapter_based | near_direct | yes | yes | yes | no |
| tale_mode_b | import_validated | adjacent | yes | yes | yes | no |
| l1_mode_a | adapter_based | near_direct | yes | yes | yes | no |
| l1_mode_b | import_validated | adjacent | yes | yes | yes | no |
| best_route_microsoft | import_validated | adjacent | yes | yes | yes | no |
| when_solve_when_verify | import_validated | adjacent | yes | yes | yes | no |
| rest_mcts | import_validated | adjacent | yes | yes | yes | no |
| qstar_deliberative_planning | discuss_only | direct | yes | no | yes | no |
| lets_verify_step_by_step | import_validated | adjacent | yes | yes | yes | no |
| rational_metareasoning_llm | discuss_only | adjacent | yes | no | yes | no |
| verifier_guided_search | runnable_direct | adjacent | yes | yes | yes | no |

## Required audit answers (high-priority targets)

### s1 (MODE A / MODE B)

- **Docs previously:** Mixed “apples-to-apples” language for MODE A; MODE B sometimes under-specified next to MODE A.
- **Code/config:** `configs/s1_budget_forcing_inference_only_v1.json`, `configs/s1_full_or_official_adapter_v1.json`, `scripts/run_s1_budget_forcing_baseline.py`, `scripts/verify_s1_mode_b_import.py`.
- **Runnable:** MODE A yes in-repo. MODE B yes **only** when user supplies official package passing validator.
- **Artifact-backed:** Configs + scripts yes; MODE B row depends on imported package.
- **Class:** MODE A `adapter_based` / `near_direct`; MODE B `import_validated` / `adjacent`.
- **Paper-safe:** Yes if MODE A is described as **inference-only adapter** on this substrate, not full s1 training reproduction.

### TALE

- Same pattern as s1 with `configs/tale_prompt_budgeting_v1.json`, `scripts/run_tale_baseline.py`, `scripts/verify_tale_mode_b_import.py`, TALE-vs-TALE-PT separation on MODE B.

### L1

- MODE A: `configs/l1_inference_adapter_v1.json`, `scripts/run_l1_baseline.py`.
- MODE B: `configs/l1_official_full_adapter_v1.json`; **repair in this pass:** added `scripts/verify_l1_mode_b_import.py` (parity with s1/TALE MODE B validators).

### BEST-Route / when_solve_when_verify / ReST-MCTS*

- **Paths:** respective `docs/*_integration.md`, `scripts/verify_*_import.py`, `external/*/README.md`.
- **Runnable:** **Import validation** is runnable; full upstream stacks are **not** reproduced in-repo.
- **Class:** `import_validated` / `adjacent` (canonical v1). Legacy `outputs/external_baseline_completeness/*_status.json` may still say `runnable_adjacent` — treat as synonym for this import-only family (see `scripts/generate_external_baseline_completeness_report.py`).

### Q* / Rational Metareasoning

- **Paths:** `external/qstar_deliberative_planning/README.md`, `docs/QSTAR_PROVENANCE_AND_INTEGRATION_PASS_20260422T013736Z.md`, `external/rational_metareasoning_llm/README.md`.
- **Runnable comparator:** **No** reproducible adapter/validator bundle without speculative integration.
- **Upgrade feasibility:** No conservative upgrade applied. Q* received a dedicated provenance hardening pass documenting canonical paper links and explicit negative findings (no verified official repo/artifacts); upgrading would require pinned official code, license checks, and a matched evaluation contract. **Remain `discuss_only`.**

### verifier_guided_search (internal)

- **Path:** Frontier simulator / comparison bundle (`verifier_guided_search` method in committed bundle summary).
- **Runnable:** Yes as internal baseline.
- **Class:** `runnable_direct` operationally, `adjacent` **control_equivalence** vs external PRM papers (implementation neighbor only).

## What was broken or inconsistent

1. **Taxonomy drift:** Docs mixed `mode_a_only`, `mode_b_partial`, `link_only`, `RUNNABLE_ADJACENT`, and the newer v1 enums.
2. **MODE B parity:** L1 lacked a dedicated MODE B import verifier script while s1/TALE had one — implied stronger MODE B story for L1 than tooling supported.
3. **Adjacent import baselines:** Narrative said “runnable-adjacent” without always tying to **`import_validated`** semantics (validator + imported artifacts, not in-repo stack reproduction).
4. **Comparison status builder:** `external_adjacent_verified_import_only` only keyed off `runnable_adjacent` in per-baseline JSON; future `import_validated` status would have been dropped — **fixed** in `scripts/build_full_method_comparison_status_20260418.py`.
5. **MCTS community reference:** Registry used `link_only` while v1 taxonomy has no `link_only` — **downgraded** registry entry to `discuss_only` to match matrix/completeness rows.

## What was repaired

1. **`scripts/verify_l1_mode_b_import.py`** — new strict MODE B import contract checker aligned with s1/TALE validators.
2. **`scripts/build_baseline_repair_and_status_audit.py`** — artifact bundle detection fixed to read `aggregate_ranking` from the committed comparison summary JSON.
3. **`scripts/generate_external_baseline_completeness_report.py`** — emits v1 columns (`status_v1_mode_a`, `status_v1_mode_b`, `control_v1_*`), refreshed taxonomy text, and explicit legacy↔v1 mapping notes.
4. **`configs/external_baselines_registry.json`** — points to matrix + audit doc; canonical `completeness_taxonomy` list updated; `mcts_llm_community` honesty fix.
5. **`.gitignore`** — whitelists `outputs/baseline_repair_and_status_audit_*/**` for committed matrices.
6. **`pyproject.toml`** — targeted `E501` ignores for long-path audit/generator scripts; **`scripts/build_full_method_comparison_status_20260418.py`** unused locals removed.

## What remains adjacent-only

- BEST-Route, When To Solve/When To Verify, ReST-MCTS*, cascade, MoB, OpenR: **import-validated adjacent neighbors** only.

## What remains discuss-only or blocked

- **Discuss-only:** Q*, Rational Metareasoning (framing), Tree-PLV, PGTS, Scaling Automated Process Verifiers, LLM Tree Search (Waterhorse), MCTS-LLM community note.
- **Blocked:** `compute_optimal_tts` (paper↔repo mapping unverified).

## Paper wording: too strong before → safe now

- **Before:** “MODE A apples-to-apples for every external training variant” / implied full s1/TALE/L1 official stack reproduction.
- **After:** “**Primary fair path on aligned substrate**” for MODE A adapters; MODE B “**import-validated reporting** only,” never merged into direct-control tables without explicit labeling.

- **Before:** “Runnable adjacent baseline” without clarifying import-only.
- **After:** “**import_validated** adjacent neighbor: validator + imported results; not in-repo official reproduction.”

## Which baselines support which comparison claims

- **Safe for primary matched-substrate budget comparisons (MODE A adapters):** `s1`, `TALE`, `L1` — as **`adapter_based` / `near_direct`**, not as bit-identical upstream systems.
- **Safe as adjacent, import-backed neighbors:** BEST-Route, when_solve_when_verify, ReST-MCTS*, cascade, MoB, OpenR.
- **Safe as internal simulator baselines:** `verifier_guided_search` and other `runnable_direct` internals in comparison bundles — label as **implementation neighbors**, not external paper reproductions.
- **Discuss-only / blocked:** Q*, LV, Rational Metareasoning, compute-optimal TTS (blocked), and other discuss-only rows in the matrix.

## Alignment with intended paper-facing baseline story

- **Intent:** Real artifact-backed internal and broad-family baselines; direct/near-direct budget control includes `s1`, `TALE`, `L1`; adjacent includes BEST-Route, solve/verify, verifier-guided search, deliberative/Q* family, ReST-MCTS*; **do not** imply every named method is fully runnable apples-to-apples.
- **Repository after this pass:** MODE A `s1`/`TALE`/`L1` are the strongest **adapter_based** paths; adjacent externals are **`import_validated`**; Q*/LV/Rational remain **`discuss_only`**; docs/registry/matrix/completeness generator now **cross-reference** the same v1 enums. **Aligned** with the intent, with explicit conservative language everywhere.
