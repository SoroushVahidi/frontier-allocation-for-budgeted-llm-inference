# Current dataset audit status (2026-04-16)

This report is a conservative audit of the **current dataset layer** before any expansion.

Scope checked:
- Evaluation-facing datasets in `experiments/hf_datasets.py` and related docs/scripts.
- External supervision / warm-start / process-supervision datasets in `experiments/external_reasoning_datasets.py` and `configs/external_reasoning_datasets_registry.json`.
- Verification artifacts generated on **2026-04-16** under `outputs/`.

## 2026-04-17 bounded top-priority expansion update

A focused expansion pass was run for the current top-priority additions (DROP, MuSR, BIG-Bench Hard, AQuA), without broadening to lower-priority datasets.

Tracked keys added to `experiments/hf_datasets.py` and tooling defaults:
- `allenai/drop` (with explicit runtime loader fallback to `ucinlp/drop` in this environment)
- `TAUR-Lab/MuSR`
- `openeval/BIG-Bench-Hard`
- `deepmind/aqua_rat`

Bounded access checks for these four all passed in this environment; see:
- `outputs/dataset_expansion_20260417/hf_access/hf_access_summary.json`
- `outputs/dataset_expansion_20260417/smoke/smoke_summary.json`
- `outputs/dataset_expansion_20260417/integration_report/dataset_integration_report.json`
- `docs/TOP_PRIORITY_DATASET_EXPANSION_READINESS_2026_04_17.md`

Conservative caveats recorded:
- DROP requested HF id `allenai/drop` remains unresolved here; current clean loader path is `ucinlp/drop` (plus AWS registry path available).
- BIG-Bench Hard card metadata does not expose a clear license value in this bounded probe, so manual confirmation is still required before redistribution-sensitive use.

Guardrails followed:
- Keep **fixed-budget next-step branch allocation** as conceptual center.
- Keep **evaluation** and **supervision** layers explicitly separated.
- Do not overclaim “integrated” as equivalent to “final paper evidence.”

## 1) Full dataset inventory

### 1.1 Evaluation layer inventory (benchmark-facing)

| Canonical key/name in repo | Source type | Documented | Integrated in code | Access verification | Smoke sampling | Intended role | Current usability (2026-04-16 audit) | Caveats |
|---|---|---:|---:|---:|---:|---|---|---|
| `openai/gsm8k` | HF | Yes | Yes (`HF_DATASET_SPECS`) | Yes (`verify_hf_dataset_access.py`: pass) | Yes (pass) | Main evaluation | **Cleanly usable now** | None major in this environment. |
| `hendrycks/competition_math` | HF | Yes | Yes (`HF_DATASET_SPECS`) | Yes (fail in this env) | Yes (fail in this env) | Main evaluation (canonical MATH id in docs/code) | **Usable with caveats** | Hub resolution failed here; mirror fallback currently important. |
| `EleutherAI/hendrycks_math` | HF mirror | Yes (docs/access notes) | Yes (`HF_DATASET_SPECS`) | Yes (pass) | No (not in smoke default) | Main evaluation mirror/fallback | **Usable with caveats** | Mirror works now; canonical-vs-mirror policy must be explicit per run. |
| `HuggingFaceH4/MATH-500` | HF | Yes | Yes | Yes (pass) | Yes (pass) | Main evaluation | **Cleanly usable now** | Keep revision pinning discipline. |
| `Idavidrein/gpqa` (`gpqa_diamond`) | HF (gated/terms-sensitive) | Yes | Yes | Yes (pass) | Yes (pass) | Main evaluation | **Usable with caveats** | Terms/auth constraints still apply despite pass. |
| `HuggingFaceH4/aime_2024` | HF | Yes | Yes | Yes (pass) | Yes (pass) | Main evaluation (AIME slice) | **Cleanly usable now** | 2024 slice only; broader AIME policy still open. |
| `Hothan/OlympiadBench` | HF mirror | Yes | Yes | Yes (pass) | Yes (pass) | Main evaluation | **Cleanly usable now** | Mirror-vs-official identity should stay explicit. |
| `meituan-longcat/AMO-Bench` | HF | Yes | Yes | Yes (pass) | Yes (pass) | Main evaluation | **Cleanly usable now** | Grading details still external to light access checks. |
| `google-deepmind/natural-plan` | Git clone | Yes | Yes (`GIT_DATASET_SPECS`) | Yes (fail: clone missing) | Yes (fail: clone missing) | Main evaluation (planning) | **Partially integrated** | Requires external clone (`NATURAL_PLAN_DIR` / default path), not ready out-of-box. |
| `livecodebench/code_generation_lite` | HF + GitHub ecosystem | Yes (optional/extended) | Yes | Yes (fail in this env) | No (not in smoke default) | Optional/extended evaluation | **Do not rely yet in current env** | Current loader error: dataset-script incompatibility. |

