# TALE: Token-Budget-Aware LLM Reasoning (external published baseline)

- Paper (ACL Anthology): https://aclanthology.org/2025.findings-acl.1274/
- PDF: https://aclanthology.org/2025.findings-acl.1274.pdf
- arXiv: https://arxiv.org/abs/2412.18547
- Official code: https://github.com/GeniusHTX/TALE

## Integration status in this repository

- Integration mode: `MODE_A_COMPLETE_MODE_B_PARTIAL`
- Scope implemented:
  - MODE A: runnable in-repo TALE-style prompt/inference token budgeting adapter (`external_tale_prompt_budgeting`).
  - MODE B: official/full TALE adapter reporting path via imported external outputs.
- Policy: no vendored upstream code; provenance links only.

## Important methodological split

- Prompt-level TALE-style budgeting (implemented here in MODE A) is not the same as TALE-PT post-training.
- TALE-PT is **not** automatically reproduced inside this repository.

## Local runner hooks

- `python scripts/run_tale_baseline.py --config configs/tale_prompt_budgeting_v1.json`
- `python scripts/run_tale_baseline.py --config configs/tale_official_adapter_v1.json`
- `python scripts/run_tale_comparison_bundle.py --run-dirs <run_dir_1,run_dir_2,...>`

See also:
- `docs/tale_baseline_integration.md`
