# production_equiv_v1 accounting patch
- Added shared helper: `experiments/call_accounting.py`.
- Added live calibration runner: `scripts/run_production_equiv_v1_live_calibration.py` with explicit run-level vs completed-row call fields.
- Added regression test in `tests/test_production_equivalence_stage3.py` for cap-hit mismatch accounting.
- Behavior: when cap is reached, summary now reports both completed-row calls and run-level calls, plus warning/source fields.
