# Comparative frontier audit (new-paper track)

This note points to **matched-budget** audits of the in-repo controller frontier vs a tagged primary method (`adaptive_min_expand_1` by default).

## Runner

```bash
python scripts/run_comparative_frontier_audit.py \
  --subset-size 64 \
  --budgets 6,8,10,12 \
  --datasets openai/gsm8k,EleutherAI/hendrycks_math
```

Optional third dataset (if Hub access works):

```bash
python scripts/run_comparative_frontier_audit.py ... --try-gpqa --subset-size 48
```

## Outputs (per run)

Directory pattern: `outputs/comparative_frontier_audit/<run_id>/`

| File | Contents |
|------|-----------|
| `run_manifest.json` | Seeds, budgets, datasets, **external baselines not integrated**, API flags |
| `method_metrics.csv` | All eight families: accuracy, cost, exhaustion, oracle gap |
| `oracle_gap_summary.csv` | Same metrics keyed for gap analysis |
| `comparison_summary.csv` | Primary (`adaptive_min_expand_1`) vs each fixed baseline |
| `main_drawbacks_report.md` | Win/loss counts, inferred weaknesses (evidence-based) |
| `selector_audit.csv` | Only if `--with-selector-split` (calibration-based selector) |

## What is “ours” vs baseline

- **Ours (tagged)**: `adaptive_min_expand_1` — adaptive expand/verify/prune with `min_expansions_before_prune=1` (anti-collapse knob).
- **Baselines in CSV**: greedy, self-consistency×3, beam-2, verifier-guided search, program-of-thought.
- **Ablations**: `adaptive_min_expand_0` and `_2` appear in `method_metrics.csv` but are not duplicated in every pairwise row in `comparison_summary.csv`.

## External baselines

Cascade routing, MoB, paper-linked third-party codebases are **documented** under `external/` but **not** executed inside this repository. The manifest lists them explicitly so we do not overclaim integration.

## Honesty: simulator vs API

Default runs use **`SimulatedBranchGenerator`**. Accuracy is a **process proxy** for allocation behavior, not GSM8K/MATH leaderboard numbers. **Program-of-thought** in simulation uses trivial numeric codegen from regex—often **near-zero accuracy** on full GSM8K questions; that is a **fairness limitation** for PoT in sim, not a claim about real codegen models. Use `--use-openai-api` for real-model matched audits when keys and budget allow.

## Example runs (repository-local)

- `outputs/comparative_frontier_audit/20260413T215319Z/` — GSM8K + MATH, subset 64, budgets 6–12 (regenerated report text).
- `outputs/comparative_frontier_audit/20260413T215237Z/` — GSM8K + MATH, subset 64, budgets 6–12 (earlier same config).
- `outputs/comparative_frontier_audit/20260413T215247Z/` — GSM8K + MATH + GPQA Diamond, subset 48.

`outputs/comparative_frontier_audit/**` is **tracked** in git (CSV/MD/JSON only). For **OpenAI/Groq/Gemini** runs, see [`comparative_frontier_audit_real_model_note.md`](comparative_frontier_audit_real_model_note.md).
