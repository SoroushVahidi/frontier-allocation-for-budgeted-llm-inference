# Science-anchor robustness extension (GPQA-Diamond, appendix-only) — 2026-04-23

## Scope and guardrails

This run is an appendix-only robustness extension and does **not** overwrite canonical manuscript 4/6/8 artifacts.

- Preferred dataset target: `gpqa_diamond` on `Idavidrein/gpqa`.
- Internal methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`.
- External anchors included only because they are already supported on the same matched substrate (`external_s1_budget_forcing`, `external_tale_prompt_budgeting`, `external_l1_max`, `external_l1_exact`).
- Budgets: `4,6,8,10,12,14` (kept because `run_science_anchor_robustness.py` natively supports this exact range and emits both canonical and appendix budget slices in one contract).

## Feasibility inspection

Feasibility was checked before running the extension:

1. Dataset access/documentation
   - `docs/datasets_access.md` already documents `Idavidrein/gpqa` with config `gpqa_diamond` and gated-access requirements.
   - `scripts/verify_hf_dataset_access.py` includes explicit GPQA loader-path verdict fields.
2. Matched substrate compatibility
   - `scripts/run_matched_surface_multiseed_main_comparison.py` shows the canonical matched substrate contract pattern and strategy-builder usage.
3. Extended-budget compatibility
   - `scripts/run_extended_budget_frontier_robustness.py` uses the same substrate family and budget extension pattern used by the current appendix robustness line.
4. Science-anchor runner
   - `scripts/run_science_anchor_robustness.py` already encodes GPQA-first design, method list, and matched-style output bundle.

### Feasibility verdict

GPQA-Diamond was feasible in this environment:

- Access check run: `python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access_science_anchor_check --datasets Idavidrein/gpqa,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024,openai/gsm8k`
- Result: GPQA accessible (`config=gpqa_diamond`, loader path `datasets`, final verdict true).

No fallback dataset was needed.

## Run executed

```bash
python scripts/run_science_anchor_robustness.py --run-id 20260423T_science_anchor_gpqa_diamond
```

Output family:

- `outputs/science_anchor_robustness_20260423T_science_anchor_gpqa_diamond/`

Included artifacts:

- `per_case_outcomes.csv`
- `comparison_table.csv`
- `per_budget_summary.csv`
- `per_method_summary.csv`
- `per_seed_summary.csv`
- `per_dataset_summary.csv`
- `pairwise_mechanism_head_to_head.csv`
- `manifest.json`
- `conservative_interpretation_note.md`

## Direct research answers

1. **Was GPQA-Diamond feasible?**
   - Yes; feasible and successfully executed on the matched-style substrate.

2. **Does the science anchor preserve manuscript-facing preference for `strict_f3`?**
   - **Weakened** on this run. On GPQA, 4/6/8 sums are `strict_f3=1.575`, `strict_gate1_cap_k6=1.700`, `strict_f2=1.675`.

3. **Does `strict_gate1_cap_k6` become stronger on harder science-style substrate?**
   - It is stronger than `strict_f3` on both 4/6/8 and 10/12/14 sums here, but not the top internal method overall.

4. **Does `strict_f2` remain unexpectedly competitive?**
   - Yes, and more than competitive here: `strict_f2` is top internal method in overall mean accuracy and high-budget sum.

5. **Failure mechanism mix (`absent_from_tree` + `present_not_selected` vs mismatch)?**
   - `output_layer_mismatch` remains effectively zero in head-to-head rows; differences are carried by `absent_from_tree` and `present_not_selected` deltas.

6. **Paper strategy impact?**
   - Keep appendix-only for now. This single science-anchor run is important robustness evidence but does not justify replacing the canonical manuscript contract.

## Conservative positioning note

This extension broadens stress-testing breadth on a harder science-heavy anchor. It should be treated as robustness evidence and future-promotion input, not a silent rewrite of the main manuscript-facing 4/6/8 contract.
