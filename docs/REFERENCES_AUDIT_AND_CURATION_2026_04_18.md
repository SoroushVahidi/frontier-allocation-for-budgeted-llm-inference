# References audit and curation (2026-04-18)

## Purpose

This note is the current repository-facing audit of the reference base.

It answers:
- which references are central to the current project,
- which references mainly inform design ideas,
- which references are empirical comparison baselines,
- which references are adjacent but not control-space-equivalent,
- which references are historical or currently low-priority,
- and how all of these should be used consistently in future writing and implementation work.

This note is intended to be the **single shortest current answer** to:

> what references matter now, why they matter, and which ones should not be treated as equally central.

## Current repository rule for references

Do **not** treat all references in the repo as belonging to the same class.

The repository currently needs a disciplined split between:
1. **core conceptual foundations**,
2. **direct/near-direct empirical baselines**,
3. **adjacent method-neighbor references**,
4. **idea/ingredient references**,
5. **frontier-track references**,
6. **dataset references**,
7. and **historical/provenance references**.

The current reference problem is not lack of references.
It is **reference overloading**: some sources are being asked to do too many jobs at once.

## Current top-level assessment

The current project is no longer mainly asking:
- what general area are we in,
- or what broad families exist.

It is now asking:

> **what target/oracle definition should govern hard close-branch decisions under a fixed compute budget?**

So the most valuable references now are the ones that help answer that specific question.

## Category A. Core conceptual foundations (highest relevance)

These are the references that most directly shape the current scientific identity of the project.

### A1. Metareasoning / value of computation
**Current relevance:** highest.

**Why:**
- This remains the cleanest conceptual foundation for the repository’s canonical question: whether the next unit of compute should be spent here.
- It supports the current continuation-value core plus bounded correction interpretation.
- It gives the right language for stop / continue / allocate-next decisions.

**What idea it gave us:**
- extra reasoning is an action with value and cost,
- and that action should only be chosen when the expected gain exceeds its opportunity cost.

**How to use in writing:**
- use as conceptual foundation,
- not as a claim that the repo has already implemented full formal rational metareasoning.

### A2. Adaptive test-time compute allocation / budgeted inference
**Current relevance:** highest.

**Why:**
- This is the main neighboring AI framing for the repo’s paper identity.
- It connects the project to the broader adaptive-inference literature without reducing it to routing only.

**What idea it gave us:**
- fixed-budget allocation across reasoning effort is the right AI-facing framing.

**How to use in writing:**
- use as the main neighboring AI literature family,
- but keep the repo’s more specific next-step frontier-allocation identity explicit.

### A3. Fixed-budget best-arm identification / small-gap allocation
**Current relevance:** very high.

**Why:**
- The repo’s current bottleneck is concentrated in hard close-branch states.
- This family is one of the best framing buckets for that narrow problem.

**What idea it gave us:**
- ambiguity is concentrated in small-gap branch sets,
- and budget should be allocated where additional information can still change the recommendation.

**How to use in writing:**
- use as a framing neighbor for the hard disagreement slice,
- not as a claim that the repo is simply a standard stochastic bandit problem.

## Category B. Direct / near-direct empirical baselines (highest comparison value)

These are the references that matter most for reviewer-facing comparison fairness.

### B1. s1
**Current relevance:** highest among direct/near-direct baselines.

**Why:**
- The repo explicitly treats s1 as a strongest practical stop/continue-style budget baseline.
- MODE A is runnable and fair for apples-to-apples unchanged-base-model comparison.

**What idea it gave us:**
- explicit budget forcing / test-time compute control should be compared directly, not only discussed.

**Current status:**
- important and active.
- keep central in comparison notes.

### B2. TALE
**Current relevance:** highest among adjacent adaptive-budget baselines.

**Why:**
- It is one of the clearest per-instance budget-allocation neighbors.
- Even when the control space differs, it remains important for reviewer-facing adaptive-budget comparisons.

**What idea it gave us:**
- token-budget-aware per-instance control is a close neighboring budget-allocation baseline.

**Current status:**
- important and active.
- keep central in comparison notes, but always mark control-space differences.

