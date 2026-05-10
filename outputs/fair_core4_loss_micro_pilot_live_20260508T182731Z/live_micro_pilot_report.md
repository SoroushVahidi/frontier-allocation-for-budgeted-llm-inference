# Fair core4 loss-bank live micro-pilot report

- Result overview: exact=2/11 with 11 calls.
- Improved_over_our_before=2; best_core4_only_fixed=2; both_wrong_fixed=0.
- Exact by scaffold: {'tale_style_decomposition': 1, 'robust_extraction_observability': 1, 'final_target_extraction_repair': 0, 'ratio_unit_equation': 0, 'state_transition_consistency': 0}.
- Exact by failure family: {'final_target_mismatch': 1, 'format_parse': 1, 'ratio_setup': 0, 'state_update': 0}.
- Interpretation: improvements indicate scaffold-level signal, but 11-case targeted set is not sufficient alone for broad runtime change claims.
- Recommendation: if one scaffold clearly dominates, test a minimal gated runtime patch on a fresh held-out micro-batch; otherwise continue production-equivalence work first.
- Caveats: targeted cases and deterministic decoding can inflate apparent gains.
