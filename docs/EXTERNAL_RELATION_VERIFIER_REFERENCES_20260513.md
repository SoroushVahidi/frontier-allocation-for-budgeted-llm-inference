# External Relation Verifier References
**Date:** 2026-05-13  
**Scope:** External repositories and paper assets inspected in a scratch directory only. No external code was copied into this repository.

## Assets Inspected

### 1. DeductReasoner / Deductive-MWP
- Paper: ACL 2022, *Learning to Reason Deductively: Math Word Problem Solving as Complex Relation Extraction*
- Official repo inspected: `https://github.com/allanj/deductive-mwp`
- Availability: official repo available
- License: no license file visible in repo root

### 2. FoVer
- Repo inspected: `https://github.com/psunlpgroup/FoVer`
- Availability: official repo available
- License:
  - code: Apache 2.0
  - dataset: CC BY 4.0
  - models: base-model dependent

### 3. OpenAI GSM8K / grade-school-math
- Repo inspected: `https://github.com/openai/grade-school-math`
- Availability: official repo available
- License: MIT

### 4. ALGES / Parsing Algebraic Word Problems into Equations
- Paper: TACL 2015
- Repo inspected: `https://gitlab.cs.washington.edu/ALGES/TACL2015`
- Availability: official repo available
- License: no license file visible in repo root

### 5. V-STaR / process verifier references
- Paper page inspected
- Availability: paper visible, but no clearly linked official code repository for the verifier paper was found during this pass
- Status: paper only / code not confirmed

## What Was Accessible

- Full clone of `FoVer`
- Full clone of `openai/grade-school-math`
- Full clone of `allanj/deductive-mwp`
- Full clone of `ALGES/TACL2015`
- Paper pages / metadata for DeductReasoner and V-STaR

## What Was Not Clearly Accessible

- A clearly linked official code repository for `V-STaR: Training Verifiers for Self-Taught Reasoners`
- An official software attachment directly from the ACL Anthology page for DeductReasoner beyond the GitHub repo
- Clear reuse terms for `deductive-mwp` and `ALGES` because no license file was visible in the inspected repo roots

## Most Useful Ideas

### DeductReasoner

The most relevant external structure for our problem.

- Treats MWP solving as iterative relation extraction over quantities.
- Preprocessing builds `equation_layer` labels that look like edge steps:
  - `[left, right, op]`
  - with operator variants like `-_rev`, `/_rev`, `^_rev`
- Data format stores:
  - normalized numbers
  - question text
  - equation text
  - layered equation decomposition
- The model scores pairwise quantity combinations and operator labels while constructing intermediate nodes `m_0`, `m_1`, ...
- This is close to a graph-edge classifier over quantity nodes.

Useful conceptual takeaways for us:
- quantity nodes
- pairwise relation/operation edge labels
- explicit intermediate-node construction
- target-variable-aware decomposition
- equation-tree scoring rather than only final-answer scoring

Less useful for our exact bottleneck:
- It is mainly a solver, not a verifier.
- It does not directly distinguish semantic relation error from arithmetic error in the way we need for runtime branch gating.

### FoVer

The most relevant external verifier-style asset.

- Uses step-level labels over reasoning traces.
- Quickstart dataset format is very close to what we need:
  - `problem`
  - `solution_steps`
  - `error_labels`
- PRM input format is multi-turn:
  - prompt with full problem
  - one step at a time
  - model outputs `correct` / `incorrect`
- Supports direct evaluation and sample-and-rank verifier workflows.
- Downstream evaluation code already assumes a verifier/ranker training loop.

Useful conceptual takeaways for us:
- step-level supervision format
- first-error-step style datasets
- explicit verification prompts separated from generation prompts
- verifier/ranker evaluation loop
- process-verifier framing without needing answer generation

Main mismatch for our use case:
- FoVer is process-step verification, not relation-readiness verification.
- Its labels are binary step correctness, not semantic relation categories.

### OpenAI GSM8K

Useful mainly as data and solution-format inspiration.

- Dataset format is simple JSONL with `question` and `answer`.
- Answers use `#### final_answer` extraction.
- Also provides a Socratic variant where each reasoning step is preceded by a generated subquestion.
- This suggests a convenient format for contrastive verifier examples:
  - question
  - target subquestion
  - candidate reasoning step
  - correctness label

Useful conceptual takeaways for us:
- clean final-answer extraction conventions
- Socratic step decomposition for target-aware subquestions
- example model-solution files that can seed verifier datasets

Main mismatch:
- no relation-specific label schema
- mostly arithmetic / answer supervision, not semantic relation verification

### ALGES

Useful for structured, non-LLM equation construction and scoring.

- Uses local and global models over equation trees.
- Includes explicit unit conversion heuristics in `unitConversion.py`.
- Supports ILP-based candidate equation generation and scoring.
- Dataset contains direct equation targets and single-equation algebra problems.

Useful conceptual takeaways for us:
- deterministic unit-conversion checker
- local edge scoring plus global tree scoring
- explicit target equation parsing
- strong separation between candidate generation and candidate ranking

Main mismatch:
- older algebraic setting
- not a learned verifier over modern LLM-generated candidate structures
- likely not directly reusable without license clarification

## Recommended Label Schema For A Learned RelationReady Verifier

