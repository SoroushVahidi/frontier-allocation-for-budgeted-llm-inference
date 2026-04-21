# NeurIPS Figure and Table Audit

## 2026-04-21 cleanup note

This audit originally documented bounded imported-methodology surfaces. The active paper artifact set has been re-canonicalized to strict-phased/default evidence bundles.
Use `docs/PAPER_ARTIFACT_CLEANUP_REPORT_2026_04_21.md` as the current source-of-truth for keep/revise/demote/remove decisions and final artifact lists.

## Canonical result sources

Primary canonical paper-facing source bundles in this repository state:

1. `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
   - fixed vs adaptive vs oracle frontier summaries
   - budget curves, oracle-gap rows, method metrics, signal slices
2. `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/`
   - strict-coupled / tie-aware / fallback control diagnostics
3. `outputs/branch_label_bruteforce_learning/soft_prob_tie_matched_20260417/`
   - tie-aware and abstention formulation diagnostics
4. `outputs/branch_scorer_v3_final_eval/`
   - auxiliary robustness context (seed/budget grid summary)

## Canonical method names and promoted line

- Core frontier methods (current canonical import layer):
  - `adaptive_budget_guarded`
  - `reasoning_beam2`
  - `self_consistency_3`
  - `reasoning_greedy`
  - `verifier_guided_search`
  - `program_of_thought`
  - `oracle_frontier_upper_bound`
- Current promoted controller-family line in docs:
  - pairwise default + tie-aware post-hoc deferral + specialist pointwise fallback
  - representative method identity: strict-coupled near-tie specialized pointwise variants

## Strongest current baselines

From currently committed canonical frontier outputs:
- `reasoning_beam2` and `self_consistency_3` are strongest fixed baselines in the GSM8K frontier bundle.

From strict-coupled/tie-aware branch-comparison bundles:
- `binary_forced_baseline` and tie-aware/posthoc-deferral variants are key internal adversaries.

## Current dataset surface

- Main frontier bundle used for paper plots is currently single-dataset: `openai/gsm8k`.
- Repo-level broader evaluation surface exists in docs/registry, but is not yet represented by a single committed, matched, canonical multi-dataset frontier bundle under the same schema.

## Budget definitions

- Canonical frontier bundle budgets: 8 and 10.
- Budget is treated as fixed test-time compute units in the branch/frontier allocation framing.

## Core metrics

- `accuracy`
- `avg_actions`
- `gap_to_oracle`
- `budget_exhaustion_rate`
- signal slice metrics (`hard_accuracy`, `easy_accuracy`) for honest failure localization
- tie-aware diagnostics (`coverage`, `deferred_rate`, strict-routed slice metrics)

## Safe paper-facing artifact bundles

Safe for paper-facing use now:
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- selected strict-coupled/tie-aware summary artifacts in
  `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/`

Use with caveats:
- `outputs/branch_scorer_v3_final_eval/` (auxiliary robustness context; different task surface)

Not safe for headline claims:
- status-only external baseline files without matched metric rows

## Audit conclusion

The repository supports a clean, conservative NeurIPS-facing artifact path centered on:
- fixed-budget frontier curves,
- oracle-gap/headroom accounting,
- anti-collapse/control diagnostics,
- and honest failure decomposition proxies.

It does not yet support a broad, single-schema, matched multi-dataset frontier story in committed canonical outputs.
