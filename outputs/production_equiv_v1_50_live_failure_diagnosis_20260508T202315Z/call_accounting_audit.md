# Call accounting audit
- Dry-run estimated total calls: 61 (extra: 11).
- Live run reached cap evidence at 80 logical calls with 30 cap-hit rows; first cap-hit row index=20.
- Summary under-reported calls (41) because per-case counters reset each row and do not represent run-global consumption once global cap enforcement trips.
- Completed-row observed call rate is 2.050, projecting ~102.5 calls for fully completed 50 rows.
- Gap vs dry-run (61) is consistent with live path consuming more internal controller calls (base + branching + occasional retry) than the dry-run abstraction captured.
- Targeted retry did not dominate call growth (triggered only 5, committed 0); base controller path likely drives most call use.
- Recommendation: fix run-level call accounting/surfacing first, then rerun 10-case with cap 50 for calibration, and full 50-case with cap >= recommended value.