### B3. L1
**Current relevance:** high.

**Why:**
- It is a direct / near-direct budget-control baseline with a strong controllable-length interpretation.
- It is useful for fixed-budget matched comparison even when it is not identical to frontier allocation.

**What idea it gave us:**
- controllable reasoning length is an important neighboring budget-control axis.

**Current status:**
- important and active.

## Category C. Adjacent method-neighbor baselines (important, but not control-space-equivalent)

These references are useful and often worth reporting, but they should not be oversold as direct control-space equivalents.

### C1. BEST-Route
**Current relevance:** high, but adjacent-only.

**What idea it gave us:**
- routing/cascading is an important adaptive-compute neighbor.

**Consistency rule:**
- label as adjacent,
- never present as direct equivalent to fixed-budget next-step branch allocation.

### C2. When To Solve, When To Verify
**Current relevance:** high, but adjacent-only.

**What idea it gave us:**
- generator-vs-verifier budget tradeoffs matter and should appear in the comparison universe.

### C3. Cascade Routing
**Current relevance:** medium-high, adjacent-only.

**What idea it gave us:**
- unified routing/cascade policies are an important neighboring budget-allocation family.

### C4. MoB (Majority-of-the-Bests)
**Current relevance:** medium-high, adjacent-only.

**What idea it gave us:**
- best-of-N / selection-style test-time scaling needs to be separated from branch-allocation methods, but still compared where appropriate.

### C5. ReST-MCTS*
**Current relevance:** medium-high, adjacent-only.

**What idea it gave us:**
- process-reward-guided search is one of the closest search-neighbor baselines.

### C6. OpenR
**Current relevance:** medium, adjacent-only.

**What idea it gave us:**
- broader search/reasoning ecosystems matter as optional adjacent comparisons.

## Category D. Ingredient / idea references (important, but not full-solution references)

These are references that gave the project useful ideas, but should not be treated as if they already solve the repository’s central problem.

### D1. Process rewards / verifiers / PRM-style work
**Current relevance:** high as an ingredient.

**What idea it gave us:**
- visible intermediate reasoning quality can and should be scored.
- this is one of the main foundations for completion-aware evidence and semantic branch-quality signals.

**Why not a full solution:**
- these references support branch-quality signals,
- but they do not by themselves settle the repo’s target/oracle question.

### D2. Tree-PLV
**Current relevance:** medium as an ingredient / related-work item.

**What idea it gave us:**
- tree-constructed preference learning over intermediate reasoning states.

**Why not central now:**
- useful for verifier/state-scoring discussion,
- but not a direct, runnable, central baseline in this repo.

### D3. PGTS
**Current relevance:** medium as an ingredient / related-work item.

**What idea it gave us:**
- policy-guided search as a learned control neighbor.

**Why not central now:**
- conceptually relevant,
- but not currently a central runnable comparison path.

### D4. Scaling Automated Process Verifiers
**Current relevance:** medium as an ingredient / related-work item.

**What idea it gave us:**
- automated process verification as dense progress supervision.

**Why not central now:**
- strong verifier-side signal family,
- but still not the repo’s full allocation target.

## Category E. Frontier-track references (important for the newer paper track)

These matter for the heterogeneous controller-family frontier story.

### E1. Snell-style test-time compute references
**Current relevance:** medium-high for the frontier track.

**What idea they gave us:**
- sample-vs-verify and broader inference-time compute allocation are important neighboring stories.

### E2. PAL / Program-of-Thought
**Current relevance:** medium for the frontier track.

**What idea it gave us:**
- code-generation-plus-execution is a distinct controller family worth placing on a frontier.

### E3. PRM800K / Let’s Verify Step by Step
**Current relevance:** medium-high for the frontier track and ingredient layer.

**What idea it gave us:**
- pluggable process-verifier interfaces and intermediate-state scoring.

## Category F. Dataset references

**Current relevance:** high for reproducibility, but not the main conceptual bottleneck.

Use these for:
- benchmark provenance,
- dataset access,
- integration details,
- and fair task-level comparison.