### 1.2 External supervision / reasoning-supervision inventory

Integrated keys from `EXTERNAL_REASONING_DATASET_SPECS` + registry JSON:

- `prm800k` → `tasksource/PRM800K`
- `math_shepherd` → `peiyi9979/Math-Shepherd`
- `ultrainteract_pair` → `openbmb/UltraInteract_pair`
- `ultrainteract_sft` → `openbmb/UltraInteract_sft`
- `deepstep_math_5k` → `BlackSnowDot/DeepStep-Math-5K`
- `webinstruct_verified` → `TIGER-Lab/WebInstruct-verified`
- `judgelm_collection_v1` → `BAAI/JudgeLM-data-collection-v1.0`
- `judgelm_100k` → `BAAI/JudgeLM-100K`
- `mt_bench_human_judgments` → `lmsys/mt_bench_human_judgments`
- `prometheus_feedback_collection` → `prometheus-eval/Feedback-Collection`
- `prometheus_preference_collection` → `prometheus-eval/Preference-Collection`
- `math_verify_s1k_r1` → `HuggingFaceH4/s1k_r1_math_verify`
- `arctraj` → `SejinKimm/ARCTraj`

Current status from audit run:
- All 13 integrated external supervision datasets were accessible in this environment (`all_access_ok: true`).
- They remain **integration/preparation** sources for supervision experiments, not final-method evidence.

### 1.3 Documented but not integrated

From candidate audit paths/docs:
- PairS (no canonical standalone dataset artifact identified).
- AgentPRM / InversePRM (gated/inaccessible or no stable public dataset artifact identified).

### 1.4 Integrated but relatively under-documented / easy-to-misread

- `EleutherAI/hendrycks_math` is operationally important as a working mirror but can be underemphasized relative to canonical `hendrycks/competition_math` wording.
- `livecodebench/code_generation_lite` is integrated as optional, but current loader incompatibility means practical readiness is lower than many readers may assume.
- `google-deepmind/natural-plan` is integrated as a git-clone spec, but usability depends on local clone prep (not pre-bundled).

## 2) Code-vs-doc consistency audit

Compared:
- `docs/main_datasets.md`
- `docs/DATASET_STATUS.md`
- `docs/datasets_access.md`
- `experiments/hf_datasets.py`
- `experiments/external_reasoning_datasets.py`
- `configs/external_reasoning_datasets_registry.json`

### 2.1 Consistent areas

- Evaluation/supervision separation is explicit across docs and code.
- Main evaluation set in docs is represented in `HF_DATASET_SPECS` + `GIT_DATASET_SPECS`.
- External supervision keys match between Python specs and JSON registry.
- Candidate non-integrated items (PairS, AgentPRM/InversePRM) are consistently marked as not integrated.

### 2.2 Mismatches / tension points (conservative)

1. **Canonical MATH id vs environment reality**
   - Docs present `hendrycks/competition_math` as canonical.
   - Current verification/smoke in this environment failed for `hendrycks/competition_math`, while `EleutherAI/hendrycks_math` passed.
   - This is not a strict docs/code contradiction, but it is a **practical readiness mismatch** that should be called out prominently.

2. **Evaluation-report script coverage is narrower than full documented core set**
   - `scripts/generate_dataset_integration_report.py` prioritizes 7 rows and omits some documented evaluation entries (notably GSM8K and LiveCodeBench in priority table).
   - This can make generated report summaries look like the full layer when they are a curated subset.

3. **LiveCodeBench integrated-but-not-currently-usable in this environment**
   - Docs already mark it optional/extended, but current verifier failure (`Dataset scripts are no longer supported`) means “integrated” should be read as adapter wiring, not immediate runnability.

4. **NaturalPlan integration requires manual clone prep**
   - Docs state this; audit confirms missing clone makes it fail out-of-box in this environment.

