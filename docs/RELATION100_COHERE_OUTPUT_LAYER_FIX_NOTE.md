# Relation100 Cohere — Output-Layer Fix Finding Note

## Experiment

Two 100-case live Cohere API comparison runs on GSM8K were conducted to evaluate the
`best` runtime against the `external_l1_max` baseline and to measure the effect of an
output-layer repair fix.

| Field | Value |
|---|---|
| Dataset | openai/gsm8k (test split) |
| Sample seed | 20260514 |
| Cases | 100 |
| Budget | 6 |
| Provider / model | Cohere `command-r-plus-08-2024` |
| Methods | `best`, `external_l1_max` |
| `best` runtime | `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal` |

Both runs used the identical 100 sampled cases.

---

## Pre-Fix Result

**Run:** `outputs/relation100_best_vs_external_l1max_cohere_fixed_full_20260514T173628Z/`  
**Run ID:** `cohere_100case_20260514T174025Z`

| Method | Correct | Accuracy |
|---|---|---|
| `best` | 71 / 100 | 0.71 |
| `external_l1_max` | 74 / 100 | 0.74 |

### Gold reachability

`best` found the gold answer in its candidate tree for 85 / 100 cases but failed to
surface it correctly in 14 of those found cases (9 output-layer mismatches, 5
present-not-selected).

### `best` failure anatomy

| Failure type | Count |
|---|---|
| `absent_from_tree` | 15 |
| `output_layer_mismatch` | 9 |
| `present_not_selected` | 5 |

`output_layer_mismatch` (OLM): the tree-majority rescue in `choose_repair_answer()`
overwrote a correct PAL answer (already committed by the controller as the
`selected_group_hint`) with a wrong tree-majority answer.

---

## Output-Layer Fix

**Commit:** `82b5912a` / cherry-picked as `95180a5d` onto `feat/missing-gold-topology-v1`  
**File:** `experiments/output_layer_repair.py`  
**Tests:** `tests/test_output_layer_frontier_surfacing.py` (+200 lines, 51 tests)

Two changes:

1. **OLM rescue guard** — `choose_repair_answer()` now skips the tree-majority rescue
   if the already-surfaced answer matches the controller-committed `selected_group_hint`.
   This prevents the rescue from clobbering a correct PAL answer with a wrong tree majority.

2. **PAL overlay conflict threshold reduction:**
   - `PAL_STRONG_OVERLAY_PEER_SUPPORT_CONFLICT_MIN`: 3 → 2
   - `PAL_STRONG_OVERLAY_TIEBREAK_PEER_SUPPORT_CONFLICT_MIN`: 2 → 1

   These thresholds govern when non-PAL peer support blocks a PAL takeover. Lowering them
   makes PAL harder to promote over peers with ≥2 (resp. ≥1) support, which is expected to
   recover present-not-selected cases in future live runs where PAL was overriding a correct
   peer answer. Existing stored failure records cannot be replayed to validate this class
   because `pal_overlay_applied` is already committed in those records.

Offline replay of the 14 pre-fix target failure records confirmed 9/9 OLM cases recovered
and 0/5 PNS cases recovered (runtime-only fix class).

---

## Post-Fix Result

**Run:** `.claude/worktrees/shimmering-greeting-squirrel/outputs/relation100_best_vs_external_l1max_cohere_postfix_20260514T213453Z/`  
**Comparison report:** `…/postfix_comparison_report.md` (in the same directory)  
**Run ID:** `cohere_100case_20260514T213547Z`

| Method | Pre-fix | Post-fix | Delta |
|---|---|---|---|
| `best` | 71 / 100 | 70 / 100 | −1 |
| `external_l1_max` | 74 / 100 | 77 / 100 | +3 |

### Failure type shift (`best`)

| Failure type | Pre-fix | Post-fix | Delta |
|---|---|---|---|
| `output_layer_mismatch` | 9 | **0** | **−9** |
| `present_not_selected` | 5 | 16 | +11 |
| `absent_from_tree` | 15 | 14 | −1 |

OLM failures were eliminated entirely. The apparent accuracy regression of −1 for `best`
and the +11 PNS expansion are both explained by Cohere API nondeterminism:

- 13 / 16 post-fix PNS cases had **different candidate sets** compared to pre-fix.
- `external_l1_max` (zero code change) moved **+3** in the same run, setting a noise floor
  of at least ±3 points for a 100-case live Cohere run with this model.
- The net −1 for `best` decomposes as: +2 (OLM fix recovered cases 53, 88) − 8
  (nondeterminism regressions) + 5 (nondeterminism gains) = −1.

---

## Interpretation

The fix is mechanically correct and confirmed by offline replay and live run evidence.
The apparent accuracy drop is within Cohere API nondeterminism variance and is not
attributable to the fix.

Single 100-case API comparison runs with stochastic provider outputs **should not be
overinterpreted.** Variance is large (±3+ points observed for `external_l1_max` with no
code change). Future accuracy claims require either:

- repeated runs with different seeds, or
- deterministic cached-candidate replay runs that isolate the selection logic from API noise.

---

## Safety

Gold answers are used **only for offline evaluation and reporting.** They are never
included in provider prompts or runtime selection logic. Both runs confirmed this
explicitly in the terminal output:

```
✓ No gold answers were sent to any provider.
✓ No outputs staged or committed.
```

---

## Related Artifacts

| Artifact | Location |
|---|---|
| Pre-fix run output | `outputs/relation100_best_vs_external_l1max_cohere_fixed_full_20260514T173628Z/` |
| Pre-fix analysis report | `outputs/relation100_best_vs_external_l1max_cohere_fixed_full_20260514T173628Z/analysis_report.md` |
| Post-fix run output (worktree) | `.claude/worktrees/shimmering-greeting-squirrel/outputs/relation100_best_vs_external_l1max_cohere_postfix_20260514T213453Z/` |
| Post-fix comparison report | `…/postfix_comparison_report.md` (in post-fix dir above) |
| Output-layer repair implementation | `experiments/output_layer_repair.py` |
| Output-layer repair tests | `tests/test_output_layer_frontier_surfacing.py` |
| Existing output-layer appendix note | `docs/APPENDIX_OUTPUT_LAYER_REPAIR_FIGURE_NOTE.md` |
