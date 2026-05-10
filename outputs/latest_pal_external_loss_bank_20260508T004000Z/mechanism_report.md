# Latest PAL external loss bank (offline)

## Output bundle
- Directory: `outputs/latest_pal_external_loss_bank_20260508T004000Z`
- Built from manifests proving `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`.

## Are the 34 preferred failures globally complete?
**No.** The 34 are **artifact-complete** for the 247-id suffix evaluation (`openai_gsm8k_1072..1318`) with three external baselines. Additional disjoint losses appear in the 300-case paired cohort, the 100-case paired cohort, and the 30-case pilot.

## Deduplicated headline counts
- Unique case IDs in union bank (union-eligible sources): **71**
- Rows in per-source bank (includes duplicates if a case appears in multiple artifacts — none observed across non-overlapping bands): **71**

## Mechanism buckets (unique cases; see `mechanism_counts.json`)
- present_not_selected (cluster/heuristic): **24**
- gold_absent_discovery: **36**
- unknown: **11**
- Track B offline fixed IDs (subset): **3**
- executable PAL present but not committed (replay `primary_commitment_mechanism`): **16**

## Top 10 anchor cases (next implementation loop)
- **openai_gsm8k_1087** — Track B replay fixed overlay vs bad PAL stdout; rate/temporal hints.
- **openai_gsm8k_1279** — Track B replay fixed; gold-vs-surface mismatch in replay table.
- **openai_gsm8k_1290** — Track B replay fixed; high-revenue charity word problem.
- **openai_gsm8k_1082** — PNS in cluster; alphabet rewrite counting.
- **openai_gsm8k_1099** — gold_absent_discovery in 4-way cluster.
- **openai_gsm8k_1125** — gold_absent_discovery; extreme rate error.
- **openai_gsm8k_773** — 300-case L1 win over PAL retry row (paired casebook).
- **openai_gsm8k_787** — 300-case L1 win; additional representative from paired retry cohort.
- **openai_gsm8k_54** — 30-case external-only pilot band.
- **openai_gsm8k_1124** — PNS + frontier tiebreak in replay table columns.

## Caveats
- 88-case input corpus and `failure_case_corpus_20260507` are inventoried but **excluded** from the union until a manifest ties rows to the latest PAL method.
- Paired 300/100 runs compare **L1 only**; “best external” scopes exist only in 4-way + 30-case pilots.
- Mechanism tags for 300-case rows lean on `pal_present_not_selected` / `pal_gold_absent`; 30-case pilot lacks cluster labels.
- `operation_hint_tags` for rate/temporal/difference are taken from `failure_cluster_summary.csv` when present; otherwise marked unknown.

## Repro
```bash
cd /home/soroush/research-next-wt
python3 /home/soroush/research-next-wt/outputs/latest_pal_external_loss_bank_20260508T004000Z/build_failure_bank.py
```