No severe canonical-ID collision was found in external supervision keys; key naming is consistent between Python and JSON registry.

## 3) Verification and smoke summary (executed checks)

Executed commands:
- `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access_audit`
- `python scripts/dataset_smoke_sample.py --output-dir outputs/dataset_smoke_audit`
- `python scripts/generate_dataset_integration_report.py`
- `python scripts/verify_external_reasoning_datasets.py --output-dir outputs/external_reasoning_datasets_audit`
- `python scripts/generate_external_reasoning_dataset_integration_report.py --run-id dataset_audit_20260416`

### 3.1 Evaluation checks

- **Pass:** GSM8K, EleutherAI MATH mirror, MATH-500, GPQA Diamond, AIME 2024, OlympiadBench (Hothan), AMO-Bench.
- **Fail in this environment:** `hendrycks/competition_math`, NaturalPlan clone-path availability, LiveCodeBench loader.

### 3.2 External supervision checks

- All 13 integrated supervision datasets passed access/schema inspection in this environment.

## 4) Usability assessment before expansion

### 4.1 Evaluation layer

**Cleanly usable now (in this environment):**
- GSM8K
- MATH-500
- GPQA Diamond (with auth/terms caveat)
- AIME 2024 slice
- OlympiadBench (Hothan mirror)
- AMO-Bench

**Usable with caveats:**
- MATH canonical (`hendrycks/competition_math`) due to current access inconsistency; mirror fallback currently safer operationally.
- GPQA due to gating/terms policy constraints (even when accessible now).

**Partially integrated / not reliably ready out-of-box:**
- NaturalPlan (clone-dependent).
- LiveCodeBench (current loader incompatibility in this environment).

### 4.2 Supervision layer

**Integration-ready for experiments (access+schema):**
- The 13 integrated external reasoning datasets listed above.

**Still prep-layer / not evidence-layer:**
- All external supervision sources remain preparation/integration assets unless tied to specific controlled experiments.

**Not integrated:**
- PairS, AgentPRM/InversePRM.

## 5) Is the current dataset layer trustworthy enough before expansion?

**Answer: yes, conditionally.**

It is trustworthy enough to continue core work **if** we treat it as a layered system with explicit caveats:
- evaluation core mostly works,
- supervision integration is broad and operational,
- but a few readiness weak points can still create confusion or reproducibility risk.

### Main weak points

1. Canonical-vs-working MATH source tension (`hendrycks/competition_math` vs mirror pass behavior).
2. NaturalPlan clone dependency creates out-of-box failure risk.
3. LiveCodeBench adapter currently not runnable in this environment.
4. “Integrated” can still be misread as “paper-evidence ready” unless explicitly constrained.

## 6) Recommended cleanup actions before adding more datasets

1. Add an explicit **“evaluation run-ready matrix”** (pass/caveat/fail) to docs and keep it updated per audit date.
2. Clarify MATH policy: canonical ID vs operational fallback/mirror when canonical fails.
3. Add NaturalPlan clone bootstrap helper (or a one-command checker+clone wrapper) to reduce setup failure.
4. Keep LiveCodeBench optional until loader path is updated to current datasets tooling expectations.
5. Keep supervision docs explicit that integration != final paper evidence.

## 7) Audit artifacts produced

- `outputs/hf_dataset_access_audit/hf_access_summary.json`
- `outputs/hf_dataset_access_audit/hf_access_summary.csv`
- `outputs/hf_dataset_access_audit/hf_access_note.md`
- `outputs/dataset_smoke_audit/smoke_summary.json`
- `outputs/dataset_integration_report.json`
- `outputs/dataset_integration_report.md`
- `outputs/external_reasoning_datasets_audit/external_reasoning_dataset_access.json`
- `outputs/external_reasoning_datasets_audit/external_reasoning_dataset_access.md`
- `outputs/external_reasoning_datasets/dataset_audit_20260416/dataset_integration_report.json`
- `outputs/external_reasoning_datasets/dataset_audit_20260416/dataset_integration_report.md`
- `outputs/external_reasoning_datasets/dataset_audit_20260416/dataset_integration_report.csv`
- `outputs/external_reasoning_datasets/dataset_audit_20260416/dataset_access_status.json`
- `outputs/dataset_layer_audit_20260416.json`
