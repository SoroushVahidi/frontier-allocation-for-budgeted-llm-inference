# When To Solve / When To Verify strengthening pass (2026-04-21)

## Exact identified baseline

- **Paper:** *When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning*
- **Authors:** Nishad Singhi, Hritik Bansal, Arian Hosseini, Aditya Grover, Kai-Wei Chang, Marcus Rohrbach, Anna Rohrbach
- **arXiv:** `2504.01005`
- **Paper URL:** <https://arxiv.org/abs/2504.01005>
- **HTML URL:** <https://arxiv.org/html/2504.01005v2>
- **Official code URL:** <https://github.com/nishadsinghi/sc-genrm-scaling>

## Upstream inspection summary (official sources)

From official arXiv + official repo materials:

- upstream method is a **fixed-budget solve-vs-verify compute allocation** comparison (SC vs GenRM paradigms),
- official code repo provides generation, verification, and success-rate evaluation workflow paths,
- upstream supports datasets including MATH, AIME24, AIME25, GPQA-Diamond (plus `math128` lane in commands),
- upstream uses vLLM-based inference pipelines,
- upstream release references Hugging Face artifacts (datasets + GenRM checkpoints),
- upstream GenRM-FT data path explicitly references GPT-4o-generated synthetic verifications.

## Chosen integration mode

**Chosen mode:** stronger import-validated comparator with reproducible artifact contract (adjacent-only).

Why this is strongest honest mode now:

- preserves official provenance and fixed-budget SC-vs-GenRM relevance,
- avoids overclaiming direct frontier/node-level control equivalence,
- gives reproducible, machine-checkable import + row-export artifacts,
- does not claim full upstream training/inference reproduction where external access/compute may be required.

## What was implemented in this pass

1. Added canonical adjacent comparison contract:
   - `configs/when_solve_when_verify_adjacent_comparison_contract_v1.json`
2. Added canonical integration runner:
   - `scripts/run_when_solve_when_verify_adjacent_integration.py`
3. Promoted registry wiring to include runner/contract/output status artifacts:
   - `configs/external_baselines_registry.json`
4. Updated integration docs with canonical commands and explicit access caveats:
   - `docs/when_solve_when_verify_integration.md`
   - `external/when_solve_when_verify/README.md`
5. Updated baseline index notes for consistent strengthened status:
   - `docs/CURRENT_BASELINE_NEXT_STEPS_2026_04_21.md`
   - `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
   - `docs/main_baselines.md`

## Canonical commands

Validator:

```bash
python scripts/verify_when_solve_when_verify_import.py \
  --config configs/when_solve_when_verify_official_import_v1.json \
  --results-path tests/fixtures/when_solve_when_verify_import_valid \
  --expected-dataset math128 \
  --expected-split test
```

Runner / artifact export:

```bash
python scripts/run_when_solve_when_verify_adjacent_integration.py \
  --import-config configs/when_solve_when_verify_official_import_v1.json \
  --contract-config configs/when_solve_when_verify_adjacent_comparison_contract_v1.json
```

## Verified now vs not verified now

Verified now:

- strict import-contract validation for `metadata.json` + `results.csv`,
- adjacent-only comparability labeling and export,
- reproducible manifest/status/validation/comparison-row artifacts.

Not verified now:

- full faithful upstream end-to-end rerun across official experiments,
- full upstream training stack reproduction (including GenRM-FT path),
- direct control-space equivalence to frontier/node-level branch-allocation controllers.

## Safe vs unsafe claims

Safe:

- official **adjacent** baseline integration for fixed-budget solve-vs-verify analysis,
- `import_validated` reporting path with reproducible artifacts,
- paper-facing adjacent comparison rows when validator verdict is `import_validated`.

Unsafe:

- claiming branch/frontier control equivalence,
- claiming full in-repo upstream reproduction,
- claiming compute-parity to all official runs without corresponding imported artifacts.

## Paper-facing readiness

**Ready for paper-facing adjacent-baseline comparison:** yes, in `import_validated` adjacent mode with strict caveats.

## Explicit blockers for fuller integration

1. **Hugging Face access** (likely mandatory for faithful upstream asset usage)
   - needed for official datasets/checkpoints referenced by upstream.
2. **Large inference compute + vLLM-serving capacity** (mandatory for full reruns)
   - needed to execute upstream-scale generation + verification sweeps.
3. **OpenAI API key** (mandatory only for exact GPT-4o synthetic-verification data reproduction path)
   - required if reproducing the exact GenRM-FT data-generation route described upstream.

Partial honest integration remains possible without these via import-validation and adjacent row export (the mode implemented here).
