# PAL-hybrid selector design memo

## PAL strengths (this slice)
- PAL/PoT excels where deterministic code execution cleanly aggregates multi-step arithmetic.

## production_equiv strengths
- Competitive when structural_commit surface aligns with problem decomposition; retry path rarely commits.

## PAL-only pattern?
- pal_only_count=0; families: {} — sparse without larger bank.

## Production-only pattern?
- production_only_count=2; families: {'unknown': 2}

## Gold-free selector features
- PAL program generated + sandbox execution success vs stderr/exception.
- Parsed PAL numeric vs production parsed numeric agreement.
- production surface source (structural_commit vs others).
- Target-quantity cues from problem text (offline NLP).
- Numeric sanity: magnitude parity between candidates.

## production_equiv_v2_pal_hybrid?
- Evidence level: pal_only≥8 is False; answer-disagreement≥10 is False.
- **Outline v2 (no-API):** run PAL as parallel candidate; if PAL executes cleanly and disagrees with prod, 
  route by confidence features (exec_ok, parse nonempty, agreement with auxiliary numeric leaves); 
  tie-break toward PAL when exec_ok and prod surface is structural_commit with low diversity metadata.

## Next data step
- If counts insufficient: expand casebook beyond 30 from same pool (`all_casebook.csv`).
