# Round2 external-only loss collection report

- Paired cases completed: **131**
- external_l1_max exact: **109**
- PAL exact: **117**
- external_correct_pal_wrong: **5**
- pal_correct_external_wrong: **13**
- both_correct / both_wrong: **104 / 9**
- calls used / cap consumed / cap: **1141 / 1500 / 1500**
- failed/skipped count: **115**
- stop reason: **B_hit_cap**
- yield rate external-only: **0.0382**
- cumulative external-only after merge with prior 15: **20**
- reached 30? **False**

## Top precise patterns in new losses
- Gold-equivalent answer absent from PAL candidate pool while external path reached correct answer.: **3**
- Gold-equivalent candidate existed in PAL pool but selector chose a different final answer.: **2**

- enough for pattern mining: **False**
- recommended next step: **B_collect_more**
