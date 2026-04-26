# Cohere direct reserve failure replay seed (latest)

- Source artifact: `outputs/cohere_direct_reserve_validation_REGENERATED_FOR_REPLAY_20260426T120000Z`
- Construction mode: regenerated (minimal real API run) because original package was absent in checkout.
- Replay cases listed in `replay_case_list.csv`: 5.
- Required summary files were copied for portability.
- Full trace files were copied because they are small in this run (<1 MB each).

## Replay fields
- For each replay case, `prior_failure_type`, per-method outcomes, and control degradation flags are included.
- Rich debugging content is preserved via `loss_cases.csv/jsonl`, `difference_cases.jsonl`, and full traces.

## Regeneration command
```bash
python scripts/run_cohere_direct_reserve_validation.py --timestamp REGENERATED_FOR_REPLAY_20260426T120000Z --provider cohere --model command-r-plus-08-2024 --dataset openai/gsm8k --budgets 4 --seeds 23 --max-cases 12 --methods strict_f3,external_l1_max,direct_reserve_strong_v1,direct_reserve_strong_plus_diverse_v1,direct_reserve_strong_plus_diverse_margin_gated_v1 --loss-artifact outputs/matched_surface_multiseed_main_comparison_20260423T203259Z/raw_case_results.csv --emit-full-traces --resume --run-real-api
```