Do **not** mix dataset references into method-neighbor or idea-reference buckets.

## Category G. Historical / provenance references

These remain useful for understanding how the repo evolved, but they are not current canonical references.

### G1. Older binary revise-routing references
**Current relevance:** low for the current canonical paper.

**What idea they gave us:**
- the earlier project identity and routing-based framing.

**Why low now:**
- the current canonical repository question is frontier / next-step branch allocation, not cheap-vs-revise routing.

### G2. Historical controller tweak references
**Current relevance:** low for current manuscript-facing use.

**Why low now:**
- many recent bounded repo passes have already ruled out a number of nearby tweaks as full solutions.
- these references remain useful for provenance, not for the front-door story.

## References currently low-priority or not safe to foreground

The following should currently be treated as low-priority, uncertain, or non-central unless a specific task requires them:

- `compute_optimal_tts` as a manuscript-facing direct comparison baseline, because its paper↔repo mapping remains blocked / weakly verified.
- community `mcts_llm_community` as a core comparison baseline, because it is link-only and not bound to a single clean canonical paper in repo policy.
- `llm_tree_search_waterhorse` as an implementation-facing baseline, because license status remains uncertain.
- older routing-only references as the main framing for the current paper.
- broad idea-takeaway references as if they were already direct empirical baselines.

These are not useless. They are just not the current center.

## Consistency rules for future reference use

### Rule 1
If a reference shapes the **paper’s central problem statement**, it belongs in:
- canonical paper-neighbor docs,
- current reference supplement,
- and the main manuscript-facing reading path.

### Rule 2
If a reference is a **reviewer-facing comparison baseline**, it must also appear consistently in:
- `docs/main_baselines.md`,
- `docs/external_baseline_completeness_report.md`,
- `external/README.md`,
- and `configs/external_baselines_registry.json`.

### Rule 3
If a reference mainly gave the repo an **idea or ingredient**, record it as such.
Do not let it silently behave like a central baseline.

### Rule 4
If a reference is historical, provenance-only, blocked, or low-confidence, say so explicitly.
Do not let it remain ambiguous.

## Current best reference-facing summary of the repo

A clean current summary is:

> The reference base is already strong enough, but it must be treated as a curated system rather than a flat bibliography. The current project is mainly grounded by metareasoning, adaptive test-time compute allocation, and fixed-budget small-gap allocation; compared empirically against direct/near-direct budget baselines such as s1, TALE, and L1; informed by verifier/process-reward and search-policy references as ingredients; and kept honest by an explicit boundary between canonical, adjacent, idea-only, and historical sources.

## Recommended immediate repository habit

When a new reference appears, record **all four** of the following explicitly:
1. relevance class (`core`, `direct baseline`, `adjacent baseline`, `ingredient`, `frontier`, `dataset`, `historical`, `blocked/uncertain`),
2. what idea it gave the project,
3. whether it is manuscript-facing, experiment-facing, or provenance-only,
4. and whether it is safe to foreground in the current paper story.


## Cross-doc baseline taxonomy consistency lock (2026-04-18)

| Family short name | Canonical title | Class | Current repo status | Paper-phase priority |
|---|---|---|---|---|
| `qstar_deliberative_planning` | Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning | direct baseline family | discuss-only / implementation-gap | essential |
| `lets_verify_step_by_step` | Let's Verify Step by Step | adjacent baseline family | discuss-only | essential adjacent |
| `rational_metareasoning_llm` | Rational Metareasoning for Large Language Models | adjacent baseline family | discuss-only | essential adjacent |
| `efficient_contextual_llm_cascades` | Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning | adjacent baseline family | runnable-adjacent via import validation | optional unless framing broadens |
| `best_arm_identification_fixed_budget` | Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence | ingredient/adjacent-boundary family | discuss-only framing reference | essential framing for near-ties |

Use this table as the canonical normalization layer across `docs/main_baselines.md`, `docs/external_baseline_completeness_report.md`, `docs/EVALUATION_AND_BASELINES_INDEX.md`, `external/README.md`, and `configs/external_baselines_registry.json`.
