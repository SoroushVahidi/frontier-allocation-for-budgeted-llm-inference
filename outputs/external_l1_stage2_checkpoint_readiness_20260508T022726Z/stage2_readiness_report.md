# Stage-2 readiness (no-API)

## Stage-1 recap
- 40 cases, 2 calls, integrated 35/40 vs external 34/40 (+1).

## Stage-2 plan
- Case count: 100
- Estimated new Cohere calls: 2
- Reuses existing external_l1 and baseline PAL outputs from the 100-case band.

## Call-plan summary
- by_action: {"targeted_retry": 2}
- by_scaffold: {"quantity_ledger": 2}

## Readiness
- Ready for dry-run validation via reproducible runner.
- Live run should proceed only if dry-run preflight passes and call cap remains <=50.

## Command (if approved later)
python scripts/run_external_l1_integrated_checkpoint.py --readiness-dir outputs/external_l1_stage2_checkpoint_readiness_20260508T022726Z --case-file outputs/external_l1_stage2_checkpoint_readiness_20260508T022726Z/stage2_recommended_cases.csv --stage-name stage2 --max-new-cohere-calls 50 --reuse-external-l1 --method-name direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal_structural_commit_v1_targeted_retry_v1 --baseline external_l1_max