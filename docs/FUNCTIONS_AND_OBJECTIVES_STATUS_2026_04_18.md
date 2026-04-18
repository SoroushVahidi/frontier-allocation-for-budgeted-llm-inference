# Functions and objectives status (2026-04-18)

## Purpose

This note freezes the current repository function stack so objective/score/decision meanings are explicit and consistent across docs and scripts.

This is a **canonicalization pass** (not a new-method proposal).

---

## Canonical decomposition (repository-facing)

### 1) Core objective function (what we actually optimize)

**Canonical objective:**

> maximize final task utility / final decision quality under a fixed compute budget, by allocating each next unit of compute to the best branch and committing only when expansion is no longer worthwhile.

Operationally, the primary repository approximation of this objective remains continuation-value-grounded branch allocation under budget constraints, with bounded completion-aware correction only in localized disagreement states.

**Canonical status:** canonical.

**Primary evidence paths:**
- `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`

---

### 2) Core expansion score (who gets the next compute unit)

**Canonical expansion score:** continuation-value-centered branch utility.

Current default family:
- `multistep_branch_utility_target_k3` (strongest bounded line)
- one-step continuation-value anchored comparisons (`estimated_value_if_allocate_next`) remain the oracle reference backbone

**Canonical status:** canonical.

**Key code locations:**
- `scripts/build_bruteforce_target_regimes.py`
  - `_multistep_utility_target_for_candidate`
  - strategy labels `multistep_branch_utility_target_k{1,2,3}`
- `scripts/run_multistep_branch_utility_target_experiment.py`

---

### 3) Core incumbent / commit-quality score (if we stop now)

**Canonical incumbent score object:** completion/current-branch-quality evidence as a bounded auxiliary signal.

This uses branch-visible completion evidence (`branch_completion_score`) and answer-evidence (`branch_answer_evidence_score`) as commit-quality proxies, with explicit recoverability metadata.

**Canonical status:** canonical as a **bounded local correction signal**, not a global replacement objective.

**Key code locations:**
- `scripts/run_completion_aware_decision_experiment.py`
  - `build_completion_signal`
- `scripts/run_oracle_mismatch_study.py`
  - `_completion_signal`
  - hybrid scalar composition over continuation + completion + answer evidence + outside-option term
- `docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`

---

### 4) Core metalevel decision rule (expand i / expand j / commit now)

The canonical metalevel rule is now explicit:

1. Compute expansion ranking from continuation-centered score (default multistep-k3 family).
2. Compute incumbent/commit-quality evidence (completion/answer evidence).
3. If state is not in disagreement/near-tie slice, use continuation-ranked expansion choice.
4. If state is in disagreement/near-tie slice, apply bounded correction/gating using completion-aware evidence and outside-gap safety checks.
5. Allow defer/commit-now outcome when instability/ambiguity gates indicate low-confidence forced expansion.

**Canonical status:** canonical decomposition; concrete policy variants remain exploratory until frozen as one final controller.

**Primary implementation families:**
- continuation ranking: `run_multistep_branch_utility_target_experiment.py`
- completion-aware local correction: `run_completion_aware_decision_experiment.py`, `run_oracle_mismatch_study.py`
- defer/abstain gates: `run_instability_decision_coupling_experiment.py`, `run_rank_instability_experiment.py`

---

### 5) Local modifiers only (not global objective replacements)

These are useful but currently **local/gating/diagnostic modifiers**, not canonical global objective replacements:

- rank-instability signals and defer coupling
- near-tie ambiguity flags and tie-aware policies
- opportunity-intensity weighting
- penalized marginal defer shaping
- completion-bonus/tie-resolution policy overlays
- outside-option-sensitive conservative gates

**Canonical status:** exploratory local modifiers.

---

## Function-family classification

### Canonical (default paper-facing stack)

1. **Objective layer**
   - fixed-budget final utility / decision quality via next-step branch allocation
2. **Expansion score layer**
   - continuation-centered multistep utility (default `multistep_k3`)
3. **Incumbent score layer**
   - bounded completion/answer-evidence commit-quality proxy
4. **Decision layer**
   - metalevel expand-vs-commit rule with bounded disagreement-slice correction

### Exploratory (active but not default)

- discounted multistep targets (`discounted_multistep_branch_utility_target_gamma*`)
- compute-response curve target (`compute_response_curve_target_h123`)
- rank-instability target (`rank_instability_target_v1`)
- penalized marginal defer target
- opportunity-intensity weighted target
- allocation-regret target variants
- tie-aware soft/ternary targets (`davidson_tie_aware`, `soft_prob_tie_aware`, partial-order variants)
- policy-level instability coupling variants and abstention heuristics
- completion-only global replacement policies

### Deprecated / demoted from default-summary role

These are **not removed**, but are demoted from canonical default story:

- “pairwise default + tie-aware post-hoc deferral + specialist pointwise fallback” as the top-level repository-wide method summary (still relevant historically for a sub-line, but no longer the canonical repository-wide function decomposition)
- broad nearby scalar-target sweeps as default next step

---

## Canonical decision pseudo-rule (normative summary)

For state `s` with active branches `B(s)` and remaining budget `b`:

- Expansion utility score per branch: `E_i = continuation_value_i` (default multistep-k3 proxy)
- Commit quality score per branch: `C_i = completion_answer_quality_i` (bounded, local)
- Let `i* = argmax_i E_i`
- If not in disagreement slice: choose `expand(i*)`
- If in disagreement slice (`near_tie || instability || completion-vs-continuation conflict`):
  - apply bounded correction gate; possibly choose alternative branch `j` if correction constraints pass
  - otherwise keep `i*`
- Compare best expansion value to commit-now utility estimate; if expansion advantage is below threshold / uncertainty-gated, allow `commit_now` (or defer/abstain in learning/eval harnesses)

This decomposition is the repository’s current canonical function map; specific numeric thresholds remain tunable experimental parameters.

---

## Practical repository rule

- Keep objective-level claims anchored to fixed-budget final utility.
- Keep continuation value as default expansion signal.
- Keep completion-aware evidence bounded and local.
- Treat instability/near-tie mechanisms as gates/modifiers, not replacement objectives.
- Do not promote exploratory targets to canonical without fresh evidence that changes this map.
