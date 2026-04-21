# Learned F2→F3 gate evaluation (20260421T034409Z)

Strict phased law maintained: finish F1 then F2 then optional F3, with gate evaluated only after full F2 completion.

## Label policy
- Binary target: `force_f3` vs `release_after_f2`.
- Label `force_f3` iff strict_f3 final correctness is better than strict_f2.
- Label `release_after_f2` otherwise.
- Tie policy: prefer `release_after_f2`, except when strict_f3 provides clear additional tree coverage benefit.

## Learned model diagnostics
- Label distribution: {'release_after_f2': 72, 'force_f3': 24}
- Validation accuracy (logreg): 0.6875
- Validation accuracy (tree): 0.7500
- Best model: **strict_learned_f2_to_f3_gate_v1_tree**
- Best-model validation confusion: {'tp': 0, 'tn': 12, 'fp': 1, 'fn': 3}
- Best-model heldout confusion: {'tp': 0, 'tn': 11, 'fp': 0, 'fn': 6}

## Held-out broader matched comparison
| method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.5882 | 5 | 2 | 15 | 12 | 5.412 | 5.059 | 0.353 | 0 | 0 | 0 |
| strict_f2 | 0.5882 | 5 | 2 | 15 | 12 | 6.118 | 5.882 | 0.235 | 0 | 0 | 0 |
| strict_f3 | 0.6471 | 5 | 1 | 15 | 12 | 6.353 | 5.941 | 0.412 | 0 | 0 | 0 |
| strict_gate1 | 0.7647 | 4 | 0 | 12 | 13 | 5.000 | 4.529 | 0.471 | 0 | 0 | 0 |
| strict_gate2 | 0.7647 | 1 | 3 | 16 | 16 | 6.294 | 5.882 | 0.412 | 0 | 0 | 0 |
| learned_f2_to_f3_gate_v1 | 0.5882 | 5 | 2 | 15 | 12 | 6.118 | 5.882 | 0.235 | 4 | 4 | 9 |

## Frozen 100-case stress comparison
| method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.0000 | 78 | 22 | 97 | 22 | 11.480 | 10.840 | 0.640 | 0 | 0 | 0 |
| strict_f2 | 0.6300 | 24 | 13 | 86 | 76 | 10.030 | 9.510 | 0.520 | 0 | 0 | 0 |
| strict_f3 | 0.6600 | 21 | 13 | 83 | 79 | 9.490 | 8.930 | 0.560 | 0 | 0 | 0 |
| strict_gate1 | 0.7000 | 21 | 9 | 77 | 79 | 9.360 | 8.750 | 0.610 | 0 | 0 | 0 |
| strict_gate2 | 0.7000 | 19 | 11 | 84 | 81 | 9.970 | 9.300 | 0.670 | 0 | 0 | 0 |
| learned_f2_to_f3_gate_v1 | 0.6800 | 23 | 9 | 85 | 77 | 10.170 | 9.590 | 0.580 | 68 | 0 | 32 |

## Scientific questions
1. Learned gate beats deterministic gates on broader held-out? **False**
2. Learned gate retains strict_f3-style coverage while limiting forced F3? Held-out decisions: {'release_after_f2': 17}
3. Extra complexity justification: compare learned vs strict_gate1/2 head-to-head in JSON summaries.
4. Final decision anchored to held-out broader surface, frozen 100 is stress-test only.

## Learned gate recommendation
- whether the learned gate is worth keeping: no
- whether it should replace deterministic gates: no
- whether it is only a promising research direction: yes
- and which model should remain the default today: strict_gate2

## Concise run summary
- files changed: scripts/run_learned_f2_to_f3_gate_v1_eval.py, docs/LEARNED_F2_TO_F3_GATE_EVAL_20260421T034409Z.md
- commands run: see shell history in PR summary
- output directory: outputs/learned_f2_to_f3_gate_20260421T034409Z
- best learned model: strict_learned_f2_to_f3_gate_v1_tree
- broader held-out vs strict_f2/strict_f3/strict_gate1/strict_gate2: {'learned_vs_strict_f2': {'unchanged': 17}, 'learned_vs_strict_f3': {'worsened': 6, 'unchanged': 6, 'improved': 5}, 'learned_vs_strict_gate1': {'worsened': 5, 'unchanged': 10, 'improved': 2}, 'learned_vs_strict_gate2': {'worsened': 5, 'unchanged': 10, 'improved': 2}}
- frozen 100 vs strict_f2/strict_f3/strict_gate1/strict_gate2: {'learned_vs_strict_f2': {'unchanged': 95, 'improved': 5}, 'learned_vs_strict_f3': {'unchanged': 58, 'worsened': 20, 'improved': 22}, 'learned_vs_strict_gate1': {'unchanged': 64, 'worsened': 19, 'improved': 17}, 'learned_vs_strict_gate2': {'unchanged': 64, 'worsened': 19, 'improved': 17}}
- one-sentence verdict: learned gate is not yet good enough to replace deterministic defaults.