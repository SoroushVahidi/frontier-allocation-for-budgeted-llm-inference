# Extended-budget broader-seed robustness note (2026-04-23)

## Scope and contract

This run is a **repeat** of the existing extended-budget robustness study and keeps the same matched extension contract:

- budgets: `10,12,14`
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- subset size: `20` per dataset-seed
- methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `external_l1_max`, `external_l1_exact`, `external_tale_prompt_budgeting`, `external_s1_budget_forcing`

The only intentional contract expansion is seed coverage:

- prior extension seeds: `11,23`
- broader-seed repeat seeds: `11,23,37,59,71,83,97,109`

Run command:

```bash
python scripts/run_extended_budget_frontier_robustness.py \
  --run-id 20260423Textended101214_multiseed_v1 \
  --seeds 11,23,37,59,71,83,97,109
```

Output family:

- `outputs/extended_budget_frontier_20260423Textended101214_multiseed_v1/`

This remains appendix/robustness-only and does **not** overwrite canonical main-paper 4/6/8 artifacts.

## Results snapshot (internal methods)

Per-budget mean accuracy:

- budget 10: `strict_f2` **0.7000**, `strict_gate1_cap_k6` **0.6875**, `strict_f3` **0.6375**
- budget 12: `strict_gate1_cap_k6` **0.6521**, `strict_f2` **0.6333**, `strict_f3` **0.6292**
- budget 14: `strict_gate1_cap_k6` **0.7229**, `strict_f2` **0.6646**, `strict_f3` **0.6625**

Head-to-head (`strict_f3 - strict_gate1_cap_k6`):

- budget 10: `-0.0500`
- budget 12: `-0.0229`
- budget 14: `-0.0604`

Overall across budgets 10/12/14 (mean over all included cases):

- `strict_gate1_cap_k6`: **0.6875**
- `strict_f2`: **0.6660**
- `strict_f3`: **0.6431**

## Direct answers to the current uncertainty

1. **Does the mixed 10/12/14 story persist under more seeds?**
   - It remains **non-uniform across methods** (different winners by budget), but the previous alternation where `strict_f3` won at budget 12 does **not** persist in this broader-seed repeat.

2. **Does `strict_f3` remain unstable at higher budgets, or does alternation wash out?**
   - `strict_f3` no longer alternates into a budget win on this slice; it trails `strict_gate1_cap_k6` at all three budgets and is effectively a non-winning high-budget option under this broader-seed contract.

3. **Does `strict_gate1_cap_k6` become the more stable high-budget choice?**
   - Yes on this study: it wins budgets 12 and 14 and is second at budget 10; it is the top overall internal method on this extension.

4. **Is `strict_f2` unexpectedly competitive only because of bounded noise, or does that persist?**
   - Competitiveness persists. `strict_f2` wins budget 10 and remains close at 12/14, so it should remain tracked as a legitimate high-budget competitor rather than dismissed as pure bounded noise.

5. **Should higher-budget extension remain appendix-only, or reconsider the main manuscript story now?**
   - Keep appendix-only for now. This run improves stability evidence for operational high-budget behavior (`strict_gate1_cap_k6`), but it does not justify replacing the canonical manuscript-facing matched-surface 4/6/8 contract or silently promoting 10/12/14 into the main story.

## Optional appendix plot-data refresh

Updated appendix plot-data was regenerated from this new bundle:

```bash
python scripts/paper/build_appendix_extended_budget_frontier_plot_data.py \
  --extended-bundle-dir outputs/extended_budget_frontier_20260423Textended101214_multiseed_v1
```

Refreshed outputs:

- `outputs/paper_plot_data/appendix_extended_budget_frontier.csv`
- `outputs/paper_plot_data/appendix_extended_budget_method_ranking.csv`
- `outputs/paper_plot_data/appendix_extended_budget_head_to_head.csv`