Our current `relation_verifier_v1` schema is too permissive because it mostly checks local plausibility. A stronger learned verifier should predict both a binary gate and typed failure labels.

Recommended fields:

- `case_id`
- `question`
- `requested_target_text`
- `target_variable_name`
- `candidate_source`
- `candidate_variables_json`
- `candidate_relations_json`
- `candidate_equations_json`
- `candidate_solution_formula`
- `candidate_final_answer`
- `candidate_process_state`
- `candidate_units_json`
- `primary_topology_label`
- `label_relation_ready`
- `label_target_binding_ok`
- `label_target_variable_ok`
- `label_source_facts_sufficient`
- `label_process_state_ok`
- `label_unit_scale_ok`
- `label_equation_semantics_ok`
- `label_arithmetic_executable`
- `label_contrastive_best_among_candidates`
- `first_error_axis`

Recommended `first_error_axis` values:
- `wrong_target_variable`
- `wrong_relation`
- `missing_source_fact`
- `wrong_process_state`
- `unit_scale_error`
- `wrong_percentage_base`
- `difference_vs_total`
- `per_unit_vs_total`
- `final_vs_original`
- `arithmetic_error`
- `format_error`
- `prompt_gold_inconsistent`
- `no_issue`

This should be explicitly first-error oriented, not just end-state scoring.

## Recommended Training Dataset Format

Best near-term format:

One JSONL row per `(question, candidate)` pair:

```json
{
  "case_id": "openai_gsm8k_1006",
  "question": "...",
  "requested_target_text": "...",
  "candidate_source": "declarative_v2",
  "candidate_context": {
    "variables": [...],
    "relations": [...],
    "equations": [...],
    "solution_formula": "...",
    "final_answer": 45.0,
    "process_state": "final"
  },
  "alternate_candidates": [
    {"source": "bftc_executable", "summary": "..."},
    {"source": "declarative_v1", "summary": "..."}
  ],
  "label_relation_ready": false,
  "label_target_binding_ok": false,
  "label_source_facts_sufficient": true,
  "label_process_state_ok": true,
  "label_unit_scale_ok": true,
  "label_equation_semantics_ok": false,
  "label_arithmetic_executable": true,
  "first_error_axis": "wrong_percentage_base"
}
```

Why this format:
- supports hand-crafted feature models
- supports pairwise rankers
- supports graph encoders
- keeps the target and candidate structure separate
- allows explicit contrastive negatives

## Strong Negative-Example Strategy

The most useful missing piece in our current system is contrastive wrong-relation data.

Recommended negative construction:
- take cases where numbers are locally right but the target binding is wrong
- pair correct-vs-wrong candidates with same numbers but different relation
- synthesize typed negatives:
  - difference vs total
  - final vs original
  - per-unit vs total
  - wrong percentage base
  - wrong target variable
  - missing source fact despite executable arithmetic
  - unit-conversion omitted

This is the highest-value lesson from our own postmortems plus DeductReasoner-style decomposition.

## Recommended First Prototype

Start with:

### 1. Deterministic + learned hybrid

This is the recommended first prototype.

- deterministic checks:
  - target variable presence
  - solve-for / target-name match
  - unit conversion compatibility
  - executable formula check
  - numeric final-vs-formula agreement
- learned scorer:
  - relation-readiness classifier on top of structured features + text

Why:
- aligns with our postmortem
- directly addresses false accepts
- avoids trusting an LLM for unit/process-state checks it should not own

### 2. Hand-crafted features + gradient boosting

Good first learned baseline.

Feature ideas:
- exact token overlap between requested target and target variable
- presence of target noun in equation lhs / solved variable
- unit mismatch indicators
- process-state keyword mismatch
- whether candidate answer equals an intermediate variable rather than target variable
- source-fact coverage features
- topology label priors

This is the fastest route to a cheap discriminative baseline.

### 3. Contrastive pairwise ranker

Strong second prototype.

- input: `(question, target, candidate_a, candidate_b)`
- objective: choose which candidate is more relation-ready
- ideal when multiple candidates exist with similar numbers but different semantics

This directly addresses the weakness of `relation_verifier_v1`, which judged one candidate in isolation.

### 4. Graph edge classifier

Promising later-stage prototype.

- nodes: quantities, target, derived intermediates
- edges: operation / relation labels
- objective: classify whether each edge is valid and whether the final target path is complete

This is conceptually strong, but higher implementation cost than the hybrid baseline.

## Recommended Next Engineering Step

Build `RelationReady_v0` as a deterministic + learned hybrid:

1. Convert current candidate artifacts into one-row-per-candidate JSONL.
2. Add typed post-hoc labels from our existing diagnostics:
   - exact/executable outcome
   - topology label
   - first error axis
   - false accept / false reject
3. Implement deterministic gates:
   - target binding
   - unit compatibility
   - process-state consistency
   - formula executability
4. Train a small tabular classifier on structured features.
5. Only after that, consider a contrastive pairwise verifier prompt or model.

This is a better immediate direction than another single-candidate live verifier prompt.

## Explicit Warning

- Do not copy external code from `deductive-mwp` or `ALGES` unless license terms are clarified.
- `FoVer` code is Apache 2.0 and its dataset is CC BY 4.0, which is friendlier for conceptual adaptation, but we should still avoid copying code directly into this repository unless there is a specific approved reuse need.
- This document summarizes ideas, formats, and architecture patterns only.
