# Local runtime final diagnosis

{
  "l1_started": true,
  "l1_completed": false,
  "drv2_started": true,
  "drv2_completed": false,
  "active_lane_at_interruption": "external_l1_max_or_setup",
  "elapsed_time_available": false,
  "api_call_count_consumed": 0,
  "failure_assessment": {
    "local_interactive_runtime_too_short": true,
    "first_lane_slowness": true,
    "drv2_slowness": true,
    "cohere_latency": true,
    "dataset_loading": false,
    "internal_bug": false,
    "unknown": false
  },
  "recommendation": "Use lane-level resumable checkpoints and continue in longer-lived cloud/background environment; keep EXP-L1-DECOMP-100 open."
}
