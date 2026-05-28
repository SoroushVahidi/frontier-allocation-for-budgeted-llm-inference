# Overnight Cerebras Supervisor — 2026-05-24

**Report generated:** 2026-05-25T20:04:24Z
**Branch:** main
**Final state:** `done`

---

## What the Supervisor Did

1. Monitored Cerebras × GSM8K job (PIDs 2195504/2195513) by polling every 10 minutes.
2. Checked: process alive, `[done]` in log, heartbeat age, method row counts.
3. Did NOT interrupt, kill, or modify the running GSM8K job at any time.
4. On GSM8K completion: ran full offline processing (integrity, accuracy, selector replay, failures).
5. On processing success: verified Scenario 6 preconditions (shared case files, no active Cerebras PIDs).
6. If conditions met: launched Cerebras × MATH-500 Scenario 6 in new tmux session.

---

## Cerebras × GSM8K Status

GSM8K completed and processed. Scenario 6 launched successfully.

---

## Scenario 6 Launch Status

| Field | Value |
|---|---|
| launched | True |
| tmux_session | cerebras_math500_s6_20260525T200409Z |
| output_root | /home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260525T200409Z |
| log_path | /home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_20260525T200409Z.log |
| launch_utc | 2026-05-25T20:04:24Z |

---

## Safety Confirmation

- No Cohere API calls launched.
- No Mistral API calls launched.
- Cerebras × GSM8K job was observed only — never killed, restarted, or modified.
- No commits or pushes made.
- No original artifacts overwritten.
- If blocked, wrote blocked report and exited safely.

---

## Files Created

| Path | Description |
|---|---|
| `outputs/overnight_cerebras_supervisor_20260524/supervisor.log` | Full supervisor log |
| `outputs/overnight_cerebras_supervisor_20260524/supervisor_status.jsonl` | Machine-readable status events |
| `outputs/overnight_cerebras_supervisor_20260524/manifest.json` | Final manifest |
| `outputs/overnight_cerebras_supervisor_20260524/cerebras_math500_scenario6_call_plan.json` | Scenario 6 call plan |
| `outputs/cerebras_gsm8k_completed_processing_20260524/` | GSM8K offline processing bundle |
| `docs/CEREBRAS_GSM8K_COMPLETED_PROCESSING_20260524.md` | GSM8K human report |

---

## Morning Commands

```bash
# 1. Check Cerebras MATH-500 Scenario 6 progress
cat outputs/overnight_cerebras_supervisor_20260524/supervisor_status.jsonl | tail -5
tmux ls

# 2. If Scenario 6 launched, check its log
tail -30 outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_*/logs/*.log 2>/dev/null || \
  tail -30 outputs/scenarios_5_6_math500_full_tracking_20260524/cerebras_math500_full_*.log 2>/dev/null

# 3. Check GSM8K processing results
cat outputs/cerebras_gsm8k_completed_processing_20260524/cerebras_gsm8k_integrity_summary.json
cat outputs/cerebras_gsm8k_completed_processing_20260524/cerebras_gsm8k_method_accuracy_summary.csv

# 4. Check supervisor state
cat outputs/overnight_cerebras_supervisor_20260524/manifest.json
```
