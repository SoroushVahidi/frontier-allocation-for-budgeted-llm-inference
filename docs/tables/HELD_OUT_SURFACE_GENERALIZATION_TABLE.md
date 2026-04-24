# Held-out surface generalization (short table)

| method | n | mean_accuracy | std_accuracy | datasets_covered | budgets_covered | seeds_covered |
| --- | --- | --- | --- | --- | --- | --- |
| self_consistency_3 | 6 | 0.666667 | 0.516398 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| strict_gate1_cap_k6 | 6 | 0.666667 | 0.516398 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| l1_exact | 6 | 0.5 | 0.547723 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| strict_f2 | 6 | 0.5 | 0.547723 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| strict_f3 | 6 | 0.5 | 0.547723 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| external_l1_max | 6 | 0.333333 | 0.516398 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| s1 | 6 | 0.333333 | 0.516398 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |
| tale | 6 | 0.166667 | 0.408248 | Hothan/OlympiadBench,Idavidrein/gpqa,livecodebench/execution-v2 | 4 | 11 |

## Claim-safety

| claim | support_status | statistical_status |
| --- | --- | --- |
| Strict-F3 generalizes as best method on held-out surfaces | not_safe | descriptive |
| Strict-F3 dominates Strict-Gate1-Cap-K6 on held-out surfaces | supportive | supportive |
| Frontier allocation dominates external_l1_max on held-out surfaces | not_safe | supportive |
| Frontier allocation is competitive but not dominant | safe | mixed |
| Held-out evidence supports formulation/diagnostic framing | safe | descriptive |
| Held-out evidence supports SOTA/dominance framing | not_safe | not_safe |

